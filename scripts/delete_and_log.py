"""Delete records and write detailed log"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, FamousPerson

log_lines = []
log_lines.append(f"=== Deletion Log - {datetime.now()} ===")
log_lines.append("")

db = SessionLocal()

# IDs to remove
ids_to_remove = [5900, 6901]

log_lines.append(f"Attempting to delete records with IDs: {ids_to_remove}")
log_lines.append("")

# First, check if records exist
for record_id in ids_to_remove:
    record = db.query(FamousPerson).filter(FamousPerson.id == record_id).first()
    if record:
        log_lines.append(f"Found record: ID {record_id} - {record.name}")
    else:
        log_lines.append(f"Record ID {record_id} NOT FOUND")

log_lines.append("")

# Delete using filter
try:
    deleted = db.query(FamousPerson).filter(FamousPerson.id.in_(ids_to_remove)).delete(synchronize_session=False)
    log_lines.append(f"Delete query executed. Rows affected: {deleted}")
    
    db.commit()
    log_lines.append("Commit successful")
    
except Exception as e:
    log_lines.append(f"ERROR during deletion: {e}")
    db.rollback()

log_lines.append("")

# Verify deletion
for record_id in ids_to_remove:
    record = db.query(FamousPerson).filter(FamousPerson.id == record_id).first()
    if record:
        log_lines.append(f"VERIFICATION: Record ID {record_id} STILL EXISTS - {record.name}")
    else:
        log_lines.append(f"VERIFICATION: Record ID {record_id} successfully deleted")

db.close()

# Write log to file
log_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'deletion_log.txt')
with open(log_file, 'w') as f:
    f.write('\n'.join(log_lines))

print("Deletion complete. Check deletion_log.txt for details.")

