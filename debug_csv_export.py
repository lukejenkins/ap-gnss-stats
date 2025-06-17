#!/usr/bin/env python3
"""
Debug script for CSV export issues.

This script helps diagnose CSV export problems by testing file system
permissions, paths, and CSV export functionality.
"""

import os
import sys
import logging
from datetime import datetime

# Add the current directory to sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from ap_gnss_stats.lib.exporters.csv_exporter import (
    export_gnss_data_to_csv,
    debug_csv_export_environment,
    _verify_csv_file_after_write
)


def setup_debug_logger():
    """Set up a logger for debugging."""
    logger = logging.getLogger('csv_debug')
    logger.setLevel(logging.DEBUG)
    
    # Create console handler with debug level
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(ch)
    
    return logger


def create_test_data():
    """Create minimal test data for CSV export."""
    return {
        "main_ap_name": "test-ap1",
        "main_gnss_detected": True,
        "main_location_acquired": True,
        "main_last_connected": "2025-06-17T10:30:00",
        "gnss_state_enabled": True,
        "gnss_state_latitude": 41.2345,
        "gnss_state_longitude": -111.6789,
        "gnss_state_altitude": 1400.5,
        "satellites": [
            {"constellation": "GPS", "prn": 1, "elevation": 45, "azimuth": 180, "cno": 40, "used": True},
            {"constellation": "GPS", "prn": 2, "elevation": 30, "azimuth": 90, "cno": 35, "used": True}
        ]
    }


def test_csv_export(output_file: str, append_mode: bool = False):
    """Test CSV export functionality."""
    logger = setup_debug_logger()
    
    print("=" * 60)
    print(f"CSV Export Debug Test")
    print(f"Output file: {output_file}")
    print(f"Append mode: {append_mode}")
    print("=" * 60)
    
    # Gather environment debug info
    print("\n1. Gathering environment information...")
    debug_info = debug_csv_export_environment(output_file, logger)
    
    # Create test data
    print("\n2. Creating test data...")
    test_data = create_test_data()
    print(f"Test data created with keys: {list(test_data.keys())}")
    
    # Test the export
    print("\n3. Testing CSV export...")
    try:
        success = export_gnss_data_to_csv(
            data=test_data,
            output_file=output_file,
            logger=logger,
            append_mode=append_mode
        )
        
        print(f"Export function returned: {success}")
        
        # Verify the file
        print("\n4. Verifying exported file...")
        verification = _verify_csv_file_after_write(output_file, logger)
        
        print("\nVerification Results:")
        for key, value in verification.items():
            print(f"  {key}: {value}")
            
        # If file exists, show a sample
        if verification["file_exists"] and verification["is_readable"]:
            print("\n5. File content sample:")
            try:
                with open(verification["absolute_path"], 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    for i, line in enumerate(lines[:5]):  # Show first 5 lines
                        print(f"  Line {i+1}: {line.strip()}")
                    if len(lines) > 5:
                        print(f"  ... and {len(lines) - 5} more lines")
            except Exception as e:
                print(f"  Error reading file content: {e}")
        else:
            print("\n5. File is not readable or doesn't exist - cannot show content")
            
    except Exception as e:
        print(f"Export test failed with error: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
    
    print("\n" + "=" * 60)
    print("Debug test complete")
    print("=" * 60)


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Debug CSV export functionality')
    parser.add_argument('-o', '--output', 
                       default='output/debug_test.csv',
                       help='Output CSV file path (default: output/debug_test.csv)')
    parser.add_argument('-a', '--append', action='store_true',
                       help='Test append mode instead of overwrite')
    
    args = parser.parse_args()
    
    # Run the test
    test_csv_export(args.output, args.append)


if __name__ == "__main__":
    main()
