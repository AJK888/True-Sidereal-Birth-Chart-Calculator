"""Migrate ALL user-related data from Render PostgreSQL to Supabase"""

import os
import sys
import psycopg2
from psycopg2.extras import execute_values
from urllib.parse import quote_plus
from datetime import datetime

# Configuration
SUPABASE_PASSWORD = "#SynthesisAstrology1"
SUPABASE_CONNECTION_STRING = f"postgresql://postgres.nfglgzrfpmtsowwacmwz:{quote_plus(SUPABASE_PASSWORD)}@aws-1-us-east-1.pooler.supabase.com:6543/postgres"

# Render database connection
RENDER_DATABASE_URL = os.getenv("RENDER_DATABASE_URL") or os.getenv("DATABASE_URL", "") or "postgresql://synthesis_astrology_user:CWSlqFoo3uW5a7ZispHrIs3ZTw7uZOlI@dpg-d4j2gcgbdp1s73fkfrg0-a.virginia-postgres.render.com/synthesis_astrology"

def create_all_tables(cursor):
    """Create all user-related tables in Supabase if they don't exist."""
    print("Creating all table schemas in Supabase...")
    
    # Users table (with all columns from database.py)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            hashed_password VARCHAR(255) NOT NULL,
            full_name VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            is_admin BOOLEAN DEFAULT FALSE,
            credits INTEGER DEFAULT 3,
            stripe_customer_id VARCHAR(255),
            stripe_subscription_id VARCHAR(255),
            subscription_status VARCHAR(50) DEFAULT 'inactive',
            subscription_start_date TIMESTAMP,
            subscription_end_date TIMESTAMP,
            has_purchased_reading BOOLEAN DEFAULT FALSE,
            reading_purchase_date TIMESTAMP,
            free_chat_month_end_date TIMESTAMP
        );
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_stripe_customer ON users(stripe_customer_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_stripe_subscription ON users(stripe_subscription_id);")
    
    # Saved charts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS saved_charts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            chart_name VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            birth_year INTEGER NOT NULL,
            birth_month INTEGER NOT NULL,
            birth_day INTEGER NOT NULL,
            birth_hour INTEGER NOT NULL,
            birth_minute INTEGER NOT NULL,
            birth_location VARCHAR(500) NOT NULL,
            unknown_time BOOLEAN DEFAULT FALSE,
            chart_data_json TEXT,
            ai_reading TEXT
        );
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_saved_charts_user_id ON saved_charts(user_id);")
    
    # Chat conversations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_conversations (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            chart_id INTEGER NOT NULL REFERENCES saved_charts(id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            title VARCHAR(255) DEFAULT 'New Conversation'
        );
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_conversations_user_id ON chat_conversations(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_conversations_chart_id ON chat_conversations(chart_id);")
    
    # Chat messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id SERIAL PRIMARY KEY,
            conversation_id INTEGER NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tokens_used INTEGER,
            credits_charged INTEGER DEFAULT 1
        );
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation_id ON chat_messages(conversation_id);")
    
    # Credit transactions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS credit_transactions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            amount INTEGER NOT NULL,
            transaction_type VARCHAR(50) NOT NULL,
            stripe_payment_id VARCHAR(255),
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_credit_transactions_user_id ON credit_transactions(user_id);")
    
    # Subscription payments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscription_payments (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            stripe_payment_intent_id VARCHAR(255),
            stripe_invoice_id VARCHAR(255),
            amount INTEGER NOT NULL,
            currency VARCHAR(10) DEFAULT 'usd',
            status VARCHAR(50) NOT NULL,
            payment_date TIMESTAMP NOT NULL,
            billing_period_start TIMESTAMP,
            billing_period_end TIMESTAMP,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_subscription_payments_user_id ON subscription_payments(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_subscription_payments_payment_intent ON subscription_payments(stripe_payment_intent_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_subscription_payments_invoice ON subscription_payments(stripe_invoice_id);")
    
    # Admin bypass logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_bypass_logs (
            id SERIAL PRIMARY KEY,
            user_email VARCHAR(255),
            endpoint VARCHAR(255) NOT NULL,
            ip_address VARCHAR(45),
            user_agent VARCHAR(500),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            details TEXT
        );
    """)
    
    print("[OK] All table schemas created")

def migrate_table(render_cursor, supabase_cursor, table_name, columns, order_by="id"):
    """Migrate a table from Render to Supabase."""
    print(f"\nMigrating {table_name}...")
    
    # Get all data from Render
    render_cursor.execute(f"SELECT * FROM {table_name} ORDER BY {order_by};")
    rows = render_cursor.fetchall()
    
    if not rows:
        print(f"  No data to migrate for {table_name}")
        return 0
    
    print(f"  Found {len(rows)} rows to migrate")
    
    # Clear existing data in Supabase (optional - comment out if you want to keep existing)
    supabase_cursor.execute(f"TRUNCATE TABLE {table_name} CASCADE;")
    
    # Prepare data
    data = []
    for row in rows:
        # Convert None to None, handle booleans, etc.
        processed_row = []
        for i, val in enumerate(row):
            if val is None:
                processed_row.append(None)
            elif isinstance(val, bool):
                processed_row.append(val)
            elif isinstance(val, (int, str, float)):
                processed_row.append(val)
            elif isinstance(val, datetime):
                processed_row.append(val)
            else:
                processed_row.append(str(val))
        data.append(tuple(processed_row))
    
    # Insert data
    if data:
        column_names = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))
        insert_sql = f"INSERT INTO {table_name} ({column_names}) VALUES %s"
        
        execute_values(supabase_cursor, insert_sql, data, template=None, page_size=100)
        print(f"  [OK] Inserted {len(data)} rows into {table_name}")
    
    return len(data)

def main():
    print("=" * 60)
    print("MIGRATE ALL USER DATA TO SUPABASE")
    print("=" * 60)
    
    render_db_url = RENDER_DATABASE_URL
    
    # Fix postgres:// to postgresql:// if needed
    if render_db_url.startswith("postgres://"):
        render_db_url = render_db_url.replace("postgres://", "postgresql://", 1)
    
    # Add port if missing
    if "@" in render_db_url:
        parts = render_db_url.split("@")
        if len(parts) == 2:
            host_db = parts[1]
            if "/" in host_db:
                host, db = host_db.split("/", 1)
                if ":" not in host:
                    render_db_url = f"{parts[0]}@{host}:5432/{db}"
    
    print(f"\n[OK] Using Render database")
    print(f"Render: {render_db_url.split('@')[1] if '@' in render_db_url else 'N/A'}")
    print(f"Supabase: aws-1-us-east-1.pooler.supabase.com")
    
    render_conn = None
    supabase_conn = None
    
    try:
        # Connect to Render
        print("\nConnecting to Render database...")
        render_conn = psycopg2.connect(render_db_url)
        render_cursor = render_conn.cursor()
        print("[OK] Connected to Render")
        
        # Connect to Supabase
        print("Connecting to Supabase...")
        supabase_conn = psycopg2.connect(SUPABASE_CONNECTION_STRING)
        supabase_cursor = supabase_conn.cursor()
        print("[OK] Connected to Supabase")
        
        # Create all tables
        create_all_tables(supabase_cursor)
        supabase_conn.commit()
        
        # Migrate in order (respecting foreign keys)
        total_migrated = 0
        
        # 1. Users (no dependencies)
        render_cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'users' ORDER BY ordinal_position;")
        user_columns = [row[0] for row in render_cursor.fetchall()]
        # Add missing columns that might not exist in Render
        expected_user_columns = ['id', 'email', 'hashed_password', 'full_name', 'created_at', 'is_active', 'is_admin', 'credits',
                                'stripe_customer_id', 'stripe_subscription_id', 'subscription_status', 'subscription_start_date', 
                                'subscription_end_date', 'has_purchased_reading', 'reading_purchase_date', 'free_chat_month_end_date']
        # Only use columns that exist in Render
        user_columns_to_migrate = [col for col in expected_user_columns if col in user_columns]
        total_migrated += migrate_table(render_cursor, supabase_cursor, "users", user_columns_to_migrate)
        supabase_conn.commit()
        
        # 2. Saved charts (depends on users)
        render_cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'saved_charts' ORDER BY ordinal_position;")
        chart_columns = [row[0] for row in render_cursor.fetchall()]
        total_migrated += migrate_table(render_cursor, supabase_cursor, "saved_charts", chart_columns)
        supabase_conn.commit()
        
        # 3. Chat conversations (depends on users and saved_charts)
        render_cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'chat_conversations' ORDER BY ordinal_position;")
        conv_columns = [row[0] for row in render_cursor.fetchall()]
        total_migrated += migrate_table(render_cursor, supabase_cursor, "chat_conversations", conv_columns)
        supabase_conn.commit()
        
        # 4. Chat messages (depends on chat_conversations)
        render_cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'chat_messages' ORDER BY ordinal_position;")
        msg_columns = [row[0] for row in render_cursor.fetchall()]
        total_migrated += migrate_table(render_cursor, supabase_cursor, "chat_messages", msg_columns)
        supabase_conn.commit()
        
        # 5. Credit transactions (depends on users)
        render_cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'credit_transactions' ORDER BY ordinal_position;")
        credit_columns = [row[0] for row in render_cursor.fetchall()]
        total_migrated += migrate_table(render_cursor, supabase_cursor, "credit_transactions", credit_columns)
        supabase_conn.commit()
        
        # 6. Subscription payments (depends on users)
        render_cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'subscription_payments' ORDER BY ordinal_position;")
        payment_columns = [row[0] for row in render_cursor.fetchall()]
        total_migrated += migrate_table(render_cursor, supabase_cursor, "subscription_payments", payment_columns)
        supabase_conn.commit()
        
        # 7. Admin bypass logs (no dependencies)
        render_cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'admin_bypass_logs' ORDER BY ordinal_position;")
        log_columns = [row[0] for row in render_cursor.fetchall()]
        total_migrated += migrate_table(render_cursor, supabase_cursor, "admin_bypass_logs", log_columns)
        supabase_conn.commit()
        
        # Verify migration
        print("\n" + "=" * 60)
        print("VERIFICATION")
        print("=" * 60)
        
        tables_to_check = ["users", "saved_charts", "chat_conversations", "chat_messages", 
                          "credit_transactions", "subscription_payments", "admin_bypass_logs"]
        
        for table in tables_to_check:
            supabase_cursor.execute(f"SELECT COUNT(*) FROM {table};")
            count = supabase_cursor.fetchone()[0]
            print(f"  {table}: {count} rows")
        
        print("\n" + "=" * 60)
        print(f"MIGRATION COMPLETE! Total rows migrated: {total_migrated}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] Error during migration: {e}")
        import traceback
        traceback.print_exc()
        if supabase_conn:
            supabase_conn.rollback()
        sys.exit(1)
    
    finally:
        if render_conn:
            render_cursor.close()
            render_conn.close()
        if supabase_conn:
            supabase_cursor.close()
            supabase_conn.close()
        print("\n[OK] Connections closed")

if __name__ == "__main__":
    main()

