import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

conninfo = (
    f"host={os.getenv('ABEL_DB_HOST')} "
    f"port={os.getenv('ABEL_DB_PORT')} "
    f"dbname={os.getenv('ABEL_DB_NAME')} "
    f"user={os.getenv('ABEL_DB_USER')} "
    f"password={os.getenv('ABEL_DB_PASSWORD')}"
)

with psycopg.connect(conninfo) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT key, value FROM current_settings")
        for row in cur.fetchall():
            print(row)