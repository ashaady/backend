from sqlalchemy.orm import Session
from app.models import CubeFact, Department, ExchangeRate, Account
from typing import List

def run_consolidation(db: Session, scenario_id: int, year: int, target_currency: str = "EUR"):
    """
    1. Identify the 'Global' department (Group)
    2. Get all 'Filiales' and their data
    3. Convert each filiale data to target_currency
    4. Aggregate into Global facts
    """
    # 1. Identify Group
    group_dept = db.query(Department).filter(Department.parent_id == None).first()
    if not group_dept:
        return {"error": "Group department not found"}

    # 2. Get Exchange Rates
    rates = {r.from_currency: r.rate for r in db.query(ExchangeRate).filter(ExchangeRate.year == year).all()}
    rates[target_currency] = 1.0 # Base rate

    # 3. Fetch subsidiary facts (excluding drivers which are non-additive)
    subs_facts = db.query(CubeFact)\
                   .join(Department, CubeFact.department_id == Department.id)\
                   .join(Account, CubeFact.account_id == Account.id)\
                   .filter(CubeFact.scenario_id == scenario_id)\
                   .filter(CubeFact.year == year)\
                   .filter(Department.id != group_dept.id)\
                   .filter(Account.type != "Driver")\
                   .filter(CubeFact.partner_id == None)\
                   .all()

    # 4. Aggregate
    # Structured as {(account_id, month): total_value}
    totals = {}
    for fact in subs_facts:
        key = (fact.account_id, fact.month)
        
        # Convert to target currency
        rate = rates.get(fact.department.currency, 1.0)
        converted_val = fact.value * rate
        
        totals[key] = totals.get(key, 0.0) + converted_val

    # 5. Save to Group Entity
    # (Simplified: wipe existing group facts for this year/scenario first)
    db.query(CubeFact).filter(
        CubeFact.scenario_id == scenario_id,
        CubeFact.department_id == group_dept.id,
        CubeFact.year == year
    ).delete()

    new_facts = [
        CubeFact(
            scenario_id=scenario_id,
            department_id=group_dept.id,
            account_id=acc_id,
            month=month,
            year=year,
            value=round(val, 2)
        )
        for (acc_id, month), val in totals.items()
    ]
    
    db.add_all(new_facts)
    db.commit()
    
    return {"status": "success", "consolidated_records": len(new_facts), "target_currency": target_currency}
