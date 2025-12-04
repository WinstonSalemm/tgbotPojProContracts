import psycopg2
import os

def db():
    return psycopg2.connect(
        host=os.getenv("PGHOST"),
        port=os.getenv("PGPORT"),
        dbname=os.getenv("PGDATABASE"),
        user=os.getenv("PGUSER"),
        password=os.getenv("PGPASSWORD"),
        sslmode="require"   # <<< ВАЖНО на Railway!
    )


def init_tables():
    conn = db()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS contracts (
        id SERIAL PRIMARY KEY,
        buyer_name TEXT,
        inn TEXT,
        phone TEXT,
        total_sum NUMERIC,
        file_url TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """)
    conn.commit()
    conn.close()

def save_contract(name, inn, phone, total, url):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO contracts(buyer_name, inn, phone, total_sum, file_url)
        VALUES (%s, %s, %s, %s, %s)
    """,(name, inn, phone, total, url))
    conn.commit()
    conn.close()
