import random
from sqlalchemy.orm import Session
from app.db import engine, Base
from app.models import Department, Account, Scenario, CubeFact

def seed_db():
    # 1. Recreate tables
    print("Dropping and recreating all tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    with Session(engine) as session:
        # 2. Create Scenarios
        print("Creating Scenarios...")
        actuals = Scenario(name="Actuals 2024", type="Actual", is_locked=True)
        budget = Scenario(name="Budget 2025", type="Budget", is_locked=False)
        session.add_all([actuals, budget])
        session.commit()

        # 3. Create Departments (Hierarchy)
        print("Creating Departments...")
        global_co = Department(name="Nexadec Global")
        session.add(global_co)
        session.commit()
        
        depts_data = [
            ("Direction", False, "XOF"),
            ("Ventes", True, "XOF"),
            ("Marketing", True, "EUR"), # Global Marketing in EUR
            ("R&D", True, "USD"),       # Technical R&D in USD
            ("IT", True, "XOF"),
            ("RH", True, "XOF"),
            ("Finance", True, "XOF"),
        ]
        depts = []
        for name, is_filiale, currency in depts_data:
            dept = Department(name=name, parent_id=global_co.id, is_filiale=is_filiale, currency=currency)
            depts.append(dept)
            session.add(dept)
        session.commit()

        # 3.5 Create Exchange Rates
        from app.models import ExchangeRate
        print("Creating Exchange Rates...")
        rates = [
            ExchangeRate(from_currency="XOF", to_currency="EUR", rate=0.0015, year=2024),
            ExchangeRate(from_currency="XOF", to_currency="EUR", rate=0.0015, year=2025),
            ExchangeRate(from_currency="USD", to_currency="EUR", rate=0.92, year=2025),
        ]
        session.add_all(rates)
        session.commit()

        # 4. Create Accounts (Chart of Accounts)
        # (Code, Name, Type, PL_Section, CF_Section)
        print("Creating Accounts...")
        accounts_data = [
            ("701", "Intérêts sur crédits", "Revenue", "INTEREST_REV", "OPERATING"),
            ("702", "Commissions", "Revenue", "COMMISSION_REV", "OPERATING"),
            ("601", "Intérêts sur épargne", "Expense", "INTEREST_EXP", "OPERATING"),
            ("602", "Salaires et charges", "Expense", "PERSONNEL_EXP", "OPERATING"),
            ("603", "Loyer et services", "Expense", "ADMIN_EXP", "OPERATING"),
            ("604", "Provisions créances", "Expense", "LOAN_PROVISION", "OPERATING"),    # Non-cash
            ("605", "Dotation aux amortissements", "Expense", "OTHER_EXPL_EXP", "OPERATING"), # Non-cash
            ("101", "Capital Social", "Equity", None, "FINANCING"),
            ("164", "Emprunts bancaires", "Liability", None, "FINANCING"),
            ("211", "Immobilisations", "Asset", None, "INVESTING"),
            # Drivers
            ("DRV_GLP", "Encours de Portefeuille (GLP)", "Driver", None, None),
            ("DRV_RATE", "Taux d'Intérêt Moyen (%)", "Driver", None, None),
        ]
        accounts = []
        for code, name, acc_type, pl_section, cf_section in accounts_data:
            # Set unit based on code
            unit = "PERCENT" if "RATE" in code else "CURRENCY"
            acc = Account(
                code=code, 
                name=name, 
                type=acc_type, 
                unit=unit, 
                pl_section=pl_section, 
                cf_section=cf_section
            )
            accounts.append(acc)
            session.add(acc)
        session.commit()

        # 5. Generate Realistic CubeFacts
        print("Generating Realistic Financial Data...")
        facts = []
        
        # Helper: Generate data for a specific scenario/year
        def generate_for_scenario(scenario_id, year, base_multiplier):
            for month in range(1, 13):
                for dept in depts:
                    for acc in accounts:
                        # Logic to make data realistic
                        if acc.type == "Revenue" and dept.name not in ["Ventes", "Direction"]:
                            continue # Only sales and top dir generate revenue
                            
                        # Base value depends on account
                        base_val = 0
                        if acc.type == "Revenue":
                            base_val = random.randint(50000, 200000)
                        elif "Salaires" in acc.name:
                            base_val = random.randint(20000, 80000)
                        elif "Marketing" in acc.name and dept.name == "Marketing":
                            base_val = random.randint(10000, 50000)
                        elif "Logiciels" in acc.name and dept.name == "IT":
                            base_val = random.randint(5000, 30000)
                        else:
                            base_val = random.randint(1000, 10000)

                        # Apply varying multipliers for seasonality and growth
                        seasonality = 1.0 + (0.1 * math.sin(month / 12.0 * math.pi))
                        final_value = base_val * base_multiplier * seasonality
                        
                        # Add a little randomness
                        final_value *= random.uniform(0.9, 1.1)

                        facts.append(CubeFact(
                            scenario_id=scenario_id,
                            department_id=dept.id,
                            account_id=acc.id,
                            year=year,
                            month=month,
                            value=round(final_value, 2)
                        ))

        import math
        # Actuals 2024
        generate_for_scenario(actuals.id, 2024, 1.0)
        # Budget 2025 (15% overall growth target from 2024)
        generate_for_scenario(budget.id, 2025, 1.15)
        
        # 6. Add Intra-group Transactions (Sample for Elimination)
        print("Adding sample Intra-group transactions...")
        # Scenario: Nexadec Global pays 50,000 to Direction for internal consulting
        # This should be eliminated in consolidation
        acc_rev = next(a for a in accounts if a.code == "702") # Commission/Service Revenue
        acc_exp = next(a for a in accounts if a.code == "603") # Admin Expense
        dept_dir = next(d for d in depts if d.name == "Direction")
        dept_global = global_co # Parent
        
        for m in range(1, 13):
            # Direction Revenue from Global (Internal)
            facts.append(CubeFact(
                scenario_id=budget.id,
                department_id=dept_dir.id,
                partner_id=dept_global.id,
                account_id=acc_rev.id,
                year=2025,
                month=m,
                value=50000.0
            ))
            # Global Expense to Direction (Internal)
            facts.append(CubeFact(
                scenario_id=budget.id,
                department_id=dept_global.id,
                partner_id=dept_dir.id,
                account_id=acc_exp.id,
                year=2025,
                month=m,
                value=50000.0
            ))
        
        # Bulk Insert
        session.bulk_save_objects(facts)
        session.commit()
        print(f"Inserted {len(facts)} CubeFacts successfully.")

if __name__ == "__main__":
    seed_db()
    print("Database seeding completed.")
