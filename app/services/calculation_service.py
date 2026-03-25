from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from app.models import CubeFact, Account, Department, Scenario, AuditLog
from datetime import datetime

def calculate_interest_revenue(db: Session, scenario_id: int, department_id: int, year: int, month: int):
    """
    Automates the calculation of Interest Revenue for a specific coordinate.
    Formula: Portfolio Balance (Driver) * Interest Rate (Driver) / 12
    """
    # 1. Identify required accounts (Assuming standard codes for now, should be configurable)
    # Portfolio Balance (GLP)
    glp_acc = db.scalar(select(Account).where(Account.code == "DRV_GLP"))
    # Interest Rate
    rate_acc = db.scalar(select(Account).where(Account.code == "DRV_RATE"))
    # Target Revenue Account
    rev_acc = db.scalar(select(Account).where(Account.code == "1000")) # Revenus - Licences/Intérêts

    if not all([glp_acc, rate_acc, rev_acc]):
        return None

    # 2. Fetch Driver Values
    glp_fact = db.scalar(
        select(CubeFact).where(
            and_(
                CubeFact.scenario_id == scenario_id,
                CubeFact.department_id == department_id,
                CubeFact.account_id == glp_acc.id,
                CubeFact.year == year,
                CubeFact.month == month
            )
        )
    )
    
    rate_fact = db.scalar(
        select(CubeFact).where(
            and_(
                CubeFact.scenario_id == scenario_id,
                CubeFact.department_id == department_id,
                CubeFact.account_id == rate_acc.id,
                CubeFact.year == year,
                CubeFact.month == month
            )
        )
    )

    if not glp_fact or not rate_fact:
        return None

    # 3. Perform Calculation
    # Formula: GLP * (Rate / 100) / 12 (assuming rate is in percentage)
    new_revenue_value = (glp_fact.value * (rate_fact.value / 100.0)) / 12.0

    # 4. Upsert Revenue Fact
    revenue_fact = db.query(CubeFact).filter(
        CubeFact.scenario_id == scenario_id,
        CubeFact.department_id == department_id,
        CubeFact.account_id == rev_acc.id,
        CubeFact.year == year,
        CubeFact.month == month
    ).first()

    old_val = 0.0
    if revenue_fact:
        old_val = revenue_fact.value
        revenue_fact.value = new_revenue_value
    else:
        revenue_fact = CubeFact(
            scenario_id=scenario_id,
            department_id=department_id,
            account_id=rev_acc.id,
            year=year,
            month=month,
            value=new_revenue_value
        )
        db.add(revenue_fact)
        db.flush() # Ensure ID is generated for audit

    # 5. Audit Log
    if old_val != new_revenue_value:
        audit = AuditLog(
            cube_fact_id=revenue_fact.id,
            action="AUTO_CALC",
            old_value=old_val,
            new_value=new_revenue_value
        )
        db.add(audit)
    
    db.commit()
    return new_revenue_value
