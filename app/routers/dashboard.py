from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import CubeFact, Scenario, Account, Department

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/overview")
def get_dashboard_overview(
    year: int = Query(2024, description="Target year for analysis"),
    department_id: Optional[int] = Query(None, description="Optional department filter"),
    db: Session = Depends(get_db)
):
    """
    Returns dynamic data for the main dashboard aggregating CubeFacts.
    """
    # 1. Resolve Scenarios (Find the primary "Actual" and "Budget" for the given year)
    # For a real EPM you might specify scenario IDs explicitly, but here we'll infer:
    actuals_scenario = db.query(Scenario).filter(Scenario.type == "Actual").order_by(Scenario.id.desc()).first()
    budget_scenario = db.query(Scenario).filter(Scenario.type == "Budget").order_by(Scenario.id.desc()).first()

    if not actuals_scenario or not budget_scenario:
        return {"kpis": [], "waterfall": [], "workflow": "no_scenarios_found"}

    # Base Queries for facts in the selected year
    base_query = db.query(CubeFact).filter(CubeFact.year == year)
    if department_id:
        base_query = base_query.filter(CubeFact.department_id == department_id)

    # 2. Calculate Total Expenses Budget
    budget_facts = base_query.filter(CubeFact.scenario_id == budget_scenario.id).join(Account).filter(Account.type == "Expense").all()
    budget_total = sum([f.value for f in budget_facts])

    # 3. Calculate Total Actual Expenses
    actual_facts = base_query.filter(CubeFact.scenario_id == actuals_scenario.id).join(Account).filter(Account.type == "Expense").all()
    actuals_total = sum([f.value for f in actual_facts])

    remaining = budget_total - actuals_total
    
    # Simple variance logic
    variance_val = budget_total - actuals_total
    variance_pct = round((variance_val / budget_total) * 100, 1) if budget_total > 0 else 0
    actuals_pct = round((actuals_total / budget_total) * 100, 1) if budget_total > 0 else 0

    kpis = [
        { 
            "id": "budget", 
            "label": "Budget Total (Dépenses)", 
            "value": budget_total, 
            "varianceValue": 0, 
            "variancePercent": 0, 
            "status": "neutral" 
        },
        { 
            "id": "actuals", 
            "label": "Dépenses Réelles", 
            "value": actuals_total, 
            "varianceValue": -variance_val, 
            "variancePercent": actuals_pct, 
            "status": "warning" if actuals_total > budget_total else "good" 
        },
        { 
            "id": "remaining", 
            "label": "Reste à Dépenser", 
            "value": max(0, remaining), 
            "varianceValue": 0, 
            "variancePercent": 0, 
            "status": "neutral" 
        },
        { 
            "id": "variance", 
            "label": "Écart Global", 
            "value": variance_val, 
            "varianceValue": variance_val, 
            "variancePercent": variance_pct, 
            "status": "good" if variance_val >= 0 else "danger"
        }
    ]

    # 4. Waterfall Calculation (Budget -> Écarts par compte -> Réel)
    # We aggregate actuals minus budget for each account to explain the bridge
    account_variances = {}
    
    # We fetch ALL accounts just to ensure we map names properly
    all_accounts = {a.id: a.name for a in db.query(Account).filter(Account.type == "Expense").all()}

    # Initialize variance to 0 for all expense accounts
    for acc_id in all_accounts.keys():
        account_variances[acc_id] = 0.0

    # Subtract Budget (Starting Point)
    for f in budget_facts:
        account_variances[f.account_id] -= f.value

    # Add Actuals (To find the Delta/Bridge)
    for f in actual_facts:
        account_variances[f.account_id] += f.value

    waterfall = []
    waterfall.append({ "name": "Budget N", "value": budget_total, "isTotal": True })

    for acc_id, delta in account_variances.items():
        if abs(delta) > 1: # Ignore rounding artifacts near 0
            waterfall.append({ "name": all_accounts[acc_id], "value": delta })

    waterfall.append({ "name": "Réel N", "value": actuals_total, "isTotal": True })

    return {
        "kpis": kpis,
        "waterfall": waterfall,
        "workflow": "in_progress"
    }
