"""
Query Optimization Utilities

Tools for analyzing and optimizing database queries.
"""

import logging
import time
from typing import Dict, Any, List, Optional
from functools import wraps
from sqlalchemy import event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Query performance tracking
_query_stats: Dict[str, List[float]] = {}
_slow_queries: List[Dict[str, Any]] = []


@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Track query execution time."""
    conn.info.setdefault('query_start_time', []).append(time.time())


@event.listens_for(Engine, "after_cursor_execute")
def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Record query execution time."""
    total = time.time() - conn.info['query_start_time'].pop()
    
    # Track slow queries (> 100ms)
    if total > 0.1:
        _slow_queries.append({
            "statement": str(statement),
            "parameters": str(parameters),
            "duration": total,
            "timestamp": time.time()
        })
        
        # Keep only last 100 slow queries
        if len(_slow_queries) > 100:
            _slow_queries.pop(0)
    
    # Track query statistics
    query_key = str(statement)[:100]  # First 100 chars as key
    if query_key not in _query_stats:
        _query_stats[query_key] = []
    _query_stats[query_key].append(total)


def track_query_performance(func):
    """
    Decorator to track query performance for a function.
    
    Usage:
        @track_query_performance
        def get_user_charts(user_id):
            return db.query(SavedChart).filter(...).all()
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            if duration > 0.1:  # Log slow queries
                logger.warning(
                    f"Slow query in {func.__name__}: {duration:.3f}s",
                    extra={"function": func.__name__, "duration": duration}
                )
            
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Query error in {func.__name__}: {e} (took {duration:.3f}s)",
                exc_info=True
            )
            raise
    
    return wrapper


def analyze_query(query, db: Session) -> Dict[str, Any]:
    """
    Analyze a SQLAlchemy query for optimization opportunities.
    
    Args:
        query: SQLAlchemy query object
        db: Database session
    
    Returns:
        Analysis results with recommendations
    """
    analysis = {
        "query": str(query),
        "has_joins": False,
        "has_subqueries": False,
        "has_aggregations": False,
        "estimated_rows": None,
        "recommendations": []
    }
    
    # Check for joins
    if hasattr(query, "column_descriptions"):
        if len(query.column_descriptions) > 1:
            analysis["has_joins"] = True
            analysis["recommendations"].append(
                "Consider using selectinload or joinedload for eager loading"
            )
    
    # Check for aggregations
    query_str = str(query)
    if any(keyword in query_str.upper() for keyword in ["COUNT", "SUM", "AVG", "MAX", "MIN", "GROUP BY"]):
        analysis["has_aggregations"] = True
    
    # Check for subqueries
    if "SELECT" in query_str.upper() and query_str.upper().count("SELECT") > 1:
        analysis["has_subqueries"] = True
        analysis["recommendations"].append(
            "Consider optimizing subqueries or using CTEs"
        )
    
    return analysis


def get_query_statistics() -> Dict[str, Any]:
    """
    Get query performance statistics.
    
    Returns:
        Dictionary with query statistics
    """
    stats = {}
    
    for query_key, durations in _query_stats.items():
        if durations:
            stats[query_key] = {
                "count": len(durations),
                "avg_duration": sum(durations) / len(durations),
                "min_duration": min(durations),
                "max_duration": max(durations),
                "total_duration": sum(durations)
            }
    
    return {
        "total_queries": sum(len(durations) for durations in _query_stats.values()),
        "unique_queries": len(_query_stats),
        "slow_queries_count": len(_slow_queries),
        "query_details": stats
    }


def get_slow_queries(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get the slowest queries.
    
    Args:
        limit: Maximum number of queries to return
    
    Returns:
        List of slow query details
    """
    return sorted(_slow_queries, key=lambda x: x["duration"], reverse=True)[:limit]


def reset_query_stats():
    """Reset query statistics."""
    global _query_stats, _slow_queries
    _query_stats = {}
    _slow_queries = []


def recommend_indexes(db: Session, table_name: str) -> List[str]:
    """
    Recommend indexes for a table based on common query patterns.
    
    Args:
        db: Database session
        table_name: Name of the table
    
    Returns:
        List of recommended index SQL statements
    """
    recommendations = []
    
    # Common index recommendations based on table
    if table_name == "saved_charts":
        recommendations.extend([
            "CREATE INDEX IF NOT EXISTS idx_saved_charts_user_id ON saved_charts(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_saved_charts_created_at ON saved_charts(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_saved_charts_user_created ON saved_charts(user_id, created_at);"
        ])
    
    elif table_name == "users":
        recommendations.extend([
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);",
            "CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);"
        ])
    
    elif table_name == "chat_conversations":
        recommendations.extend([
            "CREATE INDEX IF NOT EXISTS idx_chat_conversations_chart_id ON chat_conversations(chart_id);",
            "CREATE INDEX IF NOT EXISTS idx_chat_conversations_created_at ON chat_conversations(created_at);"
        ])
    
    elif table_name == "chat_messages":
        recommendations.extend([
            "CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation_id ON chat_messages(conversation_id);",
            "CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation_created ON chat_messages(conversation_id, created_at);"
        ])
    
    elif table_name == "famous_people":
        recommendations.extend([
            "CREATE INDEX IF NOT EXISTS idx_famous_people_name ON famous_people(name);",
            "CREATE INDEX IF NOT EXISTS idx_famous_people_birth_year ON famous_people(birth_year);"
        ])
    
    return recommendations


def check_existing_indexes(db: Session, table_name: str) -> List[str]:
    """
    Check existing indexes for a table.
    
    Args:
        db: Database session
        table_name: Name of the table
    
    Returns:
        List of existing index names
    """
    indexes = []
    
    try:
        # PostgreSQL
        if "postgresql" in str(db.bind.url):
            result = db.execute(f"""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = '{table_name}'
            """)
            indexes = [row[0] for row in result]
        # SQLite
        elif "sqlite" in str(db.bind.url):
            result = db.execute(f"""
                SELECT name 
                FROM sqlite_master 
                WHERE type='index' AND tbl_name='{table_name}'
            """)
            indexes = [row[0] for row in result]
    except Exception as e:
        logger.warning(f"Error checking indexes for {table_name}: {e}")
    
    return indexes

