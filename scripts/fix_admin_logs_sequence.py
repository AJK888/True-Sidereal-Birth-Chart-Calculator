"""
Fix admin_bypass_logs sequence synchronization issue in Supabase.

This script resets the PostgreSQL sequence to match the maximum ID in the table.
Run this whenever you see UniqueViolation errors for admin_bypass_logs.
"""

import os
import psycopg2
from urllib.parse import quote_plus

# Supabase connection
SUPABASE_PASSWORD = "#SynthesisAstrology1"
SUPABASE_CONNECTION_STRING = f"postgresql://postgres.nfglgzrfpmtsowwacmwz:{quote_plus(SUPABASE_PASSWORD)}@aws-1-us-east-1.pooler.supabase.com:6543/postgres"

def fix_sequence():
    """Reset the admin_bypass_logs sequence to the correct value."""
    try:
        conn = psycopg2.connect(SUPABASE_CONNECTION_STRING)
        cursor = conn.cursor()
        
        # Get current max ID
        cursor.execute("SELECT MAX(id) FROM admin_bypass_logs;")
        max_id_result = cursor.fetchone()
        max_id = max_id_result[0] if max_id_result[0] is not None else 0
        
        print(f"Current maximum ID in admin_bypass_logs: {max_id}")
        
        # Get current sequence value
        cursor.execute("SELECT currval('admin_bypass_logs_id_seq');")
        current_seq = cursor.fetchone()[0]
        print(f"Current sequence value: {current_seq}")
        
        # Reset sequence to max_id + 1
        new_seq_value = max_id + 1
        cursor.execute(
            f"SELECT setval('admin_bypass_logs_id_seq', {new_seq_value}, false);"
        )
        
        # Verify
        cursor.execute("SELECT currval('admin_bypass_logs_id_seq');")
        new_seq = cursor.fetchone()[0]
        print(f"New sequence value: {new_seq}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"\n✓ Sequence fixed! Next insert will use ID {new_seq}")
        return True
        
    except Exception as e:
        print(f"Error fixing sequence: {e}")
        return False

if __name__ == "__main__":
    print("Fixing admin_bypass_logs sequence...")
    print("=" * 50)
    success = fix_sequence()
    if success:
        print("\n" + "=" * 50)
        print("Sequence fix completed successfully!")
    else:
        print("\n" + "=" * 50)
        print("Sequence fix failed. Please check the error above.")

