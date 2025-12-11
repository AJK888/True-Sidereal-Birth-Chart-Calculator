"""Migrate SQLite database to Supabase PostgreSQL"""

import os
import sys
import sqlite3
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
from urllib.parse import quote_plus

# Configuration - Supabase connection details
# Using Connection Pooling (recommended - works better through firewalls)
SUPABASE_PASSWORD = "#SynthesisAstrology1"

# Connection Pooling URL (port 6543) - works better through firewalls
SUPABASE_CONNECTION_STRING = f"postgresql://postgres.nfglgzrfpmtsowwacmwz:{quote_plus(SUPABASE_PASSWORD)}@aws-1-us-east-1.pooler.supabase.com:6543/postgres"

# Direct connection (port 5432) - kept as backup
# SUPABASE_DIRECT_STRING = f"postgresql://postgres:{quote_plus(SUPABASE_PASSWORD)}@db.nfglgzrfpmtsowwacmwz.supabase.co:5432/postgres"

# Option 2: Use individual config (if connection string doesn't work)
SUPABASE_CONFIG = {
    'host': 'db.nfglgzrfpmtsowwacmwz.supabase.co',
    'port': 5432,
    'database': 'postgres',
    'user': 'postgres',
    'password': '',  # Will be prompted if not set
}

def get_sqlite_db_path():
    """Get the SQLite database path."""
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(script_dir, "synthesis_astrology.db")

def create_supabase_schema(cursor):
    """Create the famous_people table in Supabase."""
    print("Creating table schema in Supabase...")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS famous_people (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL UNIQUE,
            wikipedia_url VARCHAR(500) NOT NULL,
            occupation VARCHAR(255),
            birth_year INTEGER NOT NULL,
            birth_month INTEGER NOT NULL,
            birth_day INTEGER NOT NULL,
            birth_hour INTEGER,
            birth_minute INTEGER,
            birth_location VARCHAR(500) NOT NULL,
            unknown_time BOOLEAN DEFAULT TRUE,
            chart_data_json TEXT,
            planetary_placements_json TEXT,
            top_aspects_json TEXT,
            sun_sign_sidereal VARCHAR(50),
            sun_sign_tropical VARCHAR(50),
            moon_sign_sidereal VARCHAR(50),
            moon_sign_tropical VARCHAR(50),
            life_path_number VARCHAR(10),
            day_number VARCHAR(10),
            chinese_zodiac_animal VARCHAR(50),
            page_views INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes
    print("Creating indexes...")
    indexes = [
        ("CREATE INDEX IF NOT EXISTS idx_famous_people_name ON famous_people(name)",),
        ("CREATE INDEX IF NOT EXISTS idx_famous_people_sun_sign_sidereal ON famous_people(sun_sign_sidereal)",),
        ("CREATE INDEX IF NOT EXISTS idx_famous_people_sun_sign_tropical ON famous_people(sun_sign_tropical)",),
        ("CREATE INDEX IF NOT EXISTS idx_famous_people_moon_sign_sidereal ON famous_people(moon_sign_sidereal)",),
        ("CREATE INDEX IF NOT EXISTS idx_famous_people_moon_sign_tropical ON famous_people(moon_sign_tropical)",),
        ("CREATE INDEX IF NOT EXISTS idx_famous_people_life_path_number ON famous_people(life_path_number)",),
        ("CREATE INDEX IF NOT EXISTS idx_famous_people_chinese_zodiac_animal ON famous_people(chinese_zodiac_animal)",),
        ("CREATE INDEX IF NOT EXISTS idx_famous_people_page_views ON famous_people(page_views)",),
    ]
    
    for index_sql in indexes:
        cursor.execute(index_sql[0])
    
    print("✓ Schema created successfully")

def migrate_data(sqlite_conn, pg_conn):
    """Migrate data from SQLite to PostgreSQL."""
    sqlite_cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()
    
    # Get all records from SQLite
    print("\nReading data from SQLite...")
    sqlite_cursor.execute("SELECT * FROM famous_people ORDER BY id")
    columns = [description[0] for description in sqlite_cursor.description]
    
    # Map SQLite columns to PostgreSQL columns (exclude unwanted columns)
    wanted_columns = [
        'id', 'name', 'wikipedia_url', 'occupation',
        'birth_year', 'birth_month', 'birth_day',
        'birth_hour', 'birth_minute', 'birth_location', 'unknown_time',
        'chart_data_json', 'planetary_placements_json', 'top_aspects_json',
        'sun_sign_sidereal', 'sun_sign_tropical',
        'moon_sign_sidereal', 'moon_sign_tropical',
        'life_path_number', 'day_number',
        'chinese_zodiac_animal',
        'page_views', 'created_at', 'updated_at'
    ]
    
    # Filter to only columns that exist in SQLite and are wanted
    columns_to_use = [col for col in columns if col in wanted_columns]
    column_indices = [columns.index(col) for col in columns_to_use]
    
    print(f"Migrating {len(columns_to_use)} columns...")
    print(f"Columns: {', '.join(columns_to_use)}")
    
    # Read all rows
    rows = sqlite_cursor.fetchall()
    print(f"Found {len(rows)} records to migrate")
    
    if not rows:
        print("No records to migrate!")
        return
    
    # Prepare data for bulk insert
    data_to_insert = []
    for row in rows:
        # Extract only wanted columns
        filtered_row = [row[i] if i < len(row) else None for i in column_indices]
        
        # Convert SQLite boolean (integer) to PostgreSQL boolean
        # Find the index of unknown_time in columns_to_use
        if 'unknown_time' in columns_to_use:
            unknown_time_idx = columns_to_use.index('unknown_time')
            if filtered_row[unknown_time_idx] is not None:
                # SQLite stores booleans as 0/1, convert to True/False
                filtered_row[unknown_time_idx] = bool(filtered_row[unknown_time_idx])
        
        data_to_insert.append(filtered_row)
    
    # Clear existing data (optional - comment out if you want to keep existing)
    print("\nClearing existing data in Supabase...")
    pg_cursor.execute("TRUNCATE TABLE famous_people RESTART IDENTITY CASCADE")
    
    # Bulk insert
    print(f"\nInserting {len(data_to_insert)} records into Supabase...")
    
    # Build the INSERT statement - use execute_values with proper template
    # execute_values needs a template with %s for the VALUES part (single placeholder)
    columns_str = ', '.join(columns_to_use)
    # Template: VALUES (%s, %s, ...) - execute_values will replace %s with the values
    template = '(' + ', '.join(['%s'] * len(columns_to_use)) + ')'
    insert_sql = f"INSERT INTO famous_people ({columns_str}) VALUES %s"
    
    # Insert in batches of 1000
    batch_size = 1000
    total_inserted = 0
    
    for i in range(0, len(data_to_insert), batch_size):
        batch = data_to_insert[i:i + batch_size]
        # execute_values: SQL with %s, data rows, template for each row
        execute_values(pg_cursor, insert_sql, batch, template=template, page_size=batch_size)
        total_inserted += len(batch)
        print(f"  Inserted {total_inserted}/{len(data_to_insert)} records...")
    
    pg_conn.commit()
    print(f"\n✓ Successfully migrated {total_inserted} records to Supabase")
    
    # Verify
    pg_cursor.execute("SELECT COUNT(*) FROM famous_people")
    count = pg_cursor.fetchone()[0]
    print(f"✓ Verification: {count} records in Supabase database")

def main():
    """Main migration function."""
    print("=" * 60)
    print("MIGRATE TO SUPABASE")
    print("=" * 60)
    
    # Check configuration - prefer connection string
    use_connection_string = False
    final_connection_string = None
    
    # Check if connection string is set and needs password replacement
    if 'SUPABASE_CONNECTION_STRING' in globals() and SUPABASE_CONNECTION_STRING:
        if '[YOUR_PASSWORD]' in SUPABASE_CONNECTION_STRING:
            # Need to replace password in connection string
            print("\n⚠️  Database password needed for connection string!")
            password = input("Enter your Supabase database password: ").strip()
            if not password:
                print("✗ Password is required")
                sys.exit(1)
            final_connection_string = SUPABASE_CONNECTION_STRING.replace('[YOUR_PASSWORD]', password)
            use_connection_string = True
            print("✓ Connection string configured")
        else:
            # Connection string is ready to use
            final_connection_string = SUPABASE_CONNECTION_STRING
            use_connection_string = True
            print("\n✓ Using connection string")
    elif not SUPABASE_CONFIG['password']:
        # Use config dict, need password
        print("\n⚠️  Database password needed!")
        password = input("Enter your Supabase database password: ").strip()
        if not password:
            print("✗ Password is required")
            sys.exit(1)
        SUPABASE_CONFIG['password'] = password
    
    sqlite_path = get_sqlite_db_path()
    if not os.path.exists(sqlite_path):
        print(f"\n✗ SQLite database not found: {sqlite_path}")
        sys.exit(1)
    
    print(f"\nSQLite database: {sqlite_path}")
    print(f"Supabase host: {SUPABASE_CONFIG['host']}")
    
    # Connect to SQLite
    print("\nConnecting to SQLite...")
    sqlite_conn = sqlite3.connect(sqlite_path)
    print("✓ Connected to SQLite")
    
    # Connect to Supabase
    print("\nConnecting to Supabase (Connection Pooling)...")
    print(f"  Host: aws-1-us-east-1.pooler.supabase.com")
    print(f"  Port: 6543")
    print(f"  Database: postgres")
    print(f"  User: postgres.nfglgzrfpmtsowwacmwz")
    print("  Attempting connection (DNS test skipped - will try direct connection)...")
    
    try:
        # Use connection string if available, otherwise use config dict
        if use_connection_string and final_connection_string:
            print("  Attempting connection with connection string...")
            pg_conn = psycopg2.connect(final_connection_string, connect_timeout=10)
        else:
            print("  Attempting connection with config...")
            pg_conn = psycopg2.connect(**SUPABASE_CONFIG, connect_timeout=10)
        print("✓ Connected to Supabase")
    except psycopg2.OperationalError as e:
        print(f"\n✗ Failed to connect to Supabase: {e}")
        print("\nTroubleshooting steps:")
        print("  1. Check your internet connection")
        print("  2. Verify your Supabase project is active")
        print("  3. Check if your IP needs to be whitelisted:")
        print("     Supabase Dashboard > Settings > Database > Network Restrictions")
        print("  4. Try using Connection Pooling URL instead:")
        print("     Settings > Database > Connection pooling > Session mode")
        print("  5. Verify connection details:")
        print("     - Host: db.nfglgzrfpmtsowwacmwz.supabase.co")
        print("     - Port: 5432")
        print("     - Database: postgres")
        print("     - Username: postgres")
        print("     - Password: (check your Supabase dashboard)")
        sqlite_conn.close()
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error connecting to Supabase: {e}")
        import traceback
        traceback.print_exc()
        sqlite_conn.close()
        sys.exit(1)
    
    try:
        pg_cursor = pg_conn.cursor()
        
        # Create schema
        create_supabase_schema(pg_cursor)
        pg_conn.commit()
        
        # Migrate data
        migrate_data(sqlite_conn, pg_conn)
        
        print("\n" + "=" * 60)
        print("MIGRATION COMPLETE!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error during migration: {e}")
        import traceback
        traceback.print_exc()
        pg_conn.rollback()
        sys.exit(1)
    finally:
        sqlite_conn.close()
        pg_conn.close()
        print("\n✓ Connections closed")

if __name__ == "__main__":
    main()

