"""
CAPWAP Client Configuration Parser - Extracts CAPWAP client configuration from access point logs.

This module provides parsers for extracting CAPWAP client configuration from Cisco access points,
including both main configuration fields and nested slot configurations.
"""
import re
import os
import sys
from typing import Dict, Any, List, Optional, Tuple, Union
from collections import OrderedDict

# Use relative import for BaseParser
# Make sure we can import from the same package level
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from parsers.base_parser import BaseParser


class CapwapConfigParser(BaseParser):
    """Parser for CAPWAP client configuration from Cisco access point logs.
    
    This parser extracts and structures all configuration data from the 
    'show capwap client configuration' command output, including main fields
    and all "Slot X Config" sections.
    """
    
    def __init__(self):
        """Initialize the parser with version tracking."""
        super().__init__()
        self.version = "2.0.0"  # Updated version to reflect comprehensive parsing
    
    def parse(self, content: str) -> Dict[str, Any]:
        """Parse CAPWAP client configuration data from content.
        
        Extracts all configuration fields from the 'show capwap client configuration' 
        command output, including both main configuration and all slot configurations.
        The result is returned as a nested structure with all available fields.
        
        Args:
            content: Raw content from AP logs
            
        Returns:
            Dictionary with nested CAPWAP client configuration data structure
        """
        # Extract CAPWAP client configuration section
        capwap_section = self._extract_capwap_config_section(content)
        if not capwap_section:
            return {"show_capwap_client_config": {}}
        
        # Extract the main configuration fields and slot configurations
        main_config = self._extract_main_config(capwap_section)
        slots_config = self._extract_slot_configs(capwap_section)
        
        # Combine into a nested structure
        nested_data = {
            **main_config,
            "slots": slots_config
        }
        
        # Create the result with the nested structure
        result = {
            "show_capwap_client_config": nested_data
        }
        
        return result
    
    def _extract_capwap_config_section(self, content: str) -> str:
        """Extract the CAPWAP client configuration section from the content.
        
        Args:
            content: Raw file content
            
        Returns:
            CAPWAP client configuration section or empty string if not found
        """
        # Look for the command output section
        # This pattern matches from the command to either the next command prompt or end of file
        match = re.search(r"show capwap client configuration\s*(.*?)(?=\n\w+#|\Z)", 
                          content, re.DOTALL | re.IGNORECASE)
        
        if match:
            return match.group(1).strip()
        return ""
    
    def _extract_main_config(self, capwap_section: str) -> Dict[str, Any]:
        """Extract main configuration fields from CAPWAP section.
        
        Parses all top-level configuration fields (not in slot sections)
        and returns them in a dictionary with normalized keys.
        
        Args:
            capwap_section: CAPWAP configuration section
            
        Returns:
            Dictionary with all main configuration fields
        """
        # Define a pattern to match key-value pairs
        pattern = r"^([^:]+?)\s*:\s*(.+?)$"
        
        # Initialize the result dictionary
        main_config = {}
        
        # Process each line until we hit a Slot configuration
        lines = capwap_section.split('\n')
        for line in lines:
            # Skip empty lines
            if not line.strip():
                continue
            
            # Skip lines that start with "Slot" as they are part of slot configurations
            if line.strip().startswith("Slot"):
                continue
            
            # Skip indented lines as they are part of slot configurations
            if line.startswith("    "):
                continue
                
            # Extract key-value pairs
            match = re.match(pattern, line.strip())
            if match:
                key = match.group(1).strip().lower().replace(" ", "_")
                value = match.group(2).strip()
                
                # Try to convert numeric values
                value = self._normalize_value(value)
                main_config[key] = value
        
        return main_config
    
    def _extract_slot_configs(self, capwap_section: str) -> List[Dict[str, Any]]:
        """Extract slot configurations from CAPWAP section.
        
        Identifies all "Slot X Config" sections and extracts their complete
        configuration into a structured format. Each slot becomes a dictionary
        with slot_number and a nested configuration dictionary containing all fields.
        
        Args:
            capwap_section: CAPWAP configuration section
            
        Returns:
            List of dictionaries with slot configurations
        """
        # Initialize the result list
        slots = []
        
        # Find all slot sections
        slot_pattern = r"Slot (\d+) Config:(.*?)(?=(?:Slot \d+ Config:|\Z))"
        slot_matches = re.finditer(slot_pattern, capwap_section, re.DOTALL)
        
        for match in slot_matches:
            slot_num = int(match.group(1))
            slot_content = match.group(2).strip()
            
            # Extract key-value pairs from the slot content
            slot_config = {}
            
            # Handle nested sections (like "Load Profile", "HE Info", etc.)
            current_section = None
            current_section_data = {}
            
            # Process each line of the slot content
            for line in slot_content.split('\n'):
                # Skip empty lines
                if not line.strip():
                    continue
                
                # Check if this is a section header (ends with a colon but no value after it)
                section_match = re.match(r'^\s+([^:]+?)\s*:\s*$', line)
                if section_match:
                    # If we were processing a section, add it to the config
                    if current_section and current_section_data:
                        slot_config[current_section] = current_section_data
                    
                    # Start a new section
                    current_section = section_match.group(1).strip().lower().replace(" ", "_")
                    current_section_data = {}
                    continue
                
                # Try to match a key-value pair
                kv_match = re.match(r'^\s+([^:]+?)\s*:\s*(.+?)$', line)
                if kv_match:
                    key = kv_match.group(1).strip().lower().replace(" ", "_")
                    value = kv_match.group(2).strip()
                    value = self._normalize_value(value)
                    
                    # If we're in a section, add to that section
                    if current_section and re.match(r'^\s{6,}', line):
                        current_section_data[key] = value
                    else:
                        # Otherwise, it's a top-level key in the slot config
                        slot_config[key] = value
                        # Reset section tracking if this wasn't part of a section
                        current_section = None
                        current_section_data = {}
            
            # Don't forget to add the last section if there is one
            if current_section and current_section_data:
                slot_config[current_section] = current_section_data
            
            # Add the slot to our list
            slots.append({
                "slot_number": slot_num,
                "configuration": slot_config
            })
        
        return slots
    
    def _normalize_value(self, value: str) -> Union[str, int, float, bool]:
        """Normalize a value by converting to appropriate type.
        
        Args:
            value: The string value to normalize
            
        Returns:
            Converted value (int, float, bool, or original string)
        """
        # Try to convert to appropriate type
        value = value.strip()
        
        # Handle boolean values
        if value.lower() in ['true', 'yes', 'enabled']:
            return True
        if value.lower() in ['false', 'no', 'disabled']:
            return False
        
        # Handle numeric values
        try:
            # Try as integer first
            if value.isdigit() or (value.startswith('-') and value[1:].isdigit()):
                return int(value)
            # Then try as float
            return float(value)
        except (ValueError, TypeError):
            # Return as string if not numeric
            return value
    
    def get_version(self) -> str:
        """Get the parser version.
        
        Returns:
            Parser version string
        """
        return self.version
