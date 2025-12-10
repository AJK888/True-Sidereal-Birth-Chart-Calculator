"""Remove Vitaly Zdorovetskiy (ID 5900) and Paavo Lipponen (ID 6901)"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, FamousPerson

if __name__ == "__main__":
    db = SessionLocal()
    
    ids_to_remove = [5900, 6901]
    
    print("=" * 60)
    print("REMOVING INVALID RECORDS")
    print("=" * 60)
    
    # Show what we're about to delete
    for record_id in ids_to_remove:
        record = db.query(FamousPerson).filter(FamousPerson.id == record_id).first()
        if record:
            print(f"Found: {record.name} (ID: {record_id})")
        else:
            print(f"ID {record_id} not found (may already be deleted)")
    
    print("\nDeleting records...")
    
    # Delete the records
    deleted_count = db.query(FamousPerson).filter(FamousPerson.id.in_(ids_to_remove)).delete(synchronize_session=False)
    
    db.commit()
    
    print(f"\n✓ Deleted {deleted_count} record(s)")
    
    # Verify
    print("\nVerification:")
    for record_id in ids_to_remove:
        record = db.query(FamousPerson).filter(FamousPerson.id == record_id).first()
        if record:
            print(f"  ❌ ID {record_id} still exists")
        else:
            print(f"  ✓ ID {record_id} successfully removed")
    
    db.close()
    print("\nDone!")

