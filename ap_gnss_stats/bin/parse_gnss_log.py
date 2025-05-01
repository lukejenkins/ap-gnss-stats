#!/usr/bin/env python3
"""
GNSS Log Parser - Converts PuTTY GNSS logs to structured JSON format

This script parses PuTTY logs containing GNSS (Global Navigation Satellite System)
information and converts it to a structured JSON format for easier analysis.
Supports multiple input files and directory wildcard patterns.

IMPORTANT NOTES:
- All parsing for "show" commands (e.g., "show gnss info", "show clock") is case insensitive.
  Future parsers for any additional "show" commands must also ignore case.
- All fields defined in the schema will be present in the output JSON, even if their values are null.

Dependencies:
    - Python 3.7+
    - aiofiles (optional, for async I/O)
"""

import re
import json
import argparse
import os
import sys
import glob
import time
from typing import Dict, List, Any, Optional, Union, Set, Tuple
from datetime import datetime
from pathlib import Path
import asyncio
import concurrent.futures
from collections import OrderedDict

# ================================================================================
# JSON OUTPUT SCHEMA
# ================================================================================
# All fields in this schema will be present in the output, even if their values are null.
# {
#   "metadata": {
#     "parser_version": "string",         # Version of the parser
#     "parse_time": "ISO-8601 datetime",  # IMPORTANT: Must use dynamic timestamp
#     "input_file": "string",             # Base filename of the input file
#     "file_size": number                 # Size of the input file in bytes
#     # NO parser_user field per requirements
#     # NO processing_time_seconds field per requirements
#   },
#   "main": {
#     "ap_name": "string | null",         # Access point name extracted from command prompt
#     "show_clock_time": "string | null"  # Clock time from "show clock" command (first occurrence)
#   },
#   "gnss_state": {
#     "no_gnss_detected": boolean,        # Whether "No GNSS detected" message was found
#     
#     # Fields below are only present if GNSS is detected, otherwise null
#     "state": "string | null",                  # GNSS state (e.g., "Ready")
#     "external_antenna": "boolean | null",      # Whether external antenna is used
#     "fix_type": "string | null",               # Type of fix
#     "valid_fix": "boolean | null",             # Whether the fix is valid
#     "gnss_fix_time": "string | null",          # Time of the GNSS fix
#     "last_fix_time": "string | null",          # Time of the last fix
#     "latitude": "number | null",               # Latitude in degrees
#     "longitude": "number | null",              # Longitude in degrees
#     "horacc": "number | null",                 # Horizontal accuracy
#     "horacc_hdop": "number | null",            # Horizontal dilution of precision
#     "altitude_msl": "number | null",           # Altitude above mean sea level
#     "altitude_hae": "number | null",           # Height above ellipsoid
#     "vertacc": "number | null",                # Vertical accuracy
#     "numsat": "number | null",                 # Number of satellites used
#     "rangeres": "number | null",               # Range residual
#     "gpgstrms": "number | null",               # GPGST RMS value
#     "satellitecount": "number | null",         # Total satellite count
#     
#     # Uncertainty ellipse (if available, otherwise null)
#     "uncertainty_ellipse_major_axis": "number | null",    # Major axis of uncertainty ellipse
#     "uncertainty_ellipse_minor_axis": "number | null",    # Minor axis of uncertainty ellipse
#     "uncertainty_ellipse_orientation": "number | null",   # Orientation of uncertainty ellipse
#     
#     # DOP parameters (if available, otherwise null)
#     "pdop": "number | null",                   # Position dilution of precision
#     "hdop": "number | null",                   # Horizontal dilution of precision
#     "vdop": "number | null",                   # Vertical dilution of precision
#     "ndop": "number | null",                   # North dilution of precision
#     "edop": "number | null",                   # East dilution of precision
#     "gdop": "number | null",                   # Geometric dilution of precision
#     "tdop": "number | null"                    # Time dilution of precision
#   },
#   "gnss_postprocessor": {
#     "parser_found": boolean,                   # true if the parser found the string "GNSS_PostProcessor:" in the output of a 'show gnss info' command
#     "not_available": boolean,                  # true if the output of 'show gnss info' includes the line "GNSS_PostProcessor: N/A"  
#     "latitude": "number | null",               # Latitude in decimal degrees from this section
#     "longitude": "number | null",              # Longitude in decimal degrees from this section
#     "horacc": "number | null",                 # Horizontal accuracy for this section in meters
#     "horacc_hdop": "number | null",            # Horizontal dilution of precision for this section
#     
#     # Uncertainty ellipse from this section (if available, otherwise null)
#     "uncertainty_ellipse_major_axis": "number | null",    # Major axis of uncertainty ellipse from this section
#     "uncertainty_ellipse_minor_axis": "number | null",    # Minor axis of uncertainty ellipse from this section
#     "uncertainty_ellipse_orientation": "number | null",   # Orientation of uncertainty ellipse from this section
#
#     "altitude_msl": "number | null",           # Altitude above mean sea level in meters from this section
#     "altitude_hae": "number | null",           # Height above ellipsoid in meters from this section
#     "vertacc": "number | null",                # Vertical accuracy from this section
#   },
#   "cisco_gnss": {
#     "parser_found": boolean,                   # true if the parser found the string "CiscoGNSS:" in the output of a 'show gnss info' command
#     "not_available": boolean,                  # true if the output of 'show gnss info' includes the line "CiscoGNSS: N/A"  
#     "latitude": "number | null",               # Latitude in decimal degrees from this section
#     "longitude": "number | null",              # Longitude in decimal degrees from this section
#     "horacc": "number | null",                 # Horizontal accuracy for this section in meters
#     "horacc_hdop": "number | null",            # Horizontal dilution of precision for this section
#     
#     # Uncertainty ellipse from this section (if available, otherwise null)
#     "uncertainty_ellipse_major_axis": "number | null",    # Major axis of uncertainty ellipse from this section
#     "uncertainty_ellipse_minor_axis": "number | null",    # Minor axis of uncertainty ellipse from this section
#     "uncertainty_ellipse_orientation": "number | null",   # Orientation of uncertainty ellipse from this section
#
#     "altitude_msl": "number | null",           # Altitude above mean sea level in meters from this section
#     "altitude_hae": "number | null",           # Height above ellipsoid in meters from this section
#     "vertacc": "number | null",                # Vertical accuracy from this section
#   },
#   "last_location_acquired": {
#     "parser_found": boolean,                   # true if the parser found the string "Last Location Acquired:" in the output of a 'show gnss info' command
#     "not_available": boolean,                  # true if the output of 'show gnss info' includes the line "Last Location Acquired: N/A"   
#     "latitude": "number | null",               # Latitude in decimal degrees from this section
#     "longitude": "number | null",              # Longitude in decimal degrees from this section
#     "horacc": "number | null",                 # Horizontal accuracy for this section in meters
#     "horacc_hdop": "number | null",            # Horizontal dilution of precision for this section
#     
#     # Uncertainty ellipse from this section (if available, otherwise null)
#     "uncertainty_ellipse_major_axis": "number | null",    # Major axis of uncertainty ellipse from this section
#     "uncertainty_ellipse_minor_axis": "number | null",    # Minor axis of uncertainty ellipse from this section
#     "uncertainty_ellipse_orientation": "number | null",   # Orientation of uncertainty ellipse from this section
#
#     "altitude_msl": "number | null",           # Altitude above mean sea level in meters from this section
#     "altitude_hae": "number | null",           # Height above ellipsoid in meters from this section
#     "vertacc": "number | null",                # Vertical accuracy from this section
#     "derivation_type": "string | null",        # Value for "Derivation Type:", example outputs include 'GNSS_PostProcessor', and 'GNSS_Receiver'. There may be other values.
#     "derivation_time": "string | null"         # Time for the values in "last_location_acquired" section.
#   },
#   "satellites": [                       # Array of satellite objects, may be empty
#     {
#       "constellation": "string",        # Satellite constellation (GPS, GLONASS, Galileo, BeiDou)
#       "prn": number,                    # Satellite PRN number
#       "elevation": number,              # Elevation angle in degrees
#       "azimuth": number,                # Azimuth angle in degrees
#       "snr": number,                    # Signal-to-noise ratio
#       "used": boolean                   # Whether the satellite is used in the solution
#       # Additional fields may be present depending on the input data
#     }
#   ]
#   # "raw_data" section is optional and only included if --include-raw is specified
# }
# ================================================================================

# Check if aiofiles is available for async I/O
try:
    import aiofiles
    ASYNC_AVAILABLE = True
except ImportError:
    ASYNC_AVAILABLE = False


def examine_file(file_path: str) -> Dict[str, Any]:
    """
    Examine file contents to determine what format it might be in.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Dictionary with file analysis
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            
        # Get basic file info
        file_info = {
            "file_path": file_path,
            "file_size": os.path.getsize(file_path),
            "content_length": len(content),
            "line_count": content.count('\n') + 1
        }
        
        # Check for common patterns
        patterns = [
            "PuTTY log", "show gnss info", "GnssState:", "Latitude:", "Longitude:",
            "SatelliteCount:", "Constellation", "GPS", "Galileo", "Elevation",
            "Azimuth", "GNSS_PostProcessor", "CiscoGNSS", "No GNSS detected",
            "show clock", "Last Location Acquired"
        ]
        
        pattern_matches = {}
        for pattern in patterns:
            matches = list(re.finditer(re.escape(pattern), content, re.IGNORECASE))
            pattern_matches[pattern] = {
                "count": len(matches),
                "positions": [m.start() for m in matches][:5]  # First 5 positions
            }
            
        file_info["pattern_matches"] = pattern_matches
        
        # Get first few lines for inspection
        lines = content.split('\n')
        file_info["first_lines"] = lines[:min(10, len(lines))]
        
        # Try to determine the format
        if "PuTTY log" in content:
            file_info["likely_format"] = "PuTTY log"
        elif re.search(r'show gnss info', content, re.IGNORECASE):
            file_info["likely_format"] = "GNSS info output"
        elif "gnss" in content.lower() and ("latitude" in content.lower() or "longitude" in content.lower()):
            file_info["likely_format"] = "GNSS data (alternative format)"
        else:
            file_info["likely_format"] = "Unknown format"
            
        return file_info
        
    except Exception as e:
        return {
            "error": str(e),
            "file_path": file_path
        }


async def examine_file_async(file_path: str) -> Dict[str, Any]:
    """
    Examine file contents asynchronously to determine what format it might be in.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Dictionary with file analysis
    """
    try:
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as file:
            content = await file.read()
            
        # Get basic file info
        file_info = {
            "file_path": file_path,
            "file_size": os.path.getsize(file_path),
            "content_length": len(content),
            "line_count": content.count('\n') + 1
        }
        
        # Check for common patterns
        patterns = [
            "PuTTY log", "show gnss info", "GnssState:", "Latitude:", "Longitude:",
            "SatelliteCount:", "Constellation", "GPS", "Galileo", "Elevation",
            "Azimuth", "GNSS_PostProcessor", "CiscoGNSS", "No GNSS detected",
            "show clock", "Last Location Acquired"
        ]
        
        pattern_matches = {}
        for pattern in patterns:
            matches = list(re.finditer(re.escape(pattern), content, re.IGNORECASE))
            pattern_matches[pattern] = {
                "count": len(matches),
                "positions": [m.start() for m in matches][:5]  # First 5 positions
            }
            
        file_info["pattern_matches"] = pattern_matches
        
        # Get first few lines for inspection
        lines = content.split('\n')
        file_info["first_lines"] = lines[:min(10, len(lines))]
        
        # Try to determine the format
        if "PuTTY log" in content:
            file_info["likely_format"] = "PuTTY log"
        elif re.search(r'show gnss info', content, re.IGNORECASE):
            file_info["likely_format"] = "GNSS info output"
        elif "gnss" in content.lower() and ("latitude" in content.lower() or "longitude" in content.lower()):
            file_info["likely_format"] = "GNSS data (alternative format)"
        else:
            file_info["likely_format"] = "Unknown format"
            
        return file_info
        
    except Exception as e:
        return {
            "error": str(e),
            "file_path": file_path
        }


def extract_ap_name(content: str) -> str:
    """
    Extract the AP name from the content.
    
    Args:
        content: Raw file content
        
    Returns:
        String containing the AP name, or empty string if not found
    """
    # Look for pattern: <name>#show gnss info
    # Updated pattern to correctly match only up to the # in the line and be case insensitive
    pattern = r'(?:^|\n)([^\n#]+)#show gnss info'
    match = re.search(pattern, content, re.IGNORECASE)
    
    if match:
        return match.group(1).strip()
    
    return ""


def extract_show_clock_time(content: str) -> str:
    """
    Extract the clock time from 'show clock' command output.
    
    Args:
        content: Raw file content
        
    Returns:
        String containing the clock time, or empty string if not found
    """
    # Look for pattern: #show clock followed by a time line like *23:34:47 UTC+0000 Tue Apr 29 2025
    # Make it case insensitive
    pattern = r'show clock\s*\n\s*\*([^\n]+)'
    match = re.search(pattern, content, re.IGNORECASE)
    
    if match:
        return match.group(1).strip()
    
    return ""


def get_default_main_metrics() -> Dict[str, Any]:
    """
    Get default main metrics dictionary with all expected fields initialized to None.
    
    Returns:
        Dictionary with main metrics fields set to None
    """
    return {
        "ap_name": None,
        "show_clock_time": None
    }


def get_default_gnss_state_metrics() -> Dict[str, Any]:
    """
    Get default GNSS state metrics dictionary with all expected fields initialized to None.
    
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


def get_default_gnss_postprocessor_metrics() -> Dict[str, Any]:
    """
    Get default GNSS_PostProcessor metrics dictionary with all expected fields initialized.
    
    Returns:
        Dictionary with all GNSS_PostProcessor metrics fields initialized
    """
    return {
        "parser_found": False,
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


def get_default_cisco_gnss_metrics() -> Dict[str, Any]:
    """
    Get default cisco_gnss metrics dictionary with all expected fields initialized.
    
    Returns:
        Dictionary with all cisco_gnss metrics fields initialized
    """
    return {
        "parser_found": False,
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


def get_default_last_location_acquired_metrics() -> Dict[str, Any]:
    """
    Get default last_location_acquired metrics dictionary with all expected fields initialized.
    
    Returns:
        Dictionary with all last_location_acquired metrics fields initialized
    """
    return {
        "parser_found": False,
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


def extract_gnss_metrics(content: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Extract main and GNSS state metrics from the content.
    
    Args:
        content: Raw file content
        
    Returns:
        Tuple of (main metrics dictionary, gnss state metrics dictionary)
    """
    # Initialize metrics dictionaries with all expected fields
    main_metrics = get_default_main_metrics()
    gnss_state_metrics = get_default_gnss_state_metrics()
    
    # Extract AP name and add it to the main metrics
    ap_name = extract_ap_name(content)
    if ap_name:
        main_metrics["ap_name"] = ap_name
    
    # Extract clock time from 'show clock' command and add to main metrics
    show_clock_time = extract_show_clock_time(content)
    if show_clock_time:
        main_metrics["show_clock_time"] = show_clock_time
    
    # Check for "No GNSS detected" message
    # Look for pattern of "show gnss info" followed by "No GNSS detected"
    # Make it case insensitive
    no_gnss_pattern = r'show gnss info\s*\n\s*No GNSS detected'
    gnss_state_metrics["no_gnss_detected"] = bool(re.search(no_gnss_pattern, content, re.IGNORECASE))
    
    # If no GNSS detected, we can return early as there won't be any metrics
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
                gnss_state_metrics[key] = value.lower() == "true"
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


def extract_gnss_postprocessor_metrics(content: str) -> Dict[str, Any]:
    """
    Extract GNSS_PostProcessor metrics from the content.
    
    Args:
        content: Raw file content
        
    Returns:
        Dictionary of GNSS_PostProcessor metrics
    """
    # Initialize metrics dictionary with defaults
    metrics = get_default_gnss_postprocessor_metrics()
    
    # Check if GNSS_PostProcessor section exists
    postprocessor_match = re.search(r'GNSS_PostProcessor:', content, re.IGNORECASE)
    if not postprocessor_match:
        return metrics
    
    # Mark parser_found as true since we found the section
    metrics["parser_found"] = True
    
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
    lat_match = re.search(r'Latitude:\s*([\d\.-]+)', section_content, re.IGNORECASE)
    if lat_match:
        metrics["latitude"] = float(lat_match.group(1))
    
    lon_match = re.search(r'Longitude:\s*([\d\.-]+)', section_content, re.IGNORECASE)
    if lon_match:
        metrics["longitude"] = float(lon_match.group(1))
    
    # Extract horizontal accuracy and HDOP
    horacc_hdop_match = re.search(r'HorAcc:\s*([\d\.]+)\s+hDOP:\s*([\d\.]+)', section_content, re.IGNORECASE)
    if horacc_hdop_match:
        metrics["horacc"] = float(horacc_hdop_match.group(1))
        metrics["horacc_hdop"] = float(horacc_hdop_match.group(2))
    
    # Extract uncertainty ellipse
    uncertainty_match = re.search(r'Major axis:\s*([\d\.]+)\s+Minor axis:\s*([\d\.]+)\s+Orientation:\s*([\d\.]+)', 
                                 section_content, re.IGNORECASE)
    if uncertainty_match:
        metrics["uncertainty_ellipse_major_axis"] = float(uncertainty_match.group(1))
        metrics["uncertainty_ellipse_minor_axis"] = float(uncertainty_match.group(2))
        metrics["uncertainty_ellipse_orientation"] = float(uncertainty_match.group(3))
    
    # Extract altitude and vertical accuracy
    alt_msl_match = re.search(r'Altitude MSL:\s*([\d\.]+)', section_content, re.IGNORECASE)
    if alt_msl_match:
        metrics["altitude_msl"] = float(alt_msl_match.group(1))
    
    alt_hae_match = re.search(r'HAE:\s*([\d\.]+)', section_content, re.IGNORECASE)
    if alt_hae_match:
        metrics["altitude_hae"] = float(alt_hae_match.group(1))
    
    vertacc_match = re.search(r'VertAcc:\s*([\d\.]+)', section_content, re.IGNORECASE)
    if vertacc_match:
        metrics["vertacc"] = float(vertacc_match.group(1))
    
    return metrics


def extract_cisco_gnss_metrics(content: str) -> Dict[str, Any]:
    """
    Extract cisco_gnss metrics from the content.
    
    Args:
        content: Raw file content
        
    Returns:
        Dictionary of cisco_gnss metrics
    """
    # Initialize metrics dictionary with defaults
    metrics = get_default_cisco_gnss_metrics()
    
    # Check if CiscoGNSS section exists
    cisco_gnss_match = re.search(r'CiscoGNSS:', content, re.IGNORECASE)
    if not cisco_gnss_match:
        return metrics
    
    # Mark parser_found as true since we found the section
    metrics["parser_found"] = True
    
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
    
    # Extract latitude and longitude
    lat_match = re.search(r'Latitude:\s*([\d\.-]+)', section_content, re.IGNORECASE)
    if lat_match:
        metrics["latitude"] = float(lat_match.group(1))
    
    lon_match = re.search(r'Longitude:\s*([\d\.-]+)', section_content, re.IGNORECASE)
    if lon_match:
        metrics["longitude"] = float(lon_match.group(1))
    
    # Extract horizontal accuracy and HDOP
    horacc_hdop_match = re.search(r'HorAcc:\s*([\d\.]+)\s+hDOP:\s*([\d\.]+)', section_content, re.IGNORECASE)
    if horacc_hdop_match:
        metrics["horacc"] = float(horacc_hdop_match.group(1))
        metrics["horacc_hdop"] = float(horacc_hdop_match.group(2))
    
    # Extract uncertainty ellipse
    uncertainty_match = re.search(r'Major axis:\s*([\d\.]+)\s+Minor axis:\s*([\d\.]+)\s+Orientation:\s*([\d\.]+)', 
                                 section_content, re.IGNORECASE)
    if uncertainty_match:
        metrics["uncertainty_ellipse_major_axis"] = float(uncertainty_match.group(1))
        metrics["uncertainty_ellipse_minor_axis"] = float(uncertainty_match.group(2))
        metrics["uncertainty_ellipse_orientation"] = float(uncertainty_match.group(3))
    
    # Extract altitude and vertical accuracy
    alt_msl_match = re.search(r'Altitude MSL:\s*([\d\.]+)', section_content, re.IGNORECASE)
    if alt_msl_match:
        metrics["altitude_msl"] = float(alt_msl_match.group(1))
    
    alt_hae_match = re.search(r'HAE:\s*([\d\.]+)', section_content, re.IGNORECASE)
    if alt_hae_match:
        metrics["altitude_hae"] = float(alt_hae_match.group(1))
    
    vertacc_match = re.search(r'VertAcc:\s*([\d\.]+)', section_content, re.IGNORECASE)
    if vertacc_match:
        metrics["vertacc"] = float(vertacc_match.group(1))
    
    return metrics


def extract_last_location_acquired_metrics(content: str) -> Dict[str, Any]:
    """
    Extract last_location_acquired metrics from the content.
    
    Args:
        content: Raw file content
        
    Returns:
        Dictionary of last_location_acquired metrics
    """
    # Initialize metrics dictionary with defaults
    metrics = get_default_last_location_acquired_metrics()
    
    # Check if Last Location Acquired section exists
    last_location_match = re.search(r'Last Location Acquired:', content, re.IGNORECASE)
    if not last_location_match:
        return metrics
    
    # Mark parser_found as true since we found the section
    metrics["parser_found"] = True
    
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
    
    # Extract latitude and longitude
    lat_match = re.search(r'Latitude:\s*([\d\.-]+)', section_content, re.IGNORECASE)
    if lat_match:
        metrics["latitude"] = float(lat_match.group(1))
    
    lon_match = re.search(r'Longitude:\s*([\d\.-]+)', section_content, re.IGNORECASE)
    if lon_match:
        metrics["longitude"] = float(lon_match.group(1))
    
    # Extract horizontal accuracy and HDOP
    horacc_hdop_match = re.search(r'HorAcc:\s*([\d\.]+)\s+hDOP:\s*([\d\.]+)', section_content, re.IGNORECASE)
    if horacc_hdop_match:
        metrics["horacc"] = float(horacc_hdop_match.group(1))
        metrics["horacc_hdop"] = float(horacc_hdop_match.group(2))
    
    # Extract uncertainty ellipse
    uncertainty_match = re.search(r'Major axis:\s*([\d\.]+)\s+Minor axis:\s*([\d\.]+)\s+Orientation:\s*([\d\.]+)', 
                                 section_content, re.IGNORECASE)
    if uncertainty_match:
        metrics["uncertainty_ellipse_major_axis"] = float(uncertainty_match.group(1))
        metrics["uncertainty_ellipse_minor_axis"] = float(uncertainty_match.group(2))
        metrics["uncertainty_ellipse_orientation"] = float(uncertainty_match.group(3))
    
    # Extract altitude and vertical accuracy
    alt_msl_match = re.search(r'Altitude MSL:\s*([\d\.]+)', section_content, re.IGNORECASE)
    if alt_msl_match:
        metrics["altitude_msl"] = float(alt_msl_match.group(1))
    
    alt_hae_match = re.search(r'HAE:\s*([\d\.]+)', section_content, re.IGNORECASE)
    if alt_hae_match:
        metrics["altitude_hae"] = float(alt_hae_match.group(1))
    
    vertacc_match = re.search(r'VertAcc:\s*([\d\.]+)', section_content, re.IGNORECASE)
    if vertacc_match:
        metrics["vertacc"] = float(vertacc_match.group(1))
    
    # Extract derivation type
    derivation_type_match = re.search(r'Derivation Type:\s*([^\n]+)', section_content, re.IGNORECASE)
    if derivation_type_match:
        metrics["derivation_type"] = derivation_type_match.group(1).strip()
    
    # Extract time
    derivation_time_match = re.search(r'Time:\s*([\d-]+\s+[\d:]+)', section_content, re.IGNORECASE)
    if derivation_time_match:
        metrics["derivation_time"] = derivation_time_match.group(1).strip()
    
    return metrics


def parse_flexible(content: str) -> Dict[str, Any]:
    """
    More flexible parser that searches for GNSS data without assuming a specific format.
    
    Args:
        content: Raw file content as string
        
    Returns:
        Dictionary containing parsed GNSS data
    """
    result = {
        "raw_data": {},
        "satellites": []
    }
    
    # Extract main and GNSS state metrics from the content
    main_metrics, gnss_state_metrics = extract_gnss_metrics(content)
    
    # Add both sections to the result
    result["main"] = main_metrics
    result["gnss_state"] = gnss_state_metrics
    
    # Extract GNSS_PostProcessor metrics
    result["gnss_postprocessor"] = extract_gnss_postprocessor_metrics(content)
    
    # Extract cisco_gnss metrics
    result["cisco_gnss"] = extract_cisco_gnss_metrics(content)
    
    # Extract last_location_acquired metrics
    result["last_location_acquired"] = extract_last_location_acquired_metrics(content)
    
    # If no GNSS detected, we can skip parsing detailed data
    if gnss_state_metrics["no_gnss_detected"]:
        return result
    
    # Look for key-value pairs with flexible pattern for raw_data
    kv_pattern = r'([A-Za-z0-9_]+(?:\s+[A-Za-z0-9_]+)*)(?:\s*:)\s*([\d\.\-]+|[A-Za-z0-9]+(?:\s+[A-Za-z0-9]+)*)'
    
    for match in re.finditer(kv_pattern, content):
        key = match.group(1).strip().replace(" ", "_").lower()
        value = match.group(2).strip()
        
        # Convert value to appropriate type if possible
        if value.lower() == "true" or value.lower() == "false":
            result["raw_data"][key] = value.lower() == "true"
        else:
            try:
                if "." in value:
                    result["raw_data"][key] = float(value)
                else:
                    result["raw_data"][key] = int(value)
            except ValueError:
                result["raw_data"][key] = value
    
    # Look for satellite data in table format
    # Make the search case insensitive
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
                    
                    result["satellites"].append(satellite)
            elif re.match(r'^=', line) or re.search(r'example-', line, re.IGNORECASE):
                # End of table detected
                break
    
    return result


def reorder_json(data: Dict[str, Any]) -> OrderedDict:
    """
    Reorder the JSON data to have metadata first, then main, then gnss_state, then 
    gnss_postprocessor, then cisco_gnss, then last_location_acquired, then satellites.
    
    Args:
        data: Original data dictionary
        
    Returns:
        OrderedDict with keys in the desired order
    """
    ordered = OrderedDict()
    
    # Add sections in the desired order
    if "metadata" in data:
        ordered["metadata"] = data["metadata"]
    
    if "main" in data:
        ordered["main"] = data["main"]
    
    if "gnss_state" in data:
        ordered["gnss_state"] = data["gnss_state"]
    
    if "gnss_postprocessor" in data:
        ordered["gnss_postprocessor"] = data["gnss_postprocessor"]
    
    if "cisco_gnss" in data:
        ordered["cisco_gnss"] = data["cisco_gnss"]
    
    if "last_location_acquired" in data:
        ordered["last_location_acquired"] = data["last_location_acquired"]
    
    if "satellites" in data:
        ordered["satellites"] = data["satellites"]
    
    # Add any other sections that might exist
    for key, value in data.items():
        if key not in ["metadata", "main", "gnss_state", "gnss_postprocessor", 
                      "cisco_gnss", "last_location_acquired", "satellites", "raw_data"]:
            ordered[key] = value
    
    # Add raw_data at the end if it exists and is requested
    if "raw_data" in data:
        ordered["raw_data"] = data["raw_data"]
    
    return ordered


def expand_file_paths(paths: List[str]) -> Set[str]:
    """
    Expand file paths including wildcards to actual file paths.
    
    Args:
        paths: List of file paths, possibly with wildcards
        
    Returns:
        Set of unique, expanded file paths
    """
    expanded_paths = set()
    
    for path in paths:
        # Check if path is a directory
        if os.path.isdir(path):
            # Add all text files in the directory
            for ext in ["*.txt", "*.log"]:
                pattern = os.path.join(path, ext)
                expanded_paths.update(glob.glob(pattern))
        # Check if path contains wildcards
        elif '*' in path or '?' in path or '[' in path:
            expanded_paths.update(glob.glob(path))
        # Single file
        elif os.path.exists(path):
            expanded_paths.add(path)
        else:
            print(f"Warning: Path not found: {path}")
    
    return expanded_paths


def process_file(file_path: str, args: argparse.Namespace) -> Dict[str, Any]:
    """
    Process a single file.
    
    Args:
        file_path: Path to the file
        args: Command line arguments
        
    Returns:
        Dictionary with results
    """
    start_time = time.time()
    
    try:
        # If analyze only
        if args.analyze:
            file_info = examine_file(file_path)
            output_path = args.output_dir or os.path.dirname(file_path) or '.'
            if not os.path.exists(output_path):
                os.makedirs(output_path)
            output_file = os.path.join(output_path, 
                                      f"{os.path.splitext(os.path.basename(file_path))[0]}_analysis.json")
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(file_info, f, indent=2)
            
            return {
                "file_path": file_path,
                "output_path": output_file,
                "status": "success",
                "processing_time": time.time() - start_time
            }
        
        # Regular parsing
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        parsed_data = parse_flexible(content)
        
        # Add consolidated metadata with parser info and timestamp
        # Follow schema requirements: include parser_version, parse_time, input_file, file_size
        # NO parser_user field per requirements
        # NO processing_time_seconds field per requirements
        parsed_data["metadata"] = {
            "parser_version": "1.3.0",
            "parse_time": datetime.now().isoformat(),  # IMPORTANT: Must use dynamic timestamp
            "input_file": os.path.basename(file_path),
            "file_size": os.path.getsize(file_path)
        }
        
        # Remove raw_data if not requested
        if not args.include_raw and "raw_data" in parsed_data:
            del parsed_data["raw_data"]
        
        # Reorder the JSON fields as requested
        parsed_data = reorder_json(parsed_data)
        
        # Output the parsed data
        output_path = args.output_dir or os.path.dirname(file_path) or '.'
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        output_file = os.path.join(output_path, 
                                  f"{os.path.splitext(os.path.basename(file_path))[0]}.json")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json_indent = 4 if args.pretty else 2
            sort_keys = False  # Don't sort keys because we want to preserve our custom order
            json.dump(parsed_data, f, indent=json_indent, sort_keys=sort_keys, ensure_ascii=False)
        
        return {
            "file_path": file_path,
            "output_path": output_file,
            "status": "success",
            "processing_time": time.time() - start_time,
            "metrics_found": bool(parsed_data.get("main")),
            "satellites_found": len(parsed_data.get("satellites", []))
        }
        
    except Exception as e:
        return {
            "file_path": file_path,
            "status": "error",
            "error": str(e),
            "processing_time": time.time() - start_time
        }


async def process_file_async(file_path: str, args: argparse.Namespace) -> Dict[str, Any]:
    """
    Process a single file asynchronously.
    
    Args:
        file_path: Path to the file
        args: Command line arguments
        
    Returns:
        Dictionary with results
    """
    start_time = time.time()
    
    try:
        # If analyze only
        if args.analyze:
            file_info = await examine_file_async(file_path)
            output_path = args.output_dir or os.path.dirname(file_path) or '.'
            if not os.path.exists(output_path):
                os.makedirs(output_path)
            output_file = os.path.join(output_path, 
                                      f"{os.path.splitext(os.path.basename(file_path))[0]}_analysis.json")
            
            async with aiofiles.open(output_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(file_info, indent=2))
            
            return {
                "file_path": file_path,
                "output_path": output_file,
                "status": "success",
                "processing_time": time.time() - start_time
            }
        
        # Regular parsing
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as file:
            content = await file.read()
        
        # Use a thread pool for CPU-bound parsing to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        parsed_data = await loop.run_in_executor(None, parse_flexible, content)
        
        # Add consolidated metadata with parser info and timestamp
        # Follow schema requirements: include parser_version, parse_time, input_file, file_size
        # NO parser_user field per requirements
        # NO processing_time_seconds field per requirements
        parsed_data["metadata"] = {
            "parser_version": "1.3.0",
            "parse_time": datetime.now().isoformat(),  # IMPORTANT: Must use dynamic timestamp
            "input_file": os.path.basename(file_path),
            "file_size": os.path.getsize(file_path)
        }
        
        # Remove raw_data if not requested
        if not args.include_raw and "raw_data" in parsed_data:
            del parsed_data["raw_data"]
        
        # Reorder the JSON fields as requested
        parsed_data = reorder_json(parsed_data)
        
        # Output the parsed data
        output_path = args.output_dir or os.path.dirname(file_path) or '.'
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        output_file = os.path.join(output_path, 
                                  f"{os.path.splitext(os.path.basename(file_path))[0]}.json")
        
        json_indent = 4 if args.pretty else 2
        sort_keys = False  # Don't sort keys because we want to preserve our custom order
        json_data = json.dumps(parsed_data, indent=json_indent, sort_keys=sort_keys, ensure_ascii=False)
        
        async with aiofiles.open(output_file, 'w', encoding='utf-8') as f:
            await f.write(json_data)
        
        return {
            "file_path": file_path,
            "output_path": output_file,
            "status": "success",
            "processing_time": time.time() - start_time,
            "metrics_found": bool(parsed_data.get("main")),
            "satellites_found": len(parsed_data.get("satellites", []))
        }
        
    except Exception as e:
        return {
            "file_path": file_path,
            "status": "error",
            "error": str(e),
            "processing_time": time.time() - start_time
        }


async def process_files_async(file_paths: Set[str], args: argparse.Namespace) -> List[Dict[str, Any]]:
    """
    Process multiple files asynchronously.
    
    Args:
        file_paths: Set of file paths to process
        args: Command line arguments
        
    Returns:
        List of results for each file
    """
    tasks = []
    for file_path in file_paths:
        tasks.append(process_file_async(file_path, args))
    
    return await asyncio.gather(*tasks)


def process_files_sync(file_paths: Set[str], args: argparse.Namespace) -> List[Dict[str, Any]]:
    """
    Process multiple files synchronously.
    
    Args:
        file_paths: Set of file paths to process
        args: Command line arguments
        
    Returns:
        List of results for each file
    """
    results = []
    total_files = len(file_paths)
    
    for i, file_path in enumerate(file_paths, 1):
        if args.verbose:
            print(f"Processing file {i}/{total_files}: {file_path}")
        
        result = process_file(file_path, args)
        results.append(result)
        
        if args.verbose:
            if result["status"] == "success":
                print(f"  Success: {result['output_path']} ({result['processing_time']:.2f}s)")
            else:
                print(f"  Error: {result['error']}")
    
    return results


def process_files_parallel(file_paths: Set[str], args: argparse.Namespace) -> List[Dict[str, Any]]:
    """
    Process multiple files in parallel using a thread pool.
    
    Args:
        file_paths: Set of file paths to process
        args: Command line arguments
        
    Returns:
        List of results for each file
    """
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(32, os.cpu_count() + 4)) as executor:
        future_to_file = {
            executor.submit(process_file, file_path, args): file_path 
            for file_path in file_paths
        }
        
        total_files = len(file_paths)
        completed = 0
        
        for future in concurrent.futures.as_completed(future_to_file):
            completed += 1
            file_path = future_to_file[future]
            
            try:
                result = future.result()
                if args.verbose:
                    print(f"[{completed}/{total_files}] Processed: {file_path}")
                results.append(result)
            except Exception as e:
                if args.verbose:
                    print(f"[{completed}/{total_files}] Error processing {file_path}: {str(e)}")
                results.append({
                    "file_path": file_path,
                    "status": "error",
                    "error": str(e)
                })
    
    return results


async def main_async(args: argparse.Namespace) -> int:
    """
    Main async function for processing files.
    
    Args:
        args: Command line arguments
        
    Returns:
        Exit code
    """
    start_time = time.time()
    
    # Expand file paths
    file_paths = expand_file_paths(args.input)
    
    if not file_paths:
        print("Error: No valid input files found")
        return 1
    
    if args.verbose:
        print(f"Found {len(file_paths)} files to process")
        for path in sorted(file_paths):
            print(f"  {path}")
    
    # Process files asynchronously
    results = await process_files_async(file_paths, args)
    
    # Print summary
    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = sum(1 for r in results if r["status"] == "error")
    total_time = time.time() - start_time
    
    print(f"\nProcessing complete in {total_time:.2f} seconds")
    print(f"  Files processed successfully: {success_count}")
    print(f"  Files with errors: {error_count}")
    
    # Print errors if any
    if error_count > 0 and args.verbose:
        print("\nErrors:")
        for r in results:
            if r["status"] == "error":
                print(f"  {r['file_path']}: {r['error']}")
    
    return 0 if error_count == 0 else 1


def main_sync(args: argparse.Namespace) -> int:
    """
    Main sync function for processing files.
    
    Args:
        args: Command line arguments
        
    Returns:
        Exit code
    """
    start_time = time.time()
    
    # Expand file paths
    file_paths = expand_file_paths(args.input)
    
    if not file_paths:
        print("Error: No valid input files found")
        return 1
    
    if args.verbose:
        print(f"Found {len(file_paths)} files to process")
        for path in sorted(file_paths):
            print(f"  {path}")
    
    # Process files in parallel if multiple files
    if len(file_paths) > 1 and not args.no_parallel:
        results = process_files_parallel(file_paths, args)
    else:
        results = process_files_sync(file_paths, args)
    
    # Print summary
    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = sum(1 for r in results if r["status"] == "error")
    total_time = time.time() - start_time
    
    print(f"\nProcessing complete in {total_time:.2f} seconds")
    print(f"  Files processed successfully: {success_count}")
    print(f"  Files with errors: {error_count}")
    
    # Print errors if any
    if error_count > 0 and args.verbose:
        print("\nErrors:")
        for r in results:
            if r["status"] == "error":
                print(f"  {r['file_path']}: {r['error']}")
    
    return 0 if error_count == 0 else 1


def main():
    """Main function to examine and parse GNSS log files."""
    parser = argparse.ArgumentParser(description='Parse GNSS log files to JSON')
    parser.add_argument('input', nargs='+', help='Input file path(s) or glob pattern(s)')
    parser.add_argument('-o', '--output-dir', help='Output directory path')
    parser.add_argument('-a', '--analyze', action='store_true', help='Analyze files only without parsing')
    parser.add_argument('-v', '--verbose', action='store_true', help='Print verbose output')
    parser.add_argument('-r', '--include-raw', action='store_true', 
                       help='Include raw key-value data in output (default: off)')
    parser.add_argument('-p', '--pretty', action='store_true',
                       help='Output pretty-printed JSON with sorted keys (default: off)')
    parser.add_argument('--async', dest='use_async', action='store_true',
                       help='Use asynchronous I/O for file operations (requires aiofiles)')
    parser.add_argument('--no-parallel', action='store_true',
                       help='Disable parallel processing for multiple files')
    
    args = parser.parse_args()
    
    # Check if async is requested but not available
    if args.use_async and not ASYNC_AVAILABLE:
        print("Warning: Asynchronous I/O requested but 'aiofiles' package not found.")
        print("Install it with 'pip install aiofiles' or use synchronous mode.")
        args.use_async = False
        
    # Use async if requested and available
    if args.use_async:
        try:
            return asyncio.run(main_async(args))
        except Exception as e:
            print(f"Error in async processing: {str(e)}")
            return 1
    else:
        return main_sync(args)


if __name__ == "__main__":
    sys.exit(main())