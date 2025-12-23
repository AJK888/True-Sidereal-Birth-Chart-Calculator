"""
Advanced Charts API Routes

Endpoints for advanced astrology features:
- Synastry (relationship compatibility)
- Composite charts
- Transit calculations
- Progressed charts
- Solar return charts
"""

import logging
import pendulum
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

from app.core.logging_config import setup_logger
from app.core.exceptions import ChartCalculationError, GeocodingError, ValidationError
from app.services.synastry_service import calculate_synastry
from app.services.composite_service import calculate_composite
from app.services.transit_service import calculate_current_transits
from app.services.progression_service import calculate_progressed_chart
from app.services.solar_return_service import calculate_solar_return_chart
from database import get_db, User, SavedChart
from auth import get_current_user_optional
from natal_chart import NatalChart
from app.utils.validators import validate_chart_request_data

logger = setup_logger(__name__)

# Create router
router = APIRouter(prefix="/api/v1", tags=["advanced-charts"])

# Import centralized configuration
from app.config import OPENCAGE_KEY
import requests


# Pydantic Models
class SynastryRequest(BaseModel):
    """Request model for synastry calculation."""
    chart1: Dict[str, Any] = Field(..., description="First chart data")
    chart2: Dict[str, Any] = Field(..., description="Second chart data")
    system: str = Field("sidereal", description="Zodiac system: 'sidereal' or 'tropical'")
    
    @validator('system')
    def validate_system(cls, v):
        if v not in ['sidereal', 'tropical']:
            raise ValueError("System must be 'sidereal' or 'tropical'")
        return v
    
    @validator('chart1', 'chart2')
    def validate_chart_data(cls, v):
        required_fields = ['full_name', 'year', 'month', 'day', 'hour', 'minute', 'location']
        for field in required_fields:
            if field not in v:
                raise ValueError(f"Missing required field: {field}")
        return v


class ChartDataRequest(BaseModel):
    """Request model for chart data (used in synastry)."""
    full_name: str
    year: int
    month: int
    day: int
    hour: int
    minute: int
    location: str
    unknown_time: bool = False


def geocode_location(location: str) -> tuple:
    """
    Geocode a location string to get latitude, longitude, and timezone.
    
    Args:
        location: Location string (e.g., "New York, NY, USA")
    
    Returns:
        Tuple of (latitude, longitude, timezone_name)
    """
    try:
        url = "https://api.opencagedata.com/geocode/v1/json"
        params = {
            "q": location,
            "key": OPENCAGE_KEY,
            "limit": 1,
            "no_annotations": 1
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("results"):
            raise GeocodingError(f"Could not find location: {location}")
        
        result = data["results"][0]
        geometry = result["geometry"]
        lat = geometry["lat"]
        lng = geometry["lng"]
        
        # Get timezone
        components = result.get("components", {})
        timezone_name = result.get("annotations", {}).get("timezone", {}).get("name")
        
        if not timezone_name:
            # Try to infer from country code
            country_code = components.get("country_code", "").upper()
            # Default timezones by country (simplified)
            timezone_name = "UTC"  # Default fallback
        
        return lat, lng, timezone_name
    
    except requests.RequestException as e:
        logger.error(f"Geocoding error: {e}")
        raise GeocodingError(f"Failed to geocode location: {location}")


def create_chart_from_data(chart_data: Dict[str, Any]) -> NatalChart:
    """
    Create a NatalChart instance from chart data dictionary.
    
    Args:
        chart_data: Dictionary with chart information
    
    Returns:
        NatalChart instance
    """
    try:
        # Validate chart data
        validate_chart_request_data(
            chart_data.get("full_name", ""),
            chart_data.get("year", 0),
            chart_data.get("month", 0),
            chart_data.get("day", 0),
            chart_data.get("hour", 0),
            chart_data.get("minute", 0),
            chart_data.get("location", "")
        )
        
        # Geocode location
        lat, lng, timezone_name = geocode_location(chart_data["location"])
        
        if not timezone_name:
            timezone_name = "UTC"
        
        # Convert to UTC
        local_time = pendulum.datetime(
            chart_data["year"],
            chart_data["month"],
            chart_data["day"],
            chart_data["hour"],
            chart_data["minute"],
            tz=timezone_name
        )
        utc_time = local_time.in_timezone('UTC')
        
        # Create and calculate chart
        chart = NatalChart(
            name=chart_data["full_name"],
            year=utc_time.year,
            month=utc_time.month,
            day=utc_time.day,
            hour=utc_time.hour,
            minute=utc_time.minute,
            latitude=lat,
            longitude=lng
        )
        chart.calculate_chart(unknown_time=chart_data.get("unknown_time", False))
        
        return chart
    
    except Exception as e:
        logger.error(f"Error creating chart: {e}", exc_info=True)
        raise ChartCalculationError(f"Failed to create chart: {str(e)}")


@router.post(
    "/charts/synastry",
    summary="Calculate Synastry",
    description="""
    Calculate synastry (relationship compatibility) between two birth charts.
    
    Synastry compares:
    - Planetary aspects between the two charts
    - House overlays (where one person's planets fall in the other's houses)
    - Overall compatibility score
    
    **Rate Limit**: 50 requests per day per IP address
    """,
    response_description="Complete synastry analysis",
    tags=["advanced-charts"]
)
async def calculate_synastry_endpoint(
    request: Request,
    data: SynastryRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Calculate synastry between two charts.
    """
    try:
        # Create charts from data
        chart1 = create_chart_from_data(data.chart1)
        chart2 = create_chart_from_data(data.chart2)
        
        # Calculate synastry
        synastry_result = calculate_synastry(chart1, chart2, system=data.system)
        
        return {
            "status": "success",
            "synastry": synastry_result
        }
    
    except GeocodingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ChartCalculationError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error calculating synastry: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to calculate synastry: {str(e)}")


class CompositeRequest(BaseModel):
    """Request model for composite chart calculation."""
    chart1: Dict[str, Any] = Field(..., description="First chart data")
    chart2: Dict[str, Any] = Field(..., description="Second chart data")
    system: str = Field("sidereal", description="Zodiac system: 'sidereal' or 'tropical'")
    
    @validator('system')
    def validate_system(cls, v):
        if v not in ['sidereal', 'tropical']:
            raise ValueError("System must be 'sidereal' or 'tropical'")
        return v
    
    @validator('chart1', 'chart2')
    def validate_chart_data(cls, v):
        required_fields = ['full_name', 'year', 'month', 'day', 'hour', 'minute', 'location']
        for field in required_fields:
            if field not in v:
                raise ValueError(f"Missing required field: {field}")
        return v


@router.post(
    "/charts/composite",
    summary="Calculate Composite Chart",
    description="""
    Calculate a composite chart - a midpoint-based chart representing the relationship
    between two people as a single entity.
    
    **Rate Limit**: 50 requests per day per IP address
    """,
    response_description="Complete composite chart analysis",
    tags=["advanced-charts"]
)
async def calculate_composite_endpoint(
    request: Request,
    data: CompositeRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Calculate composite chart between two charts.
    """
    try:
        # Create charts from data
        chart1 = create_chart_from_data(data.chart1)
        chart2 = create_chart_from_data(data.chart2)
        
        # Calculate composite
        composite_result = calculate_composite(chart1, chart2, system=data.system)
        
        return {
            "status": "success",
            "composite": composite_result
        }
    
    except GeocodingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ChartCalculationError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error calculating composite chart: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to calculate composite chart: {str(e)}")


class TransitRequest(BaseModel):
    """Request model for transit calculation."""
    chart_data: Dict[str, Any] = Field(..., description="Natal chart data")
    target_date: Optional[str] = Field(None, description="Date to calculate transits for (ISO format, defaults to now)")
    system: str = Field("sidereal", description="Zodiac system: 'sidereal' or 'tropical'")
    
    @validator('system')
    def validate_system(cls, v):
        if v not in ['sidereal', 'tropical']:
            raise ValueError("System must be 'sidereal' or 'tropical'")
        return v
    
    @validator('chart_data')
    def validate_chart_data(cls, v):
        required_fields = ['full_name', 'year', 'month', 'day', 'hour', 'minute', 'location']
        for field in required_fields:
            if field not in v:
                raise ValueError(f"Missing required field: {field}")
        return v


@router.post(
    "/charts/transits",
    summary="Calculate Transits",
    description="""
    Calculate current planetary transits to a natal chart.
    
    Shows where transiting planets are making aspects to natal planets.
    
    **Rate Limit**: 100 requests per day per IP address
    """,
    response_description="Transit analysis",
    tags=["advanced-charts"]
)
async def calculate_transits_endpoint(
    request: Request,
    data: TransitRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Calculate transits to a natal chart.
    """
    try:
        # Create natal chart from data
        natal_chart = create_chart_from_data(data.chart_data)
        
        # Parse target date if provided
        target_date = None
        if data.target_date:
            try:
                target_date = datetime.fromisoformat(data.target_date.replace('Z', '+00:00'))
            except ValueError:
                raise ValidationError("Invalid date format. Use ISO format (e.g., 2025-01-22T12:00:00Z)")
        
        # Calculate transits
        transit_result = calculate_current_transits(natal_chart, target_date, system=data.system)
        
        return {
            "status": "success",
            "transits": transit_result
        }
    
    except GeocodingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ChartCalculationError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error calculating transits: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to calculate transits: {str(e)}")


@router.get(
    "/charts/{chart_hash}/transits",
    summary="Get Transits for Saved Chart",
    description="""
    Get current transits for a chart by its hash.
    
    This endpoint allows you to get transits for a previously calculated chart
    without needing to recalculate the natal chart.
    
    **Rate Limit**: 100 requests per day per IP address
    """,
    response_description="Transit analysis",
    tags=["advanced-charts"]
)
async def get_transits_by_hash_endpoint(
    request: Request,
    chart_hash: str,
    target_date: Optional[str] = None,
    system: str = "sidereal",
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get transits for a chart by hash.
    """
    try:
        # Validate system
        if system not in ['sidereal', 'tropical']:
            raise ValidationError("System must be 'sidereal' or 'tropical'")
        
        # Try to find saved chart by hash
        saved_chart = db.query(SavedChart).filter(
            SavedChart.chart_data_json.contains(f'"chart_hash":"{chart_hash}"')
        ).first()
        
        if not saved_chart:
            raise HTTPException(status_code=404, detail="Chart not found")
        
        # Parse chart data from JSON
        import json
        chart_data_json = json.loads(saved_chart.chart_data_json)
        
        # Extract birth data
        birth_data = chart_data_json.get("birth_data", {})
        if not birth_data:
            raise HTTPException(status_code=400, detail="Invalid chart data format")
        
        # Create chart data dict
        chart_data = {
            "full_name": saved_chart.chart_name,
            "year": saved_chart.birth_year,
            "month": saved_chart.birth_month,
            "day": saved_chart.birth_day,
            "hour": saved_chart.birth_hour,
            "minute": saved_chart.birth_minute,
            "location": saved_chart.birth_location,
            "unknown_time": saved_chart.unknown_time
        }
        
        # Create natal chart
        natal_chart = create_chart_from_data(chart_data)
        
        # Parse target date if provided
        target_date_obj = None
        if target_date:
            try:
                target_date_obj = datetime.fromisoformat(target_date.replace('Z', '+00:00'))
            except ValueError:
                raise ValidationError("Invalid date format. Use ISO format (e.g., 2025-01-22T12:00:00Z)")
        
        # Calculate transits
        transit_result = calculate_current_transits(natal_chart, target_date_obj, system=system)
        
        return {
            "status": "success",
            "chart_hash": chart_hash,
            "transits": transit_result
        }
    
    except HTTPException:
        raise
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting transits: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get transits: {str(e)}")


class ProgressedRequest(BaseModel):
    """Request model for progressed chart calculation."""
    chart_data: Dict[str, Any] = Field(..., description="Natal chart data")
    target_date: str = Field(..., description="Date to calculate progressed chart for (ISO format)")
    system: str = Field("sidereal", description="Zodiac system: 'sidereal' or 'tropical'")
    
    @validator('system')
    def validate_system(cls, v):
        if v not in ['sidereal', 'tropical']:
            raise ValueError("System must be 'sidereal' or 'tropical'")
        return v


@router.post(
    "/charts/progressed",
    summary="Calculate Progressed Chart",
    description="""
    Calculate a progressed chart using the day-for-year method.
    
    Each day after birth represents one year of life in the progressed chart.
    
    **Rate Limit**: 50 requests per day per IP address
    """,
    response_description="Progressed chart analysis",
    tags=["advanced-charts"]
)
async def calculate_progressed_endpoint(
    request: Request,
    data: ProgressedRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Calculate progressed chart.
    """
    try:
        # Create natal chart
        natal_chart = create_chart_from_data(data.chart_data)
        
        # Parse target date
        try:
            target_date = datetime.fromisoformat(data.target_date.replace('Z', '+00:00'))
        except ValueError:
            raise ValidationError("Invalid date format. Use ISO format (e.g., 2025-01-22T12:00:00Z)")
        
        # Calculate progressed chart
        progressed_result = calculate_progressed_chart(natal_chart, target_date, system=data.system)
        
        return {
            "status": "success",
            "progressed": progressed_result
        }
    
    except GeocodingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ChartCalculationError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error calculating progressed chart: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to calculate progressed chart: {str(e)}")


class SolarReturnRequest(BaseModel):
    """Request model for solar return chart calculation."""
    chart_data: Dict[str, Any] = Field(..., description="Natal chart data")
    target_year: int = Field(..., description="Year to calculate solar return for", ge=1900, le=2100)
    system: str = Field("sidereal", description="Zodiac system: 'sidereal' or 'tropical'")
    
    @validator('system')
    def validate_system(cls, v):
        if v not in ['sidereal', 'tropical']:
            raise ValueError("System must be 'sidereal' or 'tropical'")
        return v


@router.post(
    "/charts/solar-return",
    summary="Calculate Solar Return Chart",
    description="""
    Calculate a solar return chart - when the Sun returns to its natal position.
    
    Solar return charts are calculated for each year around the person's birthday.
    
    **Rate Limit**: 50 requests per day per IP address
    """,
    response_description="Solar return chart analysis",
    tags=["advanced-charts"]
)
async def calculate_solar_return_endpoint(
    request: Request,
    data: SolarReturnRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Calculate solar return chart.
    """
    try:
        # Create natal chart
        natal_chart = create_chart_from_data(data.chart_data)
        
        # Calculate solar return
        solar_return_result = calculate_solar_return_chart(natal_chart, data.target_year, system=data.system)
        
        return {
            "status": "success",
            "solar_return": solar_return_result
        }
    
    except GeocodingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ChartCalculationError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error calculating solar return chart: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to calculate solar return chart: {str(e)}")

