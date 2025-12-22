"""
Unit tests for cache functionality.

Tests Redis and in-memory caching for readings and famous people queries.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import json

from app.core.cache import (
    get_reading_from_cache,
    set_reading_in_cache,
    get_famous_people_from_cache,
    set_famous_people_in_cache,
    CACHE_EXPIRY_HOURS
)


class TestReadingCache:
    """Test reading cache functionality."""
    
    def test_set_and_get_reading_in_memory(self, monkeypatch):
        """Test setting and getting reading from in-memory cache."""
        # Ensure Redis is not available
        monkeypatch.setenv("REDIS_URL", "")
        
        chart_hash = "test_chart_hash_123"
        reading = "Test reading content"
        chart_name = "Test Chart"
        
        # Set reading
        set_reading_in_cache(chart_hash, reading, chart_name)
        
        # Get reading
        cached = get_reading_from_cache(chart_hash)
        
        assert cached is not None
        assert cached["reading"] == reading
        assert cached["chart_name"] == chart_name
        assert "timestamp" in cached
    
    def test_cache_expiry(self, monkeypatch):
        """Test that expired cache entries are not returned."""
        monkeypatch.setenv("REDIS_URL", "")
        
        chart_hash = "expired_chart_hash"
        reading = "Expired reading"
        chart_name = "Expired Chart"
        
        # Set reading
        set_reading_in_cache(chart_hash, reading, chart_name)
        
        # Manually expire the cache by setting old timestamp
        from app.core.cache import _reading_cache
        _reading_cache[chart_hash]["timestamp"] = datetime.now() - timedelta(hours=CACHE_EXPIRY_HOURS + 1)
        
        # Try to get expired reading
        cached = get_reading_from_cache(chart_hash)
        
        assert cached is None
    
    @patch('app.core.cache._redis_client')
    def test_redis_cache_priority(self, mock_redis):
        """Test that Redis cache is used when available."""
        # Mock Redis client
        mock_redis_client = MagicMock()
        mock_redis_client.get.return_value = json.dumps({
            "reading": "Redis cached reading",
            "timestamp": datetime.now().isoformat(),
            "chart_name": "Redis Chart"
        })
        mock_redis.return_value = mock_redis_client
        
        # Set Redis client
        import app.core.cache as cache_module
        cache_module._redis_client = mock_redis_client
        
        chart_hash = "redis_test_hash"
        cached = get_reading_from_cache(chart_hash)
        
        assert cached is not None
        assert cached["reading"] == "Redis cached reading"
        mock_redis_client.get.assert_called_once()


class TestFamousPeopleCache:
    """Test famous people cache functionality."""
    
    def test_set_and_get_famous_people_in_memory(self, monkeypatch):
        """Test setting and getting famous people matches from in-memory cache."""
        monkeypatch.setenv("REDIS_URL", "")
        
        cache_key = "test_chart_hash:10"
        matches = {
            "matches": [
                {"name": "Test Person", "similarity_score": 85.5}
            ],
            "total_compared": 100,
            "message": "Found 1 similar famous people"
        }
        
        # Set cache
        set_famous_people_in_cache(cache_key, matches)
        
        # Get from cache
        cached = get_famous_people_from_cache(cache_key)
        
        assert cached is not None
        assert cached["matches"] == matches
        assert "timestamp" in cached
    
    def test_famous_people_cache_expiry(self, monkeypatch):
        """Test that expired famous people cache entries are not returned."""
        monkeypatch.setenv("REDIS_URL", "")
        
        cache_key = "expired_famous_hash:10"
        matches = {"matches": [], "total_compared": 0}
        
        # Set cache
        set_famous_people_in_cache(cache_key, matches)
        
        # Manually expire
        from app.core.cache import _famous_people_cache
        _famous_people_cache[cache_key]["timestamp"] = datetime.now() - timedelta(hours=CACHE_EXPIRY_HOURS + 1)
        
        # Try to get expired cache
        cached = get_famous_people_from_cache(cache_key)
        
        assert cached is None
    
    @patch('app.core.cache._redis_client')
    def test_famous_people_redis_cache(self, mock_redis):
        """Test famous people cache with Redis."""
        # Mock Redis client
        mock_redis_client = MagicMock()
        mock_redis_client.get.return_value = json.dumps({
            "matches": {
                "matches": [{"name": "Redis Person", "similarity_score": 90.0}],
                "total_compared": 50
            },
            "timestamp": datetime.now().isoformat()
        })
        
        import app.core.cache as cache_module
        cache_module._redis_client = mock_redis_client
        
        cache_key = "redis_famous_hash:10"
        cached = get_famous_people_from_cache(cache_key)
        
        assert cached is not None
        assert "matches" in cached["matches"]
        mock_redis_client.get.assert_called_once()

