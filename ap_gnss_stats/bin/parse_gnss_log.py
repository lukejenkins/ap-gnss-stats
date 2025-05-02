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

# Update import paths to use relative imports
# Add the parent directory to sys.path to allow relative imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from ap_gnss_stats.lib.parsers.gnss_info_parser import GnssInfoParser

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
        
        # Use the library parser instead of the old parse_flexible function
        parser = GnssInfoParser()
        parsed_data = parser.parse(content)
        
        # Add consolidated metadata with parser info and timestamp
        # Follow schema requirements: include parser_version, parse_time, input_file, file_size
        # NO parser_user field per requirements
        # NO processing_time_seconds field per requirements
        metadata = {
            "parser_version": parser.get_version(),
            "parse_time": datetime.now().isoformat(),  # IMPORTANT: Must use dynamic timestamp
            "input_file": os.path.basename(file_path),
            "file_size": os.path.getsize(file_path)
        }
        
        # Move metadata to a temporary variable, remove it if it exists already
        if "metadata" in parsed_data:
            del parsed_data["metadata"]
        
        # Create an OrderedDict with metadata first, then add the rest of the data
        ordered_data = OrderedDict([("metadata", metadata)])
        
        # Add all other keys from parsed_data
        for key, value in parsed_data.items():
            ordered_data[key] = value
        
        # Remove raw_data if not requested
        if not args.include_raw and "raw_data" in ordered_data:
            del ordered_data["raw_data"]
        
        # Output the parsed data
        output_path = args.output_dir or os.path.dirname(file_path) or '.'
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        output_file = os.path.join(output_path, 
                                  f"{os.path.splitext(os.path.basename(file_path))[0]}.json")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json_indent = 4 if args.pretty else 2
            sort_keys = False  # Don't sort keys because we want to preserve our custom order
            json.dump(ordered_data, f, indent=json_indent, sort_keys=sort_keys, ensure_ascii=False)
        
        return {
            "file_path": file_path,
            "output_path": output_file,
            "status": "success",
            "processing_time": time.time() - start_time,
            "metrics_found": bool(ordered_data.get("main")),
            "satellites_found": len(ordered_data.get("satellites", []))
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
        parser = GnssInfoParser()
        parsed_data = await loop.run_in_executor(None, parser.parse, content)
        
        # Add consolidated metadata with parser info and timestamp
        # Follow schema requirements: include parser_version, parse_time, input_file, file_size
        # NO parser_user field per requirements
        # NO processing_time_seconds field per requirements
        metadata = {
            "parser_version": parser.get_version(),
            "parse_time": datetime.now().isoformat(),  # IMPORTANT: Must use dynamic timestamp
            "input_file": os.path.basename(file_path),
            "file_size": os.path.getsize(file_path)
        }
        
        # Move metadata to a temporary variable, remove it if it exists already
        if "metadata" in parsed_data:
            del parsed_data["metadata"]
        
        # Create an OrderedDict with metadata first, then add the rest of the data
        ordered_data = OrderedDict([("metadata", metadata)])
        
        # Add all other keys from parsed_data
        for key, value in parsed_data.items():
            ordered_data[key] = value
        
        # Remove raw_data if not requested
        if not args.include_raw and "raw_data" in ordered_data:
            del ordered_data["raw_data"]
        
        # Output the parsed data
        output_path = args.output_dir or os.path.dirname(file_path) or '.'
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        output_file = os.path.join(output_path, 
                                  f"{os.path.splitext(os.path.basename(file_path))[0]}.json")
        
        json_indent = 4 if args.pretty else 2
        sort_keys = False  # Don't sort keys because we want to preserve our custom order
        json_data = json.dumps(ordered_data, indent=json_indent, sort_keys=sort_keys, ensure_ascii=False)
        
        async with aiofiles.open(output_file, 'w', encoding='utf-8') as f:
            await f.write(json_data)
        
        return {
            "file_path": file_path,
            "output_path": output_file,
            "status": "success",
            "processing_time": time.time() - start_time,
            "metrics_found": bool(ordered_data.get("main")),
            "satellites_found": len(ordered_data.get("satellites", []))
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