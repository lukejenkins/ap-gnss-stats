#!/usr/bin/env python3
"""
CLI tool to parse Cisco AP GNSS info logs and generate JSON output.
"""
import os
import sys
import json
import logging
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add the parent directory to the path so we can import our library
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lib.parser import GnssInfoParser, __version__

def setup_logger(debug: bool = False, log_file: Optional[str] = None) -> logging.Logger:
    """
    Set up the logger for the application.
    
    Args:
        debug: Enable debug logging
        log_file: Optional path to write log output
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger('ap_gnss_stats')
    
    # Remove any existing handlers to avoid duplication
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    log_level = logging.DEBUG if debug else logging.INFO
    logger.setLevel(log_level)
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Always log to console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Add file handler if log file specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
    return logger

def generate_output_filename(ap_data: Dict[str, Any], extension: str = 'json') -> str:
    """
    Generate an output filename based on AP data and timestamp.
    
    Args:
        ap_data: The parsed AP data
        extension: File extension to use
        
    Returns:
        Formatted filename string
    """
    ap_name = ap_data.get('ap_name', 'unknown_ap')
    # Clean up the AP name to be suitable for a filename
    ap_name = ap_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
    
    # Try to use the GNSS timestamp if available, otherwise use current time
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    if 'gnss_timestamp' in ap_data:
        try:
            # Try to parse a standard format timestamp 
            gnss_time = ap_data['gnss_timestamp']
            # Remove any special characters that shouldn't be in filenames
            timestamp = gnss_time.replace(' ', '_').replace(':', '').replace('-', '')
        except Exception:
            pass  # Fall back to current time if parsing fails
            
    return f"{ap_name}_{timestamp}.{extension}"

def parse_files(files: List[str], output_dir: str, debug: bool = False, log_file: Optional[str] = None) -> None:
    """
    Parse multiple log files and output JSON results.
    
    Args:
        files: List of file paths to parse
        output_dir: Directory to write output files
        debug: Enable debug logging
        log_file: Optional path for debug log output
    """
    logger = setup_logger(debug, log_file)
    logger.info(f"Starting AP GNSS Stats parser v{__version__}")
    
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        logger.info(f"Creating output directory: {output_dir}")
        os.makedirs(output_dir)
    
    parser = GnssInfoParser(debug=debug)
    
    for file_path in files:
        try:
            logger.info(f"Processing file: {file_path}")
            
            if not os.path.exists(file_path):
                logger.error(f"File does not exist: {file_path}")
                continue
                
            # Parse the file
            result = parser.parse_file(file_path)
            
            # Generate output filename based on AP name and timestamp
            output_filename = generate_output_filename(result['ap_data'])
            output_path = os.path.join(output_dir, output_filename)
            
            # Write the result to a JSON file
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2)
                
            logger.info(f"Successfully wrote parsed data to: {output_path}")
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {str(e)}", exc_info=debug)
    
    logger.info("Processing complete")

def main():
    """Main entry point for the CLI tool."""
    parser = argparse.ArgumentParser(
        description='Parse Cisco AP GNSS info logs and generate JSON output'
    )
    
    parser.add_argument(
        'files',
        nargs='+',
        help='Log files to parse'
    )
    
    parser.add_argument(
        '-o', '--output-dir',
        default='output',
        help='Directory to write output files (default: output)'
    )
    
    parser.add_argument(
        '-d', '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    parser.add_argument(
        '-l', '--log-file',
        help='Write debug logs to specified file'
    )
    
    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'AP GNSS Stats Parser v{__version__}'
    )
    
    args = parser.parse_args()
    
    # Process the files
    parse_files(args.files, args.output_dir, args.debug, args.log_file)

if __name__ == '__main__':
    main()