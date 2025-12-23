"""
Event Broadcasting System

Provides a simple event broadcasting system for real-time updates via WebSockets.
"""

from typing import Dict, Set, Callable, Any, Optional
from enum import Enum
import asyncio
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Event types for broadcasting."""
    
    # Batch processing events
    BATCH_JOB_STARTED = "batch.job.started"
    BATCH_JOB_PROGRESS = "batch.job.progress"
    BATCH_JOB_COMPLETED = "batch.job.completed"
    BATCH_JOB_FAILED = "batch.job.failed"
    
    # Reading generation events
    READING_STARTED = "reading.started"
    READING_PROGRESS = "reading.progress"
    READING_COMPLETED = "reading.completed"
    READING_FAILED = "reading.failed"
    
    # Chart calculation events
    CHART_CALCULATED = "chart.calculated"
    
    # User events
    USER_REGISTERED = "user.registered"
    USER_LOGGED_IN = "user.logged_in"
    
    # System events
    SYSTEM_HEALTH_CHECK = "system.health_check"
    SYSTEM_WARNING = "system.warning"
    SYSTEM_ERROR = "system.error"


class EventBroadcaster:
    """
    Simple event broadcaster for WebSocket connections.
    
    Manages WebSocket connections and broadcasts events to subscribed clients.
    """
    
    def __init__(self):
        """Initialize the event broadcaster."""
        self._connections: Dict[str, Set[Any]] = {}  # event_type -> set of websockets
        self._user_connections: Dict[int, Set[Any]] = {}  # user_id -> set of websockets
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: Any, event_types: Optional[Set[EventType]] = None, user_id: Optional[int] = None):
        """
        Register a WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            event_types: Set of event types to subscribe to (None = all)
            user_id: Optional user ID for user-specific events
        """
        async with self._lock:
            if event_types is None:
                event_types = set(EventType)
            
            for event_type in event_types:
                if event_type not in self._connections:
                    self._connections[event_type] = set()
                self._connections[event_type].add(websocket)
            
            if user_id is not None:
                if user_id not in self._user_connections:
                    self._user_connections[user_id] = set()
                self._user_connections[user_id].add(websocket)
        
        logger.info(f"WebSocket connected: event_types={len(event_types)}, user_id={user_id}")
    
    async def disconnect(self, websocket: Any):
        """
        Unregister a WebSocket connection.
        
        Args:
            websocket: WebSocket connection to remove
        """
        async with self._lock:
            # Remove from event type connections
            for event_type, connections in self._connections.items():
                connections.discard(websocket)
            
            # Remove from user connections
            for user_id, connections in self._user_connections.items():
                connections.discard(websocket)
        
        logger.info("WebSocket disconnected")
    
    async def broadcast(self, event_type: EventType, data: Dict[str, Any], user_id: Optional[int] = None):
        """
        Broadcast an event to all subscribed connections.
        
        Args:
            event_type: Type of event
            data: Event data
            user_id: Optional user ID for user-specific events
        """
        event = {
            "type": event_type.value,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        message = json.dumps(event)
        
        # Get connections to notify
        connections_to_notify = set()
        
        async with self._lock:
            # Add connections subscribed to this event type
            if event_type in self._connections:
                connections_to_notify.update(self._connections[event_type])
            
            # Add user-specific connections if user_id provided
            if user_id is not None and user_id in self._user_connections:
                connections_to_notify.update(self._user_connections[user_id])
        
        # Send to all connections
        disconnected = set()
        for connection in connections_to_notify:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.warning(f"Failed to send event to WebSocket: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected connections
        if disconnected:
            async with self._lock:
                for event_type, connections in self._connections.items():
                    connections -= disconnected
                for user_id, connections in self._user_connections.items():
                    connections -= disconnected
        
        logger.debug(f"Broadcasted event {event_type.value} to {len(connections_to_notify)} connections")
    
    async def send_to_user(self, user_id: int, event_type: EventType, data: Dict[str, Any]):
        """
        Send an event to a specific user's connections.
        
        Args:
            user_id: User ID
            event_type: Type of event
            data: Event data
        """
        await self.broadcast(event_type, data, user_id=user_id)
    
    def get_connection_count(self) -> Dict[str, int]:
        """
        Get connection statistics.
        
        Returns:
            Dictionary with connection counts
        """
        return {
            "total_event_subscriptions": sum(len(conns) for conns in self._connections.values()),
            "total_user_connections": sum(len(conns) for conns in self._user_connections.values()),
            "event_types": {et.value: len(conns) for et, conns in self._connections.items()}
        }


# Global event broadcaster instance
event_broadcaster = EventBroadcaster()

