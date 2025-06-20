#!/usr/bin/env python3
"""
Test script to verify the CSV export with slot configuration data.

This script reads a sample JSON file and exports it to CSV, then verifies
that the slot configuration data is properly included in the CSV output.
"""

import os
import sys
import json
import csv
from pathlib import Path

# Add the parent directory to sys.path to allow relative imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import our exporter
from ap_gnss_stats.lib.exporters.csv_exporter import export_gnss_data_to_csv


def test_csv_export(json_file: str, output_csv: str) -> None:
    """Test the CSV exporter with a JSON file."""
    try:
        # Load the JSON data
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Export to CSV
        print(f"Exporting {json_file} to {output_csv}...")
        export_result = export_gnss_data_to_csv(data, output_csv, append_mode=False)
        
        if not export_result:
            print("CSV export failed!")
            return
        
        print("CSV export successful. Verifying slot data...")
        
        # Read the CSV file to verify slot data
        slot_columns = []
        with open(output_csv, 'r', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            headers = next(reader)
            
            # Find slot-related columns
            for header in headers:
                if "slot" in header and "show_capwap_client_config" in header:
                    slot_columns.append(header)
            
            # Read the first data row
            try:
                data_row = next(reader)
                data_dict = dict(zip(headers, data_row))
            except StopIteration:
                print("No data rows found in CSV file")
                return
        
        # Print slot columns and their values
        print(f"\nFound {len(slot_columns)} slot-related columns:")
        for col in sorted(slot_columns)[:10]:  # Show first 10 slot columns
            print(f"  {col}: {data_dict.get(col, 'N/A')}")
        
        if len(slot_columns) > 10:
            print(f"  ... and {len(slot_columns) - 10} more")
        
        # Verify the count column exists
        count_col = "show_capwap_client_config_slots_count"
        if count_col in data_dict:
            print(f"\nSlot count: {data_dict[count_col]}")
        else:
            print("\nWarning: slot count column not found")
            
        print("\nCSV export verification complete!")
        
    except Exception as e:
        print(f"Error testing CSV export: {str(e)}")


if __name__ == "__main__":
    # Check if file paths were provided
    if len(sys.argv) > 2:
        test_csv_export(sys.argv[1], sys.argv[2])
    else:
        # Use default paths
        json_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../output/20250619-125813-ogxwsc-outdoor-ap1.json"))
        output_csv = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../output/test_slots.csv"))
        
        if os.path.exists(json_file):
            test_csv_export(json_file, output_csv)
        else:
            print(f"Default JSON file not found: {json_file}")
            print("Please provide JSON and CSV file paths as arguments:")
            print("Usage: python test_csv_slots.py <json_file> <output_csv>")
            sys.exit(1)
