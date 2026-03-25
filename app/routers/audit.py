from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.db import SessionLocal
from app.models import AuditLog, CubeFact, Department, Account, Scenario

router = APIRouter(prefix="/audit", tags=["Audit"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/logs")
def get_audit_logs(limit: int = 100, db: Session = Depends(get_db)):
    """
    Returns the most recent audit logs along with the associated context.
    """
    logs = db.query(
        AuditLog, 
        CubeFact.year, 
        CubeFact.month, 
        Department.name.label("department_name"),
        Account.name.label("account_name"),
        Scenario.name.label("scenario_name")
    ).join(CubeFact, AuditLog.cube_fact_id == CubeFact.id)\
     .join(Department, CubeFact.department_id == Department.id)\
     .join(Account, CubeFact.account_id == Account.id)\
     .join(Scenario, CubeFact.scenario_id == Scenario.id)\
     .order_by(desc(AuditLog.timestamp))\
     .limit(limit)\
     .all()

    result = []
    for log, year, month, dept_name, acc_name, scenario_name in logs:
        # Mocking user context since Clerk users are separate for now,
        # but in Phase 5 we'll resolve user_id correctly.
        user_name = f"User {log.user_id}" if log.user_id else "Système / Import"
        
        result.append({
            "id": log.id,
            "timestamp": log.timestamp.isoformat(),
            "action": log.action,
            "user": user_name,
            "context": f"[{scenario_name}] {dept_name} - {acc_name} ({month}/{year})",
            "old_value": log.old_value,
            "new_value": log.new_value,
            "variance": log.new_value - (log.old_value or 0)
        })

    return {"logs": result}

@router.get("/cell")
def get_cell_audit_logs(
    scenario_id: int, 
    department_id: int, 
    account_id: int, 
    year: int, 
    month: int,
    db: Session = Depends(get_db)):
    """
    Returns the most recent 5 audit logs for a specific multidimensional coordinate.
    """
    fact = db.query(CubeFact).filter(
        CubeFact.scenario_id == scenario_id,
        CubeFact.department_id == department_id,
        CubeFact.account_id == account_id,
        CubeFact.year == year,
        CubeFact.month == month
    ).first()

    if not fact:
        return {"logs": []}

    logs = db.query(AuditLog)\
             .filter(AuditLog.cube_fact_id == fact.id)\
             .order_by(desc(AuditLog.timestamp))\
             .limit(5)\
             .all()

    result = []
    for log in logs:
        user_name = f"User {log.user_id}" if log.user_id else "Système / Import"
        result.append({
            "action": log.action,
            "user": user_name,
            "timestamp": log.timestamp.isoformat(),
            "old_value": log.old_value,
            "new_value": log.new_value
        })

    return {"logs": result}
