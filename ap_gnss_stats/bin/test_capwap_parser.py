#!/usr/bin/env python3
"""
Test script to verify the CAPWAP client configuration parser works correctly.

This script parses a session capture file containing 'show capwap client configuration'
output and displays the parsed data to verify the parser is working correctly.
"""

import os
import sys
import json
from pathlib import Path
import argparse

# Add the parent directory to sys.path to allow relative imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import our parser library
from ap_gnss_stats.lib.parsers.capwap_config_parser import CapwapConfigParser


def test_parser(file_path: str, verbose: bool = False) -> None:
    """Test the parser with the specified file.
    
    Args:
        file_path: Path to the file to parse
        verbose: Whether to show detailed output
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Create parser instance
        parser = CapwapConfigParser()
        
        # Parse the content
        parsed_data = parser.parse(content)
        
        # Print parser version
        print(f"CAPWAP Parser Version: {parser.get_version()}")
        
        # Basic validation
        if "show_capwap_client_config" not in parsed_data:
            print("\nERROR: 'show_capwap_client_config' section is missing")
            return
        
        capwap_config = parsed_data["show_capwap_client_config"]
        
        # Check for slots
        if "slots" not in capwap_config:
            print("\nERROR: 'slots' section is missing")
            return
        
        # Print statistics
        main_fields_count = len(capwap_config) - 1  # Subtract 1 for the slots field
        slot_count = len(capwap_config["slots"])
        
        print(f"\nParsed data from {os.path.basename(file_path)}:")
        print(f"Main fields: {main_fields_count}")
        print(f"Slot count: {slot_count}")
        
        # Print slot information
        for i, slot in enumerate(capwap_config["slots"]):
            slot_num = slot.get("slot_number", "unknown")
            config_fields = len(slot.get("configuration", {}))
            print(f"  Slot {slot_num}: {config_fields} configuration fields")
        
        # Verify important fields are present
        important_fields = [
            "name",
            "adminstate",
            "primary_controller_name",
            "apmode",
            "policy_tag",
            "rf_tag",
            "site_tag",
            "tag_source",
            "swver"
        ]
        
        missing_fields = [field for field in important_fields if field not in capwap_config]
        
        if missing_fields:
            print(f"\nWARNING: The following fields are missing: {', '.join(missing_fields)}")
        else:
            print("\nAll expected main fields are present.")
        
        # If verbose, print the full parsed data
        if verbose:
            print("\nFull parsed data:")
            print(json.dumps(parsed_data, indent=2))
        
    except Exception as e:
        print(f"Error testing parser: {str(e)}")


def find_log_files() -> list:
    """Find all log files in the logs directory that likely contain CAPWAP configuration.
    
    Returns:
        List of log file paths
    """
    logs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../logs"))
    log_files = []
    
    if os.path.exists(logs_dir):
        for file in os.listdir(logs_dir):
            if file.endswith(".log") and not file.endswith("-netmiko.log"):
                log_files.append(os.path.join(logs_dir, file))
    
    return log_files


if __name__ == "__main__":
    # Setup argument parser
    parser = argparse.ArgumentParser(description='Test the CAPWAP client configuration parser.')
    parser.add_argument('file', nargs='?', help='Path to file containing CAPWAP configuration output')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed output')
    parser.add_argument('--all-logs', '-a', action='store_true', help='Test with all log files in the logs directory')
    args = parser.parse_args()
    
    # If a specific file was provided, test it
    if args.file:
        test_parser(args.file, args.verbose)
    elif args.all_logs:
        # Test with all log files in the logs directory
        log_files = find_log_files()
        
        if not log_files:
            print("No log files found in the logs directory.")
            sys.exit(1)
        
        print(f"Testing with {len(log_files)} log files:")
        for log_file in log_files:
            print(f"\n{'='*50}")
            print(f"Testing with log file: {os.path.basename(log_file)}")
            test_parser(log_file, args.verbose)
    else:
        # Use netmiko log files if they exist
        netmiko_logs = []
        logs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../logs"))
        
        if os.path.exists(logs_dir):
            for file in os.listdir(logs_dir):
                if file.endswith("-netmiko.log"):
                    netmiko_logs.append(os.path.join(logs_dir, file))
        
        if netmiko_logs:
            # Use the most recent netmiko log
            most_recent = max(netmiko_logs, key=os.path.getmtime)
            print(f"Testing with most recent netmiko log: {os.path.basename(most_recent)}")
            test_parser(most_recent, args.verbose)
        else:
            print("No log files specified and no netmiko logs found.")
            print("Usage: python test_capwap_parser.py [file_path] [--verbose] [--all-logs]")
            sys.exit(1)
