#!/usr/bin/env python3
"""
GNSS Log Parser - Converts PuTTY GNSS logs to structured JSON format

This script parses PuTTY logs containing GNSS (Global Navigation Satellite System)
information and converts it to a structured JSON format for easier analysis.
Supports multiple input files and directory wildcard patterns.

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
from typing import Dict, List, Any, Optional, Union, Set
from datetime import datetime
from pathlib import Path
import asyncio
import concurrent.futures


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
        "satellites": []
        # Removed parse_time from here as it will be included in metadata
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
        
        # Add consolidated metadata with parser info, timestamp, and file info
        # Removed parse_date_time and parser_user as requested
        parsed_data["metadata"] = {
            "parser_version": "1.3.0",
            "parse_time": datetime.now().isoformat(),
            "input_file": os.path.basename(file_path),
            "file_path": os.path.basename(file_path),
            "file_size": os.path.getsize(file_path),
            "processing_time_seconds": time.time() - start_time
        }
        
        # Remove raw_data if not requested
        if not args.include_raw and "raw_data" in parsed_data:
            del parsed_data["raw_data"]
        
        # Output the parsed data
        output_path = args.output_dir or os.path.dirname(file_path) or '.'
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        output_file = os.path.join(output_path, 
                                  f"{os.path.splitext(os.path.basename(file_path))[0]}.json")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json_indent = 4 if args.pretty else 2
            sort_keys = args.pretty
            json.dump(parsed_data, f, indent=json_indent, sort_keys=sort_keys, ensure_ascii=False)
        
        return {
            "file_path": file_path,
            "output_path": output_file,
            "status": "success",
            "processing_time": time.time() - start_time,
            "metrics_found": bool(parsed_data.get("main_gnss_metrics")),
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
        
        # Add consolidated metadata with parser info, timestamp, and file info
        # Removed parse_date_time and parser_user as requested
        parsed_data["metadata"] = {
            "parser_version": "1.3.0",
            "parse_time": datetime.now().isoformat(),
            "input_file": os.path.basename(file_path),
            "file_path": os.path.basename(file_path),
            "file_size": os.path.getsize(file_path),
            "processing_time_seconds": time.time() - start_time
        }
        
        # Remove raw_data if not requested
        if not args.include_raw and "raw_data" in parsed_data:
            del parsed_data["raw_data"]
        
        # Output the parsed data
        output_path = args.output_dir or os.path.dirname(file_path) or '.'
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        output_file = os.path.join(output_path, 
                                  f"{os.path.splitext(os.path.basename(file_path))[0]}.json")
        
        json_indent = 4 if args.pretty else 2
        sort_keys = args.pretty
        json_data = json.dumps(parsed_data, indent=json_indent, sort_keys=sort_keys, ensure_ascii=False)
        
        async with aiofiles.open(output_file, 'w', encoding='utf-8') as f:
            await f.write(json_data)
        
        return {
            "file_path": file_path,
            "output_path": output_file,
            "status": "success",
            "processing_time": time.time() - start_time,
            "metrics_found": bool(parsed_data.get("main_gnss_metrics")),
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