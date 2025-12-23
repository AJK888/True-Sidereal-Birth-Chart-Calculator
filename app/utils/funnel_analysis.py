"""
Conversion Funnel Analysis

Analyzes user conversion funnels and identifies drop-off points.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class ConversionFunnel:
    """Analyzes conversion funnels."""
    
    def __init__(self, steps: List[str]):
        """
        Initialize funnel with steps.
        
        Args:
            steps: List of funnel step names in order
        """
        self.steps = steps
        self.step_counts = defaultdict(int)
        self.user_journeys = defaultdict(list)
        self.drop_offs = defaultdict(int)
    
    def track_step(self, user_id: Optional[int], session_id: str, step: str):
        """
        Track a user reaching a funnel step.
        
        Args:
            user_id: Optional user ID
            session_id: Session ID
            step: Funnel step name
        """
        if step not in self.steps:
            logger.warning(f"Unknown funnel step: {step}")
            return
        
        self.step_counts[step] += 1
        self.user_journeys[session_id].append({
            "step": step,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id
        })
    
    def analyze_funnel(self) -> Dict[str, Any]:
        """
        Analyze the conversion funnel.
        
        Returns:
            Dictionary with funnel analysis
        """
        if not self.steps:
            return {"error": "No funnel steps defined"}
        
        # Calculate conversion rates
        conversions = []
        total_at_start = self.step_counts.get(self.steps[0], 0)
        
        for i, step in enumerate(self.steps):
            count = self.step_counts.get(step, 0)
            
            if i == 0:
                conversion_rate = 100.0  # First step is 100%
            else:
                conversion_rate = (count / total_at_start * 100) if total_at_start > 0 else 0
            
            drop_off = 0
            if i > 0:
                prev_count = self.step_counts.get(self.steps[i-1], 0)
                if prev_count > 0:
                    drop_off = ((prev_count - count) / prev_count * 100)
            
            conversions.append({
                "step": step,
                "count": count,
                "conversion_rate": round(conversion_rate, 2),
                "drop_off_rate": round(drop_off, 2) if i > 0 else 0
            })
        
        # Identify biggest drop-offs
        biggest_drop_offs = sorted(
            [(i, conversions[i]["drop_off_rate"]) for i in range(1, len(conversions))],
            key=lambda x: x[1],
            reverse=True
        )[:3]
        
        return {
            "funnel_steps": conversions,
            "total_started": total_at_start,
            "total_completed": self.step_counts.get(self.steps[-1], 0),
            "overall_conversion": round(
                (self.step_counts.get(self.steps[-1], 0) / total_at_start * 100) if total_at_start > 0 else 0,
                2
            ),
            "biggest_drop_offs": [
                {
                    "from_step": self.steps[drop[0] - 1],
                    "to_step": self.steps[drop[0]],
                    "drop_off_rate": drop[1]
                }
                for drop in biggest_drop_offs
            ],
            "timestamp": datetime.utcnow().isoformat()
        }


# Predefined funnels
CHART_FUNNEL = ConversionFunnel([
    "chart.calculated",
    "chart.viewed",
    "reading.requested",
    "reading.generated",
    "chart.saved"
])

READING_FUNNEL = ConversionFunnel([
    "reading.requested",
    "reading.generated",
    "reading.viewed",
    "reading.shared"
])


def get_chart_funnel_analysis() -> Dict[str, Any]:
    """
    Get chart conversion funnel analysis.
    
    Returns:
        Funnel analysis dictionary
    """
    return CHART_FUNNEL.analyze_funnel()


def get_reading_funnel_analysis() -> Dict[str, Any]:
    """
    Get reading conversion funnel analysis.
    
    Returns:
        Funnel analysis dictionary
    """
    return READING_FUNNEL.analyze_funnel()


def track_funnel_step(funnel_name: str, session_id: str, step: str, user_id: Optional[int] = None):
    """
    Track a funnel step (convenience function).
    
    Args:
        funnel_name: Name of funnel ("chart" or "reading")
        session_id: Session ID
        step: Step name
        user_id: Optional user ID
    """
    if funnel_name == "chart":
        CHART_FUNNEL.track_step(user_id, session_id, step)
    elif funnel_name == "reading":
        READING_FUNNEL.track_step(user_id, session_id, step)
    else:
        logger.warning(f"Unknown funnel: {funnel_name}")

