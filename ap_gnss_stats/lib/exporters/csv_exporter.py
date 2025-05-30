#!/usr/bin/env python3
"""
CSV Exporter for GNSS data.

This module provides functionality to export parsed GNSS data to CSV format.
Each Access Point is represented as a single row in the CSV with all metrics
flattened into columns.
"""

import os
import csv
import logging
from typing import Dict, Any, List, Optional, Union, Set
from datetime import datetime


def export_gnss_data_to_csv(
    data: Union[Dict[str, Any], List[Dict[str, Any]]],
    output_file: str,
    logger: Optional[logging.Logger] = None,
    append_mode: bool = False
) -> bool:
    """
    Export GNSS data to CSV format.
    
    Args:
        data: Single AP data dictionary or list of AP data dictionaries
        output_file: Path to the output CSV file
        logger: Optional logger for debug information
        append_mode: If True, append to existing file; if False, overwrite
        
    Returns:
        True if export was successful, False otherwise
    """
    try:
        # Ensure data is a list for consistent processing
        if isinstance(data, dict):
            data_list = [data]
        else:
            data_list = data
            
        if not data_list:
            if logger:
                logger.warning("No data provided for CSV export")
            return False
            
        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_file)
        if output_dir:  # Only create directory if there is a directory path
            os.makedirs(output_dir, exist_ok=True)
        
        if logger:
            action = "Appending" if append_mode else "Exporting"
            logger.info(f"{action} {len(data_list)} AP record(s) to CSV: {output_file}")
            
        # Handle append mode vs overwrite mode
        if append_mode and os.path.exists(output_file):
            # Append mode: read existing columns and append new data
            existing_columns = []
            try:
                with open(output_file, 'r', encoding='utf-8') as existing_file:
                    reader = csv.reader(existing_file)
                    existing_columns = next(reader, [])  # Get header row
            except Exception as e:
                if logger:
                    logger.warning(f"Could not read existing CSV header: {e}. Will overwrite file.")
                append_mode = False
            
            if existing_columns:
                # Use existing column structure for append
                all_columns = existing_columns
                
                # Append new data to existing file
                with open(output_file, 'a', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=all_columns)
                    
                    for ap_data in data_list:
                        flattened_row = _flatten_ap_data(ap_data, all_columns)
                        writer.writerow(flattened_row)
                        
                if logger:
                    logger.info(f"Successfully appended to CSV with {len(all_columns)} columns")
            else:
                # File exists but is empty, treat as new file
                append_mode = False
        
        if not append_mode:
            # Normal mode: create new file or overwrite existing
            # Get all possible column names from all AP records
            all_columns = _get_all_column_names(data_list)
            
            # Write CSV file
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=all_columns)
                writer.writeheader()
                
                for ap_data in data_list:
                    flattened_row = _flatten_ap_data(ap_data, all_columns)
                    writer.writerow(flattened_row)
                    
            if logger:
                logger.info(f"Successfully exported CSV with {len(all_columns)} columns")
            
        return True
        
    except Exception as e:
        if logger:
            logger.error(f"Failed to export CSV: {str(e)}")
        return False


def _get_all_column_names(data_list: List[Dict[str, Any]]) -> List[str]:
    """
    Get all possible column names from a list of AP data dictionaries.
    
    Args:
        data_list: List of AP data dictionaries
        
    Returns:
        Ordered list of all column names
    """
    all_columns = set()
    
    for ap_data in data_list:
        columns = _extract_column_names_from_ap_data(ap_data)
        all_columns.update(columns)
    
    # Convert to sorted list for consistent column ordering
    return sorted(list(all_columns))


def _extract_column_names_from_ap_data(data: Dict[str, Any]) -> Set[str]:
    """
    Extract all possible column names from a single AP data dictionary.
    
    Args:
        data: Single AP data dictionary
        
    Returns:
        Set of column names
    """
    columns = set()
    
    # Process each section of the parsed data
    for section_name, section_data in data.items():
        if section_name == "satellites":
            # Handle satellites specially - create columns for satellite metrics
            columns.update(_get_satellite_column_names(section_data))
        elif section_name == "raw_data":
            # Handle raw data - prefix with raw_
            if isinstance(section_data, dict):
                for key in section_data.keys():
                    columns.add(f"raw_{key}")
        elif isinstance(section_data, dict):
            # Flatten nested dictionaries
            for key, value in section_data.items():
                column_name = f"{section_name}_{key}"
                columns.add(column_name)
        else:
            # Simple value
            columns.add(section_name)
    
    return columns


def _get_satellite_column_names(satellites: List[Dict[str, Any]]) -> Set[str]:
    """
    Get column names for satellite data aggregations.
    
    Args:
        satellites: List of satellite dictionaries
        
    Returns:
        Set of satellite-related column names
    """
    columns = set()
    
    # Add count columns
    columns.add("satellites_total_count")
    columns.add("satellites_used_count")
    columns.add("satellites_unused_count")
    
    # Add constellation-specific counts
    constellations = set()
    for sat in satellites:
        constellation = sat.get("constellation", "unknown").lower()
        constellations.add(constellation)
    
    for constellation in constellations:
        columns.add(f"satellites_{constellation}_total")
        columns.add(f"satellites_{constellation}_used")
        columns.add(f"satellites_{constellation}_unused")
    
    # Add SNR statistics
    columns.add("satellites_snr_min")
    columns.add("satellites_snr_max")
    columns.add("satellites_snr_avg")
    columns.add("satellites_snr_median")
    
    # Add elevation statistics
    columns.add("satellites_elevation_min")
    columns.add("satellites_elevation_max")
    columns.add("satellites_elevation_avg")
    columns.add("satellites_elevation_median")
    
    return columns


def _flatten_ap_data(data: Dict[str, Any], all_columns: List[str]) -> Dict[str, Any]:
    """
    Flatten AP data into a single row dictionary suitable for CSV export.
    
    Args:
        data: AP data dictionary
        all_columns: List of all possible column names
        
    Returns:
        Flattened dictionary with values for CSV row
    """
    flattened = {}
    
    # Initialize all columns with None/empty values
    for column in all_columns:
        flattened[column] = None
    
    # Process each section
    for section_name, section_data in data.items():
        if section_name == "satellites":
            # Handle satellites with aggregations
            satellite_metrics = _aggregate_satellite_data(section_data)
            flattened.update(satellite_metrics)
        elif section_name == "raw_data":
            # Handle raw data with raw_ prefix
            if isinstance(section_data, dict):
                for key, value in section_data.items():
                    column_name = f"raw_{key}"
                    if column_name in flattened:
                        flattened[column_name] = _format_csv_value(value)
        elif isinstance(section_data, dict):
            # Flatten nested dictionaries
            for key, value in section_data.items():
                column_name = f"{section_name}_{key}"
                if column_name in flattened:
                    flattened[column_name] = _format_csv_value(value)
        else:
            # Simple value
            if section_name in flattened:
                flattened[section_name] = _format_csv_value(section_data)
    
    return flattened


def _aggregate_satellite_data(satellites: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate satellite data into summary statistics.
    
    Args:
        satellites: List of satellite dictionaries
        
    Returns:
        Dictionary with aggregated satellite metrics
    """
    if not satellites:
        return {}
    
    metrics = {}
    
    # Count statistics
    total_count = len(satellites)
    used_count = sum(1 for sat in satellites if str(sat.get("used", "")).lower() == "yes")
    unused_count = total_count - used_count
    
    metrics["satellites_total_count"] = total_count
    metrics["satellites_used_count"] = used_count
    metrics["satellites_unused_count"] = unused_count
    
    # Constellation-specific counts
    constellation_stats = {}
    for sat in satellites:
        constellation = sat.get("constellation", "unknown").lower()
        is_used = str(sat.get("used", "")).lower() == "yes"
        
        if constellation not in constellation_stats:
            constellation_stats[constellation] = {"total": 0, "used": 0, "unused": 0}
        
        constellation_stats[constellation]["total"] += 1
        if is_used:
            constellation_stats[constellation]["used"] += 1
        else:
            constellation_stats[constellation]["unused"] += 1
    
    for constellation, stats in constellation_stats.items():
        metrics[f"satellites_{constellation}_total"] = stats["total"]
        metrics[f"satellites_{constellation}_used"] = stats["used"]
        metrics[f"satellites_{constellation}_unused"] = stats["unused"]
    
    # SNR statistics
    snr_values = []
    for sat in satellites:
        snr = sat.get("snr") or sat.get("cn0") or sat.get("cno")  # Try different field names
        if snr is not None:
            try:
                snr_float = float(snr)
                # Filter out invalid values (commonly -128 indicates no signal)
                if snr_float > -100:
                    snr_values.append(snr_float)
            except (ValueError, TypeError):
                pass
    
    if snr_values:
        snr_values.sort()
        metrics["satellites_snr_min"] = min(snr_values)
        metrics["satellites_snr_max"] = max(snr_values)
        metrics["satellites_snr_avg"] = round(sum(snr_values) / len(snr_values), 2)
        metrics["satellites_snr_median"] = _calculate_median(snr_values)
    
    # Elevation statistics
    elevation_values = []
    for sat in satellites:
        elevation = sat.get("elev") or sat.get("elevation")
        if elevation is not None:
            try:
                elev_float = float(elevation)
                # Filter out invalid values (commonly -128 indicates unknown)
                if elev_float > -100:
                    elevation_values.append(elev_float)
            except (ValueError, TypeError):
                pass
    
    if elevation_values:
        elevation_values.sort()
        metrics["satellites_elevation_min"] = min(elevation_values)
        metrics["satellites_elevation_max"] = max(elevation_values)
        metrics["satellites_elevation_avg"] = round(sum(elevation_values) / len(elevation_values), 2)
        metrics["satellites_elevation_median"] = _calculate_median(elevation_values)
    
    return metrics


def _calculate_median(values: List[float]) -> float:
    """
    Calculate the median of a list of values.
    
    Args:
        values: Sorted list of values
        
    Returns:
        Median value
    """
    n = len(values)
    if n % 2 == 1:
        return values[n // 2]
    else:
        return (values[n // 2 - 1] + values[n // 2]) / 2


def _format_csv_value(value: Any) -> str:
    """
    Format a value for CSV output.
    
    Args:
        value: Value to format
        
    Returns:
        String representation suitable for CSV
    """
    if value is None:
        return ""
    elif isinstance(value, bool):
        return str(value).lower()
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, str):
        # Remove any problematic characters that might break CSV parsing
        cleaned = value.replace('\n', ' ').replace('\r', ' ').strip()
        return cleaned
    else:
        # Convert other types to string
        return str(value)


def get_csv_schema_info() -> Dict[str, Any]:
    """
    Get information about the CSV export schema.
    
    Returns:
        Dictionary with schema information
    """
    return {
        "description": "CSV export of GNSS data with one row per Access Point",
        "column_naming": {
            "metadata_*": "Metadata fields (parser version, timestamps, etc.)",
            "main_*": "Main GNSS metrics (AP name, clock time)",
            "show_version_*": "AP version information",
            "show_inventory_*": "AP inventory information",
            "gnss_state_*": "GNSS state metrics (position, accuracy, DOP values)",
            "gnss_postprocessor_*": "GNSS postprocessor location data",
            "cisco_gnss_*": "Cisco GNSS specific data",
            "last_location_acquired_*": "Last acquired location information",
            "satellites_*": "Aggregated satellite statistics",
            "raw_*": "Raw key-value pairs from parsed data"
        },
        "satellite_aggregations": [
            "Total, used, and unused counts by constellation",
            "SNR/CN0 statistics (min, max, average, median)",
            "Elevation statistics (min, max, average, median)"
        ],
        "data_types": {
            "numeric": "Coordinates, accuracies, DOP values, counts, statistics",
            "text": "AP names, serial numbers, software versions",
            "boolean": "Flags and status indicators (converted to true/false)",
            "datetime": "Timestamps in ISO format"
        }
    }


def validate_csv_export_data(data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> List[str]:
    """
    Validate data before CSV export and return any warnings.
    
    Args:
        data: Data to validate
        
    Returns:
        List of validation warnings (empty if no issues)
    """
    warnings = []
    
    # Ensure data is a list
    if isinstance(data, dict):
        data_list = [data]
    else:
        data_list = data
    
    if not data_list:
        warnings.append("No data provided for export")
        return warnings
    
    # Check each AP record
    for i, ap_data in enumerate(data_list):
        if not isinstance(ap_data, dict):
            warnings.append(f"Record {i}: Not a dictionary")
            continue
            
        # Check for required sections
        expected_sections = ["main", "gnss_state", "metadata"]
        for section in expected_sections:
            if section not in ap_data:
                warnings.append(f"Record {i}: Missing '{section}' section")
        
        # Check for AP identification
        main_section = ap_data.get("main", {})
        if not main_section.get("main_ap_name"):
            warnings.append(f"Record {i}: No AP name found in main section")
        
        # Check satellites data format
        satellites = ap_data.get("satellites", [])
        if satellites and not isinstance(satellites, list):
            warnings.append(f"Record {i}: Satellites data is not a list")
    
    return warnings
