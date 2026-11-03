"""
Data models for Divar search and post details.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class CityInfo(BaseModel):
    id: int
    name: str
    slug: str


class DivarPostSummary(BaseModel):
    token: str
    title: str
    price: Optional[str] = None
    price_toman: Optional[int] = None
    district: Optional[str] = None
    city: Optional[str] = None
    time_text: Optional[str] = None
    image_url: Optional[str] = None
    url: str


class DivarPostDetail(BaseModel):
    token: str
    title: str
    url: str
    city: Optional[str] = None
    district: Optional[str] = None
    price: Optional[str] = None
    price_toman: Optional[int] = None
    description: Optional[str] = None
    specifications: Dict[str, str] = Field(default_factory=dict)
    images: List[str] = Field(default_factory=list)
    published_time: Optional[str] = None
    chat_enabled: bool = False
    raw_data: Optional[Dict[str, Any]] = None
