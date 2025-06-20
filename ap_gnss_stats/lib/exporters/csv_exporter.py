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
        # Comprehensive input validation and debugging
        if logger:
            logger.info(f"=== CSV Export Debug Information ===")
            logger.info(f"Output file requested: {output_file}")
            logger.info(f"Append mode: {append_mode}")
            logger.info(f"Data type: {type(data)}")
        
        # Ensure data is a list for consistent processing
        if isinstance(data, dict):
            data_list = [data]
        else:
            data_list = data
            
        if not data_list:
            if logger:
                logger.warning("No data provided for CSV export")
            return False
            
        if logger:
            logger.info(f"Processing {len(data_list)} AP record(s)")
            
        # Validate output file path
        output_file = os.path.abspath(output_file)  # Get absolute path
        output_dir = os.path.dirname(output_file)
        
        if logger:
            logger.info(f"Absolute output file path: {output_file}")
            logger.info(f"Output directory: {output_dir}")
            
        # Check if directory exists and is writable
        if not output_dir:
            if logger:
                logger.error("No directory path specified in output file")
            return False
            
        # Create output directory if it doesn't exist
        try:
            if not os.path.exists(output_dir):
                if logger:
                    logger.info(f"Creating output directory: {output_dir}")
                os.makedirs(output_dir, exist_ok=True)
                if logger:
                    logger.info(f"Directory created successfully")
            else:
                if logger:
                    logger.info(f"Output directory already exists")
                    
            # Check directory permissions
            if not os.access(output_dir, os.W_OK):
                if logger:
                    logger.error(f"No write permission for directory: {output_dir}")
                return False
            else:
                if logger:
                    logger.info(f"Directory is writable")
                    
        except Exception as e:
            if logger:
                logger.error(f"Failed to create/access output directory {output_dir}: {e}")
            return False
        
        if logger:
            action = "Appending" if append_mode else "Exporting"
            logger.info(f"{action} {len(data_list)} AP record(s) to CSV: {output_file}")
             # Handle append mode vs overwrite mode
        file_written = False
        
        if append_mode and os.path.exists(output_file):
            if logger:
                logger.info(f"File exists for append mode: {output_file}")
                file_size = os.path.getsize(output_file)
                logger.info(f"Existing file size: {file_size:,} bytes")
                
            # Append mode: read existing columns and append new data
            existing_columns = []
            try:
                with open(output_file, 'r', encoding='utf-8') as existing_file:
                    reader = csv.reader(existing_file)
                    existing_columns = next(reader, [])  # Get header row
                    
                if logger:
                    logger.info(f"Read {len(existing_columns)} existing columns from CSV header")
                    
            except Exception as e:
                if logger:
                    logger.warning(f"Could not read existing CSV header: {e}. Will create new file instead.")
                # Don't set append_mode = False here, just continue to create new file
                existing_columns = []
            
            if existing_columns:
                # Use existing column structure for append
                all_columns = existing_columns
                
                if logger:
                    logger.info(f"Appending new data with existing column structure")
                
                # Append new data to existing file
                with open(output_file, 'a', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=all_columns)
                    
                    rows_written = 0
                    for ap_data in data_list:
                        flattened_row = _flatten_ap_data(ap_data, all_columns)
                        writer.writerow(flattened_row)
                        rows_written += 1
                        
                if logger:
                    logger.info(f"Successfully appended {rows_written} rows to CSV with {len(all_columns)} columns")
                    
                # Verify file was written correctly
                _verify_csv_file_after_write(output_file, logger)
                file_written = True
                    
            else:
                # File exists but is empty, treat as new file
                if logger:
                    logger.info("Existing file has no header, will create new file")
        
        # Create new file if we haven't written one yet (either overwrite mode or append mode with no existing file)
        if not file_written:
            if append_mode and not os.path.exists(output_file):
                if logger:
                    logger.info("Append mode requested but file doesn't exist - creating new file")
            elif not append_mode:
                if logger:
                    logger.info("Creating new CSV file (overwrite mode)")
            else:
                if logger:
                    logger.info("Creating new CSV file")
            # Get all possible column names from all AP records
            all_columns = _get_all_column_names(data_list)
            
            if logger:
                logger.info(f"Generated {len(all_columns)} total columns from data")
            
            # Write CSV file
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=all_columns)
                writer.writeheader()
                
                rows_written = 0
                for ap_data in data_list:
                    flattened_row = _flatten_ap_data(ap_data, all_columns)
                    writer.writerow(flattened_row)
                    rows_written += 1
                    
            if logger:
                logger.info(f"Successfully created CSV with {rows_written} rows and {len(all_columns)} columns")
                
            # Verify file was written correctly
            _verify_csv_file_after_write(output_file, logger)
            
        return True
        
    except Exception as e:
        if logger:
            logger.error(f"Failed to export CSV: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
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
                
                # Handle nested arrays like "slots"
                if isinstance(value, list) and key == "slots":
                    # Process the slots array - extract all possible slot fields
                    slot_columns = _extract_slots_column_names(value, section_name)
                    columns.update(slot_columns)
                else:
                    columns.add(column_name)
        else:
            # Simple value
            columns.add(section_name)
    
    return columns


def _extract_slots_column_names(slots: List[Dict[str, Any]], parent_prefix: str) -> Set[str]:
    """
    Extract column names from slot configurations.
    
    Args:
        slots: List of slot dictionaries
        parent_prefix: Prefix for the column names (section name)
        
    Returns:
        Set of slot-related column names
    """
    columns = set()
    
    # Add count column
    columns.add(f"{parent_prefix}_slots_count")
    
    # Process each slot to get all possible fields
    for slot in slots:
        slot_num = slot.get("slot_number", 0)
        configuration = slot.get("configuration", {})
        
        if not configuration:
            continue
            
        # Add columns for each configuration field in each slot
        for key, value in configuration.items():
            column_name = f"{parent_prefix}_slot{slot_num}_{key}"
            columns.add(column_name)
    
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
                # Handle the slots array specially
                if key == "slots" and isinstance(value, list):
                    slot_metrics = _flatten_slots_data(value, section_name, all_columns)
                    for slot_col, slot_val in slot_metrics.items():
                        if slot_col in flattened:
                            flattened[slot_col] = slot_val
                else:
                    column_name = f"{section_name}_{key}"
                    if column_name in flattened:
                        flattened[column_name] = _format_csv_value(value)
        else:
            # Simple value
            if section_name in flattened:
                flattened[section_name] = _format_csv_value(section_data)
    
    return flattened


def _flatten_slots_data(slots: List[Dict[str, Any]], parent_prefix: str, all_columns: List[str]) -> Dict[str, Any]:
    """
    Flatten slot data into columns.
    
    Args:
        slots: List of slot dictionaries
        parent_prefix: Prefix for column names (section name)
        all_columns: List of all possible column names
        
    Returns:
        Dictionary with flattened slot data
    """
    flattened = {}
    
    # Add count of slots
    flattened[f"{parent_prefix}_slots_count"] = len(slots)
    
    # Process each slot
    for slot in slots:
        slot_num = slot.get("slot_number", 0)
        configuration = slot.get("configuration", {})
        
        if not configuration:
            continue
            
        # Add values for each configuration field
        for key, value in configuration.items():
            column_name = f"{parent_prefix}_slot{slot_num}_{key}"
            if column_name in all_columns:
                flattened[column_name] = _format_csv_value(value)
    
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


def _verify_csv_file_after_write(output_file: str, logger: Optional[logging.Logger] = None) -> Dict[str, Any]:
    """
    Verify that the CSV file was written correctly and gather diagnostic information.
    
    Args:
        output_file: Path to the CSV file to verify
        logger: Optional logger for debug information
        
    Returns:
        Dictionary with verification results and file statistics
    """
    verification_results = {
        "file_exists": False,
        "file_size": 0,
        "is_readable": False,
        "header_count": 0,
        "row_count": 0,
        "permissions": None,
        "absolute_path": None,
        "directory_exists": False,
        "directory_writable": False
    }
    
    try:
        # Get absolute path for clarity
        abs_path = os.path.abspath(output_file)
        verification_results["absolute_path"] = abs_path
        
        # Check if file exists
        if os.path.exists(abs_path):
            verification_results["file_exists"] = True
            
            # Get file size
            file_size = os.path.getsize(abs_path)
            verification_results["file_size"] = file_size
            
            # Check if file is readable
            verification_results["is_readable"] = os.access(abs_path, os.R_OK)
            
            # Get file permissions
            import stat
            file_stat = os.stat(abs_path)
            verification_results["permissions"] = oct(file_stat.st_mode)[-3:]
            
            # Count rows and headers if file is readable
            if verification_results["is_readable"]:
                try:
                    with open(abs_path, 'r', encoding='utf-8') as csvfile:
                        reader = csv.reader(csvfile)
                        rows = list(reader)
                        if rows:
                            verification_results["header_count"] = len(rows[0])
                            verification_results["row_count"] = len(rows) - 1  # Exclude header
                except Exception as read_error:
                    if logger:
                        logger.warning(f"Could not read CSV content for verification: {read_error}")
            
            if logger:
                logger.info(f"File verification - EXISTS: {verification_results['file_exists']}")
                logger.info(f"File verification - SIZE: {verification_results['file_size']:,} bytes")
                logger.info(f"File verification - READABLE: {verification_results['is_readable']}")
                logger.info(f"File verification - PERMISSIONS: {verification_results['permissions']}")
                logger.info(f"File verification - HEADERS: {verification_results['header_count']}")
                logger.info(f"File verification - DATA ROWS: {verification_results['row_count']}")
        else:
            if logger:
                logger.error(f"File verification FAILED - File does not exist: {abs_path}")
        
        # Check directory
        directory = os.path.dirname(abs_path)
        verification_results["directory_exists"] = os.path.exists(directory)
        verification_results["directory_writable"] = os.access(directory, os.W_OK) if verification_results["directory_exists"] else False
        
        if logger:
            logger.info(f"Directory verification - EXISTS: {verification_results['directory_exists']}")
            logger.info(f"Directory verification - WRITABLE: {verification_results['directory_writable']}")
            
    except Exception as e:
        if logger:
            logger.error(f"File verification error: {e}")
    
    return verification_results


def debug_csv_export_environment(output_file: str, logger: Optional[logging.Logger] = None) -> Dict[str, Any]:
    """
    Gather comprehensive debugging information about the CSV export environment.
    
    Args:
        output_file: Path to the CSV file being exported
        logger: Optional logger for debug information
        
    Returns:
        Dictionary with environment debugging information
    """
    debug_info = {
        "python_version": None,
        "current_working_directory": None,
        "user_id": None,
        "output_file_absolute": None,
        "output_directory": None,
        "disk_space_available": None,
        "environment_variables": {}
    }
    
    try:
        import sys
        import pwd
        import shutil
        
        # Basic environment info
        debug_info["python_version"] = sys.version
        debug_info["current_working_directory"] = os.getcwd()
        
        try:
            debug_info["user_id"] = pwd.getpwuid(os.getuid()).pw_name
        except:
            debug_info["user_id"] = str(os.getuid())
        
        # File path info
        debug_info["output_file_absolute"] = os.path.abspath(output_file)
        debug_info["output_directory"] = os.path.dirname(debug_info["output_file_absolute"])
        
        # Disk space
        try:
            statvfs = shutil.disk_usage(debug_info["output_directory"])
            debug_info["disk_space_available"] = statvfs.free
        except:
            debug_info["disk_space_available"] = "Unknown"
        
        # Relevant environment variables
        env_vars_to_check = ["HOME", "USER", "TMPDIR", "PWD", "PATH"]
        for var in env_vars_to_check:
            debug_info["environment_variables"][var] = os.environ.get(var, "Not set")
        
        if logger:
            logger.info("=== CSV Export Environment Debug ===")
            logger.info(f"Python version: {debug_info['python_version']}")
            logger.info(f"Current working directory: {debug_info['current_working_directory']}")
            logger.info(f"User: {debug_info['user_id']}")
            logger.info(f"Output file (absolute): {debug_info['output_file_absolute']}")
            logger.info(f"Output directory: {debug_info['output_directory']}")
            logger.info(f"Available disk space: {debug_info['disk_space_available']}")
            for var, value in debug_info["environment_variables"].items():
                logger.info(f"ENV {var}: {value}")
                
    except Exception as e:
        if logger:
            logger.error(f"Failed to gather debug environment info: {e}")
    
    return debug_info
