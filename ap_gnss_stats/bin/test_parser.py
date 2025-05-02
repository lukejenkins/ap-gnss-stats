#!/usr/bin/env python3
"""
Test script for the GNSS parser library

This script demonstrates how to use the GNSS parser library to parse GNSS logs
and extract information from them.
"""

import os
import json
import argparse
import sys
from datetime import datetime
from typing import Dict, Any

# Add the parent directory to sys.path to allow relative imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from ap_gnss_stats.lib.parsers.gnss_info_parser import GnssInfoParser
from ap_gnss_stats.lib import utils


def main():
    """Main function for the test script."""
    parser = argparse.ArgumentParser(description='Test GNSS parser library')
    parser.add_argument('file', help='Path to a GNSS log file or directory')
    parser.add_argument('-o', '--output', help='Output file path (defaults to stdout)')
    parser.add_argument('-r', '--recursive', action='store_true', 
                      help='Recursively search for log files if directory is provided')
    parser.add_argument('-p', '--pretty', action='store_true', 
                      help='Pretty-print JSON output')
    
    args = parser.parse_args()
    
    # Check if the input is a file or directory
    if os.path.isfile(args.file):
        files_to_process = [args.file]
    elif os.path.isdir(args.file):
        print(f"Searching for log files in {args.file}...")
        files_to_process = utils.find_gnss_log_files(args.file, args.recursive)
        print(f"Found {len(files_to_process)} file(s)")
    else:
        print(f"Error: {args.file} is not a valid file or directory")
        return 1
    
    # Process each file
    results = []
    parser = GnssInfoParser()
    
    for file_path in files_to_process:
        try:
            print(f"Processing {file_path}...")
            
            # Read the file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse the content
            parsed_data = parser.parse(content)
            
            # Add metadata
            parsed_data["metadata"] = {
                "parser_version": parser.get_version(),
                "parse_time": datetime.now().isoformat(),
                "input_file": os.path.basename(file_path),
                "file_size": os.path.getsize(file_path)
            }
            
            # Extract AP name from filename if not found in the content
            if parsed_data["main"]["main_ap_name"] is None:
                ap_name = utils.get_ap_name_from_filename(os.path.basename(file_path))
                if ap_name:
                    parsed_data["main"]["main_ap_name"] = ap_name
            
            # Extract timestamp from filename if available
            timestamp = utils.parse_timestamp_from_filename(os.path.basename(file_path))
            if timestamp and "file_timestamp" not in parsed_data["metadata"]:
                parsed_data["metadata"]["file_timestamp"] = timestamp.isoformat()
            
            # Add to results
            results.append({
                "file_path": file_path,
                "data": parsed_data
            })
            
            # Save individual file result if processing multiple files
            if len(files_to_process) > 1:
                output_dir = os.path.dirname(args.output) if args.output else '.'
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                
                output_file = args.output or os.path.join(
                    output_dir, 
                    f"{os.path.splitext(os.path.basename(file_path))[0]}_parsed.json"
                )
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(
                        parsed_data, 
                        f, 
                        indent=4 if args.pretty else None, 
                        ensure_ascii=False
                    )
                print(f"Saved to {output_file}")
            
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
            results.append({
                "file_path": file_path,
                "error": str(e)
            })
    
    # Write output if processing a single file
    if len(files_to_process) == 1 and not args.output:
        json_data = json.dumps(
            results[0]["data"], 
            indent=4 if args.pretty else None, 
            ensure_ascii=False
        )
        print(json_data)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())