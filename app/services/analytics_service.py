"""
Analytics service for collecting and processing usage metrics.

Provides analytics collection, aggregation, and reporting capabilities.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

# In-memory analytics storage (in production, use database or analytics service)
_analytics_data: Dict[str, List[Dict[str, Any]]] = defaultdict(list)


def track_event(
    event_type: str,
    user_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Track an analytics event.
    
    Args:
        event_type: Type of event (e.g., "chart.calculated", "reading.generated")
        user_id: Optional user ID
        metadata: Optional event metadata
    """
    event = {
        "event_type": event_type,
        "user_id": user_id,
        "metadata": metadata or {},
        "timestamp": datetime.now().isoformat()
    }
    
    _analytics_data[event_type].append(event)
    
    # Keep only last 10000 events per type (in production, use proper storage)
    if len(_analytics_data[event_type]) > 10000:
        _analytics_data[event_type] = _analytics_data[event_type][-10000:]
    
    logger.debug(f"Analytics event tracked: {event_type}")


def get_event_counts(
    event_type: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> int:
    """
    Get count of events for a specific type.
    
    Args:
        event_type: Event type
        start_date: Optional start date filter
        end_date: Optional end date filter
        
    Returns:
        Event count
    """
    events = _analytics_data.get(event_type, [])
    
    if start_date or end_date:
        filtered_events = []
        for event in events:
            event_time = datetime.fromisoformat(event["timestamp"])
            if start_date and event_time < start_date:
                continue
            if end_date and event_time > end_date:
                continue
            filtered_events.append(event)
        return len(filtered_events)
    
    return len(events)


def get_user_activity(
    user_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Get user activity summary.
    
    Args:
        user_id: User ID
        start_date: Optional start date filter
        end_date: Optional end date filter
        
    Returns:
        User activity dictionary
    """
    activity = {
        "user_id": user_id,
        "total_events": 0,
        "events_by_type": defaultdict(int),
        "first_activity": None,
        "last_activity": None
    }
    
    for event_type, events in _analytics_data.items():
        for event in events:
            if event.get("user_id") == user_id:
                event_time = datetime.fromisoformat(event["timestamp"])
                
                # Apply date filters
                if start_date and event_time < start_date:
                    continue
                if end_date and event_time > end_date:
                    continue
                
                activity["total_events"] += 1
                activity["events_by_type"][event_type] += 1
                
                if not activity["first_activity"] or event_time < activity["first_activity"]:
                    activity["first_activity"] = event_time
                if not activity["last_activity"] or event_time > activity["last_activity"]:
                    activity["last_activity"] = event_time
    
    # Convert to regular dict
    activity["events_by_type"] = dict(activity["events_by_type"])
    
    return activity


def get_usage_statistics(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Get overall usage statistics.
    
    Args:
        start_date: Optional start date filter
        end_date: Optional end date filter
        
    Returns:
        Usage statistics dictionary
    """
    stats = {
        "total_events": 0,
        "events_by_type": defaultdict(int),
        "unique_users": set(),
        "events_by_day": defaultdict(int),
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None
    }
    
    for event_type, events in _analytics_data.items():
        for event in events:
            event_time = datetime.fromisoformat(event["timestamp"])
            
            # Apply date filters
            if start_date and event_time < start_date:
                continue
            if end_date and event_time > end_date:
                continue
            
            stats["total_events"] += 1
            stats["events_by_type"][event_type] += 1
            
            if event.get("user_id"):
                stats["unique_users"].add(event["user_id"])
            
            # Group by day
            day_key = event_time.date().isoformat()
            stats["events_by_day"][day_key] += 1
    
    # Convert to regular dicts
    stats["events_by_type"] = dict(stats["events_by_type"])
    stats["events_by_day"] = dict(stats["events_by_day"])
    stats["unique_users_count"] = len(stats["unique_users"])
    stats["unique_users"] = list(stats["unique_users"])[:100]  # Limit to 100 for response size
    
    return stats


def get_endpoint_metrics(
    endpoint: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Get metrics for a specific endpoint.
    
    Args:
        endpoint: Endpoint path
        start_date: Optional start date filter
        end_date: Optional end date filter
        
    Returns:
        Endpoint metrics dictionary
    """
    metrics = {
        "endpoint": endpoint,
        "total_requests": 0,
        "successful_requests": 0,
        "failed_requests": 0,
        "average_response_time": 0.0,
        "requests_by_day": defaultdict(int),
        "requests_by_hour": defaultdict(int)
    }
    
    # Filter events for this endpoint
    endpoint_events = [
        e for events in _analytics_data.values()
        for e in events
        if e.get("metadata", {}).get("endpoint") == endpoint
    ]
    
    response_times = []
    
    for event in endpoint_events:
        event_time = datetime.fromisoformat(event["timestamp"])
        
        # Apply date filters
        if start_date and event_time < start_date:
            continue
        if end_date and event_time > end_date:
            continue
        
        metrics["total_requests"] += 1
        
        metadata = event.get("metadata", {})
        if metadata.get("status_code", 200) < 400:
            metrics["successful_requests"] += 1
        else:
            metrics["failed_requests"] += 1
        
        if "response_time" in metadata:
            response_times.append(metadata["response_time"])
        
        # Group by day and hour
        day_key = event_time.date().isoformat()
        hour_key = event_time.hour
        metrics["requests_by_day"][day_key] += 1
        metrics["requests_by_hour"][hour_key] += 1
    
    # Calculate average response time
    if response_times:
        metrics["average_response_time"] = sum(response_times) / len(response_times)
    
    # Convert to regular dicts
    metrics["requests_by_day"] = dict(metrics["requests_by_day"])
    metrics["requests_by_hour"] = dict(metrics["requests_by_hour"])
    
    return metrics

