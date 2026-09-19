import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

conninfo = (
    f"host={os.environ['POSTGRES_HOST']} port={os.environ['POSTGRES_PORT']} "
    f"dbname={os.environ['POSTGRES_DB']} user={os.environ['POSTGRES_USER']} "
    f"password={os.environ['POSTGRES_PASSWORD']}"
)

with psycopg.connect(conninfo) as conn:
    rows = conn.execute(
        "SELECT schema_name FROM information_schema.schemata "
        "WHERE schema_name IN ('raw','staging','marts','quality') ORDER BY 1"
    ).fetchall()

print([r[0] for r in rows])