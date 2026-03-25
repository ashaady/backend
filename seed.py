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
        
        depts_data = ["Direction", "Ventes", "Marketing", "R&D", "IT", "RH", "Finance"]
        depts = []
        for d in depts_data:
            dept = Department(name=d, parent_id=global_co.id)
            depts.append(dept)
            session.add(dept)
        session.commit()

        # 4. Create Accounts (Chart of Accounts)
        print("Creating Accounts...")
        accounts_data = [
            ("1000", "Revenus - Licences SaaS", "Revenue"),
            ("1100", "Revenus - Services Pro", "Revenue"),
            ("6000", "Salaires et Charges", "Expense"),
            ("6100", "Matériel et Équipement", "Expense"),
            ("6200", "Logiciels et Cloud (AWS, etc.)", "Expense"),
            ("6300", "Campagnes Marketing", "Expense"),
            ("6400", "Déplacements et Repas", "Expense"),
            ("6500", "Consulting Externe", "Expense"),
        ]
        accounts = []
        for code, name, acc_type in accounts_data:
            acc = Account(code=code, name=name, type=acc_type)
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
        
        # Bulk Insert
        session.bulk_save_objects(facts)
        session.commit()
        print(f"Inserted {len(facts)} CubeFacts successfully.")

if __name__ == "__main__":
    seed_db()
    print("Database seeding completed.")
