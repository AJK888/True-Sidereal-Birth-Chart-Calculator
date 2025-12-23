"""
Admin API Routes

Administrative endpoints for user management, chart moderation,
system configuration, and analytics.
"""

from fastapi import APIRouter

# Create admin router (no prefix here, will be added in api.py)
router = APIRouter(tags=["admin"])

# Import sub-routers
from .users import router as users_router
from .charts import router as charts_router
from .analytics import router as analytics_router
from .system import router as system_router

# Include sub-routers (they have their own prefixes)
router.include_router(users_router)
router.include_router(charts_router)
router.include_router(analytics_router)
router.include_router(system_router)

