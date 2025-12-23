"""
Field Selection Utilities

Utilities for sparse fieldsets (selecting specific fields in responses).
"""

from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel


def parse_fields_param(fields_param: Optional[str]) -> Set[str]:
    """Parse fields parameter (comma-separated list)."""
    if not fields_param:
        return set()
    
    return {field.strip() for field in fields_param.split(",") if field.strip()}


def filter_dict_fields(data: Dict[str, Any], fields: Set[str]) -> Dict[str, Any]:
    """Filter dictionary to include only specified fields."""
    if not fields:
        return data
    
    return {key: value for key, value in data.items() if key in fields}


def filter_model_fields(model: BaseModel, fields: Set[str]) -> Dict[str, Any]:
    """Filter Pydantic model to include only specified fields."""
    if not fields:
        return model.model_dump()
    
    data = model.model_dump()
    return filter_dict_fields(data, fields)


def filter_list_fields(items: List[Dict[str, Any]], fields: Set[str]) -> List[Dict[str, Any]]:
    """Filter list of dictionaries to include only specified fields."""
    if not fields:
        return items
    
    return [filter_dict_fields(item, fields) for item in items]


def apply_field_selection(
    data: Any,
    fields_param: Optional[str]
) -> Any:
    """Apply field selection to data (dict, list, or model)."""
    if not fields_param:
        return data
    
    fields = parse_fields_param(fields_param)
    
    if isinstance(data, dict):
        return filter_dict_fields(data, fields)
    elif isinstance(data, list):
        return filter_list_fields(data, fields)
    elif hasattr(data, 'model_dump'):
        # Pydantic model
        return filter_model_fields(data, fields)
    else:
        return data

