"""Verify that the records were removed"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, FamousPerson

db = SessionLocal()

ids_to_check = [5900, 6901]

results = []
for record_id in ids_to_check:
    record = db.query(FamousPerson).filter(FamousPerson.id == record_id).first()
    exists = record is not None
    results.append(f"ID {record_id} exists: {exists}")

db.close()

output = "\n".join(results)
print(output)

with open('verify_removal.txt', 'w') as f:
    f.write(output)

