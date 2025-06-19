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

# Add the parent directory to sys.path to allow relative imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import our parser library
from ap_gnss_stats.lib.parsers.capwap_config_parser import CapwapConfigParser


def test_parser(file_path: str) -> None:
    """Test the parser with the specified file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Create parser instance
        parser = CapwapConfigParser()
        
        # Parse the content
        parsed_data = parser.parse(content)
        
        # Print the parsed data
        print(f"Parsed data from {os.path.basename(file_path)}:")
        print(json.dumps(parsed_data, indent=2))
        
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
        
        if "show_capwap_client_config" not in parsed_data:
            print("\nWARNING: 'show_capwap_client_config' section is missing")
        else:
            config_data = parsed_data["show_capwap_client_config"]
            missing_fields = [field for field in important_fields if field not in config_data]
            
            if missing_fields:
                print(f"\nWARNING: The following fields are missing: {', '.join(missing_fields)}")
            else:
                print("\nAll expected fields are present in the show_capwap_client_config section.")
            
            # Count fields with non-None values
            populated_fields = sum(1 for field in important_fields if field in config_data and config_data[field] is not None)
            print(f"Fields with values: {populated_fields}/{len(important_fields)}")
        
    except Exception as e:
        print(f"Error testing parser: {str(e)}")


if __name__ == "__main__":
    # Check if a file path was provided
    if len(sys.argv) > 1:
        test_parser(sys.argv[1])
    else:
        # Use the example files if no file was specified
        example_files = [
            "../examples/private/session-capture.d02-202-ap1.mgmt.weber.edu.2025-06-19-100555.361.txt",
            "../examples/private/session-capture.hb-outdoor-ap3.mgmt.weber.edu.2025-06-19-100335.013.txt"
        ]
        
        # Find the first example file that exists
        found = False
        for example_file in example_files:
            example_path = os.path.join(os.path.dirname(__file__), example_file)
            if os.path.exists(example_path):
                print(f"Testing with example file: {example_path}")
                test_parser(example_path)
                found = True
                break
        
        if not found:
            print("No example files found. Please provide a file path as an argument.")
            print("Usage: python test_capwap_parser.py <file_path>")
            sys.exit(1)
