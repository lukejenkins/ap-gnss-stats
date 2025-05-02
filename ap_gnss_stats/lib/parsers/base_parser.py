"""
Base parser functionality for GNSS data.

This module provides base classes and utilities for the parser implementations.
"""

import re
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from collections import OrderedDict


class BaseParser:
    """Base class for all parser implementations."""
    
    @staticmethod
    def convert_to_bool(value: str) -> bool:
        """Convert string value to boolean.
        
        Args:
            value: String value (e.g., "true", "false")
            
        Returns:
            Boolean representation of the value
        """
        return value.lower() == "true"
    
    @staticmethod
    def extract_with_pattern(content: str, pattern: str, group: int = 1, 
                           flags: int = re.IGNORECASE, 
                           conversion: Optional[callable] = None,
                           default: Any = None) -> Any:
        """Extract value from content using regex pattern.
        
        Args:
            content: Text content to search in
            pattern: Regular expression pattern
            group: Capture group to extract (default: 1)
            flags: Regex flags to use (default: re.IGNORECASE)
            conversion: Optional function to convert extracted value
            default: Default value if pattern not found
            
        Returns:
            Extracted and optionally converted value, or default if not found
        """
        match = re.search(pattern, content, flags)
        if match:
            value = match.group(group).strip()
            return conversion(value) if conversion else value
        return default
    
    def parse(self, content: str) -> Dict[str, Any]:
        """Parse content and return extracted data.
        
        Args:
            content: Text content to parse
            
        Returns:
            Dictionary with parsed data
        """
        raise NotImplementedError("Parser implementations must override this method")
    
    @staticmethod
    def reorder_json(data: Dict[str, Any], order: List[str]) -> OrderedDict:
        """Reorder a dictionary according to the given key order.
        
        Args:
            data: Dictionary to reorder
            order: List of keys in the desired order
            
        Returns:
            OrderedDict with keys in the desired order
        """
        ordered = OrderedDict()
        
        # Add keys in the specified order
        for key in order:
            if key in data:
                ordered[key] = data[key]
        
        # Add any remaining keys not in the order list
        for key, value in data.items():
            if key not in order:
                ordered[key] = value
        
        return ordered