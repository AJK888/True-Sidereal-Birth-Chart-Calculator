"""Remove invalid records from the database"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, FamousPerson, init_db

# Initialize database
init_db()

db = SessionLocal()

# IDs to remove
ids_to_remove = [5900, 6901]

output_lines = []
output_lines.append("Removing invalid records from database...")
output_lines.append(f"IDs to remove: {ids_to_remove}")

removed_count = 0
for record_id in ids_to_remove:
    record = db.query(FamousPerson).filter(FamousPerson.id == record_id).first()
    if record:
        output_lines.append(f"  Removing: {record.name} (ID: {record_id})")
        db.delete(record)
        removed_count += 1
    else:
        output_lines.append(f"  Record ID {record_id} not found")

try:
    db.commit()
    output_lines.append(f"\n✓ Successfully removed {removed_count} records")
except Exception as e:
    output_lines.append(f"\n✗ Error committing: {e}")
    db.rollback()

for line in output_lines:
    print(line)

# Also write to file
output_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'remove_records_output.txt')
with open(output_file, 'w') as f:
    f.write('\n'.join(output_lines))

db.close()

