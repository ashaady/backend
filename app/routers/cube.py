import io
import polars as pl
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.constants import utcnow
from app.db import SessionLocal
from app.models import CubeFact, Department, Account, Scenario, AuditLog, SubmissionStatus
from app.services.calculation_service import calculate_interest_revenue

router = APIRouter(prefix="/cube", tags=["Cube"])

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class CellUpdate(BaseModel):
    scenario_id: int
    department_id: int
    account_id: int
    year: int
    month: int
    newValue: float | str | int | None

@router.get("/scenarios")
def get_scenarios(db: Session = Depends(get_db)):
    """
    Returns all scenarios available for the Cube.
    """
    scenarios = db.query(Scenario).all()
    return {"scenarios": [{"id": s.id, "name": s.name, "type": s.type, "is_locked": s.is_locked} for s in scenarios]}

@router.get("/departments")
def get_departments(db: Session = Depends(get_db)):
    """
    Returns all departments for Perimeter filtering.
    """
    depts = db.query(Department).all()
    return {"departments": [{"id": d.id, "name": d.name} for d in depts]}

@router.get("/data")
def get_cube_data(scenario_id: int = None, compare_scenario_id: int = None, department_id: int = None, db: Session = Depends(get_db)):
    """
    Returns the grid data from the Database (CubeFacts joined with Dimensions).
    Defaults to the first unlocked scenario (e.g. Budget 2025).
    """
    if not scenario_id:
        # Get default scenario (first unlocked)
        scenario = db.query(Scenario).filter(Scenario.is_locked == False).first()
        if not scenario:
            scenario = db.query(Scenario).first()
        scenario_id = scenario.id if scenario else 0

    # Join CubeFact with Department and Account to get plain names for the grid
    query = db.query(CubeFact, Department.name.label("department"), Account.name.label("account"))\
              .join(Department, CubeFact.department_id == Department.id)\
              .join(Account, CubeFact.account_id == Account.id)\
              .filter(CubeFact.scenario_id == scenario_id)
              
    if department_id:
        query = query.filter(CubeFact.department_id == department_id)
        
    facts = query.all()

    # Pivot data: Group by (department_id, account_id, year)
    # Output row: { id: "deptId_accId_year", department_id, account_id, department, account, year, month_1: val, month_2: val, ..., total: val }
    pivoted = {}
    
    for fact, dept_name, acc_name in facts:
        key = f"{fact.department_id}_{fact.account_id}_{fact.year}"
        if key not in pivoted:
            pivoted[key] = {
                "id": key, # composite ID for the frontend grid row
                "department_id": fact.department_id,
                "account_id": fact.account_id,
                "department": dept_name,
                "account": acc_name,
                "year": fact.year,
                "total": 0.0
            }
            # Initialize all months to 0
            for i in range(1, 13):
                pivoted[key][f"month_{i}"] = 0.0
                
        # Set the specific month's value
        month_key = f"month_{fact.month}"
        pivoted[key][month_key] = fact.value
        pivoted[key]["total"] += fact.value

    # Second Pass: Comparative Scenario (Read Only Reference)
    if compare_scenario_id:
        comp_query = db.query(CubeFact)\
                  .join(Department, CubeFact.department_id == Department.id)\
                  .join(Account, CubeFact.account_id == Account.id)\
                  .filter(CubeFact.scenario_id == compare_scenario_id)
                  
        if department_id:
            comp_query = comp_query.filter(CubeFact.department_id == department_id)
            
        comp_facts = comp_query.all()
        for fact in comp_facts:
            key = f"{fact.department_id}_{fact.account_id}_{fact.year}"
            if key in pivoted:
                # Add comparative columns to existing row
                comp_key = f"comp_month_{fact.month}"
                pivoted[key][comp_key] = fact.value
                
                if "comp_total" not in pivoted[key]:
                    pivoted[key]["comp_total"] = 0.0
                pivoted[key]["comp_total"] += fact.value

    data = list(pivoted.values())

    return {"data": data, "scenario_id": scenario_id}


@router.post("/update")
def update_cell(update: CellUpdate, db: Session = Depends(get_db)):
    """
    Receives an update from the frontend grid.
    Updates the structural Database and logs the Audit trail.
    """
    fact = db.query(CubeFact).filter(
        CubeFact.scenario_id == update.scenario_id,
        CubeFact.department_id == update.department_id,
        CubeFact.account_id == update.account_id,
        CubeFact.year == update.year,
        CubeFact.month == update.month
    ).first()
    
    # NEW: Check Workflow Status (Phase 4)
    ws_status = db.query(SubmissionStatus).filter(
        SubmissionStatus.scenario_id == update.scenario_id,
        SubmissionStatus.department_id == update.department_id,
        SubmissionStatus.year == update.year
    ).first()
    
    if ws_status and ws_status.status in ["SUBMITTED", "APPROVED"]:
        raise HTTPException(
            status_code=403, 
            detail=f"Modification interdite : Le budget est déjà {ws_status.status}."
        )
    
    new_val = float(update.newValue) if update.newValue is not None else 0.0
    old_value = 0.0

    if not fact:
        # Check Scenario Lock before creating
        scenario = db.query(Scenario).filter(Scenario.id == update.scenario_id).first()
        if not scenario:
             raise HTTPException(status_code=404, detail="Scenario not found.")
        if scenario.is_locked:
             raise HTTPException(status_code=403, detail="Scenario is locked. Cannot edit.")
             
        fact = CubeFact(
            scenario_id=update.scenario_id,
            department_id=update.department_id,
            account_id=update.account_id,
            year=update.year,
            month=update.month,
            value=new_val
        )
        db.add(fact)
        db.commit() # commit early to get fact.id for audit log
        db.refresh(fact)
    else:
        # Check Scenario Lock before updating
        if fact.scenario.is_locked:
             raise HTTPException(status_code=403, detail="Scenario is locked. Cannot edit.")
        
        old_value = fact.value
        fact.value = new_val
    
    # Write Audit Log
    audit = AuditLog(
        cube_fact_id=fact.id,
        action="UPDATE",
        old_value=old_value,
        new_value=new_val
    )
    db.add(audit)
    db.commit()

    # Trigger Automated Calculation if this is a Driver
    # (Assuming any update to a Driver account triggers the refresh)
    if fact.account.type == "Driver":
        calculate_interest_revenue(
            db, 
            fact.scenario_id, 
            fact.department_id, 
            fact.year, 
            fact.month
        )

    # Calculate Totals via SQL for this scenario
    total_val = db.query(func.sum(CubeFact.value)).filter(CubeFact.scenario_id == fact.scenario_id).scalar() or 0.0

    # Group by department
    dept_totals_query = db.query(Department.name, func.sum(CubeFact.value))\
                          .join(CubeFact, CubeFact.department_id == Department.id)\
                          .filter(CubeFact.scenario_id == fact.scenario_id)\
                          .group_by(Department.name).all()
    
    dept_totals = {dept: val for dept, val in dept_totals_query}

    return {
        "status": "success", 
        "message": "Update saved to Database and Audited",
        "totals": {
            "overall": total_val,
            "departments": dept_totals
        }
    }

@router.get("/status")
def get_workflow_status(scenario_id: int, department_id: int, year: int, db: Session = Depends(get_db)):
    """
    Returns the current workflow status of a worksheet.
    """
    ws = db.query(SubmissionStatus).filter(
        SubmissionStatus.scenario_id == scenario_id,
        SubmissionStatus.department_id == department_id,
        SubmissionStatus.year == year
    ).first()
    
    return {
        "status": ws.status if ws else "DRAFT",
        "details": ws if ws else None
    }

@router.post("/status/submit")
def submit_worksheet(scenario_id: int, department_id: int, year: int, user_id: str, db: Session = Depends(get_db)):
    """
    Submits a worksheet for approval. Locks it from further edits by the user.
    """
    ws = db.query(SubmissionStatus).filter(
        SubmissionStatus.scenario_id == scenario_id,
        SubmissionStatus.department_id == department_id,
        SubmissionStatus.year == year
    ).first()
    
    if not ws:
        ws = SubmissionStatus(
            scenario_id=scenario_id, 
            department_id=department_id, 
            year=year
        )
        db.add(ws)
    
    ws.status = "SUBMITTED"
    ws.submitted_by = user_id
    ws.submitted_at = utcnow()
    db.commit()
    return {"status": "SUBMITTED"}

@router.post("/status/approve")
def approve_worksheet(scenario_id: int, department_id: int, year: int, user_id: str, db: Session = Depends(get_db)):
    """
    Approves a submitted worksheet. Higher-level lock.
    """
    ws = db.query(SubmissionStatus).filter(
        SubmissionStatus.scenario_id == scenario_id,
        SubmissionStatus.department_id == department_id,
        SubmissionStatus.year == year
    ).first()
    
    if not ws or ws.status != "SUBMITTED":
        raise HTTPException(status_code=400, detail="Seuls les budgets soumis peuvent être approuvés.")
        
    ws.status = "APPROVED"
    ws.approved_by = user_id
    ws.approved_at = utcnow()
    db.commit()
    return {"status": "APPROVED"}


@router.post("/import")
async def import_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Receives a CSV file, parses with Polars, updates the DB structurally, and logs audit.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
        
    try:
        content = await file.read()
        uploaded_df = pl.read_csv(io.BytesIO(content))
        uploaded_df = uploaded_df.drop_nulls(subset=["id"])
        
        # We only care about id and value for a structural EPM update
        updates = uploaded_df.select(["id", "value"]).to_dicts()
        
        audit_logs = []
        scenario_ids = set()
        
        for up in updates:
            fact = db.query(CubeFact).filter(CubeFact.id == up["id"]).first()
            if fact and not fact.scenario.is_locked:
                old_val = fact.value
                new_val = float(up["value"])
                
                if old_val != new_val:
                    fact.value = new_val
                    scenario_ids.add(fact.scenario_id)
                    
                    audit_logs.append(AuditLog(
                        cube_fact_id=fact.id,
                        action="IMPORT",
                        old_value=old_val,
                        new_value=new_val
                    ))
        
        # Batch insert audit logs and commit facts
        if audit_logs:
            db.bulk_save_objects(audit_logs)
            db.commit()
            
        # Re-fetch the updated data to return to the frontend
        # Assuming we just return data for the first unlocked scenario we touched
        scenario_id = list(scenario_ids)[0] if scenario_ids else None
        
        if not scenario_id:
            scenario = db.query(Scenario).filter(Scenario.is_locked == False).first()
            scenario_id = scenario.id if scenario else 0

        # Run the standard GET query to hydrate frontend
        facts_query = db.query(CubeFact, Department.name.label("department"), Account.name.label("account"))\
                        .join(Department, CubeFact.department_id == Department.id)\
                        .join(Account, CubeFact.account_id == Account.id)\
                        .filter(CubeFact.scenario_id == scenario_id)\
                        .all()

        data = []
        for fact, dept_name, acc_name in facts_query:
            data.append({
                "id": fact.id,
                "year": fact.year,
                "month": fact.month,
                "department": dept_name,
                "account": acc_name,
                "value": fact.value
            })
            
        # Calculate Totals
        total_val = db.query(func.sum(CubeFact.value)).filter(CubeFact.scenario_id == scenario_id).scalar() or 0.0
        dept_totals_query = db.query(Department.name, func.sum(CubeFact.value))\
                              .join(CubeFact, CubeFact.department_id == Department.id)\
                              .filter(CubeFact.scenario_id == scenario_id)\
                              .group_by(Department.name).all()
        dept_totals = {dept: val for dept, val in dept_totals_query}
        
        return {
            "status": "success", 
            "message": f"CSV Imported: {len(audit_logs)} rows updated and audited.",
            "data": data,
            "totals": {
                "overall": total_val,
                "departments": dept_totals
            }
        }
        
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
