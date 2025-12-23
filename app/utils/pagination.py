"""
Pagination Utilities

Standardized pagination for list endpoints.
"""

from typing import List, Dict, Any, Optional, TypeVar, Generic
from pydantic import BaseModel, Field
from math import ceil

T = TypeVar('T')


class PaginationParams(BaseModel):
    """Standard pagination parameters."""
    skip: int = Field(0, ge=0, description="Number of items to skip")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of items to return")
    
    @property
    def page(self) -> int:
        """Calculate page number from skip and limit."""
        return (self.skip // self.limit) + 1 if self.limit > 0 else 1


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response format."""
    items: List[T]
    total: int
    skip: int
    limit: int
    page: int
    pages: int
    
    @classmethod
    def create(
        cls,
        items: List[T],
        total: int,
        skip: int,
        limit: int
    ) -> "PaginatedResponse[T]":
        """Create a paginated response."""
        page = (skip // limit) + 1 if limit > 0 else 1
        pages = ceil(total / limit) if limit > 0 else 1
        
        return cls(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
            page=page,
            pages=pages
        )


def paginate_query(query, skip: int = 0, limit: int = 100):
    """Apply pagination to a SQLAlchemy query."""
    return query.offset(skip).limit(limit)


def create_paginated_response(
    items: List[T],
    total: int,
    skip: int,
    limit: int
) -> Dict[str, Any]:
    """Create a paginated response dictionary."""
    page = (skip // limit) + 1 if limit > 0 else 1
    pages = ceil(total / limit) if limit > 0 else 1
    
    return {
        "items": items,
        "pagination": {
            "total": total,
            "skip": skip,
            "limit": limit,
            "page": page,
            "pages": pages,
            "has_next": skip + limit < total,
            "has_previous": skip > 0
        }
    }

