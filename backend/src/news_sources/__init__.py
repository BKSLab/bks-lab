"""Supported collection sources, maintained and verified with application code."""

from src.news_sources.base import SourceProfile
from src.news_sources.registry import get_source_profile, get_source_profiles

__all__ = ["SourceProfile", "get_source_profile", "get_source_profiles"]
