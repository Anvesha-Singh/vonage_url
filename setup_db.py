"""
setup_db.py — Run this ONCE to create the database schema, seed products,
and import existing customers from 'Address Book.xlsx'.

Usage:
    python setup_db.py
"""

import psycopg2
import psycopg2.extras
import pandas as pd
import re
import os
from dotenv import load_dotenv

# Load DB URL from .env
load_dotenv()
DB_URL = os.getenv("DB_URL") or "postgresql://postgres:[YOUR-PASSWORD]@db.adyabpbzlfpfvfakfwtn.supabase.co:5432/postgres"

PRODUCTS = [
    "47kg Propane", "19kg Propane", "18kg FLT Propane",
    "11kg Propane Red", "11kg Propane Green", "6kg Propane Red",
    "6kg Propane Green", "13kg Butane", "7kg Butane",
    "10kg Gaslight", "5kg Gaslight"
]

def normalize_phone(phone):
    if not phone or (isinstance(phone, float) and pd.isna(phone)):
        return None
    clean = re.sub(r'\D', '', str(phone))
    if clean.startswith('0'):
        clean = '44' + clean[1:]
    elif len(clean) == 10 and (clean.startswith('7') or clean.startswith('1')):
        clean = '44' + clean
    return f"+{clean}"

def get_conn():
    conn = psycopg2.connect(DB_URL)
    return conn

def create_schema(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            phone      TEXT PRIMARY KEY,
            name       TEXT,
            address    TEXT,
            town       TEXT,
            postcode   TEXT,
            gas_request TEXT
        );

        CREATE TABLE IF NOT EXISTS products (
            id   SERIAL PRIMARY KEY,
            name TEXT UNIQUE
        );

        CREATE TABLE IF NOT EXISTS orders (
            id         SERIAL PRIMARY KEY,
            phone      TEXT NOT NULL REFERENCES customers(phone),
            order_date TEXT NOT NULL,
            notes      TEXT
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id         SERIAL PRIMARY KEY,
            order_id   INTEGER NOT NULL REFERENCES orders(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            quantity   INTEGER NOT NULL DEFAULT 1
        );
    """)
    conn.commit()
    print("✅ Schema created / verified.")

def seed_products(conn):
    cur = conn.cursor()
    for p in PRODUCTS:
        cur.execute("""
            INSERT INTO products (name)
            VALUES (%s)
            ON CONFLICT (name) DO NOTHING
        """, (p,))
    conn.commit()
    print(f"✅ {len(PRODUCTS)} products seeded.")

def import_customers(conn, excel_path="Address Book.xlsx"):
    if not os.path.exists(excel_path):
        print(f"ℹ️  No Excel file found at '{excel_path}' — skipping customer import.")
        return

    try:
        df = pd.read_excel(excel_path)
        df.columns = [str(c).strip().lower() for c in df.columns]
        print(f"   Columns found: {df.columns.tolist()}")

        records = []
        for _, row in df.iterrows():
            phone = normalize_phone(row.get('phone'))
            if not phone:
                continue
            name = row.get('name')
            if pd.isna(name) or str(name).strip() == "":
                name = "Unnamed Customer"
            records.append((
                phone,
                str(name).strip(),
                row.get('address line 1', ''),
                row.get('town', ''),
                row.get('postcode', ''),
                str(row.get('gas request', ''))
            ))

        if records:
            cur = conn.cursor()
            for r in records:
                cur.execute("""
                    INSERT INTO customers (phone, name, address, town, postcode, gas_request)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (phone) DO UPDATE SET
                        name = EXCLUDED.name,
                        address = EXCLUDED.address,
                        town = EXCLUDED.town,
                        postcode = EXCLUDED.postcode,
                        gas_request = EXCLUDED.gas_request
                """, r)
            conn.commit()
            print(f"✅ Imported {len(records)} customers from '{excel_path}'.")
        else:
            print("⚠️  No valid records to import.")

    except Exception as e:
        print(f"❌ Import failed: {e}")

if __name__ == "__main__":
    print("\n🔧 Setting up PostgreSQL database\n")
    conn = get_conn()
    create_schema(conn)
    seed_products(conn)
    import_customers(conn)
    conn.close()
    print("\n✅ Done. Database ready in Supabase/PostgreSQL\n")