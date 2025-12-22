"""
Shared cache for the application.

In-memory cache for storing completed readings and other temporary data.
"""

from typing import Dict, Any

# Reading cache for frontend polling
# Key: chart_hash, Value: {reading, timestamp, chart_name}
reading_cache: Dict[str, Dict[str, Any]] = {}
CACHE_EXPIRY_HOURS = 24  # Readings expire after 24 hours

