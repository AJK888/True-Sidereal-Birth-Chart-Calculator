"""
Database Query Analysis Script

Analyzes database queries and provides optimization recommendations.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database import get_db, init_db
from app.utils.query_optimizer import (
    get_query_statistics,
    get_slow_queries,
    recommend_indexes,
    check_existing_indexes,
    reset_query_stats
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def analyze_database():
    """Analyze database and provide optimization recommendations."""
    init_db()
    db = next(get_db())
    
    try:
        print("=" * 80)
        print("DATABASE QUERY ANALYSIS")
        print("=" * 80)
        print()
        
        # Get query statistics
        print("Query Statistics:")
        print("-" * 80)
        stats = get_query_statistics()
        print(f"Total Queries: {stats['total_queries']}")
        print(f"Unique Queries: {stats['unique_queries']}")
        print(f"Slow Queries (>100ms): {stats['slow_queries_count']}")
        print()
        
        # Show slow queries
        if stats['slow_queries_count'] > 0:
            print("Slowest Queries:")
            print("-" * 80)
            slow_queries = get_slow_queries(limit=10)
            for i, query in enumerate(slow_queries, 1):
                print(f"{i}. Duration: {query['duration']:.3f}s")
                print(f"   Query: {query['statement'][:200]}...")
                print()
        
        # Show query details
        if stats.get('query_details'):
            print("Query Performance Details:")
            print("-" * 80)
            for query_key, details in list(stats['query_details'].items())[:10]:
                print(f"Query: {query_key[:100]}...")
                print(f"  Count: {details['count']}")
                print(f"  Avg Duration: {details['avg_duration']:.3f}s")
                print(f"  Max Duration: {details['max_duration']:.3f}s")
                print()
        
        # Index recommendations
        print("Index Recommendations:")
        print("-" * 80)
        tables = ["saved_charts", "users", "chat_conversations", "chat_messages", "famous_people"]
        
        for table in tables:
            print(f"\n{table}:")
            existing = check_existing_indexes(db, table)
            recommended = recommend_indexes(db, table)
            
            print(f"  Existing indexes: {len(existing)}")
            if existing:
                for idx in existing:
                    print(f"    - {idx}")
            
            print(f"  Recommended indexes: {len(recommended)}")
            for idx_sql in recommended:
                idx_name = idx_sql.split("idx_")[1].split(" ")[0] if "idx_" in idx_sql else "unknown"
                if idx_name not in existing:
                    print(f"    + {idx_sql}")
        
        print()
        print("=" * 80)
        print("ANALYSIS COMPLETE")
        print("=" * 80)
        
    finally:
        db.close()


if __name__ == "__main__":
    analyze_database()

