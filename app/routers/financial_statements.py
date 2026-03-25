from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from app.db import SessionLocal
from app.models import CubeFact, Account, Department, Scenario
from app.services.consolidation_service import run_consolidation
from typing import List, Dict

router = APIRouter(prefix="/reports", tags=["Reports"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/pl")
def get_profit_and_loss(scenario_id: int, department_id: int = None, year: int = 2025, db: Session = Depends(get_db)):
    """
    Generates a structured P&L report based on Account.pl_section.
    """
    # 1. Fetch all facts for the scenario/year
    query = db.query(CubeFact, Account.pl_section, Account.type, Account.name)\
              .join(Account, CubeFact.account_id == Account.id)\
              .filter(CubeFact.scenario_id == scenario_id)\
              .filter(CubeFact.year == year)
    
    if department_id:
        query = query.filter(CubeFact.department_id == department_id)
        dept = db.query(Department).filter(Department.id == department_id).first()
        currency = dept.currency if dept else "XOF"
    else:
        # All Group = Global Dept
        dept = db.query(Department).filter(Department.parent_id == None).first()
        currency = dept.currency if dept else "EUR"
        
    facts = query.all()
    
    # 2. Defined Sections (Order preserved)
    section_map = {
        "INTEREST_REV": "Produits d'intérêt",
        "INTEREST_EXP": "Charges d'intérêt",
        "COMMISSION_REV": "Commissions et autres produits",
        "PERSONNEL_EXP": "Charges de personnel",
        "ADMIN_EXP": "Frais administratifs",
        "LOAN_PROVISION": "Dotations aux provisions pour créances",
        "OTHER_EXPL_REV": "Autres produits d'exploitation",
        "OTHER_EXPL_EXP": "Autres charges d'exploitation",
        "FINANCIAL_RESULT": "Résultat financier",
        "EXCEPTIONAL_RESULT": "Résultat exceptionnel",
        "TAXES": "Impôts sur les bénéfices"
    }

    report = {
        s_id: {"name": s_name, "total": 0.0, "months": [0.0]*12} 
        for s_id, s_name in section_map.items()
    }
    
    # 3. Aggregate
    totals = {"PNB": [0.0]*12, "RESULTAT_EXPL": [0.0]*12, "RESULTAT_NET": [0.0]*12}

    for fact, pl_section, acc_type, acc_name in facts:
        m_idx = fact.month - 1
        val = fact.value
        
        if pl_section in report:
            report[pl_section]["months"][m_idx] += val
            report[pl_section]["total"] += val
            
            # Sub-totals logic
            if pl_section in ["INTEREST_REV", "COMMISSION_REV"]:
                totals["PNB"][m_idx] += val
            elif pl_section == "INTEREST_EXP":
                totals["PNB"][m_idx] -= val
                
            if acc_type == "Revenue":
                totals["RESULTAT_NET"][m_idx] += val
            else:
                totals["RESULTAT_NET"][m_idx] -= val

    return {
        "scenario_id": scenario_id,
        "year": year,
        "currency": currency,
        "sections": report,
        "sub_totals": totals
    }

@router.get("/balance-sheet")
def get_balance_sheet(scenario_id: int, year: int, month: int, department_id: int = None, db: Session = Depends(get_db)):
    """
    Generates a point-in-time Balance Sheet check.
    """
    # 1. Fetch facts up to the specified month (Cumulative for Balance Sheet)
    query = db.query(CubeFact, Account.type, Account.pl_section)\
              .join(Account, CubeFact.account_id == Account.id)\
              .filter(CubeFact.scenario_id == scenario_id)\
              .filter(CubeFact.year == year)\
              .filter(CubeFact.month <= month)
    
    if department_id:
        query = query.filter(CubeFact.department_id == department_id)
        dept = db.query(Department).filter(Department.id == department_id).first()
        currency = dept.currency if dept else "XOF"
    else:
        dept = db.query(Department).filter(Department.parent_id == None).first()
        currency = dept.currency if dept else "EUR"

    facts = query.all()
    
    # 2. Structure
    bs = {
        "ASSETS": {"name": "Actif", "total": 0.0},
        "LIABILITIES": {"name": "Passif", "total": 0.0},
        "EQUITY": {"name": "Capitaux Propres", "total": 0.0}
    }
    
    for fact, acc_type, pl_section in facts:
        val = fact.value
        # Very simplified mapping for demonstration
        if pl_section == "INTEREST_REV": # In reality, we'd have specific BS accounts
             bs["ASSETS"]["total"] += val
        elif pl_section == "PERSONNEL_EXP":
             bs["LIABILITIES"]["total"] += val

    # 3. Equality Check
    imbalance = bs["ASSETS"]["total"] - (bs["LIABILITIES"]["total"] + bs["EQUITY"]["total"])
    
    return {
        "scenario_id": scenario_id,
        "year": year,
        "month": month,
        "currency": currency,
        "sections": bs,
        "is_balanced": abs(imbalance) < 0.01,
        "imbalance": imbalance,
        "indicator": "OK" if abs(imbalance) < 0.01 else "IMBALANCED"
    }

@router.get("/cash-flow")
def get_cash_flow(scenario_id: int, year: int, department_id: int = None, db: Session = Depends(get_db)):
    """
    Generates a Cash Flow statement using the indirect method.
    """
    # 1. Fetch Net Income (from P&L logic)
    pl_data = get_profit_and_loss(scenario_id, department_id, year, db)
    net_income_months = pl_data["sub_totals"]["RESULTAT_NET"]
    
    # 2. Fetch Non-Cash Items (Amortissements, Provisions)
    # These are added back to Net Income
    non_cash_query = db.query(CubeFact, Account.name)\
                       .join(Account, CubeFact.account_id == Account.id)\
                       .filter(CubeFact.scenario_id == scenario_id)\
                       .filter(CubeFact.year == year)\
                       .filter(Account.code.in_(["604", "605"]))
    if department_id:
        non_cash_query = non_cash_query.filter(CubeFact.department_id == department_id)
    
    non_cash_facts = non_cash_query.all()
    non_cash_months = [0.0]*12
    for fact, name in non_cash_facts:
        non_cash_months[fact.month - 1] += fact.value

    # 3. Categorized Cash Flow (Operating, Investing, Financing)
    # Simplified approach: Summing all accounts mapped to these sections
    cf_query = db.query(CubeFact, Account.cf_section, Account.type)\
                 .join(Account, CubeFact.account_id == Account.id)\
                 .filter(CubeFact.scenario_id == scenario_id)\
                 .filter(CubeFact.year == year)
    if department_id:
        cf_query = cf_query.filter(CubeFact.department_id == department_id)
        
    cf_facts = cf_query.all()
    
    cf_sections = {
        "OPERATING": {"name": "Flux d'exploitation", "months": [0.0]*12, "total": 0.0},
        "INVESTING": {"name": "Flux d'investissement", "months": [0.0]*12, "total": 0.0},
        "FINANCING": {"name": "Flux de financement", "months": [0.0]*12, "total": 0.0}
    }
    
    # Logic for Indirect Operating CF: Net Income + Non-Cash +/- Change in WCR
    # For this simplified EPM, we use the specific CF_Section mappings from Account
    for fact, section, acc_type in cf_facts:
        if section in cf_sections:
            m_idx = fact.month - 1
            val = fact.value
            
            # Sign logic: 
            # - Revenues in CF sections are (+)
            # - Expenses in CF sections (except Operating where they are already in Net Income) are (-)
            # - Assets in Investing (Immobilisations) are (-) if value increases (Purchase)
            # - Liabilities in Financing (Emprunts) are (+) if value increases (New loan)
            
            if section == "OPERATING":
                # Operating is already based on Net Income, we only add/subtract deltas if not in P&L
                # But here we just use the mapped items for simplicity
                cf_sections[section]["months"][m_idx] += val if acc_type == "Revenue" else -val
            elif section == "INVESTING":
                cf_sections[section]["months"][m_idx] -= val # Purchase of assets (-)
            elif section == "FINANCING":
                cf_sections[section]["months"][m_idx] += val # New equity/loans (+)

    # Override Operating with the actual Indirect formula: Net Income + Non-Cash
    for i in range(12):
        cf_sections["OPERATING"]["months"][i] = net_income_months[i] + non_cash_months[i]
    
    # Totals
    variation_net_months = [0.0]*12
    for i in range(12):
        total_m = sum(sec["months"][i] for sec in cf_sections.values())
        variation_net_months[i] = total_m
        
    for key in cf_sections:
        cf_sections[key]["total"] = sum(cf_sections[key]["months"])

    return {
        "scenario_id": scenario_id,
        "year": year,
        "sections": cf_sections,
        "variation_net": {
            "months": variation_net_months,
            "total": sum(variation_net_months)
        }
    }

@router.get("/ratios")
def get_microfinance_ratios(scenario_id: int, year: int, department_id: int = None, db: Session = Depends(get_db)):
    """
    Calculates industry-standard Microfinance KPIs (OSS, Yield, Cost of Risk).
    """
    # 1. Fetch P&L data for components
    pl = get_profit_and_loss(scenario_id, department_id, year, db)
    
    # Components from sections
    rev = pl["sub_totals"]["PNB"] # Actually Operating Revenue
    exp_fin = pl["sections"].get("INTEREST_EXP", {"months": [0.0]*12})["months"]
    exp_ops = pl["sections"].get("PERSONNEL_EXP", {"months": [0.0]*12})["months"]
    exp_admin = pl["sections"].get("ADMIN_EXP", {"months": [0.0]*12})["months"]
    prov = pl["sections"].get("LOAN_PROVISION", {"months": [0.0]*12})["months"]
    
    # 2. Fetch Drivers for PAR and Portfolio
    glp_query = db.query(CubeFact)\
                  .join(Account, CubeFact.account_id == Account.id)\
                  .filter(CubeFact.scenario_id == scenario_id)\
                  .filter(CubeFact.year == year)\
                  .filter(Account.code == "DRV_GLP")
    if department_id:
        glp_query = glp_query.filter(CubeFact.department_id == department_id)
    
    glp_facts = glp_query.all()
    glp_months = [0.0]*12
    for f in glp_facts: glp_months[f.month - 1] = f.value

    # 3. Calculate Ratios
    oss_months = []
    yield_months = []
    cir_months = [] # Cost Income Ratio
    
    for i in range(12):
        r = rev[i]
        total_costs = exp_fin[i] + exp_ops[i] + exp_admin[i] + prov[i]
        
        # OSS = Revenue / Total Costs
        oss = (r / total_costs * 100) if total_costs > 0 else 0
        oss_months.append(round(oss, 1))
        
        # Yield = Revenue / GLP
        y = (r / glp_months[i] * 12 * 100) if glp_months[i] > 0 else 0
        yield_months.append(round(y, 1))
        
        # CIR = (Ops + Admin) / Revenue
        cir = ((exp_ops[i] + exp_admin[i]) / r * 100) if r > 0 else 0
        cir_months.append(round(cir, 1))

    return {
        "scenario_id": scenario_id,
        "year": year,
        "ratios": {
            "OSS": {"name": "Autosuffisance Opérationnelle (%)", "months": oss_months, "target": 110.0, "description": "> 100% signifies profitabilité"},
            "YIELD": {"name": "Rendement du Portefeuille (%)", "months": yield_months, "target": 25.0, "description": "Revenu annualisé / Encours"},
            "CIR": {"name": "Coefficient d'Exploitation (%)", "months": cir_months, "target": 65.0, "description": "Charges d'exploitation / Revenus"}
        }
    }

@router.post("/consolidate")
def trigger_consolidation(
    scenario_id: int = Query(...), 
    year: int = Query(...), 
    target_currency: str = Query("EUR"), 
    db: Session = Depends(get_db)
):
    """
    Triggers the calculation of consolidated group data.
    """
    result = run_consolidation(db, scenario_id, year, target_currency)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
