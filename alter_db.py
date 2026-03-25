from sqlalchemy import text
from app.db import engine

with engine.connect() as con:
    con.execute(text("ALTER TABLE access_users ADD COLUMN restricted_department_id INTEGER REFERENCES departments(id);"))
    con.commit()
print("Success")
