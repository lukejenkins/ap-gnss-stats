#!/usr/bin/env python3
"""
AP SSH Collector - Connect to Cisco APs via SSH, collect GNSS data, and parse the output.

This script connects to Cisco Access Points via SSH, collects output from various
'show' commands, logs the entire session with timestamps, and parses the collected
data using the GNSS parser library.

Usage:
    ap_ssh_collector.py -a <ap_address> -u <username> [-p <password>] [-e <enable_password>]
    ap_ssh_collector.py -f <file_with_ap_list> -u <username> [-p <password>] [-e <enable_password>]

Dependencies:
    - netmiko: For SSH connections to network devices
    - dotenv: For loading credentials from environment variables
    - ap_gnss_stats: Local libraries for parsing AP GNSS data
    - prometheus_client: Optional, for exporting data to Prometheus
"""

import os
import sys
import json
import re
import logging
import argparse
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Callable, TypeVar, Union, Mapping
from pathlib import Path
from collections import OrderedDict
import getpass
import threading
import socket
import time
import traceback

# Add the parent directory to sys.path to allow relative imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import required libraries
try:
    from netmiko import ConnectHandler
    from netmiko.exceptions import NetMikoTimeoutException, NetMikoAuthenticationException
except ImportError:
    print("Error: Netmiko library is required. Install it with 'pip install netmiko'")
    sys.exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    print("Warning: python-dotenv not installed. Credentials cannot be loaded from .env file.")
    # Define a no-op function as fallback that accepts any arguments
    load_dotenv = lambda *args, **kwargs: None

# Import our parser libraries
from ap_gnss_stats.lib.parsers.gnss_info_parser import GnssInfoParser
from ap_gnss_stats.lib.parsers.capwap_config_parser import CapwapConfigParser

# Try to import Prometheus exporter
try:
    from ap_gnss_stats.lib.exporters import (
        is_prometheus_available,
        push_gnss_data_to_prometheus,
        export_gnss_data_to_csv
    )
except ImportError:
    # Define placeholder functions if the module is not available
    def is_prometheus_available() -> bool:
        return False
    
    def push_gnss_data_to_prometheus(*args, **kwargs) -> bool:
        return False
    
    def export_gnss_data_to_csv(*args, **kwargs) -> bool:
        return False

# Constants - default values which can be overridden by environment variables
DEFAULT_LOG_DIR = "logs"
DEFAULT_OUTPUT_DIR = "output"
DEFAULT_SSH_PORT = 22
DEFAULT_SSH_TIMEOUT = 30
DEFAULT_SSH_CONN_TIMEOUT = 15
DEFAULT_COMMAND_TIMEOUT = 60
DEFAULT_SESSION_LOG_EXTENSION = ".log"
DEFAULT_CONCURRENT_CONNECTIONS = 1
DEFAULT_INCLUDE_RAW_DATA = False
DEFAULT_DEVICE_TYPE = "cisco_ios"
DEFAULT_GLOBAL_DELAY_FACTOR = 1.5

# Prometheus defaults
DEFAULT_PROMETHEUS_ENABLED = False
DEFAULT_PROMETHEUS_JOB = "ap_gnss_stats"
DEFAULT_PROMETHEUS_TIMEOUT = 10
DEFAULT_PROMETHEUS_URL = None
DEFAULT_PROMETHEUS_USERNAME = None
DEFAULT_PROMETHEUS_PASSWORD = None
DEFAULT_PROMETHEUS_DEBUG = False
DEFAULT_ENV_DEBUG = False # New global for general .env debug

# CSV export defaults
DEFAULT_CSV_ENABLED = False
DEFAULT_CSV_OUTPUT_FILE = None
DEFAULT_CSV_APPEND_MODE = False

# Load environment variables from .env file
def load_env_config():
    """Load configuration from environment variables or .env file."""
    global DEFAULT_PROMETHEUS_ENABLED, DEFAULT_PROMETHEUS_URL, DEFAULT_PROMETHEUS_JOB
    global DEFAULT_PROMETHEUS_USERNAME, DEFAULT_PROMETHEUS_PASSWORD, DEFAULT_PROMETHEUS_TIMEOUT, DEFAULT_PROMETHEUS_DEBUG
    global DEFAULT_CSV_ENABLED, DEFAULT_CSV_OUTPUT_FILE, DEFAULT_CSV_APPEND_MODE
    global DEFAULT_ENV_DEBUG # Ensure new global is included
    
    print("\n### DEBUG: load_env_config called ###\n")  # Added debug print
    
    # Try to load from .env file first
    env_file = find_dotenv_file()
    if env_file:
        load_dotenv(env_file)
        # Debug print about which file was loaded will be handled in main()
    else:
        # Try default .env locations
        load_dotenv()  # Tries .env in current directory
    
    # Helper function to get environment variables with type conversion
    def get_env_or_default(env_name: str, default_value: Any, convert_func: Callable[[str], Any] = str) -> Any:
        """Get environment variable with type conversion or return default.
        
        Args:
            env_name: Name of the environment variable
            default_value: Default value if env variable not found or invalid
            convert_func: Function or type class to convert string to desired type
        
        Returns:
            The converted value from environment variable or the default value
        """
        env_value = os.getenv(env_name)
        if env_value is not None:
            try:
                return convert_func(env_value)
            except (ValueError, TypeError):
                print(f"Warning: Invalid value for {env_name}, using default: {default_value}")
        return default_value
    
    # Helper function to convert string to boolean
    def str_to_bool(value: str) -> bool:
        """Convert string to boolean value."""
        return value.lower() in ('true', '1', 'yes', 'y')
    
    
    # Update Prometheus configuration from environment variables
    DEFAULT_PROMETHEUS_ENABLED = get_env_or_default("AP_PROMETHEUS_ENABLED", DEFAULT_PROMETHEUS_ENABLED, str_to_bool)
    DEFAULT_PROMETHEUS_URL = get_env_or_default("AP_PROMETHEUS_URL", DEFAULT_PROMETHEUS_URL)
    DEFAULT_PROMETHEUS_JOB = get_env_or_default("AP_PROMETHEUS_JOB", DEFAULT_PROMETHEUS_JOB)
    DEFAULT_PROMETHEUS_USERNAME = get_env_or_default("AP_PROMETHEUS_USERNAME", DEFAULT_PROMETHEUS_USERNAME)
    DEFAULT_PROMETHEUS_PASSWORD = get_env_or_default("AP_PROMETHEUS_PASSWORD", DEFAULT_PROMETHEUS_PASSWORD)
    DEFAULT_PROMETHEUS_TIMEOUT = get_env_or_default("AP_PROMETHEUS_TIMEOUT", DEFAULT_PROMETHEUS_TIMEOUT, int)
    DEFAULT_PROMETHEUS_DEBUG = get_env_or_default("AP_PROMETHEUS_DEBUG", DEFAULT_PROMETHEUS_DEBUG, str_to_bool)

    # Update CSV configuration from environment variables
    DEFAULT_CSV_ENABLED = get_env_or_default("AP_CSV_ENABLED", DEFAULT_CSV_ENABLED, str_to_bool)
    DEFAULT_CSV_OUTPUT_FILE = get_env_or_default("AP_CSV_OUTPUT_FILE", DEFAULT_CSV_OUTPUT_FILE)
    DEFAULT_CSV_APPEND_MODE = get_env_or_default("AP_CSV_APPEND_MODE", DEFAULT_CSV_APPEND_MODE, str_to_bool)

    # Update general environment debug flag from environment variable
    DEFAULT_ENV_DEBUG = get_env_or_default("AP_ENV_DEBUG", DEFAULT_ENV_DEBUG, str_to_bool)

    # Removed the debug printing block from here; it will be handled in main().

def find_dotenv_file() -> Optional[str]:
    """
    Find the .env file by looking in the current directory and parent directories.
    
    Returns:
        Path to the .env file if found, None otherwise
    """
    # Start with the current working directory
    current_dir = os.path.abspath(os.getcwd())
    
    # Also check the script's directory
    script_dir = os.path.abspath(os.path.dirname(__file__))
    
    # Check both directories and their parents
    for base_dir in [current_dir, script_dir]:
        # Check up to 3 parent directories
        for _ in range(4):
            env_path = os.path.join(base_dir, ".env")
            if os.path.isfile(env_path):
                return env_path
            # Move up one directory
            base_dir = os.path.dirname(base_dir)
    
    return None

class TimestampedFileHandler(logging.FileHandler):
    """Custom log handler that prepends timestamps to each line."""

    def __init__(self, filename, mode='a', encoding=None, delay=False):
        """Initialize the handler with the specified file parameters."""
        super().__init__(filename, mode, encoding, delay)
        
    def emit(self, record):
        """Emit a record with timestamp prefix."""
        try:
            # Add timestamp to the beginning of the message
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            record.msg = f"[{timestamp}] {record.msg}"
            super().emit(record)
        except Exception:
            self.handleError(record)


def setup_logging(ap_name: str, log_dir: str = DEFAULT_LOG_DIR) -> Tuple[logging.Logger, str]:
    """
    Set up logging configuration for SSH session.
    
    Args:
        ap_name: Name or IP of the access point
        log_dir: Directory to store log files
        
    Returns:
        Tuple of (logger, log_file_path)
    """
    # Create log directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)
    
    # Generate timestamp for log filename
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    
    # Sanitize AP name for filename (replace invalid chars)
    # The original regex r\'[^\\\\w\\\\-\\\\.]\' incorrectly escaped metacharacters in a raw string.
    # The corrected regex r'[^\w\-\.]' properly defines characters to keep:
    # \\w: word characters (alphanumeric + underscore)
    # \\-: literal hyphen
    # \\.: literal period
    # [^...]: replace any character NOT in this set with an underscore.
    safe_ap_name = re.sub(r'[^\w\-\.]', '_', ap_name)
    
    # Create log filename
    log_file = os.path.join(log_dir, f"{timestamp}-{safe_ap_name}{DEFAULT_SESSION_LOG_EXTENSION}")
    
    # Configure logger
    logger = logging.getLogger(f"ssh_session_{safe_ap_name}")
    
    # Only add handlers if none exist for this logger, to prevent duplication.
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        # Set up file handler with timestamp prefix
        file_handler = TimestampedFileHandler(log_file)
        formatter = logging.Formatter('%(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        # Optional: Prevent propagation to avoid duplicate logs if root logger is configured
        # logger.propagate = False
    
    # Log basic session information (will use existing handlers if logger was already set up)
    logger.info(f"Starting SSH session to {ap_name}")
    logger.info(f"Session log started at {timestamp} (or re-using existing log setup for this AP name if called multiple times)") # Clarified log message
    
    return logger, log_file


def get_credentials() -> Dict[str, Optional[str]]:
    """
    Get credentials from environment variables or .env file.
    
    Returns:
        Dictionary containing credentials, values may be None if not found
    """
    # Try to load .env file if it exists
    load_dotenv()
    
    credentials = {
        "username": os.getenv("AP_SSH_USERNAME"),
        "password": os.getenv("AP_SSH_PASSWORD"),
        "enable_password": os.getenv("AP_SSH_ENABLE_PASSWORD"),
    }
    
    return credentials


def connect_to_ap(
    ap_address: str,
    username: str,
    password: str,
    enable_password: Optional[str] = None,
    port: int = DEFAULT_SSH_PORT,
    logger: Optional[logging.Logger] = None,
) -> Dict[str, Any]:
    """
    Connect to an access point via SSH.
    
    Args:
        ap_address: Hostname or IP address of the AP
        username: SSH username
        password: SSH password
        enable_password: Enable mode password (if different from SSH password)
        port: SSH port number
        logger: Logger for SSH session
        
    Returns:
        Dictionary containing connection information
    """
    # Log connection attempt
    if logger:
        logger.info(f"Attempting to resolve hostname: {ap_address}")
    
    # Try to resolve hostname to IP (for logging purposes)
    try:
        ip_address = socket.gethostbyname(ap_address)
        if logger and ip_address != ap_address:
            logger.info(f"Resolved {ap_address} to IP: {ip_address}")
    except socket.gaierror:
        ip_address = "Unknown"
        if logger:
            logger.info(f"Could not resolve hostname: {ap_address}")
    
    # If enable password is not provided, use the login password
    if not enable_password:
        enable_password = password
    
    # Create a session log file path for Netmiko
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_ap_name = re.sub(r'[^\w\-\.]', '_', ap_address)
    session_log_path = os.path.join(DEFAULT_LOG_DIR, f"{timestamp}-{safe_ap_name}-netmiko{DEFAULT_SESSION_LOG_EXTENSION}")
    
    # Define device parameters for Netmiko
    device_params = {
        "device_type": "cisco_ios",  # Use cisco_ios for Cisco APs
        "host": ap_address,
        "username": username,
        "password": password,
        "port": port,
        "secret": enable_password,
        "verbose": True,  # To capture SSH connection details
        "session_log": session_log_path,  # Use file path instead of logger object
        "global_delay_factor": 1.5,  # Slightly longer delay for slower devices
        "conn_timeout": DEFAULT_SSH_CONN_TIMEOUT,
        "timeout": DEFAULT_SSH_TIMEOUT,
    }
    
    if logger:
        logger.info(f"Connecting to {ap_address} (port {port}) with username: {username}")
        logger.info(f"Netmiko session log will be saved to: {session_log_path}")
    
    try:
        # Make sure the log directory exists
        os.makedirs(os.path.dirname(session_log_path), exist_ok=True)
        
        # Connect to the device
        connection = ConnectHandler(**device_params)
        
        if logger:
            logger.info(f"Successfully connected to {ap_address}")
        
        # Enter privileged mode (enable) to run privileged commands
        try:
            if logger:
                logger.info(f"Entering privileged mode on {ap_address}")
            connection.enable()
            if logger:
                logger.info(f"Successfully entered privileged mode on {ap_address}")
        except Exception as enable_error:
            error_msg = f"Failed to enter privileged mode on {ap_address}: {str(enable_error)}"
            if logger:
                logger.error(error_msg)
            # Close the connection since we can't use it properly
            try:
                connection.disconnect()
            except Exception:
                pass
            return {"success": False, "error": error_msg, "address": ap_address}

        return {
            "success": True,
            "connection": connection,
            "address": ap_address,
            "ip": ip_address,
        }
    
    except NetMikoTimeoutException:
        error_msg = f"Connection to {ap_address} timed out"
        if logger:
            logger.error(error_msg)
        return {"success": False, "error": error_msg, "address": ap_address}
    
    except NetMikoAuthenticationException:
        error_msg = f"Authentication failed for {ap_address}"
        if logger:
            logger.error(error_msg)
        return {"success": False, "error": error_msg, "address": ap_address}
    
    except Exception as e:
        error_msg = f"Error connecting to {ap_address}: {str(e)}"
        if logger:
            logger.error(error_msg)
        return {"success": False, "error": error_msg, "address": ap_address}


def run_ap_commands(
    connection: Any,
    logger: Optional[logging.Logger] = None,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    include_raw: bool = False,
    prometheus_config: Optional[Dict[str, Any]] = None,
    csv_config: Optional[Dict[str, Any]] = None,
    ap_address: str = ""  # Add original AP address parameter
) -> Dict[str, Any]:
    """
    Run commands on the AP and parse the output.
    
    Args:
        connection: Active Netmiko connection
        logger: Logger for command execution
        output_dir: Directory to save parsed output
        include_raw: Whether to include raw data in the output
        prometheus_config: Prometheus export configuration, if enabled
        csv_config: CSV export configuration, if enabled
        ap_address: Original AP address, used to handle hostname truncation
        
    Returns:
        Dictionary with command execution results
    """
    # Make sure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Commands to run in order
    commands = [
        "show clock",
        "show gnss info",
        "show version",
        "show inventory",
        "show capwap client configuration"
    ]
    
    # Collect all outputs
    full_output = ""
    
    # Run each command and collect output
    for command in commands:
        if logger:
            logger.info(f"Executing command: {command}")
        
        try:
            # Run command with extended timeout for potentially slow commands
            command_output = connection.send_command(
                command, 
                read_timeout=DEFAULT_COMMAND_TIMEOUT
            )
            
            # If we got output, add it to full output with command prompt
            if command_output:
                # Add command with prompt to full output
                full_output += f"{connection.base_prompt}#{command}\n{command_output}\n\n"
                
                if logger:
                    logger.info(f"Command completed successfully")
            else:
                if logger:
                    logger.warning(f"Command returned no output")
        
        except Exception as e:
            error_msg = f"Error executing command '{command}': {str(e)}"
            if logger:
                logger.error(error_msg)
            
            # Continue to next command even if this one failed
            continue
    
    # Create a timestamp and hostname for the output filename
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    
    # Get hostname from the connection's base_prompt, but handle potential truncation
    base_hostname = connection.base_prompt.replace(" ", "_")
    
    # NETMIKO TRUNCATION ISSUE:
    # Netmiko has a known behavior where the base_prompt property might truncate hostnames
    # under certain conditions. This is especially common with hostnames containing hyphens
    # where the final segment is just one or two characters. For example:
    # "ogxwsc-outdoor-ap1" might be truncated to "ogxwsc-outdoor-a"
    # This truncation affects:
    # 1. Output filenames
    # 2. The main_ap_name field in the parsed data
    #
    # The detection pattern looks for:
    # - Hostname containing a hyphen
    # - Last segment after hyphen is just 1 or 2 characters
    # - Original AP address is available for cross-checking
    if ap_address and '-' in base_hostname and len(base_hostname.split('-')[-1]) <= 2:
        # Extract hostname part from the FQDN (e.g., "ogxwsc-outdoor-ap1" from "ogxwsc-outdoor-ap1.mgmt.weber.edu")
        original_hostname = ap_address.split('.')[0]
        
        # Check if the original hostname is longer and starts with the base_hostname (minus the last char)
        # This provides stronger validation that we're dealing with a truncation
        if len(original_hostname) > len(base_hostname) and original_hostname.startswith(base_hostname[:-1]):
            hostname = original_hostname
            if logger:
                logger.info(f"Detected truncated hostname. Original base_prompt: '{base_hostname}' (length: {len(base_hostname)})")
                logger.info(f"Using original hostname from AP address: '{hostname}' (length: {len(hostname)})")
        else:
            hostname = base_hostname
            if logger:
                logger.info(f"Hostname contained hyphen with short final segment but didn't match truncation pattern.")
                logger.info(f"Using original base_prompt: '{hostname}' (length: {len(hostname)})")
    else:
        hostname = base_hostname
        if logger:
            logger.info(f"Using hostname from base_prompt: '{hostname}' (length: {len(hostname)})")
    
    # Parse the collected output
    if logger:
        logger.info("Parsing collected command output")
    
    # Check if we have any output to parse
    if not full_output or not full_output.strip():
        error_msg = "No command output collected for parsing"
        if logger:
            logger.error(error_msg)
        
        # Save an empty raw output file to indicate the issue
        raw_output_file = os.path.join(output_dir, f"{timestamp}-{hostname}-no-output.txt")
        with open(raw_output_file, 'w', encoding='utf-8') as f:
            f.write("No command output was collected - all commands may have failed or returned empty results\n")
        
        return {
            "success": False,
            "hostname": hostname,
            "error": error_msg,
            "raw_output_file": raw_output_file
        }
    
    try:
        # Use the GnssInfoParser to parse the GNSS data
        gnss_parser = GnssInfoParser()
        parsed_data = gnss_parser.parse(full_output, ap_address)
        
        # Use the CapwapConfigParser to parse the CAPWAP client configuration data
        capwap_parser = CapwapConfigParser()
        capwap_data = capwap_parser.parse(full_output)
        
        # Merge the CAPWAP client configuration data into the parsed data
        # Since it's already nested under show_capwap_client_config, we can merge directly
        for key, value in capwap_data.items():
            parsed_data[key] = value
        
        # Add metadata
        parsed_data["metadata"] = {
            "gnss_parser_version": gnss_parser.get_version(),
            "capwap_parser_version": capwap_parser.get_version(),
            "parse_time": datetime.now().isoformat(),
            "collection_method": "ssh",
            "ap_address": connection.host,
            "collector_timestamp": timestamp
        }
        
        # Create an OrderedDict with metadata first, then add the rest of the data
        ordered_data: Dict[str, Any] = OrderedDict([("metadata", parsed_data["metadata"])])
        
        # Add all other keys from parsed_data
        for key, value in parsed_data.items():
            if key != "metadata":
                ordered_data[key] = value
        
        # Remove raw_data if not requested
        if not include_raw and "raw_data" in ordered_data:
            del ordered_data["raw_data"]
        
        # Save the parsed data to a JSON file
        output_file = os.path.join(output_dir, f"{timestamp}-{hostname}.json")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(ordered_data, f, indent=4, ensure_ascii=False)
        
        if logger:
            logger.info(f"Parsed data saved to {output_file}")
        
        # Export to Prometheus if enabled
        prometheus_result = {
            "success": False,
            "error": "Prometheus export not enabled",
            "details": None
        }
        
        if prometheus_config and prometheus_config.get("enabled"):
            if logger:
                logger.info(f"Exporting data to Prometheus Pushgateway: {prometheus_config.get('url')}")
            
            # Check if Prometheus client is available
            if not is_prometheus_available():
                error_msg = "Prometheus client library not available. Install with 'pip install prometheus-client'"
                if logger:
                    logger.error(error_msg)
                prometheus_result["error"] = error_msg
            else:
                try:
                    # Get debug mode from config
                    debug_mode = prometheus_config.get("debug", DEFAULT_PROMETHEUS_DEBUG)
                    
                    # Log Prometheus configuration details when debug is enabled
                    if debug_mode and logger:
                        logger.info(f"Prometheus configuration: URL={prometheus_config.get('url')}, "
                                   f"Job={prometheus_config.get('job')}, "
                                   f"Timeout={prometheus_config.get('timeout')}, "
                                   f"Auth={'Yes' if prometheus_config.get('username') else 'No'}")
                        
                        # Log data sizes to help identify potential issues
                        data_size = len(json.dumps(ordered_data))
                        logger.info(f"Data size to be exported: {data_size} bytes")
                        
                        # Log some key data points that will be exported
                        if "gnss_state" in ordered_data:
                            state = ordered_data["gnss_state"].get("state", "Unknown")
                            fix_type = ordered_data["gnss_state"].get("fix_type", "Unknown")
                            logger.info(f"GNSS State: {state}, Fix Type: {fix_type}")
                    
                    # Push data to Prometheus with debug mode
                    push_success = push_gnss_data_to_prometheus(
                        data=ordered_data,
                        gateway_url=prometheus_config.get("url"),
                        job_name=prometheus_config.get("job"),
                        username=prometheus_config.get("username"),
                        password=prometheus_config.get("password"),
                        timeout=prometheus_config.get("timeout", 10),
                        logger=logger,
                        debug=debug_mode
                    )
                    
                    if push_success:
                        if logger:
                            logger.info("Successfully exported data to Prometheus")
                        prometheus_result = {
                            "success": True, 
                            "error": None,
                            "details": "Data successfully exported to Prometheus"
                        }
                    else:
                        error_msg = "Failed to export data to Prometheus (see logs for details)"
                        if logger:
                            logger.error(error_msg)
                            # Check log file for possible connectivity issues
                            logger.info("Verify Prometheus gateway is accessible and properly configured")
                            logger.info(f"Check connectivity to {prometheus_config.get('url')} from this host")
                        
                        prometheus_result = {
                            "success": False,
                            "error": error_msg,
                            "details": "Check logs for more details on the failure"
                        }
                        
                except Exception as e:
                    error_msg = f"Error exporting to Prometheus: {str(e)}"
                    if logger:
                        logger.error(error_msg)
                        logger.error(f"Exception type: {type(e).__name__}")
                        
                        # Provide more verbose error information in debug mode
                        if prometheus_config.get("debug", DEFAULT_PROMETHEUS_DEBUG):
                            logger.error(f"Exception traceback: {traceback.format_exc()}")
                    
                    prometheus_result = {
                        "success": False,
                        "error": error_msg,
                        "details": traceback.format_exc() if prometheus_config.get("debug", DEFAULT_PROMETHEUS_DEBUG) else None
                    }
        
        # Store the parsed data for potential CSV export later
        csv_result = {
            "success": False,
            "error": "CSV export not enabled",
            "details": None
        }
        
        # Determine if this should be considered a successful result
        # Success means we have meaningful parsed data beyond just metadata
        success = True
        error_msg = None
        
        # Check if we have meaningful parsed data
        if not ordered_data or len(ordered_data) <= 1: # Only metadata
            success = False
            error_msg = "Parsed data is empty or contains only metadata"
            if logger:
                logger.warning(error_msg)
        else:
            # Check if main data sections are present
            main_sections = ['gnss_state', 'show_version', 'satellites']
            has_data = any(section in ordered_data for section in main_sections)
            if not has_data:
                success = False
                error_msg = "Parsed data missing main GNSS/version sections"
                if logger:
                    logger.warning(error_msg)
        
        return {
            "success": success,
            "hostname": hostname,
            "output_file": output_file,
            "parsed_data": ordered_data if success else None,
            "error": error_msg,
            "prometheus_export": prometheus_result["success"],
            "prometheus_error": prometheus_result["error"],
            "prometheus_details": prometheus_result["details"],
            "csv_export": csv_result["success"],
            "csv_error": csv_result["error"],
            "csv_details": csv_result["details"]
        }
        
    except Exception as e:
        error_msg = f"Error parsing command output: {str(e)}"
        if logger:
            logger.error(error_msg)
        
        # Save the raw output as a text file since parsing failed
        raw_output_file = os.path.join(output_dir, f"{timestamp}-{hostname}-raw.txt")
        
        with open(raw_output_file, 'w', encoding='utf-8') as f:
            f.write(full_output)
        
        if logger:
            logger.info(f"Raw output saved to {raw_output_file}")
        
        return {
            "success": False,
            "hostname": hostname,
            "error": error_msg,
            "raw_output_file": raw_output_file
        }


def process_single_ap(
    ap_address: str,
    username: str,
    password: str,
    enable_password: Optional[str] = None,
    log_dir: str = DEFAULT_LOG_DIR,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    include_raw: bool = False,
    port: int = DEFAULT_SSH_PORT,
    prometheus_config: Optional[Dict[str, Any]] = None,
    csv_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Process a single access point.
    
    Args:
        ap_address: AP address (hostname or IP)
        username: SSH username
        password: SSH password
        enable_password: Enable password (if different)
        log_dir: Directory for session logs
        output_dir: Directory for command output
        include_raw: Whether to include raw data
        port: SSH port
        prometheus_config: Prometheus export configuration, if enabled
        csv_config: CSV export configuration, if enabled
        
    Returns:
        Dictionary with results for the AP
    """
    # Set up logging for this AP
    logger, log_file = setup_logging(ap_address, log_dir)
    
    try:
        # Connect to the AP
        connection_result = connect_to_ap(
            ap_address=ap_address,
            username=username, 
            password=password,
            enable_password=enable_password,
            port=port,
            logger=logger
        )
        
        if not connection_result["success"]:
            logger.error(f"Failed to connect: {connection_result.get('error', 'Unknown error')}")
            return {
                "ap_address": ap_address,
                "success": False,
                "error": connection_result.get("error"),
                "log_file": log_file
            }
        
        # Successfully connected, run commands
        connection = connection_result["connection"]
        
        # Run commands and parse output
        command_result = run_ap_commands(
            connection=connection,
            logger=logger,
            output_dir=output_dir,
            include_raw=include_raw,
            prometheus_config=prometheus_config,
            csv_config=csv_config,
            ap_address=ap_address  # Pass the original AP address
        )
        
        # Safely disconnect
        try:
            logger.info("Disconnecting from AP")
            connection.disconnect()
            logger.info("Disconnected successfully")
        except Exception as e:
            logger.warning(f"Error during disconnect: {str(e)}")
        
        # Return results
        result = {
            "ap_address": ap_address,
            "success": command_result["success"],
            "hostname": command_result.get("hostname", "unknown"),
            "output_file": command_result.get("output_file"),
            "raw_output_file": command_result.get("raw_output_file"),
            "log_file": log_file,
            "error": command_result.get("error")
        }
        
        # Include parsed_data for CSV export if available
        if "parsed_data" in command_result:
            result["parsed_data"] = command_result["parsed_data"]
        
        # Add Prometheus export result and details
        if "prometheus_export" in command_result:
            result["prometheus_export"] = command_result["prometheus_export"]
            
            # Include detailed error information if available
            if not command_result["prometheus_export"] and "prometheus_error" in command_result:
                result["prometheus_error"] = command_result.get("prometheus_error")
                result["prometheus_details"] = command_result.get("prometheus_details")
        
        return result
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            "ap_address": ap_address,
            "success": False,
            "error": str(e),
            "log_file": log_file
        }


def read_ap_list_from_file(file_path: str) -> List[str]:
    """
    Read a list of AP addresses from a file.
    
    Args:
        file_path: Path to file containing AP addresses (can include ~)
        
    Returns:
        List of AP addresses, or empty list on error.
    """
    ap_list_internal = []
    # Ensure the path is absolute and user-expanded before trying to open
    actual_path = os.path.abspath(os.path.expanduser(file_path))
    
    if not os.path.isfile(actual_path):
        print(f"Error in read_ap_list_from_file: File not found at resolved path '{actual_path}' (original input: '{file_path}').")
        return []

    try:
        with open(actual_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    ap_list_internal.append(line)
        if not ap_list_internal:
            # This is more of a warning than an error if the file is empty or only has comments
            print(f"Info in read_ap_list_from_file: No APs loaded from '{actual_path}'. File might be empty or only contain comments/empty lines.")
        return ap_list_internal
    except Exception as e:
        print(f"Error reading AP list from {actual_path}: {str(e)}")
        return []


def get_prometheus_config() -> Dict[str, Any]:
    """
    Get Prometheus configuration from environment variables.
    
    Returns:
        Dictionary containing Prometheus configuration
    """
    prometheus_config = {
        "enabled": DEFAULT_PROMETHEUS_ENABLED,
        "url": DEFAULT_PROMETHEUS_URL,
        "job": DEFAULT_PROMETHEUS_JOB,
        "username": DEFAULT_PROMETHEUS_USERNAME,
        "password": DEFAULT_PROMETHEUS_PASSWORD,
        "timeout": DEFAULT_PROMETHEUS_TIMEOUT,
        "debug": DEFAULT_PROMETHEUS_DEBUG
    }
    
    return prometheus_config


def get_csv_config() -> Dict[str, Any]:
    """
    Get CSV export configuration from environment variables.
    
    Returns:
        Dictionary with CSV configuration
    """
    csv_config = {
        "enabled": DEFAULT_CSV_ENABLED,
        "output_file": DEFAULT_CSV_OUTPUT_FILE,
        "append_mode": DEFAULT_CSV_APPEND_MODE,
        "debug": False  # Will be set from command line args
    }
    
    return csv_config


def main():
    """Main function to connect to APs and collect data."""
    # Load environment variables from .env file. This populates the DEFAULT_* globals.
    load_env_config()

    parser = argparse.ArgumentParser(description='Connect to Cisco APs via SSH and collect GNSS data')

    # Create group for AP selection (either single AP or file with list)
    # Make the group not strictly required by argparse; we'll check manually later.
    ap_group = parser.add_mutually_exclusive_group()  # Removed required=True
    ap_group.add_argument('-a', '--ap-address', help='Hostname or IP address of the AP')
    ap_group.add_argument('-f', '--file', help='File containing a list of AP addresses (overrides AP_LIST_FILE env var if used)')

    # Authentication parameters
    parser.add_argument('-u', '--username', help='SSH username')
    parser.add_argument('-p', '--password', help='SSH password (will prompt if not provided)')
    parser.add_argument('-e', '--enable-password', help='Enable password (if different from SSH password)')
    
    # Other parameters
    parser.add_argument('--port', type=int, default=DEFAULT_SSH_PORT, help='SSH port number')
    parser.add_argument('-o', '--output-dir', default=DEFAULT_OUTPUT_DIR, help='Output directory for parsed data')
    parser.add_argument('-l', '--log-dir', default=DEFAULT_LOG_DIR, help='Directory for SSH session logs')
    parser.add_argument('-r', '--include-raw', action='store_true', default=DEFAULT_INCLUDE_RAW_DATA, 
                       help='Include raw data in parsed output')
    parser.add_argument('-c', '--concurrent', type=int, default=DEFAULT_CONCURRENT_CONNECTIONS, 
                       help=f'Number of concurrent AP connections (default: {DEFAULT_CONCURRENT_CONNECTIONS})')
    
    # New argument for general .env debug
    parser.add_argument('--debug-env', action='store_true', default=False, 
                       help='Enable verbose debugging for .env file loading and initial settings from environment.')

    # Prometheus parameters
    prometheus_group = parser.add_argument_group('Prometheus export options')
    prometheus_group.add_argument('--prometheus', action='store_true', default=DEFAULT_PROMETHEUS_ENABLED,
                                help='Enable export to Prometheus Pushgateway')
    prometheus_group.add_argument('--prometheus-url', 
                                help='URL of the Prometheus Pushgateway (e.g., http://localhost:9091)')
    prometheus_group.add_argument('--prometheus-job', default=DEFAULT_PROMETHEUS_JOB,
                                help='Job name for Prometheus metrics')
    prometheus_group.add_argument('--prometheus-username', 
                                help='Username for Prometheus Pushgateway authentication')
    prometheus_group.add_argument('--prometheus-password', 
                                help='Password for Prometheus Pushgateway authentication')
    prometheus_group.add_argument('--prometheus-timeout', type=int, default=DEFAULT_PROMETHEUS_TIMEOUT,
                                help='Timeout in seconds for Prometheus Pushgateway connection')
    prometheus_group.add_argument('--prometheus-debug', action='store_true', default=DEFAULT_PROMETHEUS_DEBUG,
                                help='Enable verbose debugging for Prometheus export')
    
    # CSV export parameters
    csv_group = parser.add_argument_group('CSV export options')
    csv_group.add_argument('--csv', action='store_true', default=DEFAULT_CSV_ENABLED,
                          help='Enable export to CSV format')
    csv_group.add_argument('--csv-output', 
                          help='Output CSV file path (default: auto-generated with timestamp)')
    csv_group.add_argument('--csv-append', action='store_true', default=DEFAULT_CSV_APPEND_MODE,
                          help='Append to existing CSV file instead of overwriting')
    csv_group.add_argument('--csv-debug', action='store_true', default=False,
                          help='Enable verbose debugging for CSV export operations')
    
    args = parser.parse_args()

    # Determine effective debug level for .env loading
    # DEFAULT_ENV_DEBUG is set by load_env_config() from AP_ENV_DEBUG (or remains False).
    # args.debug_env is True if --debug-env is used on CLI, False otherwise.
    effective_env_debug = DEFAULT_ENV_DEBUG or args.debug_env

    if effective_env_debug:
        print("\\n### Environment Settings Debug Info ###")
        
        env_file_path = find_dotenv_file()
        if env_file_path:
            print(f"  Note: .env file found at '{env_file_path}' was consulted during loading.")
        else:
            print("  Note: No .env file was found by find_dotenv_file(); settings are from environment variables or script defaults.")

        # This dictionary maps the environment variable names to the global DEFAULT_* variables
        # that store their values after being processed by load_env_config().
        env_vars_to_report = {
            "AP_PROMETHEUS_ENABLED": DEFAULT_PROMETHEUS_ENABLED,
            "AP_PROMETHEUS_URL": DEFAULT_PROMETHEUS_URL,
            "AP_PROMETHEUS_JOB": DEFAULT_PROMETHEUS_JOB,
            "AP_PROMETHEUS_USERNAME": DEFAULT_PROMETHEUS_USERNAME,
            "AP_PROMETHEUS_PASSWORD": DEFAULT_PROMETHEUS_PASSWORD,
            "AP_PROMETHEUS_TIMEOUT": DEFAULT_PROMETHEUS_TIMEOUT,
            "AP_PROMETHEUS_DEBUG": DEFAULT_PROMETHEUS_DEBUG, # For Prometheus-specific debug
            "AP_CSV_ENABLED": DEFAULT_CSV_ENABLED,
            "AP_CSV_OUTPUT_FILE": DEFAULT_CSV_OUTPUT_FILE,
            "AP_CSV_APPEND_MODE": DEFAULT_CSV_APPEND_MODE,
            "AP_ENV_DEBUG": DEFAULT_ENV_DEBUG # The general .env debug flag itself
            # Add other DEFAULT_* variables here if they are loaded from .env and relevant to report
        }
        
        print("  Current values for key configurations (after .env load, before CLI overrides for execution):")
        any_config_shown = False
        for config_name, current_value_from_global in env_vars_to_report.items():
            original_env_value_str = os.getenv(config_name)
            type_name = type(current_value_from_global).__name__
            if original_env_value_str is not None:
                print(f"  - {config_name}: {current_value_from_global} (type: {type_name}) (from .env/environment: '{original_env_value_str}')")
            else:
                print(f"  - {config_name}: {current_value_from_global} (type: {type_name}) (not in .env/environment, using script default or logic)")
            any_config_shown = True

        if not any_config_shown:
            print("  No key configurations to report from the predefined list.")
        print("###########################################################\\n")

    # Get credentials (from args, environment, or prompt)
    env_creds = get_credentials()
    
    username = args.username or env_creds["username"]
    password = args.password or env_creds["password"]
    enable_password = args.enable_password or env_creds["enable_password"]
    
    # Prompt for missing credentials
    if not username:
        username = input("Enter SSH username: ")
    
    if not password:
        password = getpass.getpass("Enter SSH password: ")
    
    if not enable_password:
        enable_password_prompt = "Enter enable password (press Enter to use SSH password): "
        enable_password_input = getpass.getpass(enable_password_prompt)
        enable_password = enable_password_input if enable_password_input else password
    
    # Get Prometheus configuration
    prometheus_config = get_prometheus_config()

    # Get CSV configuration
    csv_config = get_csv_config()

    # Override with command line arguments if provided
    prometheus_config["enabled"] = args.prometheus
    if args.prometheus_url:
        prometheus_config["url"] = args.prometheus_url
    if args.prometheus_job:
        prometheus_config["job"] = args.prometheus_job
    if args.prometheus_username:
        prometheus_config["username"] = args.prometheus_username
    if args.prometheus_password:
        prometheus_config["password"] = args.prometheus_password
    if args.prometheus_timeout: # This was missing in the original, ensuring it's here.
        prometheus_config["timeout"] = args.prometheus_timeout
    prometheus_config["debug"] = args.prometheus_debug # This correctly sets the final debug state for Prometheus operations

    # Override CSV configuration with command line arguments if provided
    csv_config["enabled"] = args.csv
    if args.csv_output:
        csv_config["output_file"] = args.csv_output
    csv_config["append_mode"] = args.csv_append
    csv_config["debug"] = args.csv_debug  # Add debug flag from command line
    
    # If CSV is enabled, set up output file if not specified
    if csv_config["enabled"] and not csv_config["output_file"]:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        csv_config["output_file"] = f"ap_gnss_export_{timestamp}.csv"
    
    # If Prometheus is enabled but URL is not set, prompt for it
    if prometheus_config["enabled"] and not prometheus_config["url"]:
        prometheus_config["url"] = input("Enter Prometheus Pushgateway URL: ")
        if not prometheus_config["url"]:
            print("Prometheus export disabled due to missing URL")
            prometheus_config["enabled"] = False
    
    # Display Prometheus status
    if prometheus_config["enabled"]:
        print(f"Prometheus export enabled, using pushgateway: {prometheus_config['url']}")
        if prometheus_config["debug"]: # This uses the final, potentially CLI-overridden, debug value
            print("Prometheus debug mode enabled - detailed logging for Prometheus operations will be available")
        
        # Verify required dependencies
        if not is_prometheus_available():
            print("Warning: Prometheus client library not installed. Install with 'pip install prometheus-client'")
            print("Prometheus export will be skipped.")
            prometheus_config["enabled"] = False
    
    # Display CSV status
    if csv_config["enabled"]:
        print(f"CSV export enabled, output file: {csv_config['output_file']}")
        append_mode_text = "append" if csv_config["append_mode"] else "overwrite"
        print(f"CSV mode: {append_mode_text}")
    
    # Determine the list of APs to process
    ap_list: List[str] = []
    ap_source_description = ""
    raw_ap_list_for_dedupe_check: Optional[List[str]] = None 
    source_file_for_dedupe_check: Optional[str] = None

    if args.ap_address:
        ap_list = [args.ap_address]
        ap_source_description = f"AP address from command line: \'{args.ap_address}\'"
    elif args.file:  # -f/--file was explicitly used
        print(f"Info: Using AP list file from --file argument: \'{args.file}\'")
        expanded_file_path = os.path.expanduser(args.file)
        if os.path.isfile(expanded_file_path):
            ap_list_raw_from_file = read_ap_list_from_file(expanded_file_path)
            if ap_list_raw_from_file:
                raw_ap_list_for_dedupe_check = list(ap_list_raw_from_file) # Keep original for dedupe message
                source_file_for_dedupe_check = expanded_file_path
                ap_list = list(OrderedDict.fromkeys(ap_list_raw_from_file))
                ap_source_description = f"AP list from file (command line): \'{expanded_file_path}\'"
                if not ap_list: 
                     print(f"Warning: AP list file from --file argument (\'{args.file}\') resulted in an empty list after processing (e.g. only duplicates, or empty lines).")
            else:
                # File was specified by -f but was empty or only comments
                print(f"Warning: AP list file from --file argument (\'{args.file}\') was empty or only contained comments. Check file content.")
        else:
            # File specified by -f not found
            print(f"Error: AP list file specified with --file argument (\'{args.file}\' expanded to \'{expanded_file_path}\') not found or is not a regular file.")
            # If -f is used, it must be a valid file; no fallback to AP_LIST_FILE here.
            # The script will exit later if ap_list remains empty.
    else: # Neither -a nor -f was used on the command line, try AP_LIST_FILE from environment
        env_ap_list_file = os.getenv("AP_LIST_FILE")
        if env_ap_list_file:
            print(f"Info: No AP address or file specified on command line. Checking AP_LIST_FILE environment variable: \'{env_ap_list_file}\'")
            expanded_env_file_path = os.path.expanduser(env_ap_list_file)
            if os.path.isfile(expanded_env_file_path):
                ap_list_raw_from_env = read_ap_list_from_file(expanded_env_file_path)
                if ap_list_raw_from_env:
                    raw_ap_list_for_dedupe_check = list(ap_list_raw_from_env)
                    source_file_for_dedupe_check = expanded_env_file_path
                    ap_list = list(OrderedDict.fromkeys(ap_list_raw_from_env))
                    ap_source_description = f"AP list from AP_LIST_FILE (environment variable): \'{expanded_env_file_path}\'"
                    if not ap_list: # If deduplication resulted in an empty list
                        print(f"Warning: AP list file from AP_LIST_FILE (\'{expanded_env_file_path}\') resulted in an empty list after processing.")
                else:
                    # AP_LIST_FILE was found but empty or only comments
                    print(f"Warning: AP list file from AP_LIST_FILE environment variable (\'{expanded_env_file_path}\') is empty or only contained comments.")
            else:
                # AP_LIST_FILE points to a non-existent file
                print(f"Error: AP list file from AP_LIST_FILE environment variable (\'{expanded_env_file_path}\') not found or is not a regular file.")
        # If env_ap_list_file is None (AP_LIST_FILE not set), ap_list remains empty, handled by the check below.

    # Check for duplicates if list came from a file and print info
    if raw_ap_list_for_dedupe_check is not None and source_file_for_dedupe_check is not None:
        if len(ap_list) < len(raw_ap_list_for_dedupe_check):
            print(f"Info: Duplicate AP entries found in \'{source_file_for_dedupe_check}\'. Processing {len(ap_list)} unique AP(s).")
            print(f"      (Original count: {len(raw_ap_list_for_dedupe_check)}, Unique count: {len(ap_list)})")

    if not ap_list:
        parser.error( # parser.error will print usage and exit
            "No APs to process. Please provide an AP address using -a/--ap-address, "
            "a valid AP list file using -f/--file, or set the AP_LIST_FILE environment variable "
            "to point to a valid file that contains AP addresses."
        )
    
    print(f"Will process {len(ap_list)} access point(s). Source: {ap_source_description}")
    
    # Process APs (single-threaded or multi-threaded)
    results = []
    
    if args.concurrent <= 1 or len(ap_list) == 1:
        # Single-threaded processing
        for ap_address in ap_list:
            print(f"Processing AP: {ap_address}")
            result = process_single_ap(
                ap_address=ap_address,
                username=username,
                password=password,
                enable_password=enable_password,
                log_dir=args.log_dir,
                output_dir=args.output_dir,
                include_raw=args.include_raw,
                port=args.port,
                prometheus_config=prometheus_config,
                csv_config=csv_config
            )
            results.append(result)
            print(f"Completed AP: {ap_address} - {'Success' if result['success'] else 'Failed'}")
            if not result['success']:
                print(f"  Error: {result.get('error', 'Unknown error')}")
            print(f"  Log file: {result['log_file']}")
            if 'output_file' in result:
                print(f"  Output file: {result['output_file']}")
            if 'prometheus_export' in result:
                prometheus_status = "Success" if result['prometheus_export'] else "Failed"
                print(f"  Prometheus export: {prometheus_status}")
                if not result['prometheus_export'] and 'prometheus_error' in result:
                    print(f"    Error: {result.get('prometheus_error')}")
                    print(f"    Check log file for details: {result['log_file']}")
    else:
        # Multi-threaded processing
        print(f"Using {min(args.concurrent, len(ap_list))} concurrent connections")
        
        # Define a thread function
        def process_ap_thread(ap_address):
            print(f"Starting thread for AP: {ap_address}")
            result = process_single_ap(
                ap_address=ap_address,
                username=username,
                password=password,
                enable_password=enable_password,
                log_dir=args.log_dir,
                output_dir=args.output_dir,
                include_raw=args.include_raw,
                port=args.port,
                prometheus_config=prometheus_config,
                csv_config=csv_config
            )
            results.append(result)
            print(f"Thread completed for AP: {ap_address}")
            # Add immediate Prometheus status feedback for this AP
            if 'prometheus_export' in result:
                prometheus_status = "Success" if result['prometheus_export'] else "Failed"
                print(f"  Prometheus export for {ap_address}: {prometheus_status}")
                if not result['prometheus_export'] and prometheus_config["debug"]:
                    print(f"    Error: {result.get('prometheus_error', 'Unknown error')}")
        
        # Create and start threads (with throttling)
        threads = []
        max_threads = min(args.concurrent, len(ap_list))
        active_threads = 0
        
        for ap_address in ap_list:
            # Wait if we've reached max concurrent threads
            while active_threads >= max_threads:
                # Check for completed threads
                for t in threads[:]:
                    if not t.is_alive():
                        threads.remove(t)
                        active_threads -= 1
                time.sleep(0.5)
            
            # Start a new thread
            thread = threading.Thread(target=process_ap_thread, args=(ap_address,))
            thread.start()
            threads.append(thread)
            active_threads += 1
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
    
    # Print summary
    success_count = sum(1 for r in results if r["success"])
    failure_count = len(results) - success_count
    
    print("\nProcessing complete")
    print(f"  Total APs: {len(results)}")
    print(f"  Successful: {success_count}")
    print(f"  Failed: {failure_count}")
    
    # Print Prometheus summary if enabled
    if prometheus_config["enabled"]:
        prom_success = sum(1 for r in results if r.get("prometheus_export", False))
        prom_failure = sum(1 for r in results if r.get("prometheus_export") is False)
        prom_skipped = len(results) - prom_success - prom_failure
        
        print("\nPrometheus export summary:")
        print(f"  Success: {prom_success}")
        print(f"  Failed: {prom_failure}")
        if prom_skipped > 0:
            print(f"  Skipped: {prom_skipped} (parse failures)")
        
        # If any Prometheus exports failed, show a detailed summary
        if prom_failure > 0:
            print("\nPrometheus export failures:")
            for result in results:
                if result.get("prometheus_export") is False:
                    ap_id = result.get("hostname", result.get("ap_address", "unknown"))
                    error_msg = result.get("prometheus_error", "Unknown error")
                    print(f"  {ap_id}: {error_msg}")
                    # Show the log file location for debugging
                    print(f"    Log file: {result['log_file']}")
            
            # Add troubleshooting tips
            print("\nTroubleshooting tips:")
            print("  1. Check connectivity to the Prometheus Pushgateway")
            print(f"     - Can you reach {prometheus_config['url']} from this host?")
            print("  2. Verify Pushgateway is running and accepting connections")
            print("  3. Check the log files for detailed error messages")
            print("  4. Run with --prometheus-debug flag for more detailed logging")
            if not prometheus_config["debug"]:
                print("     Example: Add --prometheus-debug to your command line")
    
    # Export to CSV if enabled and we have successful results
    if csv_config["enabled"] and success_count > 0:
        print(f"\nExporting {success_count} successful AP record(s) to CSV: {csv_config['output_file']}")
        
        # Collect parsed data from successful results
        csv_data_list = []
        missing_data_count = 0
        
        # Debug: Check result structure for successful APs
        print("Debug: Analyzing successful AP results...")
        successful_aps = [r for r in results if r.get("success")]
        print(f"  Total successful APs: {len(successful_aps)}")
        
        # Count different types of results
        with_parsed_data = 0
        without_parsed_data = 0
        
        for i, result in enumerate(successful_aps):
            ap_addr = result.get('ap_address', 'unknown')
            has_parsed_data = "parsed_data" in result
            
            if has_parsed_data:
                with_parsed_data += 1
                # Only show details for first few and last few, or if there are issues
                if i < 5 or i >= len(successful_aps) - 5 or len(successful_aps) <= 10:
                    print(f"  [{i+1}] {ap_addr}: parsed_data=True")
            else:
                without_parsed_data += 1
                print(f"  [{i+1}] {ap_addr}: parsed_data=False")
                # Check what keys are available
                available_keys = list(result.keys())
                print(f"    Available keys: {available_keys}")
                if 'error' in result:
                    print(f"    Error: {result['error']}")
        
        # Show summary for large lists
        if len(successful_aps) > 10:
            print(f"  ... (showing first 5 and last 5 of {len(successful_aps)} successful APs)")
        
        print(f"  Summary: {with_parsed_data} with data, {without_parsed_data} missing data")
        
        # Collect the data
        for result in successful_aps:
            if "parsed_data" in result:
                csv_data_list.append(result["parsed_data"])
        
        if without_parsed_data > 0:
            print(f"Warning: {without_parsed_data} successful APs are missing parsed_data")
        
        if csv_data_list:
            try:
                # Enhanced debugging for CSV export
                if csv_config["debug"]:
                    print(f"\n=== CSV Export Debug Mode ===")
                    print(f"CSV output file: {csv_config['output_file']}")
                    print(f"CSV append mode: {csv_config['append_mode']}")
                    print(f"Number of AP records to export: {len(csv_data_list)}")
                    print(f"Output directory: {os.path.dirname(csv_config['output_file'])}")
                    print(f"Output directory exists: {os.path.exists(os.path.dirname(csv_config['output_file']))}")
                    
                    # Import and run the debug environment function
                    try:
                        from ap_gnss_stats.lib.exporters.csv_exporter import debug_csv_export_environment
                        debug_info = debug_csv_export_environment(csv_config["output_file"], None)
                        print(f"Environment debug info collected: {len(debug_info)} items")
                    except Exception as debug_error:
                        print(f"Debug info collection error: {debug_error}")
                else:
                    # Basic debug info (always shown)
                    print(f"\n=== CSV Export Info ===")
                    print(f"CSV output file: {csv_config['output_file']}")
                    print(f"CSV append mode: {csv_config['append_mode']}")
                    print(f"Number of AP records to export: {len(csv_data_list)}")
                    print(f"Number of AP records to export: {len(csv_data_list)}")
                
                # Set up logging for CSV export if debug mode is enabled
                csv_logger = None
                if csv_config["debug"]:
                    csv_logger = logging.getLogger('csv_export_debug')
                    csv_logger.setLevel(logging.DEBUG)
                    
                    # Create console handler if it doesn't exist
                    if not csv_logger.handlers:
                        console_handler = logging.StreamHandler()
                        console_handler.setLevel(logging.DEBUG)
                        formatter = logging.Formatter('CSV-DEBUG: %(message)s')
                        console_handler.setFormatter(formatter)
                        csv_logger.addHandler(console_handler)
                
                # Export to CSV using the CSV exporter with enhanced debugging
                export_success = export_gnss_data_to_csv(
                    data=csv_data_list,
                    output_file=csv_config["output_file"],
                    append_mode=csv_config["append_mode"],
                    logger=csv_logger
                )
                
                if export_success:
                    action = "appended to" if csv_config["append_mode"] else "created"
                    print(f"CSV export successful: {action} {csv_config['output_file']}")
                    
                    # Enhanced file verification (always run)
                    print(f"=== Post-Export Verification ===")
                    abs_path = os.path.abspath(csv_config["output_file"])
                    print(f"Absolute path: {abs_path}")
                    print(f"File exists: {os.path.exists(abs_path)}")
                    
                    if os.path.exists(abs_path):
                        try:
                            file_size = os.path.getsize(abs_path)
                            print(f"CSV file size: {file_size:,} bytes")
                            
                            # Count rows
                            import csv
                            with open(abs_path, 'r', encoding='utf-8') as f:
                                reader = csv.reader(f)
                                rows = list(reader)
                                print(f"CSV total rows (including header): {len(rows)}")
                                if rows:
                                    print(f"CSV columns: {len(rows[0])}")
                                    
                            # Additional debug info in debug mode
                            if csv_config["debug"]:
                                print(f"First few column names: {rows[0][:10] if rows else 'N/A'}")
                                if len(rows) > 1:
                                    print(f"First data row sample: {str(rows[1][:3])[:100]}...")
                                    
                        except Exception as verification_error:
                            print(f"File verification error: {verification_error}")
                            if csv_config["debug"]:
                                import traceback
                                print(f"Verification traceback: {traceback.format_exc()}")
                    else:
                        print(f"WARNING: CSV file does not exist after export!")
                        print(f"Checking directory contents...")
                        try:
                            directory = os.path.dirname(abs_path)
                            if os.path.exists(directory):
                                contents = os.listdir(directory)
                                print(f"Directory contents: {contents}")
                                
                                # Check if there are any CSV files in the directory
                                csv_files = [f for f in contents if f.endswith('.csv')]
                                if csv_files:
                                    print(f"CSV files found in directory: {csv_files}")
                            else:
                                print(f"Directory does not exist: {directory}")
                        except Exception as dir_error:
                            print(f"Could not list directory: {dir_error}")
                            
                else:
                    print("CSV export failed - check debug output above for details")
                    
            except Exception as e:
                print(f"CSV export error: {str(e)}")
                if csv_config["debug"]:
                    import traceback
                    print(f"Full traceback: {traceback.format_exc()}")
        else:
            print("No valid data available for CSV export")
    elif csv_config["enabled"] and success_count == 0:
        print("\nCSV export skipped - no successful AP data to export")
            
    # Print failures if any
    if failure_count > 0:
        print("\nFailed APs:")
        for result in results:
            if not result["success"]:
                print(f"  {result['ap_address']}: {result.get('error', 'Unknown error')}")
    
    return 0 if failure_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())