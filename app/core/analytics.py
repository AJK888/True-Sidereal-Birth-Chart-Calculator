"""
Analytics Tracking

Core analytics system for tracking user behavior, events, and conversion funnels.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


class EventTracker:
    """Tracks user events and behavior."""
    
    def __init__(self):
        self.events = []
        self.event_counts = defaultdict(int)
        self.user_events = defaultdict(list)
        self.session_events = defaultdict(list)
        self.max_events = 10000  # Keep last 10k events in memory
    
    def track_event(
        self,
        event_type: str,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Track a user event.
        
        Args:
            event_type: Type of event (e.g., "chart.calculated", "reading.generated")
            user_id: Optional user ID
            session_id: Optional session ID
            metadata: Optional event metadata
        """
        event = {
            "event_type": event_type,
            "user_id": user_id,
            "session_id": session_id,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.events.append(event)
        self.event_counts[event_type] += 1
        
        if user_id:
            self.user_events[user_id].append(event)
        
        if session_id:
            self.session_events[session_id].append(event)
        
        # Limit memory usage
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
    
    def get_event_counts(self, event_type: Optional[str] = None) -> Dict[str, int]:
        """
        Get event counts.
        
        Args:
            event_type: Optional specific event type
        
        Returns:
            Dictionary of event counts
        """
        if event_type:
            return {event_type: self.event_counts.get(event_type, 0)}
        return dict(self.event_counts)
    
    def get_user_events(self, user_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get events for a specific user.
        
        Args:
            user_id: User ID
            limit: Maximum number of events to return
        
        Returns:
            List of events
        """
        return self.user_events.get(user_id, [])[-limit:]
    
    def get_session_events(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get events for a specific session.
        
        Args:
            session_id: Session ID
        
        Returns:
            List of events
        """
        return self.session_events.get(session_id, [])


# Global event tracker
_event_tracker = EventTracker()


def track_event(
    event_type: str,
    user_id: Optional[int] = None,
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Track a user event (convenience function).
    
    Args:
        event_type: Type of event
        user_id: Optional user ID
        session_id: Optional session ID
        metadata: Optional event metadata
    """
    _event_tracker.track_event(event_type, user_id, session_id, metadata)


def get_event_statistics() -> Dict[str, Any]:
    """
    Get event statistics.
    
    Returns:
        Dictionary with event statistics
    """
    return {
        "total_events": len(_event_tracker.events),
        "event_counts": _event_tracker.get_event_counts(),
        "unique_users": len(_event_tracker.user_events),
        "unique_sessions": len(_event_tracker.session_events),
        "timestamp": datetime.utcnow().isoformat()
    }

