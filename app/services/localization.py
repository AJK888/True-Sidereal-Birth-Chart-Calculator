"""
Localization Service

Provides localized content, date/time formats, and regional astrology traditions.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import pendulum
from app.core.i18n import Language, DEFAULT_LANGUAGE, get_translation, get_supported_languages

logger = logging.getLogger(__name__)


# Regional date/time format preferences
DATE_FORMATS: Dict[str, Dict[str, str]] = {
    "en": {
        "date": "MM/DD/YYYY",
        "time": "HH:mm",
        "datetime": "MM/DD/YYYY HH:mm"
    },
    "es": {
        "date": "DD/MM/YYYY",
        "time": "HH:mm",
        "datetime": "DD/MM/YYYY HH:mm"
    },
    "fr": {
        "date": "DD/MM/YYYY",
        "time": "HH:mm",
        "datetime": "DD/MM/YYYY HH:mm"
    },
    "de": {
        "date": "DD.MM.YYYY",
        "time": "HH:mm",
        "datetime": "DD.MM.YYYY HH:mm"
    },
}


def format_date_localized(date: datetime, language: str = DEFAULT_LANGUAGE.value) -> str:
    """
    Format date according to locale.
    
    Args:
        date: Datetime object
        language: Language code
    
    Returns:
        Formatted date string
    """
    formats = DATE_FORMATS.get(language, DATE_FORMATS[DEFAULT_LANGUAGE.value])
    
    try:
        dt = pendulum.instance(date)
        return dt.format(formats["date"])
    except Exception:
        return date.strftime("%Y-%m-%d")


def format_time_localized(date: datetime, language: str = DEFAULT_LANGUAGE.value) -> str:
    """
    Format time according to locale.
    
    Args:
        date: Datetime object
        language: Language code
    
    Returns:
        Formatted time string
    """
    formats = DATE_FORMATS.get(language, DATE_FORMATS[DEFAULT_LANGUAGE.value])
    
    try:
        dt = pendulum.instance(date)
        return dt.format(formats["time"])
    except Exception:
        return date.strftime("%H:%M")


def get_regional_traditions(language: str = DEFAULT_LANGUAGE.value) -> Dict[str, Any]:
    """
    Get regional astrology traditions for a language/region.
    
    Args:
        language: Language code
    
    Returns:
        Dictionary with regional tradition information
    """
    traditions = {
        "en": {
            "primary_system": "Western",
            "zodiac_systems": ["Tropical", "Sidereal"],
            "house_systems": ["Placidus", "Equal", "Whole Sign"],
            "aspects": ["Conjunction", "Opposition", "Trine", "Square", "Sextile"]
        },
        "es": {
            "primary_system": "Occidental",
            "zodiac_systems": ["Tropical", "Sidereal"],
            "house_systems": ["Plácido", "Igual", "Signo Completo"],
            "aspects": ["Conjunción", "Oposición", "Trino", "Cuadratura", "Sextil"]
        },
        "fr": {
            "primary_system": "Occidental",
            "zodiac_systems": ["Tropical", "Sidereal"],
            "house_systems": ["Placidus", "Égal", "Signe Entier"],
            "aspects": ["Conjonction", "Opposition", "Trine", "Carré", "Sextile"]
        },
    }
    
    return traditions.get(language, traditions[DEFAULT_LANGUAGE.value])


def localize_chart_data(chart_data: Dict[str, Any], language: str = DEFAULT_LANGUAGE.value) -> Dict[str, Any]:
    """
    Localize chart data for a specific language.
    
    Args:
        chart_data: Chart data dictionary
        language: Language code
    
    Returns:
        Localized chart data
    """
    # Create a copy to avoid modifying original
    localized = chart_data.copy()
    
    # Translate sign names if needed
    # In production, this would translate all text content
    
    return localized


def get_localized_content(key: str, language: str = DEFAULT_LANGUAGE.value, **kwargs) -> str:
    """
    Get localized content by key.
    
    Args:
        key: Content key
        language: Language code
        **kwargs: Formatting parameters
    
    Returns:
        Localized content string
    """
    content = get_translation(key, language)
    
    # Format with parameters if provided
    if kwargs:
        try:
            return content.format(**kwargs)
        except (KeyError, ValueError):
            return content
    
    return content

