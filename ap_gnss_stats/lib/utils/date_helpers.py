#!/usr/bin/env python3
"""
Date utility functions for ap-gnss-stats.

This module provides helper functions for working with dates and times.
It also serves as a central place for dateutil imports to help IDE recognition.
"""

from typing import Optional, Union
from datetime import datetime

# Import dateutil explicitly to help IDE recognition
try:
    from dateutil import parser
    DATEUTIL_AVAILABLE = True
except ImportError:
    DATEUTIL_AVAILABLE = False


def parse_datetime(date_string: str) -> Optional[datetime]:
    """
    Parse a datetime string using dateutil if available.
    
    Args:
        date_string: The string representation of a date/time
        
    Returns:
        datetime object or None if parsing fails or dateutil is not available
    """
    if not DATEUTIL_AVAILABLE:
        return None
        
    try:
        return parser.parse(date_string)
    except Exception:
        return None
