import psycopg2
import os
import json

def db():
    return psycopg2.connect(
        host=os.getenv("PGHOST"),
        port=os.getenv("PGPORT"),
        database=os.getenv("PGDATABASE"),
        user=os.getenv("PGUSER"),
        password=os.getenv("PGPASSWORD")
    )

def init_tables():
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS contracts (
            id SERIAL PRIMARY KEY,
            buyer_name TEXT,
            inn TEXT,
            address TEXT,
            phone TEXT,
            account TEXT,
            bank TEXT,
            mfo TEXT,
            director TEXT,
            items JSONB,
            file_url TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    conn.commit()
    conn.close()

def save_contract(data: dict, file_url: str):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO contracts
        (buyer_name, inn, address, phone, account, bank, mfo, director, items, file_url)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        data["buyer_name"],
        data["inn"],
        data["address"],
        data["phone"],
        data["account"],
        data["bank"],
        data["mfo"],
        data["director"],
        json.dumps(data["items"]),
        file_url
    ))

    conn.commit()
    conn.close()
