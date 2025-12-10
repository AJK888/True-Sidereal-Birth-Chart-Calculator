"""Directly delete records by ID"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, FamousPerson

db = SessionLocal()

# IDs to remove
ids_to_remove = [5900, 6901]

print(f"Deleting records with IDs: {ids_to_remove}")

# Delete using filter
deleted = db.query(FamousPerson).filter(FamousPerson.id.in_(ids_to_remove)).delete(synchronize_session=False)

db.commit()

print(f"Deleted {deleted} records")

# Verify deletion
remaining = db.query(FamousPerson).filter(FamousPerson.id.in_(ids_to_remove)).count()
print(f"Remaining records with these IDs: {remaining}")

db.close()

