"""
WebSocket API Routes

Real-time communication endpoints for live updates.
"""

import json
import logging
from typing import Optional, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.websockets import WebSocketState

from app.core.logging_config import setup_logger
from app.core.events import EventBroadcaster, EventType, event_broadcaster
from database import get_db, User

logger = setup_logger(__name__)

# Create router
router = APIRouter(prefix="/ws", tags=["websocket"])


async def get_websocket_user(websocket: WebSocket, token: Optional[str] = None) -> Optional[User]:
    """
    Authenticate WebSocket connection.
    
    Args:
        websocket: WebSocket connection
        token: Optional JWT token from query parameter
    
    Returns:
        User if authenticated, None otherwise
    """
    if not token:
        return None
    
    try:
        from jose import jwt
        import os
        SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production-please-use-env-var")
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        
        if user_id:
            db = next(get_db())
            try:
                user = db.query(User).filter(User.id == int(user_id)).first()
                return user
            finally:
                db.close()
    except Exception as e:
        logger.warning(f"WebSocket authentication failed: {e}")
    
    return None


@router.websocket("")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="JWT token for authentication"),
    events: Optional[str] = Query(None, description="Comma-separated list of event types to subscribe to")
):
    """
    Main WebSocket endpoint for real-time updates.
    
    Query Parameters:
        token: Optional JWT token for authenticated connections
        events: Optional comma-separated list of event types (default: all)
    
    Example:
        ws://api.example.com/ws?token=eyJ...&events=batch.job.progress,reading.progress
    """
    await websocket.accept()
    
    # Authenticate if token provided
    user = await get_websocket_user(websocket, token)
    user_id = user.id if user else None
    
    # Parse event types
    event_types: Optional[Set[EventType]] = None
    if events:
        try:
            event_type_strings = [e.strip() for e in events.split(",")]
            event_types = {EventType(et) for et in event_type_strings if et in [e.value for e in EventType]}
        except (ValueError, KeyError) as e:
            logger.warning(f"Invalid event types: {events}, error: {e}")
            await websocket.send_json({
                "type": "error",
                "message": f"Invalid event types: {events}"
            })
            await websocket.close()
            return
    
    # Register connection
    await event_broadcaster.connect(websocket, event_types=event_types, user_id=user_id)
    
    try:
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "message": "WebSocket connection established",
            "user_id": user_id,
            "subscribed_events": [et.value for et in (event_types or set(EventType))]
        })
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages (ping/pong or commands)
                data = await websocket.receive_text()
                
                try:
                    message = json.loads(data)
                    command = message.get("command")
                    
                    if command == "ping":
                        await websocket.send_json({"type": "pong", "timestamp": message.get("timestamp")})
                    elif command == "subscribe":
                        # Subscribe to additional event types
                        new_events = message.get("events", [])
                        try:
                            new_event_types = {EventType(et) for et in new_events if et in [e.value for e in EventType]}
                            await event_broadcaster.connect(websocket, event_types=new_event_types, user_id=user_id)
                            await websocket.send_json({
                                "type": "subscribed",
                                "events": [et.value for et in new_event_types]
                            })
                        except (ValueError, KeyError) as e:
                            await websocket.send_json({
                                "type": "error",
                                "message": f"Invalid event types: {new_events}"
                            })
                    elif command == "unsubscribe":
                        # Note: Full unsubscribe not implemented, would need to track per-connection subscriptions
                        await websocket.send_json({
                            "type": "info",
                            "message": "Unsubscribe not yet implemented"
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Unknown command: {command}"
                        })
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid JSON"
                    })
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}", exc_info=True)
                try:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Internal server error"
                    })
                except:
                    pass
                break
    
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}", exc_info=True)
    finally:
        # Unregister connection
        await event_broadcaster.disconnect(websocket)


@router.websocket("/batch/{job_id}")
async def batch_job_websocket(
    websocket: WebSocket,
    job_id: str,
    token: Optional[str] = Query(None, description="JWT token for authentication")
):
    """
    WebSocket endpoint for batch job status updates.
    
    Subscribes to events for a specific batch job.
    """
    await websocket.accept()
    
    # Authenticate
    user = await get_websocket_user(websocket, token)
    if not user:
        await websocket.send_json({
            "type": "error",
            "message": "Authentication required"
        })
        await websocket.close()
        return
    
    # Subscribe to batch job events for this specific job
    event_types = {
        EventType.BATCH_JOB_STARTED,
        EventType.BATCH_JOB_PROGRESS,
        EventType.BATCH_JOB_COMPLETED,
        EventType.BATCH_JOB_FAILED
    }
    
    await event_broadcaster.connect(websocket, event_types=event_types, user_id=user.id)
    
    try:
        await websocket.send_json({
            "type": "connected",
            "message": f"Subscribed to batch job {job_id}",
            "job_id": job_id
        })
        
        # Keep connection alive
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("command") == "ping":
                    await websocket.send_json({"type": "pong"})
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Batch job WebSocket error: {e}")
                break
    
    except WebSocketDisconnect:
        pass
    finally:
        await event_broadcaster.disconnect(websocket)


@router.websocket("/reading/{chart_hash}")
async def reading_websocket(
    websocket: WebSocket,
    chart_hash: str,
    token: Optional[str] = Query(None, description="JWT token for authentication")
):
    """
    WebSocket endpoint for reading generation progress.
    
    Subscribes to events for a specific reading generation.
    """
    await websocket.accept()
    
    # Authenticate
    user = await get_websocket_user(websocket, token)
    if not user:
        await websocket.send_json({
            "type": "error",
            "message": "Authentication required"
        })
        await websocket.close()
        return
    
    # Subscribe to reading events
    event_types = {
        EventType.READING_STARTED,
        EventType.READING_PROGRESS,
        EventType.READING_COMPLETED,
        EventType.READING_FAILED
    }
    
    await event_broadcaster.connect(websocket, event_types=event_types, user_id=user.id)
    
    try:
        await websocket.send_json({
            "type": "connected",
            "message": f"Subscribed to reading {chart_hash}",
            "chart_hash": chart_hash
        })
        
        # Keep connection alive
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("command") == "ping":
                    await websocket.send_json({"type": "pong"})
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Reading WebSocket error: {e}")
                break
    
    except WebSocketDisconnect:
        pass
    finally:
        await event_broadcaster.disconnect(websocket)


@router.get("/stats")
async def websocket_stats():
    """
    Get WebSocket connection statistics.
    
    Admin-only endpoint for monitoring WebSocket connections.
    """
    stats = event_broadcaster.get_connection_count()
    return {
        "status": "success",
        "stats": stats
    }

