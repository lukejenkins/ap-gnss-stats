"""
Parser module for Cisco AP GNSS statistics from 'show gnss info' command output.
"""
import re
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union

__version__ = '0.1.0'

# Configure logger
logger = logging.getLogger(__name__)

class GnssInfoParser:
    """
    Parser for Cisco AP 'show gnss info' command output.
    
    This parser extracts detailed GNSS information from the output of the
    'show gnss info' command run on Cisco WiFi Access Points.
    """
    
    def __init__(self, debug: bool = False):
        """
        Initialize the GNSS info parser.
        
        Args:
            debug: Enable debug logging
        """
        self.debug = debug
        if debug:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)
            
        # Common regex patterns
        self._ap_name_pattern = re.compile(r'(?:AP|ap)\s+Name\s*:\s*(.+)$', re.IGNORECASE)
        self._model_pattern = re.compile(r'AP\s+Model\s*:\s*(.+)$', re.IGNORECASE)
        self._mac_pattern = re.compile(r'MAC\s+Address\s*:\s*([0-9a-fA-F:]+)$', re.IGNORECASE)
        self._ip_pattern = re.compile(r'IP\s+Address\s*:\s*(\d+\.\d+\.\d+\.\d+)$', re.IGNORECASE)
        self._location_pattern = re.compile(r'AP\s+Location\s*:\s*(.+)$', re.IGNORECASE)
        self._gnss_status_pattern = re.compile(r'GNSS\s+Status\s*:\s*(.+)$', re.IGNORECASE)
        self._latitude_pattern = re.compile(r'Latitude\s*:\s*([-+]?\d+\.\d+)$', re.IGNORECASE)
        self._longitude_pattern = re.compile(r'Longitude\s*:\s*([-+]?\d+\.\d+)$', re.IGNORECASE)
        self._altitude_pattern = re.compile(r'Altitude\s*:\s*([-+]?\d+\.\d+)\s*m$', re.IGNORECASE)
        self._satellites_pattern = re.compile(r'Number\s+of\s+Satellites\s*:\s*(\d+)$', re.IGNORECASE)
        self._timestamp_pattern = re.compile(r'Time\s+Stamp\s*:\s*(.+)$', re.IGNORECASE)

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """
        Parse a file containing the output of 'show gnss info'.
        
        Args:
            file_path: Path to the file to parse
            
        Returns:
            Dictionary containing the parsed GNSS data
        """
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            logger.debug(f"Successfully read file: {file_path}")
            
            # Get file metadata
            import os
            file_stats = os.stat(file_path)
            file_metadata = {
                'filename': os.path.basename(file_path),
                'file_created': datetime.fromtimestamp(file_stats.st_ctime).isoformat(),
                'file_modified': datetime.fromtimestamp(file_stats.st_mtime).isoformat()
            }
            
            # Parse the content
            parsed_data = self.parse_text(content)
            
            # Add metadata
            result = {
                'tool': {
                    'name': 'ap-gnss-stats',
                    'version': __version__,
                    'parser': 'GnssInfoParser',
                    'parser_version': __version__
                },
                'timestamp': datetime.now().isoformat(),
                'file_metadata': file_metadata,
                'ap_data': parsed_data
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing file {file_path}: {str(e)}")
            raise
    
    def parse_text(self, text: str) -> Dict[str, Any]:
        """
        Parse the text output of 'show gnss info'.
        
        Args:
            text: The text output to parse
            
        Returns:
            Dictionary containing the parsed GNSS data
        """
        if self.debug:
            logger.debug("Parsing text content:")
            logger.debug("-" * 40)
            logger.debug(text[:200] + "..." if len(text) > 200 else text)
            logger.debug("-" * 40)
        
        result = {}
        
        # Basic AP information
        ap_name_match = self._ap_name_pattern.search(text)
        if ap_name_match:
            result['ap_name'] = ap_name_match.group(1).strip()
        
        model_match = self._model_pattern.search(text)
        if model_match:
            result['model'] = model_match.group(1).strip()
            
        mac_match = self._mac_pattern.search(text)
        if mac_match:
            result['mac_address'] = mac_match.group(1).strip()
            
        ip_match = self._ip_pattern.search(text)
        if ip_match:
            result['ip_address'] = ip_match.group(1).strip()
            
        location_match = self._location_pattern.search(text)
        if location_match:
            result['location'] = location_match.group(1).strip()
            
        # GNSS specific information
        gnss_status_match = self._gnss_status_pattern.search(text)
        if gnss_status_match:
            result['gnss_status'] = gnss_status_match.group(1).strip()
            
        latitude_match = self._latitude_pattern.search(text)
        if latitude_match:
            try:
                result['latitude'] = float(latitude_match.group(1))
            except ValueError:
                result['latitude'] = latitude_match.group(1)
                
        longitude_match = self._longitude_pattern.search(text)
        if longitude_match:
            try:
                result['longitude'] = float(longitude_match.group(1))
            except ValueError:
                result['longitude'] = longitude_match.group(1)
                
        altitude_match = self._altitude_pattern.search(text)
        if altitude_match:
            try:
                result['altitude_meters'] = float(altitude_match.group(1))
            except ValueError:
                result['altitude_meters'] = altitude_match.group(1)
                
        satellites_match = self._satellites_pattern.search(text)
        if satellites_match:
            try:
                result['satellites_count'] = int(satellites_match.group(1))
            except ValueError:
                result['satellites_count'] = satellites_match.group(1)
                
        timestamp_match = self._timestamp_pattern.search(text)
        if timestamp_match:
            result['gnss_timestamp'] = timestamp_match.group(1).strip()
        
        # Parse satellite details if available in the text
        # This would need to be expanded based on actual examples
        
        logger.debug(f"Parsed data: {json.dumps(result, indent=2)}")
        return result