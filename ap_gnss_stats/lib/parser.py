import re
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any

__version__ = '0.1.1'

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
        self._latitude_pattern = re.compile(r'Latitude\s*:\s*([-+]?\d+\.\d+)', re.IGNORECASE)
        self._longitude_pattern = re.compile(r'Longitude\s*:\s*([-+]?\d+\.\d+)', re.IGNORECASE)
        self._fix_pattern = re.compile(r'Fix\s*:\s*(\S+)\s+ValidFix\s*:\s*(\w+)', re.IGNORECASE)
        self._satellite_count_pattern = re.compile(r'SatelliteCount\s*:\s*(\d+)', re.IGNORECASE)
        self._gnss_postprocessor_pattern = re.compile(r'GNSS_PostProcessor:\s*(.*?)\n\n', re.DOTALL)

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """
        Parse a file containing the output of 'show gnss info'.
        
        Args:
            file_path: Path to the file to parse
            
        Returns:
            Dictionary containing the parsed GNSS data
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            logger.debug(f"Successfully read file: {file_path}")

            # Get file metadata
            file_stats = os.stat(file_path)
            file_metadata = {
                'filename': os.path.basename(file_path),
                'file_path': file_path,
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
        result = {}

        # Extract latitude and longitude
        latitude_match = self._latitude_pattern.search(text)
        if latitude_match:
            result['latitude'] = float(latitude_match.group(1))

        longitude_match = self._longitude_pattern.search(text)
        if longitude_match:
            result['longitude'] = float(longitude_match.group(1))

        # Extract Fix type and ValidFix
        fix_match = self._fix_pattern.search(text)
        if fix_match:
            result['fix_type'] = fix_match.group(1)
            result['valid_fix'] = fix_match.group(2).lower() == 'true'

        # Extract satellite count
        satellite_count_match = self._satellite_count_pattern.search(text)
        if satellite_count_match:
            result['satellite_count'] = int(satellite_count_match.group(1))

        # Extract GNSS PostProcessor metrics
        postprocessor_match = self._gnss_postprocessor_pattern.search(text)
        if postprocessor_match:
            # Further parsing can be added here for detailed metrics
            result['gnss_postprocessor'] = postprocessor_match.group(1).strip()

        return result
