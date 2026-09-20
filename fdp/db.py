import os
import psycopg
from dotenv import load_dotenv


def get_conn() -> psycopg.Connection:
    load_dotenv()
    return psycopg.connect(
        host=os.environ["POSTGRES_HOST"], port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"], user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        autocommit=True,  # les transactions sont ouvertes explicitement avec conn.transaction()
    )