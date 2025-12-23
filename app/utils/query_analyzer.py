"""
Query Performance Analyzer

Utilities for analyzing and optimizing database queries.
"""

import logging
import time
from typing import Dict, Any, Optional, List
from contextlib import contextmanager
from sqlalchemy.orm import Session
from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.core.logging_config import setup_logger

logger = setup_logger(__name__)

# Global query statistics
query_stats = {
    "total_queries": 0,
    "slow_queries": [],
    "query_times": [],
    "queries_by_table": {}
}


@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Log query execution start time."""
    context._query_start_time = time.time()


@event.listens_for(Engine, "after_cursor_execute")
def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Log query execution time and analyze slow queries."""
    total = time.time() - context._query_start_time
    
    query_stats["total_queries"] += 1
    query_stats["query_times"].append(total)
    
    # Track slow queries (>100ms)
    if total > 0.1:
        slow_query = {
            "statement": statement[:200],  # Truncate long queries
            "parameters": str(parameters)[:200] if parameters else None,
            "duration": total,
            "timestamp": time.time()
        }
        query_stats["slow_queries"].append(slow_query)
        
        # Keep only last 100 slow queries
        if len(query_stats["slow_queries"]) > 100:
            query_stats["slow_queries"] = query_stats["slow_queries"][-100:]
        
        logger.warning(f"Slow query detected: {total:.3f}s - {statement[:100]}")
    
    # Track queries by table
    statement_lower = statement.lower()
    for table in ["users", "saved_charts", "chat_conversations", "chat_messages", "credit_transactions"]:
        if table in statement_lower:
            if table not in query_stats["queries_by_table"]:
                query_stats["queries_by_table"][table] = {
                    "count": 0,
                    "total_time": 0,
                    "avg_time": 0
                }
            query_stats["queries_by_table"][table]["count"] += 1
            query_stats["queries_by_table"][table]["total_time"] += total
            query_stats["queries_by_table"][table]["avg_time"] = (
                query_stats["queries_by_table"][table]["total_time"] /
                query_stats["queries_by_table"][table]["count"]
            )


@contextmanager
def query_timer(description: str = "Query"):
    """Context manager for timing queries."""
    start = time.time()
    try:
        yield
    finally:
        duration = time.time() - start
        if duration > 0.1:
            logger.warning(f"{description} took {duration:.3f}s")


def get_query_statistics() -> Dict[str, Any]:
    """Get query performance statistics."""
    query_times = query_stats["query_times"]
    
    if not query_times:
        return {
            "total_queries": 0,
            "avg_time": 0,
            "min_time": 0,
            "max_time": 0,
            "p95_time": 0,
            "p99_time": 0,
            "slow_queries_count": 0,
            "queries_by_table": {}
        }
    
    sorted_times = sorted(query_times)
    n = len(sorted_times)
    
    return {
        "total_queries": query_stats["total_queries"],
        "avg_time": sum(query_times) / n,
        "min_time": min(query_times),
        "max_time": max(query_times),
        "p95_time": sorted_times[int(n * 0.95)] if n > 0 else 0,
        "p99_time": sorted_times[int(n * 0.99)] if n > 0 else 0,
        "slow_queries_count": len(query_stats["slow_queries"]),
        "slow_queries": query_stats["slow_queries"][-10:],  # Last 10 slow queries
        "queries_by_table": query_stats["queries_by_table"]
    }


def reset_query_statistics():
    """Reset query statistics."""
    global query_stats
    query_stats = {
        "total_queries": 0,
        "slow_queries": [],
        "query_times": [],
        "queries_by_table": {}
    }
    logger.info("Query statistics reset")


def analyze_query_plan(db: Session, query_str: str) -> Dict[str, Any]:
    """Analyze query execution plan (PostgreSQL only)."""
    try:
        # PostgreSQL EXPLAIN ANALYZE
        explain_query = f"EXPLAIN ANALYZE {query_str}"
        result = db.execute(explain_query)
        plan = "\n".join([row[0] for row in result])
        
        return {
            "query": query_str,
            "plan": plan,
            "analyzed": True
        }
    except Exception as e:
        logger.error(f"Error analyzing query plan: {str(e)}")
        return {
            "query": query_str,
            "plan": None,
            "analyzed": False,
            "error": str(e)
        }

