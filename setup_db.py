"""
setup_db.py
-----------
Initialise le schéma mlb et toutes les tables.
A lancer une seule fois (ou pour réinitialiser la structure).

Usage :
    python setup_db.py
"""

import os
import re
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

SQL_DIR = Path(__file__).parent / "sql"
SQL_FILES = [
    SQL_DIR / "init_mlb_schema.sql",   # schéma + gallery_players
    SQL_DIR / "init_mlb_tables.sql",   # teams, players, gameweeks, scores, prices
]


def _run_sql_file(conn, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    sql = re.sub(r"--[^\n]*", "", sql)  # supprime les commentaires -- avant de splitter
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    for stmt in statements:
        conn.execute(text(stmt))
    print(f"  OK : {path.name}")


def main():
    env_path = Path(__file__).parent / ".." / ".env"
    load_dotenv(dotenv_path=env_path)

    engine = create_engine(
        f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
        f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )

    with engine.begin() as conn:
        for sql_file in SQL_FILES:
            _run_sql_file(conn, sql_file)

    print("Schéma mlb initialisé.")


if __name__ == "__main__":
    main()
