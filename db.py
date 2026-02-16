import sqlite3
from pathlib import Path
from typing import List, Tuple

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "talk2data.db"
DATA_DIR = BASE_DIR / "data"


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection to the main database."""
    return sqlite3.connect(DB_PATH)


def describe_schema(conn: sqlite3.Connection) -> str:
    """
    Return a human-readable description of all tables and columns
    in the currently connected SQLite database.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
    )
    tables = [row[0] for row in cur.fetchall()]

    if not tables:
        return "No user tables found in this database."

    lines: List[str] = []
    for table in tables:
        lines.append(f"Table {table}:")
        cur.execute(f"PRAGMA table_info('{table}');")
        cols = cur.fetchall()
        for col in cols:
            # PRAGMA table_info: cid, name, type, notnull, dflt_value, pk
            _, name, col_type, notnull, default, pk = col
            col_desc = f"  - {name} {col_type or ''}".rstrip()
            extras = []
            if pk:
                extras.append("PRIMARY KEY")
            if notnull:
                extras.append("NOT NULL")
            if default is not None:
                extras.append(f"DEFAULT {default}")
            if extras:
                col_desc += " (" + ", ".join(extras) + ")"
            lines.append(col_desc)
        lines.append("")  # blank line between tables

    return "\n".join(lines).strip()


def _load_sample_data() -> None:
    """Create a simple sales table with sample data if it does not exist."""
    DATA_DIR.mkdir(exist_ok=True)

    csv_path = DATA_DIR / "sales.csv"
    if not csv_path.exists():
        # Create a small synthetic dataset
        df = pd.DataFrame(
            [
                # date, product, category, region, quantity, price
                ("2024-01-05", "Widget A", "Widgets", "North", 10, 19.99),
                ("2024-01-12", "Widget B", "Widgets", "South", 5, 24.99),
                ("2024-02-03", "Widget A", "Widgets", "North", 7, 19.99),
                ("2024-02-15", "Gadget C", "Gadgets", "West", 20, 9.99),
                ("2024-03-01", "Widget B", "Widgets", "East", 8, 24.99),
                ("2024-03-18", "Gadget C", "Gadgets", "North", 15, 9.99),
                ("2024-04-02", "Widget A", "Widgets", "South", 12, 19.99),
                ("2024-04-20", "Gadget D", "Gadgets", "West", 9, 14.99),
                ("2024-05-05", "Widget B", "Widgets", "North", 6, 24.99),
                ("2024-05-22", "Gadget D", "Gadgets", "East", 18, 14.99),
            ],
            columns=[
                "order_date",
                "product",
                "category",
                "region",
                "quantity",
                "unit_price",
            ],
        )
        df.to_csv(csv_path, index=False)

    conn = get_connection()
    try:
        df = pd.read_csv(csv_path, parse_dates=["order_date"])
        df.to_sql("sales", conn, if_exists="replace", index=False)
    finally:
        conn.close()


def init_db() -> Tuple[Path, Path]:
    """Ensure the database and sample data exist. Returns (db_path, data_dir)."""
    if not DB_PATH.exists():
        _load_sample_data()
    else:
        # Make sure the sales table exists; if not, load data.
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sales';"
            )
            exists = cur.fetchone() is not None
        finally:
            conn.close()
        if not exists:
            _load_sample_data()

    return DB_PATH, DATA_DIR

