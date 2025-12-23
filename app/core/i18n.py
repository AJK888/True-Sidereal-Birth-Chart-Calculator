"""
Internationalization (i18n) Support

Provides multi-language support for the application.
"""

import logging
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class Language(str, Enum):
    """Supported languages."""
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    ITALIAN = "it"
    PORTUGUESE = "pt"
    JAPANESE = "ja"
    CHINESE = "zh"
    RUSSIAN = "ru"
    HINDI = "hi"


DEFAULT_LANGUAGE = Language.ENGLISH
SUPPORTED_LANGUAGES = [lang.value for lang in Language]


# Translation dictionaries (in production, these would be loaded from files)
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en": {
        "chart.calculated": "Chart Calculated",
        "reading.generated": "Reading Generated",
        "error.chart_calculation": "Failed to calculate chart",
        "error.geocoding": "Could not find location",
        "error.reading_generation": "Failed to generate reading",
        "success.chart_saved": "Chart saved successfully",
        "success.reading_sent": "Reading sent to your email",
    },
    "es": {
        "chart.calculated": "Carta Calculada",
        "reading.generated": "Lectura Generada",
        "error.chart_calculation": "Error al calcular la carta",
        "error.geocoding": "No se pudo encontrar la ubicación",
        "error.reading_generation": "Error al generar la lectura",
        "success.chart_saved": "Carta guardada exitosamente",
        "success.reading_sent": "Lectura enviada a tu correo",
    },
    "fr": {
        "chart.calculated": "Carte Calculée",
        "reading.generated": "Lecture Générée",
        "error.chart_calculation": "Échec du calcul de la carte",
        "error.geocoding": "Impossible de trouver l'emplacement",
        "error.reading_generation": "Échec de la génération de la lecture",
        "success.chart_saved": "Carte enregistrée avec succès",
        "success.reading_sent": "Lecture envoyée à votre email",
    },
}


def get_translation(key: str, language: str = DEFAULT_LANGUAGE.value) -> str:
    """
    Get translation for a key.
    
    Args:
        key: Translation key
        language: Language code (defaults to English)
    
    Returns:
        Translated string or key if translation not found
    """
    if language not in TRANSLATIONS:
        language = DEFAULT_LANGUAGE.value
    
    translations = TRANSLATIONS.get(language, {})
    return translations.get(key, key)


def translate(text: str, language: str = DEFAULT_LANGUAGE.value) -> str:
    """
    Translate text (if translation exists).
    
    Args:
        text: Text to translate
        language: Language code
    
    Returns:
        Translated text or original if no translation
    """
    # For now, return original text
    # In production, this would use a translation service
    return text


def get_supported_languages() -> Dict[str, Any]:
    """
    Get list of supported languages.
    
    Returns:
        Dictionary with supported languages
    """
    language_names = {
        "en": "English",
        "es": "Español",
        "fr": "Français",
        "de": "Deutsch",
        "it": "Italiano",
        "pt": "Português",
        "ja": "日本語",
        "zh": "中文",
        "ru": "Русский",
        "hi": "हिन्दी"
    }
    
    return {
        "supported_languages": [
            {
                "code": lang,
                "name": language_names.get(lang, lang),
                "is_default": lang == DEFAULT_LANGUAGE.value
            }
            for lang in SUPPORTED_LANGUAGES
        ],
        "default_language": DEFAULT_LANGUAGE.value
    }


def detect_language(request_headers: Dict[str, str]) -> str:
    """
    Detect language from request headers.
    
    Args:
        request_headers: Request headers dictionary
    
    Returns:
        Language code
    """
    # Check Accept-Language header
    accept_language = request_headers.get("Accept-Language", "")
    
    if not accept_language:
        return DEFAULT_LANGUAGE.value
    
    # Parse Accept-Language (e.g., "en-US,en;q=0.9,es;q=0.8")
    languages = []
    for lang_part in accept_language.split(","):
        lang_code = lang_part.split(";")[0].strip().split("-")[0].lower()
        if lang_code in SUPPORTED_LANGUAGES:
            languages.append(lang_code)
    
    return languages[0] if languages else DEFAULT_LANGUAGE.value

