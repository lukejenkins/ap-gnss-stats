"""
CAPWAP Client Configuration Parser - Extracts CAPWAP client configuration from access point logs.

This module provides parsers for extracting CAPWAP client configuration from Cisco access points.
"""
import re
import os
import sys
from typing import Dict, Any, List, Optional
from collections import OrderedDict

# Use relative import for BaseParser
# Make sure we can import from the same package level
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from parsers.base_parser import BaseParser


class CapwapConfigParser(BaseParser):
    """Parser for CAPWAP client configuration from Cisco access point logs."""
    
    def __init__(self):
        """Initialize the parser."""
        super().__init__()
        self.version = "1.0.0"
    
    def parse(self, content: str) -> Dict[str, Any]:
        """Parse CAPWAP client configuration data from content.
        
        Args:
            content: Raw content from AP logs
            
        Returns:
            Dictionary with parsed CAPWAP client configuration data
        """
        # Extract CAPWAP client configuration section
        capwap_section = self._extract_capwap_config_section(content)
        if not capwap_section:
            return {"show_capwap_client_config": {}}
        
        # Initialize nested structure for CAPWAP client config
        nested_data = {
            "name": self._extract_name(capwap_section),
            "adminstate": self._extract_admin_state(capwap_section),
            "primary_controller_name": self._extract_primary_controller_name(capwap_section),
            "apmode": self._extract_ap_mode(capwap_section),
            "policy_tag": self._extract_policy_tag(capwap_section),
            "rf_tag": self._extract_rf_tag(capwap_section),
            "site_tag": self._extract_site_tag(capwap_section),
            "tag_source": self._extract_tag_source(capwap_section),
            "swver": self._extract_sw_ver(capwap_section)
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
        match = re.search(r"show capwap client configuration\s*(.*?)(?=\n\w+#|\Z)", 
                          content, re.DOTALL | re.IGNORECASE)
        
        if match:
            return match.group(1).strip()
        return ""
    
    def _extract_admin_state(self, capwap_section: str) -> Optional[str]:
        """Extract AdminState from CAPWAP configuration.
        
        Args:
            capwap_section: CAPWAP configuration section
            
        Returns:
            AdminState value or None if not found
        """
        return self.extract_with_pattern(
            capwap_section,
            r"AdminState\s*[:=]\s*([^\n]+)",
            conversion=str.strip
        )
    
    def _extract_name(self, capwap_section: str) -> Optional[str]:
        """Extract Name from CAPWAP configuration.
        
        Args:
            capwap_section: CAPWAP configuration section
            
        Returns:
            Name value or None if not found
        """
        return self.extract_with_pattern(
            capwap_section,
            r"Name\s*[:=]\s*([^\n]+)",
            conversion=str.strip
        )
    
    def _extract_primary_controller_name(self, capwap_section: str) -> Optional[str]:
        """Extract Primary controller name from CAPWAP configuration.
        
        Args:
            capwap_section: CAPWAP configuration section
            
        Returns:
            Primary controller name or None if not found
        """
        return self.extract_with_pattern(
            capwap_section,
            r"Primary controller name\s*[:=]\s*([^\n]+)",
            conversion=str.strip
        )
    
    def _extract_ap_mode(self, capwap_section: str) -> Optional[str]:
        """Extract ApMode from CAPWAP configuration.
        
        Args:
            capwap_section: CAPWAP configuration section
            
        Returns:
            ApMode value or None if not found
        """
        return self.extract_with_pattern(
            capwap_section,
            r"ApMode\s*[:=]\s*([^\n]+)",
            conversion=str.strip
        )
    
    def _extract_policy_tag(self, capwap_section: str) -> Optional[str]:
        """Extract AP Policy Tag from CAPWAP configuration.
        
        Args:
            capwap_section: CAPWAP configuration section
            
        Returns:
            AP Policy Tag value or None if not found
        """
        return self.extract_with_pattern(
            capwap_section,
            r"AP Policy Tag\s*[:=]\s*([^\n]+)",
            conversion=str.strip
        )
    
    def _extract_rf_tag(self, capwap_section: str) -> Optional[str]:
        """Extract AP RF Tag from CAPWAP configuration.
        
        Args:
            capwap_section: CAPWAP configuration section
            
        Returns:
            AP RF Tag value or None if not found
        """
        return self.extract_with_pattern(
            capwap_section,
            r"AP RF Tag\s*[:=]\s*([^\n]+)",
            conversion=str.strip
        )
    
    def _extract_site_tag(self, capwap_section: str) -> Optional[str]:
        """Extract AP Site Tag from CAPWAP configuration.
        
        Args:
            capwap_section: CAPWAP configuration section
            
        Returns:
            AP Site Tag value or None if not found
        """
        return self.extract_with_pattern(
            capwap_section,
            r"AP Site Tag\s*[:=]\s*([^\n]+)",
            conversion=str.strip
        )
    
    def _extract_tag_source(self, capwap_section: str) -> Optional[str]:
        """Extract AP Tag Source from CAPWAP configuration.
        
        Args:
            capwap_section: CAPWAP configuration section
            
        Returns:
            AP Tag Source value or None if not found
        """
        return self.extract_with_pattern(
            capwap_section,
            r"AP Tag Source\s*[:=]\s*([^\n]+)",
            conversion=str.strip
        )
    
    def _extract_sw_ver(self, capwap_section: str) -> Optional[str]:
        """Extract SwVer from CAPWAP configuration.
        
        Args:
            capwap_section: CAPWAP configuration section
            
        Returns:
            SwVer value or None if not found
        """
        return self.extract_with_pattern(
            capwap_section,
            r"SwVer\s*[:=]\s*([^\n]+)",
            conversion=str.strip
        )
    
    def get_version(self) -> str:
        """Get the parser version.
        
        Returns:
            Parser version string
        """
        return self.version
