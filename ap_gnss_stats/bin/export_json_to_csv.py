#!/usr/bin/env python3
"""
Script to export existing parsed JSON files to CSV with the updated slot handling.

This script reads all JSON files in the output directory and exports them
to a single CSV file with the updated slot configuration handling.
"""

import os
import sys
import json
import glob
from pathlib import Path

# Add the parent directory to sys.path to allow relative imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import our exporter
from ap_gnss_stats.lib.exporters.csv_exporter import export_gnss_data_to_csv


def export_all_json_to_csv(json_dir: str, csv_file: str, append: bool = False) -> None:
    """Export all JSON files in a directory to a single CSV file."""
    try:
        # Find all JSON files
        json_files = glob.glob(os.path.join(json_dir, "*.json"))
        if not json_files:
            print(f"No JSON files found in {json_dir}")
            return
        
        print(f"Found {len(json_files)} JSON files in {json_dir}")
        
        # Load all JSON data
        all_data = []
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    all_data.append(data)
                    print(f"Loaded {json_file}")
            except Exception as e:
                print(f"Error loading {json_file}: {str(e)}")
        
        if not all_data:
            print("No valid JSON data loaded")
            return
        
        print(f"Loaded {len(all_data)} JSON files successfully")
        
        # Export to CSV
        print(f"Exporting {len(all_data)} records to {csv_file} (append={append})...")
        export_result = export_gnss_data_to_csv(all_data, csv_file, append_mode=append)
        
        if export_result:
            print(f"CSV export successful: {csv_file}")
            
            # Check if slot data was included
            with open(csv_file, 'r', encoding='utf-8') as f:
                header = f.readline().strip()
                slot_columns = [col for col in header.split(',') if 'slot' in col.lower()]
                print(f"CSV file contains {len(slot_columns)} slot-related columns")
        else:
            print("CSV export failed!")
        
    except Exception as e:
        print(f"Error exporting JSON to CSV: {str(e)}")


if __name__ == "__main__":
    # Get command line arguments
    if len(sys.argv) > 2:
        json_dir = sys.argv[1]
        csv_file = sys.argv[2]
        append = len(sys.argv) > 3 and sys.argv[3].lower() == 'append'
    else:
        # Use default paths
        json_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../output"))
        csv_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../output/all_data_with_slots.csv"))
        append = False
        
    export_all_json_to_csv(json_dir, csv_file, append)
