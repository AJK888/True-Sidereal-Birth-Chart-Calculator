"""View statistics about pageviews in the database"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, FamousPerson
from sqlalchemy import func

def view_pageview_stats():
    """Display statistics about pageviews in the database."""
    db = SessionLocal()
    
    try:
        total_records = db.query(FamousPerson).count()
        records_with_pageviews = db.query(FamousPerson).filter(
            FamousPerson.page_views.isnot(None),
            FamousPerson.page_views > 0
        ).count()
        records_without_pageviews = total_records - records_with_pageviews
        
        # Get statistics
        stats = db.query(
            func.min(FamousPerson.page_views).label('min'),
            func.max(FamousPerson.page_views).label('max'),
            func.avg(FamousPerson.page_views).label('avg'),
            func.sum(FamousPerson.page_views).label('total')
        ).filter(
            FamousPerson.page_views.isnot(None),
            FamousPerson.page_views > 0
        ).first()
        
        # Get top 10 by pageviews
        top_10 = db.query(FamousPerson).filter(
            FamousPerson.page_views.isnot(None),
            FamousPerson.page_views > 0
        ).order_by(FamousPerson.page_views.desc()).limit(10).all()
        
        print("=" * 60)
        print("PAGEVIEW STATISTICS")
        print("=" * 60)
        print(f"Total records: {total_records:,}")
        print(f"Records with pageviews: {records_with_pageviews:,}")
        print(f"Records without pageviews: {records_without_pageviews:,}")
        print()
        
        if stats and stats.min is not None:
            print("Pageview Statistics (past year):")
            print(f"  Minimum: {stats.min:,}")
            print(f"  Maximum: {stats.max:,}")
            print(f"  Average: {stats.avg:,.0f}")
            print(f"  Total: {stats.total:,}")
            print()
        
        if top_10:
            print("Top 10 by Pageviews:")
            for idx, person in enumerate(top_10, 1):
                print(f"  {idx:2d}. {person.name:40s} - {person.page_views:>12,} views")
        
        print("=" * 60)
        
    finally:
        db.close()

if __name__ == "__main__":
    view_pageview_stats()

