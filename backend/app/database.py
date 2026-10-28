import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./md_decision_lab.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema_compatibility(target_engine=None):
    from sqlalchemy import text
    target = target_engine or engine
    with target.connect() as conn:
        tables = [row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()]
        if "fashion_decisions" in tables:
            cols = {row[1] for row in conn.execute(text("PRAGMA table_info(fashion_decisions)")).fetchall()}
            new_cols = [
                ("chosen_option", "TEXT"),
                ("discount_pct", "REAL"),
                ("expected_units_30d", "INTEGER"),
                ("purchase_units", "INTEGER DEFAULT 0"),
                ("estimated_revenue", "REAL"),
                ("estimated_gross_profit", "REAL"),
                ("estimated_remaining_stock", "INTEGER"),
                ("feasible", "BOOLEAN"),
            ]
            for col_name, col_type in new_cols:
                if col_name not in cols:
                    conn.execute(text(f"ALTER TABLE fashion_decisions ADD COLUMN {col_name} {col_type}"))
            conn.commit()
