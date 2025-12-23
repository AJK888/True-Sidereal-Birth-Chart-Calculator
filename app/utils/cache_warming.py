"""
Cache Warming Utilities

Strategies for pre-populating cache with popular or frequently accessed data.
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from database import get_db, SavedChart, User, FamousPerson
from app.core.advanced_cache import get_from_cache, set_in_cache
from app.core.cache import get_reading_from_cache, set_reading_in_cache, get_famous_people_from_cache, set_famous_people_in_cache
from app.services.chart_service import generate_chart_hash

logger = logging.getLogger(__name__)


class CacheWarmingStrategy:
    """Base class for cache warming strategies."""
    
    def __init__(self, name: str, priority: int = 0):
        """
        Initialize cache warming strategy.
        
        Args:
            name: Strategy name
            priority: Priority (higher = more important)
        """
        self.name = name
        self.priority = priority
    
    async def warm(self) -> Dict[str, Any]:
        """
        Execute cache warming strategy.
        
        Returns:
            Dictionary with warming results
        """
        raise NotImplementedError


class PopularChartsStrategy(CacheWarmingStrategy):
    """Warm cache with popular/recently accessed charts."""
    
    def __init__(self, limit: int = 50):
        """
        Initialize popular charts warming strategy.
        
        Args:
            limit: Maximum number of charts to warm
        """
        super().__init__("popular_charts", priority=3)
        self.limit = limit
    
    async def warm(self) -> Dict[str, Any]:
        """Warm cache with popular charts."""
        db = next(get_db())
        try:
            # Get recently created charts (popular)
            recent_charts = db.query(SavedChart)\
                .order_by(SavedChart.created_at.desc())\
                .limit(self.limit)\
                .all()
            
            warmed = 0
            skipped = 0
            
            for chart in recent_charts:
                if not chart.chart_data_json:
                    skipped += 1
                    continue
                
                # Generate cache key
                chart_hash = generate_chart_hash(
                    chart.birth_year,
                    chart.birth_month,
                    chart.birth_day,
                    chart.birth_hour,
                    chart.birth_minute,
                    chart.birth_location
                )
                
                # Check if already cached
                cached = get_from_cache(f"chart:{chart_hash}")
                if cached:
                    skipped += 1
                    continue
                
                # Cache chart data
                try:
                    import json
                    chart_data = json.loads(chart.chart_data_json)
                    set_in_cache(f"chart:{chart_hash}", chart_data, expiry_hours=24)
                    warmed += 1
                except Exception as e:
                    logger.warning(f"Failed to warm chart {chart.id}: {e}")
                    skipped += 1
            
            return {
                "strategy": self.name,
                "warmed": warmed,
                "skipped": skipped,
                "total": len(recent_charts)
            }
        finally:
            db.close()


class PopularReadingsStrategy(CacheWarmingStrategy):
    """Warm cache with popular readings."""
    
    def __init__(self, limit: int = 20):
        """
        Initialize popular readings warming strategy.
        
        Args:
            limit: Maximum number of readings to warm
        """
        super().__init__("popular_readings", priority=2)
        self.limit = limit
    
    async def warm(self) -> Dict[str, Any]:
        """Warm cache with popular readings."""
        db = next(get_db())
        try:
            # Get charts with readings
            charts_with_readings = db.query(SavedChart)\
                .filter(SavedChart.ai_reading.isnot(None))\
                .order_by(SavedChart.created_at.desc())\
                .limit(self.limit)\
                .all()
            
            warmed = 0
            skipped = 0
            
            for chart in charts_with_readings:
                if not chart.chart_data_json or not chart.ai_reading:
                    skipped += 1
                    continue
                
                # Generate cache key
                chart_hash = generate_chart_hash(
                    chart.birth_year,
                    chart.birth_month,
                    chart.birth_day,
                    chart.birth_hour,
                    chart.birth_minute,
                    chart.birth_location
                )
                
                # Check if already cached
                cached = get_reading_from_cache(chart_hash)
                if cached:
                    skipped += 1
                    continue
                
                # Cache reading
                try:
                    set_reading_in_cache(chart_hash, chart.ai_reading)
                    warmed += 1
                except Exception as e:
                    logger.warning(f"Failed to warm reading for chart {chart.id}: {e}")
                    skipped += 1
            
            return {
                "strategy": self.name,
                "warmed": warmed,
                "skipped": skipped,
                "total": len(charts_with_readings)
            }
        finally:
            db.close()


class FamousPeopleStrategy(CacheWarmingStrategy):
    """Warm cache with popular famous people data."""
    
    def __init__(self, limit: int = 100):
        """
        Initialize famous people warming strategy.
        
        Args:
            limit: Maximum number of famous people to warm
        """
        super().__init__("famous_people", priority=1)
        self.limit = limit
    
    async def warm(self) -> Dict[str, Any]:
        """Warm cache with famous people data."""
        db = next(get_db())
        try:
            # Get popular famous people (by page views)
            popular_people = db.query(FamousPerson)\
                .filter(FamousPerson.page_views.isnot(None))\
                .order_by(FamousPerson.page_views.desc())\
                .limit(self.limit)\
                .all()
            
            warmed = 0
            skipped = 0
            
            for person in popular_people:
                if not person.chart_data_json:
                    skipped += 1
                    continue
                
                # Generate a simple cache key (using name for now)
                cache_key = f"famous_person:{person.id}"
                
                # Check if already cached
                cached = get_from_cache(cache_key)
                if cached:
                    skipped += 1
                    continue
                
                # Cache famous person data
                try:
                    import json
                    chart_data = json.loads(person.chart_data_json)
                    set_in_cache(cache_key, chart_data, expiry_hours=168)  # 1 week
                    warmed += 1
                except Exception as e:
                    logger.warning(f"Failed to warm famous person {person.id}: {e}")
                    skipped += 1
            
            return {
                "strategy": self.name,
                "warmed": warmed,
                "skipped": skipped,
                "total": len(popular_people)
            }
        finally:
            db.close()


class CacheWarmer:
    """Manages cache warming strategies."""
    
    def __init__(self):
        """Initialize cache warmer."""
        self.strategies: List[CacheWarmingStrategy] = []
    
    def add_strategy(self, strategy: CacheWarmingStrategy):
        """
        Add a cache warming strategy.
        
        Args:
            strategy: Cache warming strategy
        """
        self.strategies.append(strategy)
        # Sort by priority (higher first)
        self.strategies.sort(key=lambda s: s.priority, reverse=True)
    
    async def warm_all(self) -> Dict[str, Any]:
        """
        Execute all cache warming strategies.
        
        Returns:
            Dictionary with warming results
        """
        results = {
            "started_at": datetime.utcnow().isoformat(),
            "strategies": [],
            "total_warmed": 0,
            "total_skipped": 0
        }
        
        for strategy in self.strategies:
            try:
                logger.info(f"Executing cache warming strategy: {strategy.name}")
                result = await strategy.warm()
                results["strategies"].append(result)
                results["total_warmed"] += result.get("warmed", 0)
                results["total_skipped"] += result.get("skipped", 0)
            except Exception as e:
                logger.error(f"Cache warming strategy {strategy.name} failed: {e}", exc_info=True)
                results["strategies"].append({
                    "strategy": strategy.name,
                    "error": str(e),
                    "warmed": 0,
                    "skipped": 0
                })
        
        results["completed_at"] = datetime.utcnow().isoformat()
        results["duration_seconds"] = (
            datetime.fromisoformat(results["completed_at"]) -
            datetime.fromisoformat(results["started_at"])
        ).total_seconds()
        
        logger.info(
            f"Cache warming complete: {results['total_warmed']} items warmed, "
            f"{results['total_skipped']} skipped"
        )
        
        return results
    
    async def warm_selective(self, strategy_names: List[str]) -> Dict[str, Any]:
        """
        Execute specific cache warming strategies.
        
        Args:
            strategy_names: List of strategy names to execute
        
        Returns:
            Dictionary with warming results
        """
        results = {
            "started_at": datetime.utcnow().isoformat(),
            "strategies": [],
            "total_warmed": 0,
            "total_skipped": 0
        }
        
        strategies_to_run = [s for s in self.strategies if s.name in strategy_names]
        
        for strategy in strategies_to_run:
            try:
                logger.info(f"Executing cache warming strategy: {strategy.name}")
                result = await strategy.warm()
                results["strategies"].append(result)
                results["total_warmed"] += result.get("warmed", 0)
                results["total_skipped"] += result.get("skipped", 0)
            except Exception as e:
                logger.error(f"Cache warming strategy {strategy.name} failed: {e}", exc_info=True)
                results["strategies"].append({
                    "strategy": strategy.name,
                    "error": str(e),
                    "warmed": 0,
                    "skipped": 0
                })
        
        results["completed_at"] = datetime.utcnow().isoformat()
        results["duration_seconds"] = (
            datetime.fromisoformat(results["completed_at"]) -
            datetime.fromisoformat(results["started_at"])
        ).total_seconds()
        
        return results


# Global cache warmer instance
cache_warmer = CacheWarmer()

# Register default strategies
cache_warmer.add_strategy(PopularChartsStrategy(limit=50))
cache_warmer.add_strategy(PopularReadingsStrategy(limit=20))
cache_warmer.add_strategy(FamousPeopleStrategy(limit=100))

