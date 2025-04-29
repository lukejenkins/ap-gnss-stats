#!/usr/bin/env python3
"""
GNSS Log Parser - Converts PuTTY GNSS logs to structured JSON format

This script parses PuTTY logs containing GNSS (Global Navigation Satellite System)
information and converts it to a structured JSON format for easier analysis.

Dependencies:
    - Python 3.x
"""

import re
import json
import argparse
import os
import sys
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path


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
            "Azimuth", "GNSS_PostProcessor", "CiscoGNSS"
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
        elif "show gnss info" in content.lower():
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


def extract_gnss_metrics(content: str) -> Dict[str, Any]:
    """
    Extract main GNSS metrics from the content.
    
    Args:
        content: Raw file content
        
    Returns:
        Dictionary of GNSS metrics
    """
    metrics = {}
    
    # Extract the GNSS state section
    gnss_state_start = content.find("GnssState:")
    if gnss_state_start == -1:
        return metrics
        
    # Find the end of the state section (satellite table start)
    sat_table_start = content.find("Const.", gnss_state_start)
    if sat_table_start == -1:
        # If satellite table not found, use a large section
        state_section = content[gnss_state_start:]
    else:
        state_section = content[gnss_state_start:sat_table_start]
    
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
    uncertainty_match = re.search(uncertainty_pattern, state_section)
    
    if uncertainty_match:
        metrics["uncertainty_ellipse_major_axis"] = float(uncertainty_match.group(1))
        metrics["uncertainty_ellipse_minor_axis"] = float(uncertainty_match.group(2))
        metrics["uncertainty_ellipse_orientation"] = float(uncertainty_match.group(3))
    
    # Extract DOP parameters - these might be presented together in a line
    dop_pattern = r"pDOP:\s*([\d\.]+)\s+hDOP:\s*([\d\.]+)\s+vDOP:\s*([\d\.]+)\s+nDOP:\s*([\d\.]+)\s+eDOP:\s*([\d\.]+)\s+gDOP:\s*([\d\.]+)\s+tDOP:\s*([\d\.]+)"
    dop_match = re.search(dop_pattern, state_section)
    
    if dop_match:
        metrics["pdop"] = float(dop_match.group(1))
        metrics["hdop"] = float(dop_match.group(2))
        metrics["vdop"] = float(dop_match.group(3))
        metrics["ndop"] = float(dop_match.group(4))
        metrics["edop"] = float(dop_match.group(5))
        metrics["gdop"] = float(dop_match.group(6))
        metrics["tdop"] = float(dop_match.group(7))
    
    # Extract first hDOP value separately (may appear before the DOP section)
    horacc_hdop_pattern = r"HorAcc:\s*[\d\.]+\s+hDOP:\s*([\d\.]+)"
    horacc_hdop_match = re.search(horacc_hdop_pattern, state_section)
    
    if horacc_hdop_match:
        metrics["horacc_hdop"] = float(horacc_hdop_match.group(1))
    
    # Process the main patterns
    for key, pattern in patterns.items():
        match = re.search(pattern, state_section)
        if match:
            value = match.group(1)
            if key in ["external_antenna", "valid_fix"]:
                metrics[key] = value.lower() == "true"
            elif key in ["latitude", "longitude", "horacc", "altitude_msl", 
                        "altitude_hae", "vertacc", "rangeres", "gpgstrms"]:
                try:
                    # Ensure float values are parsed correctly with full precision
                    metrics[key] = float(value)
                except ValueError:
                    metrics[key] = value
            elif key in ["numsat", "satellitecount"]:
                try:
                    metrics[key] = int(value)
                except ValueError:
                    metrics[key] = value
            else:
                metrics[key] = value
    
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
        "satellites": [],
        "parse_time": datetime.now().isoformat()
    }
    
    # Extract main GNSS metrics from the state section
    result["main_gnss_metrics"] = extract_gnss_metrics(content)
    
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
    table_start = content.find("Const.")
    if table_start >= 0:
        table_lines = content[table_start:].split('\n')
        headers = re.split(r'\s+', table_lines[0].strip())
        
        # Process each line that might contain satellite data
        for i in range(1, min(50, len(table_lines))):  # Limit to first 50 lines
            line = table_lines[i].strip()
            if not line:
                continue
                
            # Check if this looks like satellite data (starts with GPS, GLONASS, Galileo, etc.)
            if any(line.startswith(system) for system in ["GPS", "GLONASS", "Galileo", "BeiDou"]):
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
            elif line.startswith("=") or "example-" in line:
                # End of table detected
                break
    
    return result


def main():
    """Main function to examine and parse GNSS log file."""
    parser = argparse.ArgumentParser(description='Parse GNSS log file to JSON')
    parser.add_argument('log_file', help='Path to the GNSS log file')
    parser.add_argument('-o', '--output', help='Output JSON file path')
    parser.add_argument('-a', '--analyze', action='store_true', help='Analyze file only without parsing')
    parser.add_argument('-v', '--verbose', action='store_true', help='Print verbose output')
    parser.add_argument('-r', '--include-raw', action='store_true', 
                       help='Include raw key-value data in output (default: off)')
    parser.add_argument('-p', '--pretty', action='store_true',
                       help='Output pretty-printed JSON with sorted keys (default: off)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.log_file):
        print(f"Error: File not found: {args.log_file}")
        return 1
    
    # Always perform file analysis
    file_info = examine_file(args.log_file)
    
    if args.verbose:
        print(f"File analysis:")
        print(f"  Path: {file_info['file_path']}")
        print(f"  Size: {file_info['file_size']} bytes")
        print(f"  Content length: {file_info['content_length']} characters")
        print(f"  Line count: {file_info['line_count']}")
        print(f"  Likely format: {file_info.get('likely_format', 'Unknown')}")
        
        print("\nPattern matches:")
        for pattern, match_info in file_info.get('pattern_matches', {}).items():
            print(f"  '{pattern}': {match_info['count']} occurrences")
            
        print("\nFirst few lines:")
        for i, line in enumerate(file_info.get('first_lines', [])):
            print(f"  {i+1}: {line[:70]}{'...' if len(line) > 70 else ''}")
    
    # If only analysis was requested, save and exit
    if args.analyze:
        analyze_output = args.output or os.path.splitext(args.log_file)[0] + "_analysis.json"
        with open(analyze_output, 'w', encoding='utf-8') as f:
            json.dump(file_info, f, indent=2)
        print(f"File analysis saved to: {analyze_output}")
        return 0
    
    # Otherwise proceed with parsing
    with open(args.log_file, 'r', encoding='utf-8') as file:
        content = file.read()
    
    parsed_data = parse_flexible(content)
    
    # Add metadata with parser info and timestamp - using the provided values
    parsed_data["metadata"] = {
        "parser_version": "1.2.0",
        "parse_date_time": "2025-04-29 23:15:12",
        "parser_user": "lukejenkins"
    }
    
    # Add the file info to the parsed data
    parsed_data["file_info"] = {
        "file_path": os.path.basename(args.log_file),
        "file_size": file_info["file_size"],
        "likely_format": file_info.get("likely_format", "Unknown"),
        "pattern_matches": {k: v["count"] for k, v in file_info.get("pattern_matches", {}).items()}
    }
    
    # Remove raw_data if not requested (default behavior)
    if not args.include_raw and "raw_data" in parsed_data:
        del parsed_data["raw_data"]
    
    # Output the parsed data
    output_path = args.output or os.path.splitext(args.log_file)[0] + ".json"
    with open(output_path, 'w', encoding='utf-8') as f:
        # Use sort_keys=True for consistent output and ensure_ascii=False to handle non-ASCII characters
        # Use higher indent for better readability if pretty option is selected
        json_indent = 4 if args.pretty else 2
        sort_keys = args.pretty
        
        json.dump(parsed_data, f, indent=json_indent, sort_keys=sort_keys, ensure_ascii=False)
    
    print(f"JSON data saved to: {output_path}")
    
    if not parsed_data.get("main_gnss_metrics"):
        print("Warning: No GNSS metrics were found in the file.")
    
    if "satellites" in parsed_data and len(parsed_data["satellites"]) == 0:
        print("Warning: No satellite data was found in the file.")
        
    if not parsed_data.get("main_gnss_metrics") and "satellites" in parsed_data and len(parsed_data["satellites"]) == 0:
        print("Try running with --analyze option to get more details about the file content.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())