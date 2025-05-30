"""
GNSS Info Parser - Extracts GNSS information from access point logs.

This module provides parsers for extracting GNSS information from Cisco access point logs.
"""

import re
from typing import Dict, Any, List, Tuple, Optional
from collections import OrderedDict

# Use relative import for BaseParser
import os
import sys
# Make sure we can import from the same package level
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from parsers.base_parser import BaseParser


class GnssInfoParser(BaseParser):
    """Parser for GNSS information from Cisco access point logs."""
    
    def __init__(self):
        """Initialize the parser."""
        super().__init__()
        self.version = "1.3.0"
    
    def parse(self, content: str, ap_address: str = "") -> Dict[str, Any]:
        """Parse GNSS data from content.
        
        Args:
            content: Raw content from AP logs
            ap_address: Optional original AP address to help with name reconstruction
            
        Returns:
            Dictionary with parsed GNSS data
        """
        result = {
            "raw_data": {},
            "satellites": []
        }
        
        # Extract main and GNSS state metrics
        main_metrics, gnss_state_metrics = self._extract_gnss_metrics(content, ap_address)
        
        # Add sections to the result
        result["main"] = main_metrics
        result["show_version"] = self._extract_show_version_metrics(content)
        result["gnss_state"] = gnss_state_metrics
        result["gnss_postprocessor"] = self._extract_gnss_postprocessor_metrics(content)
        result["cisco_gnss"] = self._extract_cisco_gnss_metrics(content)
        result["last_location_acquired"] = self._extract_last_location_acquired_metrics(content)
        result["show_inventory"] = self._extract_show_inventory_metrics(content)
        
        # If no GNSS detected, we can skip parsing satellite data
        if not gnss_state_metrics["no_gnss_detected"]:
            # Parse satellite data
            result["satellites"] = self._extract_satellite_data(content)
            
            # Extract raw key-value pairs for additional data
            result["raw_data"] = self._extract_raw_data(content)
        
        # Reorder the result according to the desired order
        ordered_result = self.reorder_json(result, [
            "metadata",  # Added first but will be populated later
            "main",
            "show_version",
            "show_inventory",
            "gnss_state",
            "gnss_postprocessor",
            "cisco_gnss",
            "last_location_acquired",
            "satellites",
            "raw_data"
        ])
        
        return ordered_result
    
    def _extract_gnss_metrics(self, content: str, ap_address: str = "") -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Extract main and GNSS state metrics from the content.
        
        Args:
            content: Raw file content
            ap_address: Optional original AP address to help with name reconstruction
            
        Returns:
            Tuple of (main metrics dictionary, gnss state metrics dictionary)
        """
        # Initialize metrics dictionaries with all expected fields
        main_metrics = self._get_default_main_metrics()
        gnss_state_metrics = self._get_default_gnss_state_metrics()
        
        # Extract AP name and add it to the main metrics
        ap_name = self._extract_ap_name(content)
        
        # NETMIKO TRUNCATION ISSUE HANDLING:
        # Netmiko sometimes truncates hostnames, especially those with hyphens where the final segment
        # is a single character or short string. For example:
        # "ogxwsc-outdoor-ap1" -> "ogxwsc-outdoor-a"
        # 
        # This logic checks for truncation patterns and attempts to reconstruct the full hostname
        # using the original AP address provided by the caller (typically from run_ap_commands).
        if ap_name and ap_address and '-' in ap_name:
            # Check for truncation pattern: hostname with a hyphen and last segment is 1 or 2 characters
            last_segment = ap_name.split('-')[-1]
            if len(last_segment) <= 2:
                # Extract hostname part from the FQDN (e.g., "ogxwsc-outdoor-ap1" from "ogxwsc-outdoor-ap1.mgmt.weber.edu")
                original_hostname = ap_address.split('.')[0]
                
                # Several checks to validate the reconstruction:
                # 1. Original hostname should be longer than the truncated one
                # 2. Original hostname should start with most of the truncated name (minus the last 1-2 chars)
                if (len(original_hostname) > len(ap_name) and 
                    original_hostname.startswith(ap_name[:-len(last_segment)])):
                    # Use the original hostname instead of the truncated one
                    ap_name = original_hostname
        
        if ap_name:
            main_metrics["main_ap_name"] = ap_name
        
        # Extract clock time from 'show clock' command and add to main metrics
        show_clock_time = self._extract_show_clock_time(content)
        if show_clock_time:
            main_metrics["show_clock_time"] = show_clock_time
        
        # Check for "No GNSS detected" message
        no_gnss_pattern = r'show gnss info\s*\n\s*No GNSS detected'
        gnss_state_metrics["no_gnss_detected"] = bool(re.search(no_gnss_pattern, content, re.IGNORECASE))
        
        # If no GNSS detected, we can return early
        if gnss_state_metrics["no_gnss_detected"]:
            return main_metrics, gnss_state_metrics
        
        # Extract the GNSS state section
        gnss_state_start = content.find("GnssState:")
        if gnss_state_start == -1:
            # Try case insensitive search
            match = re.search(r'gnssstate:', content, re.IGNORECASE)
            if match:
                gnss_state_start = match.start()
            else:
                return main_metrics, gnss_state_metrics
        
        # Find the end of the state section (satellite table start)
        sat_table_start = re.search(r'Const\.', content[gnss_state_start:], re.IGNORECASE)
        if sat_table_start:
            state_section = content[gnss_state_start:gnss_state_start + sat_table_start.start()]
        else:
            # If satellite table not found, use a large section
            state_section = content[gnss_state_start:]
        
        # Define patterns for each metric
        patterns = {
            "state": r"GnssState:\s*(\w+)",
            "external_antenna": r"ExternalAntenna:\s*(true|false)",
            "fix_type": r"Fix:\s*([^\s]+)",
            "valid_fix": r"ValidFix:\s*(true|false)",
            "gnss_fix_time": r"Time:\s*([\d-]+\s+[\d:]+)",
            "latitude": r"Latitude:\s*([\d\.-]+)",
            "longitude": r"Longitude:\s*([\d\.-]+)",
            "horacc": r"HorAcc:\s*([\d\.]+)",
            "altitude_msl": r"Altitude MSL:\s*([\d\.]+)",
            "altitude_hae": r"HAE:\s*([\d\.]+)",
            "vertacc": r"VertAcc:\s*([\d\.]+)",
            "numsat": r"NumSat:\s*(\d+)",
            "rangeres": r"RangeRes:\s*([\d\.]+)",
            "gpgstrms": r"GpGstRms:\s*([\d\.]+)",
            "satellitecount": r"SatelliteCount:\s*(\d+)",
            "last_fix_time": r"LastFixTime:\s*([\d-]+\s+[\d:]+)",
        }
        
        # Extract uncertainty ellipse separately
        uncertainty_pattern = r"Uncertainty Ellipse:\s*Major axis:\s*([\d\.]+)\s*Minor axis:\s*([\d\.]+)\s*Orientation:\s*([\d\.]+)"
        uncertainty_match = re.search(uncertainty_pattern, state_section, re.IGNORECASE)
        
        if uncertainty_match:
            gnss_state_metrics["uncertainty_ellipse_major_axis"] = float(uncertainty_match.group(1))
            gnss_state_metrics["uncertainty_ellipse_minor_axis"] = float(uncertainty_match.group(2))
            gnss_state_metrics["uncertainty_ellipse_orientation"] = float(uncertainty_match.group(3))
        
        # Extract DOP parameters - these might be presented together in a line
        dop_pattern = r"pDOP:\s*([\d\.]+)\s+hDOP:\s*([\d\.]+)\s+vDOP:\s*([\d\.]+)\s+nDOP:\s*([\d\.]+)\s+eDOP:\s*([\d\.]+)\s+gDOP:\s*([\d\.]+)\s+tDOP:\s*([\d\.]+)"
        dop_match = re.search(dop_pattern, state_section, re.IGNORECASE)
        
        if dop_match:
            gnss_state_metrics["pdop"] = float(dop_match.group(1))
            gnss_state_metrics["hdop"] = float(dop_match.group(2))
            gnss_state_metrics["vdop"] = float(dop_match.group(3))
            gnss_state_metrics["ndop"] = float(dop_match.group(4))
            gnss_state_metrics["edop"] = float(dop_match.group(5))
            gnss_state_metrics["gdop"] = float(dop_match.group(6))
            gnss_state_metrics["tdop"] = float(dop_match.group(7))
        
        # Extract first hDOP value separately (may appear before the DOP section)
        horacc_hdop_pattern = r"HorAcc:\s*[\d\.]+\s+hDOP:\s*([\d\.]+)"
        horacc_hdop_match = re.search(horacc_hdop_pattern, state_section, re.IGNORECASE)
        
        if horacc_hdop_match:
            gnss_state_metrics["horacc_hdop"] = float(horacc_hdop_match.group(1))
        
        # Process the main patterns
        for key, pattern in patterns.items():
            match = re.search(pattern, state_section, re.IGNORECASE)
            if match:
                value = match.group(1)
                if key in ["external_antenna", "valid_fix"]:
                    gnss_state_metrics[key] = self.convert_to_bool(value)
                elif key in ["latitude", "longitude", "horacc", "altitude_msl", 
                           "altitude_hae", "vertacc", "rangeres", "gpgstrms"]:
                    try:
                        # Ensure float values are parsed correctly with full precision
                        gnss_state_metrics[key] = float(value)
                    except ValueError:
                        gnss_state_metrics[key] = value
                elif key in ["numsat", "satellitecount"]:
                    try:
                        gnss_state_metrics[key] = int(value)
                    except ValueError:
                        gnss_state_metrics[key] = value
                else:
                    gnss_state_metrics[key] = value
        
        return main_metrics, gnss_state_metrics

    def _extract_ap_name(self, content: str) -> str:
        """Extract the AP name from the content.
        
        Args:
            content: Raw file content
            
        Returns:
            String containing the AP name, or empty string if not found
        """
        # Cisco AP prompt is typically: <ap_name>#show ...
        # AP names can be up to 32 characters (Cisco limit)
        # First try to match entire prompt lines, then apply length limit
        pattern = r'(?:^|\n)([^\n#]+)#show '
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            ap_name = match.group(1).strip()
            
            # Check for potential Netmiko truncation
            # Netmiko can truncate AP names in different patterns:
            # Example: "ogxwsc-outdoor-a" is truncated from "ogxwsc-outdoor-ap1"
            # Example: "server-c" might be truncated from "server-core"
            # 
            # This primarily happens with hostnames containing hyphens where the last segment
            # is only 1-2 characters long after truncation.
            truncation_suspected = False
            
            # Detect potential truncation: hyphen followed by 1-2 chars at the end
            if '-' in ap_name:
                last_segment = ap_name.split('-')[-1] 
                if len(last_segment) <= 2:
                    truncation_suspected = True
            
            if truncation_suspected:
                # Look for the full hostname in metadata if available
                # This is only relevant when called during parsing in run_ap_commands
                # and won't help with direct parsing, but it's better than nothing
                original_hostname_pattern = r'hostname: ([^\s,]+)'
                hostname_match = re.search(original_hostname_pattern, content, re.IGNORECASE)
                if hostname_match:
                    full_hostname = hostname_match.group(1).strip()
                    # Verify the potential match makes sense
                    if len(full_hostname) > len(ap_name) and full_hostname.startswith(ap_name[:-len(last_segment)]):
                        ap_name = full_hostname
                        
            # Defensive: enforce max 32 chars, but do not truncate shorter names
            if len(ap_name) > 32:
                ap_name = ap_name[:32]
            return ap_name
        return ""

    def _extract_show_clock_time(self, content: str) -> str:
        """Extract the clock time from 'show clock' command output.

        Args:
            content: Raw file content
        
        Returns:
            String containing the clock time, or empty string if not found
        """
        # Try prompt-based format
        pattern_prompt = r'show clock\s*\n\s*\*([^\n]+)'
        match_prompt = re.search(pattern_prompt, content, re.IGNORECASE)
        if match_prompt:
            return match_prompt.group(1).strip()

        # Try asterisk-delimited format
        pattern_asterisk_section = r'\*{5} show clock \*{5}([\s\S]+?)(?=\n\*{5} )'
        match_asterisk_section = re.search(pattern_asterisk_section, content, re.IGNORECASE)
        if match_asterisk_section:
            section = match_asterisk_section.group(1)
            # Find the first line starting with * (the clock time)
            for line in section.splitlines():
                line = line.strip()
                if line.startswith("*"):
                    return line.lstrip("*").strip()
        return ""

    def _get_default_main_metrics(self) -> Dict[str, Any]:
        """Get default main metrics dictionary with all expected fields initialized to None.
        
        Returns:
            Dictionary with main metrics fields set to None
        """
        return {
            "main_ap_name": None,
            "show_clock_time": None
        }

    def _get_default_gnss_state_metrics(self) -> Dict[str, Any]:
        """Get default GNSS state metrics dictionary with all expected fields initialized to None.
        
        Returns:
            Dictionary with GNSS state metrics fields set to None
        """
        return {
            "no_gnss_detected": False,
            "state": None,
            "external_antenna": None,
            "fix_type": None,
            "valid_fix": None,
            "gnss_fix_time": None,
            "last_fix_time": None,
            "latitude": None,
            "longitude": None,
            "horacc": None,
            "horacc_hdop": None,
            "altitude_msl": None,
            "altitude_hae": None,
            "vertacc": None,
            "numsat": None,
            "rangeres": None,
            "gpgstrms": None,
            "satellitecount": None,
            "uncertainty_ellipse_major_axis": None,
            "uncertainty_ellipse_minor_axis": None,
            "uncertainty_ellipse_orientation": None,
            "pdop": None,
            "hdop": None,
            "vdop": None,
            "ndop": None,
            "edop": None,
            "gdop": None,
            "tdop": None
        }

    def _get_default_gnss_postprocessor_metrics(self) -> Dict[str, Any]:
        """Get default GNSS_PostProcessor metrics dictionary with all expected fields initialized.
        
        Returns:
            Dictionary with all GNSS_PostProcessor metrics fields initialized
        """
        return {
            "gnss_pp_parser_found": False,
            "not_available": False,
            "latitude": None,
            "longitude": None,
            "horacc": None,
            "horacc_hdop": None,
            "uncertainty_ellipse_major_axis": None,
            "uncertainty_ellipse_minor_axis": None,
            "uncertainty_ellipse_orientation": None,
            "altitude_msl": None,
            "altitude_hae": None,
            "vertacc": None
        }

    def _get_default_cisco_gnss_metrics(self) -> Dict[str, Any]:
        """Get default cisco_gnss metrics dictionary with all expected fields initialized.
        
        Returns:
            Dictionary with all cisco_gnss metrics fields initialized
        """
        return {
            "cisco_gnss_parser_found": False,
            "not_available": False,
            "latitude": None,
            "longitude": None,
            "horacc": None,
            "horacc_hdop": None,
            "uncertainty_ellipse_major_axis": None,
            "uncertainty_ellipse_minor_axis": None,
            "uncertainty_ellipse_orientation": None,
            "altitude_msl": None,
            "altitude_hae": None,
            "vertacc": None
        }

    def _get_default_last_location_acquired_metrics(self) -> Dict[str, Any]:
        """Get default last_location_acquired metrics dictionary with all expected fields initialized.
        
        Returns:
            Dictionary with all last_location_acquired metrics fields initialized
        """
        return {
            "last_location_parser_found": False,
            "not_available": False,
            "latitude": None,
            "longitude": None,
            "horacc": None,
            "horacc_hdop": None,
            "uncertainty_ellipse_major_axis": None,
            "uncertainty_ellipse_minor_axis": None,
            "uncertainty_ellipse_orientation": None,
            "altitude_msl": None,
            "altitude_hae": None,
            "vertacc": None,
            "derivation_type": None,
            "derivation_time": None
        }

    def _get_default_show_version_metrics(self) -> Dict[str, Any]:
        """Get default show_version metrics dictionary with all expected fields initialized to None.

        Returns:
            Dictionary with show_version metrics fields set to None
        """
        return {
            "ver_ap_name": None,
            "ap_serial_number": None,
            "ap_model": None,
            "ap_image_family": None,
            "ap_image_string": None,
            "ap_running_image": None,
            "ap_uptime_days": None,
            "ap_uptime_hours": None,
            "ap_uptime_minutes": None,
            "last_reload_time": None,
            "last_reload_reason": None,
            "ethernet_mac_address": None,
            "cloud_id": None
        }

    def _get_default_show_inventory_metrics(self) -> Dict[str, Any]:
        """Get default show_inventory metrics dictionary with all expected fields initialized.
        
        Returns:
            Dictionary with show_inventory metrics fields initialized
        """
        return {
            "inv_parser_found": False,
            "inv_ap_type": None,
            "inv_ap_descr": None,
            "inv_ap_pid": None,
            "inv_ap_vid": None,
            "inv_ap_serial": None,
            "inv_ap_devid": None,
            "inv_usb_detected": None,
            "inv_usb_status": None,
            "inv_usb_pid": None,
            "inv_usb_vid": None,
            "inv_usb_manuf": None,
            "inv_usb_descr": None,
            "inv_usb_serial": None,
            "inv_usb_max_power": None
        }

    def _extract_show_inventory_metrics(self, content: str) -> Dict[str, Any]:
        """Extract show_inventory metrics from the content.
        
        Args:
            content: Raw file content
            
        Returns:
            Dictionary of show_inventory metrics
        """
        metrics = self._get_default_show_inventory_metrics()
        
        # Find the show inventory section with more flexible pattern matching
        # Look for the command itself first
        show_inv_cmd = re.search(r'(?:^|\n)([^\n#]+)#\s*show\s+inventory', content, re.IGNORECASE)
        if not show_inv_cmd:
            # Try asterisk format as a fallback
            asterisk_match = re.search(r'\*{5}\s*show\s+inventory\s*\*{5}([\s\S]+?)(?=\n\*{5}|\Z)', content, re.IGNORECASE)
            if asterisk_match:
                section = asterisk_match.group(1)
                metrics["inv_parser_found"] = True
            else:
                return metrics  # Section not found
        else:
            # We found the command, now extract content up to next command prompt
            ap_prompt = show_inv_cmd.group(1).strip()
            cmd_pos = show_inv_cmd.end()
            next_prompt = re.search(r'\n' + re.escape(ap_prompt) + r'#', content[cmd_pos:])
            
            if next_prompt:
                # Extract content between command and next prompt
                section = content[cmd_pos:cmd_pos + next_prompt.start()]
            else:
                # If no next prompt, take a reasonable chunk of text
                section = content[cmd_pos:cmd_pos + 2000]  # Limit to 2000 chars to avoid taking too much
            
            metrics["inv_parser_found"] = True
        
        # Parse NAME and DESCR with more flexible pattern matching
        name_descr_match = re.search(r'NAME\s*:\s*([^,]+),\s*DESCR\s*:\s*([^\n]+)', section, re.IGNORECASE)
        if name_descr_match:
            metrics["inv_ap_type"] = name_descr_match.group(1).strip()
            metrics["inv_ap_descr"] = name_descr_match.group(2).strip()
        
        # Parse PID, VID, SN with more flexible pattern
        pid_vid_sn_match = re.search(r'PID\s*:\s*([^,]+)\s*,\s*VID\s*:\s*([^,]+),\s*SN\s*:\s*([^\n]+)', section, re.IGNORECASE)
        if pid_vid_sn_match:
            metrics["inv_ap_pid"] = pid_vid_sn_match.group(1).strip()
            metrics["inv_ap_vid"] = pid_vid_sn_match.group(2).strip()
            metrics["inv_ap_serial"] = pid_vid_sn_match.group(3).strip()
        
        # Parse DEVID with more flexible pattern
        devid_match = re.search(r'DEVID\s*:\s*([^\n]+)', section, re.IGNORECASE)
        if devid_match:
            metrics["inv_ap_devid"] = devid_match.group(1).strip()
        
        # Parse USB fields (if present) with more flexible patterns
        usb_fields = [
            ("inv_usb_detected", r'Detected\s*:\s*([^\n]+)'),
            ("inv_usb_status", r'Status\s*:\s*([^\n]+)'),
            ("inv_usb_pid", r'Product ID\s*:\s*([^\n]+)'),
            ("inv_usb_vid", r'Vendor ID\s*:\s*([^\n]+)'),
            ("inv_usb_manuf", r'Manufacturer\s*:\s*([^\n]+)'),
            ("inv_usb_descr", r'Description\s*:\s*([^\n]+)'),
            ("inv_usb_serial", r'Serial Number\s*:\s*([^\n]+)'),
            ("inv_usb_max_power", r'Max Power\s*:\s*([^\n]+)')
        ]
        
        for field_name, pattern in usb_fields:
            match = re.search(pattern, section, re.IGNORECASE)
            if match:
                metrics[field_name] = match.group(1).strip()
        
        # Debug logging if needed (you can include logging to see what's happening)
        # if not any(v for k, v in metrics.items() if k != "inv_parser_found"):
        #     # No values were parsed, log the section for debugging
        #     print(f"Failed to parse inventory section: {section[:200]}...")
        
        return metrics

    def _extract_show_version_metrics(self, content: str) -> Dict[str, Any]:
        """Extract show_version metrics from the content.

        Args:
            content: Raw file content

        Returns:
            Dictionary of show_version metrics
        """
        metrics = self._get_default_show_version_metrics()

        # Find the show version section (prompt or asterisk style)
        prompt_match = re.search(r'(^|\n)([^\n#]+)#show version[\s\S]+?\n\2#', content, re.IGNORECASE)
        if prompt_match:
            section = prompt_match.group(0)
        else:
            # Asterisk-based: ***** show version ***** ... *****
            asterisk_match = re.search(r'\*{5} show version \*{5}[\s\S]+?(?=\n\*{5} )', content, re.IGNORECASE)
            if asterisk_match:
                section = asterisk_match.group(0)
            else:
                return metrics  # Section not found

        # ap_name: <name> uptime is X days, Y hours, Z minutes
        ap_name_match = re.search(r'^(.*?) uptime is (\d+) days, (\d+) hours, (\d+) minutes', section, re.MULTILINE)
        if ap_name_match:
            metrics["ver_ap_name"] = ap_name_match.group(1).strip()
            try:
                metrics["ap_uptime_days"] = int(ap_name_match.group(2))
                metrics["ap_uptime_hours"] = int(ap_name_match.group(3))
                metrics["ap_uptime_minutes"] = int(ap_name_match.group(4))
            except Exception:
                pass

        # Extract various fields using regex patterns
        fields_to_extract = [
            ("ap_serial_number", r'Top Assembly Serial Number\s*:\s*([^\n]+)'),
            ("ap_model", r'Product/Model Number\s*:\s*([^\n]+)'),
            ("ap_running_image", r'AP Running Image\s*:\s*([^\n]+)'),
            ("last_reload_time", r'Last reload time\s*:\s*([^\n]+)'),
            ("ethernet_mac_address", r'Base ethernet MAC Address\s*:\s*([^\n]+)'),
            ("cloud_id", r'Cloud ID\s*:\s*([^\n]+)')
        ]
        
        for field_name, pattern in fields_to_extract:
            match = re.search(pattern, section)
            if match:
                metrics[field_name] = match.group(1).strip()

        # ap_image_family and ap_image_string: Cisco AP Software, (ap1g6a), C9166, RELEASE SOFTWARE
        image_line_match = re.search(r'Cisco AP Software, \(([^)]+)\),\s*([^\n]+)', section)
        if image_line_match:
            metrics["ap_image_family"] = image_line_match.group(1).strip()
            # Everything after "), "
            after_paren = section[image_line_match.end(1)+2:].split("\n", 1)[0].strip()
            metrics["ap_image_string"] = after_paren

        # last_reload_reason with special handling
        last_reload_reason_match = re.search(
            r"^Last reload reason\s*:\s*(.*)$", section, re.MULTILINE
        )
        if last_reload_reason_match:
            # Defensive: If the entire line is just 'Last reload reason :' (with or without whitespace), set to None
            if last_reload_reason_match.group(0).strip() == "Last reload reason :":
                metrics["last_reload_reason"] = None
            else:
                value = last_reload_reason_match.group(1)
                if value.strip() == "":
                    metrics["last_reload_reason"] = None
                else:
                    metrics["last_reload_reason"] = value

        return metrics

    def _extract_gnss_postprocessor_metrics(self, content: str) -> Dict[str, Any]:
        """Extract GNSS_PostProcessor metrics from the content.
        
        Args:
            content: Raw file content
            
        Returns:
            Dictionary of GNSS_PostProcessor metrics
        """
        metrics = self._get_default_gnss_postprocessor_metrics()
        
        # Check if GNSS_PostProcessor section exists
        postprocessor_match = re.search(r'GNSS_PostProcessor:', content, re.IGNORECASE)
        if not postprocessor_match:
            return metrics
        
        # Mark parser_found as true since we found the section
        metrics["gnss_pp_parser_found"] = True
        
        # Check if it's "N/A"
        if re.search(r'GNSS_PostProcessor:\s*N/A', content, re.IGNORECASE):
            metrics["not_available"] = True
            return metrics
        
        # Extract the GNSS_PostProcessor section
        section_start = postprocessor_match.start()
        
        # Find the end of the section (next major section or end of content)
        next_section_match = re.search(r'\n\n', content[section_start:])
        if next_section_match:
            section_end = section_start + next_section_match.start()
            section_content = content[section_start:section_end]
        else:
            section_content = content[section_start:]
        
        # Extract latitude and longitude
        fields_to_extract = [
            ("latitude", r'Latitude:\s*([\d\.-]+)', float),
            ("longitude", r'Longitude:\s*([\d\.-]+)', float),
            ("altitude_msl", r'Altitude MSL:\s*([\d\.]+)', float),
            ("altitude_hae", r'HAE:\s*([\d\.]+)', float),
            ("vertacc", r'VertAcc:\s*([\d\.]+)', float)
        ]
        
        for field_name, pattern, conversion in fields_to_extract:
            match = re.search(pattern, section_content, re.IGNORECASE)
            if match:
                try:
                    metrics[field_name] = conversion(match.group(1))
                except (ValueError, TypeError):
                    pass
        
        # Extract horizontal accuracy and HDOP
        horacc_hdop_match = re.search(r'HorAcc:\s*([\d\.]+)\s+hDOP:\s*([\d\.]+)', section_content, re.IGNORECASE)
        if horacc_hdop_match:
            try:
                metrics["horacc"] = float(horacc_hdop_match.group(1))
                metrics["horacc_hdop"] = float(horacc_hdop_match.group(2))
            except (ValueError, TypeError):
                pass
        
        # Extract uncertainty ellipse
        uncertainty_match = re.search(r'Major axis:\s*([\d\.]+)\s+Minor axis:\s*([\d\.]+)\s+Orientation:\s*([\d\.]+)', 
                                    section_content, re.IGNORECASE)
        if uncertainty_match:
            try:
                metrics["uncertainty_ellipse_major_axis"] = float(uncertainty_match.group(1))
                metrics["uncertainty_ellipse_minor_axis"] = float(uncertainty_match.group(2))
                metrics["uncertainty_ellipse_orientation"] = float(uncertainty_match.group(3))
            except (ValueError, TypeError):
                pass
        
        return metrics

    def _extract_cisco_gnss_metrics(self, content: str) -> Dict[str, Any]:
        """Extract cisco_gnss metrics from the content.
        
        Args:
            content: Raw file content
            
        Returns:
            Dictionary of cisco_gnss metrics
        """
        metrics = self._get_default_cisco_gnss_metrics()
        
        # Check if CiscoGNSS section exists
        cisco_gnss_match = re.search(r'CiscoGNSS:', content, re.IGNORECASE)
        if not cisco_gnss_match:
            return metrics
        
        # Mark parser_found as true since we found the section
        metrics["cisco_gnss_parser_found"] = True
        
        # Check if it's "N/A"
        if re.search(r'CiscoGNSS:\s*N/A', content, re.IGNORECASE):
            metrics["not_available"] = True
            return metrics
        
        # Extract the CiscoGNSS section
        section_start = cisco_gnss_match.start()
        
        # Find the end of the section (next major section or end of content)
        next_section_match = re.search(r'\n\n', content[section_start:])
        if next_section_match:
            section_end = section_start + next_section_match.start()
            section_content = content[section_start:section_end]
        else:
            section_content = content[section_start:]
        
        # Extract numeric fields
        fields_to_extract = [
            ("latitude", r'Latitude:\s*([\d\.-]+)', float),
            ("longitude", r'Longitude:\s*([\d\.-]+)', float),
            ("altitude_msl", r'Altitude MSL:\s*([\d\.]+)', float),
            ("altitude_hae", r'HAE:\s*([\d\.]+)', float),
            ("vertacc", r'VertAcc:\s*([\d\.]+)', float)
        ]
        
        for field_name, pattern, conversion in fields_to_extract:
            match = re.search(pattern, section_content, re.IGNORECASE)
            if match:
                try:
                    metrics[field_name] = conversion(match.group(1))
                except (ValueError, TypeError):
                    pass
        
        # Extract horizontal accuracy and HDOP
        horacc_hdop_match = re.search(r'HorAcc:\s*([\d\.]+)\s+hDOP:\s*([\d\.]+)', section_content, re.IGNORECASE)
        if horacc_hdop_match:
            try:
                metrics["horacc"] = float(horacc_hdop_match.group(1))
                metrics["horacc_hdop"] = float(horacc_hdop_match.group(2))
            except (ValueError, TypeError):
                pass
        
        # Extract uncertainty ellipse
        uncertainty_match = re.search(r'Major axis:\s*([\d\.]+)\s+Minor axis:\s*([\d\.]+)\s+Orientation:\s*([\d\.]+)', 
                                    section_content, re.IGNORECASE)
        if uncertainty_match:
            try:
                metrics["uncertainty_ellipse_major_axis"] = float(uncertainty_match.group(1))
                metrics["uncertainty_ellipse_minor_axis"] = float(uncertainty_match.group(2))
                metrics["uncertainty_ellipse_orientation"] = float(uncertainty_match.group(3))
            except (ValueError, TypeError):
                pass
        
        return metrics

    def _extract_last_location_acquired_metrics(self, content: str) -> Dict[str, Any]:
        """Extract last_location_acquired metrics from the content.
        
        Args:
            content: Raw file content
            
        Returns:
            Dictionary of last_location_acquired metrics
        """
        metrics = self._get_default_last_location_acquired_metrics()
        
        # Check if Last Location Acquired section exists
        last_location_match = re.search(r'Last Location Acquired:', content, re.IGNORECASE)
        if not last_location_match:
            return metrics
        
        # Mark parser_found as true since we found the section
        metrics["last_location_parser_found"] = True
        
        # Check if it's "N/A"
        if re.search(r'Last Location Acquired:\s*N/A', content, re.IGNORECASE):
            metrics["not_available"] = True
            return metrics
        
        # Extract the Last Location Acquired section
        section_start = last_location_match.start()
        
        # Find the end of the section (next major section or end of content)
        next_section_match = re.search(r'\n\n', content[section_start:])
        if next_section_match:
            section_end = section_start + next_section_match.start()
            section_content = content[section_start:section_end]
        else:
            section_content = content[section_start:]
        
        # Extract numeric fields
        fields_to_extract = [
            ("latitude", r'Latitude:\s*([\d\.-]+)', float),
            ("longitude", r'Longitude:\s*([\d\.-]+)', float),
            ("altitude_msl", r'Altitude MSL:\s*([\d\.]+)', float),
            ("altitude_hae", r'HAE:\s*([\d\.]+)', float),
            ("vertacc", r'VertAcc:\s*([\d\.]+)', float)
        ]
        
        for field_name, pattern, conversion in fields_to_extract:
            match = re.search(pattern, section_content, re.IGNORECASE)
            if match:
                try:
                    metrics[field_name] = conversion(match.group(1))
                except (ValueError, TypeError):
                    pass
        
        # Extract horizontal accuracy and HDOP
        horacc_hdop_match = re.search(r'HorAcc:\s*([\d\.]+)\s+hDOP:\s*([\d\.]+)', section_content, re.IGNORECASE)
        if horacc_hdop_match:
            try:
                metrics["horacc"] = float(horacc_hdop_match.group(1))
                metrics["horacc_hdop"] = float(horacc_hdop_match.group(2))
            except (ValueError, TypeError):
                pass
        
        # Extract uncertainty ellipse
        uncertainty_match = re.search(r'Major axis:\s*([\d\.]+)\s+Minor axis:\s*([\d\.]+)\s+Orientation:\s*([\d\.]+)', 
                                    section_content, re.IGNORECASE)
        if uncertainty_match:
            try:
                metrics["uncertainty_ellipse_major_axis"] = float(uncertainty_match.group(1))
                metrics["uncertainty_ellipse_minor_axis"] = float(uncertainty_match.group(2))
                metrics["uncertainty_ellipse_orientation"] = float(uncertainty_match.group(3))
            except (ValueError, TypeError):
                pass
        
        # Extract derivation type and time
        derivation_type_match = re.search(r'Derivation Type:\s*([^\n]+)', section_content, re.IGNORECASE)
        if derivation_type_match:
            metrics["derivation_type"] = derivation_type_match.group(1).strip()
        
        derivation_time_match = re.search(r'Time:\s*([\d-]+\s+[\d:]+)', section_content, re.IGNORECASE)
        if derivation_time_match:
            metrics["derivation_time"] = derivation_time_match.group(1).strip()
        
        return metrics

    def _extract_satellite_data(self, content: str) -> List[Dict[str, Any]]:
        """Extract satellite data from the content.
        
        Args:
            content: Raw file content
            
        Returns:
            List of dictionaries containing satellite data
        """
        satellites = []
        
        # Look for satellite data in table format
        table_match = re.search(r'Const\.', content, re.IGNORECASE)
        
        if table_match:
            table_start = table_match.start()
            table_lines = content[table_start:].split('\n')
            headers = re.split(r'\s+', table_lines[0].strip())
            
            # Process each line that might contain satellite data
            for i in range(1, min(50, len(table_lines))):  # Limit to first 50 lines
                line = table_lines[i].strip()
                if not line:
                    continue
                    
                # Check if this looks like satellite data (starts with GPS, GLONASS, Galileo, etc.)
                if any(line.upper().startswith(system) for system in ["GPS", "GLONASS", "GALILEO", "BEIDOU"]):
                    parts = re.split(r'\s+', line)
                    if len(parts) >= 5:  # Minimal validation - needs at least a few columns
                        satellite = {"constellation": parts[0]}
                        
                        # Add as many fields as available
                        for j in range(1, min(len(parts), len(headers))):
                            key = headers[j].lower() if j < len(headers) else f"field_{j}"
                            try:
                                # Try to convert to int or float if appropriate
                                if parts[j].isdigit():
                                    satellite[key] = int(parts[j])
                                elif re.match(r'^[\d\.]+$', parts[j]):
                                    satellite[key] = float(parts[j])
                                else:
                                    satellite[key] = parts[j]
                            except:
                                satellite[key] = parts[j]
                        
                        satellites.append(satellite)
                elif re.match(r'^=', line) or re.search(r'example-', line, re.IGNORECASE):
                    # End of table detected
                    break
        
        return satellites

    def _extract_raw_data(self, content: str) -> Dict[str, Any]:
        """Extract raw key-value pairs from the content.
        
        Args:
            content: Raw file content
            
        Returns:
            Dictionary containing raw key-value pairs
        """
        raw_data = {}
        
        # Look for key-value pairs with flexible pattern
        kv_pattern = r'([A-Za-z0-9_]+(?:\s+[A-Za-z0-9_]+)*)(?:\s*:)\s*([\d\.\-]+|[A-Za-z0-9]+(?:\s+[A-Za-z0-9]+)*)'
        
        for match in re.finditer(kv_pattern, content):
            key = match.group(1).strip().replace(" ", "_").lower()
            value = match.group(2).strip()
            
            # Convert value to appropriate type if possible
            if value.lower() == "true" or value.lower() == "false":
                raw_data[key] = value.lower() == "true"
            else:
                try:
                    if "." in value:
                        raw_data[key] = float(value)
                    else:
                        raw_data[key] = int(value)
                except ValueError:
                    raw_data[key] = value
        
        return raw_data

    def get_version(self) -> str:
        """Get parser version.
        
        Returns:
            Parser version string
        """
        return self.version