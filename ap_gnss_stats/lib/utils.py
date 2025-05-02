"""
Utility functions for GNSS data processing.

This module provides helper functions for file operations, content analysis,
and other common tasks used in the GNSS data processing.
"""

import os
import re
import glob
from typing import List, Set, Dict, Any, Optional, Union
from datetime import datetime


def get_ap_name_from_filename(filename: str) -> Optional[str]:
    """
    Extract the AP name from a filename following common patterns.
    
    Args:
        filename: The filename to extract AP name from
        
    Returns:
        Extracted AP name or None if not found
    """
    # Common patterns in filenames:
    # - putty-example-outdoor-ap1.txt
    # - session-capture.ogxwsc-outdoor-ap1.mgmt.weber.edu.2025-04-29-173449.474.txt
    
    patterns = [
        r'putty-([^-\.]+)-([^-\.]+)-([^-\.]+)\.', # Match putty-location-type-apname.ext
        r'session-capture\.([^\.]+)\.', # Match session-capture.apname.domain.ext
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            # For the putty- pattern, we want the full AP name (e.g., outdoor-ap1)
            if 'putty-' in pattern:
                return f"{match.group(2)}-{match.group(3)}"
            # For session-capture, return first capturing group
            else:
                return match.group(1)
    
    return None


def parse_timestamp_from_filename(filename: str) -> Optional[datetime]:
    """
    Extract a timestamp from a filename following common patterns.
    
    Args:
        filename: The filename to extract timestamp from
        
    Returns:
        Extracted datetime object or None if not found
    """
    # Common patterns:
    # - 20250421-101648-putty-example-outdoor-ap1.txt
    # - session-capture.ap1.mgmt.weber.edu.2025-04-29-173449.474.txt
    
    patterns = [
        r'^(\d{8})-(\d{6})', # YYYYMMDD-HHMMSS at start of filename
        r'\.(\d{4}-\d{2}-\d{2}-\d{6})\.', # YYYY-MM-DD-HHMMSS in domain-style name
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            timestamp_str = match.group(1)
            try:
                if '-' in timestamp_str:
                    # Format: 2025-04-29-173449
                    date_part, time_part = timestamp_str.rsplit('-', 1)
                    hour = time_part[:2]
                    minute = time_part[2:4]
                    second = time_part[4:6]
                    return datetime.strptime(f"{date_part} {hour}:{minute}:{second}", 
                                          "%Y-%m-%d %H:%M:%S")
                else:
                    # Format: 20250421
                    return datetime.strptime(f"{timestamp_str[:4]}-{timestamp_str[4:6]}-{timestamp_str[6:8]} {match.group(2)[:2]}:{match.group(2)[2:4]}:{match.group(2)[4:6]}", 
                                          "%Y-%m-%d %H:%M:%S")
            except (ValueError, IndexError):
                pass
    
    return None


def find_gnss_log_files(directory: str, recursive: bool = False) -> List[str]:
    """
    Find GNSS log files in a directory.
    
    Args:
        directory: Directory to search in
        recursive: Whether to search recursively in subdirectories
        
    Returns:
        List of file paths
    """
    if not os.path.isdir(directory):
        return []
    
    extensions = ['.txt', '.log']
    result = []
    
    if recursive:
        for root, _, files in os.walk(directory):
            for file in files:
                if any(file.lower().endswith(ext) for ext in extensions):
                    result.append(os.path.join(root, file))
    else:
        for ext in extensions:
            result.extend(glob.glob(os.path.join(directory, f'*{ext}')))
    
    return result


def categorize_files_by_ap(file_paths: List[str]) -> Dict[str, List[str]]:
    """
    Categorize files by AP name.
    
    Args:
        file_paths: List of file paths
        
    Returns:
        Dictionary mapping AP names to lists of file paths
    """
    result = {}
    
    for file_path in file_paths:
        filename = os.path.basename(file_path)
        ap_name = get_ap_name_from_filename(filename)
        
        if ap_name:
            if ap_name not in result:
                result[ap_name] = []
            result[ap_name].append(file_path)
        else:
            # Files with unrecognized name pattern go into 'unknown' category
            if 'unknown' not in result:
                result['unknown'] = []
            result['unknown'].append(file_path)
    
    return result