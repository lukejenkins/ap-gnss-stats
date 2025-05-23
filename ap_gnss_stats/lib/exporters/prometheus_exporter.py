#!/usr/bin/env python3
"""
Prometheus Pushgateway exporter for GNSS data.

This module provides functionality to export GNSS data to Prometheus using the Pushgateway.
It handles connection, metric definition, and data pushing.
"""

import os
import time
import logging
import traceback
import socket
import requests
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import re

# Try to import prometheus_client; if it fails, we'll handle it gracefully
try:
    from prometheus_client import CollectorRegistry, Gauge, Counter, push_to_gateway
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


def is_prometheus_available() -> bool:
    """
    Check if the Prometheus client library is available.
    
    Returns:
        bool: True if available, False otherwise
    """
    return PROMETHEUS_AVAILABLE


def push_gnss_data_to_prometheus(
    data: Dict[str, Any],
    gateway_url: str,
    job_name: str = "ap_gnss_stats",
    username: Optional[str] = None,
    password: Optional[str] = None,
    timeout: int = 10,
    logger: Optional[logging.Logger] = None,
    debug: bool = False
) -> bool:
    """
    Push GNSS data to Prometheus Pushgateway.
    
    Args:
        data: Parsed GNSS data in the standard format
        gateway_url: URL of the Prometheus Push Gateway (e.g., "http://localhost:9091")
        job_name: Name of the job in Prometheus
        username: Username for Push Gateway authentication (if required)
        password: Password for Push Gateway authentication (if required)
        timeout: Connection timeout in seconds
        logger: Logger for output messages
        debug: Whether to enable additional debug logging
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not PROMETHEUS_AVAILABLE:
        if logger:
            logger.error(
                "Prometheus client library not found. "
                "Install it with 'pip install prometheus-client'"
            )
        return False
        
    if not gateway_url:
        if logger:
            logger.error("Prometheus Gateway URL must be provided")
        return False
    
    # Create a logger if none was provided
    if not logger:
        logger = logging.getLogger(__name__)
    
    # Extract AP name from data (do this early for better logs)
    ap_name = _get_ap_name(data)
    if not ap_name:
        logger.warning("No AP name found in data, using 'unknown'")
        ap_name = "unknown"
    
    # Log attempt with detailed information
    logger.info(f"Attempting to push metrics for {ap_name} to Prometheus gateway: {gateway_url}")
    
    # Perform connectivity test before attempting to push
    conn_test_result = _test_gateway_connectivity(gateway_url, timeout, logger)
    if not conn_test_result["success"]:
        logger.error(f"Connectivity test to Prometheus gateway failed: {conn_test_result['error']}")
        return False
    
    logger.info(f"Connectivity test to {gateway_url} successful")
    
    try:
        # Log authentication information (without revealing credentials)
        if username:
            logger.info(f"Using HTTP Basic Auth for Prometheus gateway with username: {username}")
        
        # Initialize registry and metrics
        registry = CollectorRegistry()
        
        # Log the metrics creation process
        logger.info(f"Creating metrics for AP: {ap_name}")
        metric_counts = _create_prometheus_metrics_with_counts(registry, data, ap_name, logger, debug)
        
        if debug:
            for metric_type, count in metric_counts.items():
                logger.debug(f"Created {count} {metric_type} metrics")
        
        # Prepare grouping labels
        job_grouping = {"job": job_name}
        logger.info(f"Using job name: {job_name}, grouping keys: {job_grouping}")
        
        # Create auth handler if credentials are provided
        handler = None
        if username and password:
            handler = _create_auth_handler(username, password)
            if not handler:
                logger.warning("Failed to create authentication handler, proceeding without authentication")
        
        # Log push attempt
        logger.info(f"Pushing {sum(metric_counts.values())} metrics to Prometheus gateway: {gateway_url}")
        
        # Push to gateway - only include handler if it's not None
        start_time = time.time()
        push_kwargs = {
            "gateway": gateway_url,
            "job": job_name,
            "registry": registry,
            "grouping_key": job_grouping,
            "timeout": timeout
        }
        
        # Only add the handler if it exists
        if handler is not None:
            push_kwargs["handler"] = handler
            
        push_to_gateway(**push_kwargs)
        duration = time.time() - start_time
        
        logger.info(f"Successfully pushed GNSS data for {ap_name} to Prometheus Pushgateway in {duration:.2f} seconds")
        return True
            
    except requests.exceptions.RequestException as e:
        # Network or HTTP-specific errors
        logger.error(f"HTTP error pushing data to Prometheus: {str(e)}")
        if debug:
            logger.debug(f"Request exception details: {traceback.format_exc()}")
        return False
    except socket.error as e:
        # Socket-related errors
        logger.error(f"Socket error connecting to Prometheus gateway: {str(e)}")
        if debug:
            logger.debug(f"Socket error details: {traceback.format_exc()}")
        return False 
    except Exception as e:
        # General exception handling with more details
        logger.error(f"Error pushing data to Prometheus: {str(e)}")
        if debug:
            logger.debug(f"Exception details: {traceback.format_exc()}")
        return False


def _test_gateway_connectivity(gateway_url: str, timeout: int, logger: logging.Logger) -> Dict[str, Any]:
    """
    Test connectivity to the Prometheus gateway before attempting to push metrics.
    
    Args:
        gateway_url: The URL of the Prometheus Pushgateway
        timeout: Connection timeout in seconds
        logger: Logger for output
        
    Returns:
        Dict containing success status and error message if applicable
    """
    try:
        # Extract hostname and port from URL for initial connectivity test
        from urllib.parse import urlparse
        parsed_url = urlparse(gateway_url)
        
        hostname = parsed_url.hostname
        port = parsed_url.port
        
        if not hostname:
            return {"success": False, "error": f"Invalid URL format: {gateway_url}"}
            
        # If port is not specified, use default ports based on scheme
        if not port:
            if parsed_url.scheme == "https":
                port = 443
            else:
                port = 80
                
        logger.info(f"Testing TCP connection to {hostname}:{port}")
        
        # Attempt socket connection to test basic connectivity
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((hostname, port))
        sock.close()
        
        if result != 0:
            return {"success": False, "error": f"Could not connect to {hostname}:{port}, error code: {result}"}
        
        # Try HTTP HEAD request to verify service is responding
        logger.info(f"Testing HTTP connectivity to {gateway_url}")
        try:
            response = requests.head(gateway_url, timeout=timeout)
            logger.info(f"HTTP HEAD status: {response.status_code}")
            
            # Some Prometheus Pushgateways might return 405 Method Not Allowed for HEAD
            if response.status_code >= 400 and response.status_code not in [404, 405]:
                return {"success": False, "error": f"HTTP error: {response.status_code}"}
                
        except requests.exceptions.RequestException as req_err:
            return {"success": False, "error": f"HTTP request error: {req_err}"}
        
        return {"success": True}
        
    except Exception as e:
        return {"success": False, "error": f"Connectivity test error: {str(e)}"}


def _create_prometheus_metrics_with_counts(
    registry: Any, 
    data: Dict[str, Any], 
    ap_name: str,
    logger: logging.Logger,
    debug: bool = False
) -> Dict[str, int]:
    """
    Create and populate Prometheus metrics from GNSS data with metric counts.
    
    Args:
        registry: Prometheus collector registry
        data: Parsed GNSS data
        ap_name: AP name for labels
        logger: Logger for detailed information
        debug: Whether to log detailed metric creation info
        
    Returns:
        Dictionary with counts of created metrics by type
    """
    metric_counts = {
        "info": 0,
        "metadata": 0,
        "version": 0,
        "inventory": 0,
        "state": 0,
        "position": 0,
        "satellite": 0,
        "dop": 0,
        "uptime": 0,
        "timestamp": 0,
        "uncertainty": 0,
        "derivation": 0,  # New category
        "raw_data": 0      # New category
    }
    
    # Metadata metrics
    try:
        metadata_count = _create_metadata_metrics(registry, data, ap_name)
        metric_counts["metadata"] += metadata_count
        if debug:
            logger.debug(f"Created {metadata_count} metadata metrics for {ap_name}")
    except Exception as e:
        logger.warning(f"Failed to create metadata metrics: {str(e)}")
    
    # AP Info metric
    try:
        info_count = _create_ap_info_metric(registry, data, ap_name)
        metric_counts["info"] += info_count
        if debug:
            logger.debug(f"Created {info_count} AP info metrics for {ap_name}")
    except Exception as e:
        logger.warning(f"Failed to create AP info metrics: {str(e)}")
    
    # Version metrics
    try:
        version_count = _create_version_metrics(registry, data, ap_name)
        metric_counts["version"] += version_count
        if debug:
            logger.debug(f"Created {version_count} version metrics for {ap_name}")
    except Exception as e:
        logger.warning(f"Failed to create version metrics: {str(e)}")
    
    # Inventory metrics
    try:
        inventory_count = _create_inventory_metrics(registry, data, ap_name)
        metric_counts["inventory"] += inventory_count
        if debug:
            logger.debug(f"Created {inventory_count} inventory metrics for {ap_name}")
    except Exception as e:
        logger.warning(f"Failed to create inventory metrics: {str(e)}")
    
    # GNSS state metrics
    try:
        state_count = _create_gnss_state_metrics(registry, data, ap_name)
        metric_counts["state"] += state_count
        if debug:
            logger.debug(f"Created {state_count} GNSS state metrics for {ap_name}")
    except Exception as e:
        logger.warning(f"Failed to create GNSS state metrics: {str(e)}")
    
    # Position metrics
    try:
        position_count = _create_position_metrics(registry, data, ap_name)
        metric_counts["position"] += position_count
        if debug:
            logger.debug(f"Created {position_count} position metrics for {ap_name}")
    except Exception as e:
        logger.warning(f"Failed to create position metrics: {str(e)}")
    
    # Uncertainty ellipse metrics
    try:
        uncertainty_count = _create_uncertainty_metrics(registry, data, ap_name)
        metric_counts["uncertainty"] += uncertainty_count
        if debug:
            logger.debug(f"Created {uncertainty_count} uncertainty metrics for {ap_name}")
    except Exception as e:
        logger.warning(f"Failed to create uncertainty metrics: {str(e)}")
    
    # Satellite metrics
    try:
        satellite_count = _create_satellite_metrics(registry, data, ap_name)
        metric_counts["satellite"] += satellite_count
        if debug:
            logger.debug(f"Created {satellite_count} satellite metrics for {ap_name}")
    except Exception as e:
        logger.warning(f"Failed to create satellite metrics: {str(e)}")
    
    # DOP metrics
    try:
        dop_count = _create_dop_metrics(registry, data, ap_name)
        metric_counts["dop"] += dop_count
        if debug:
            logger.debug(f"Created {dop_count} DOP metrics for {ap_name}")
    except Exception as e:
        logger.warning(f"Failed to create DOP metrics: {str(e)}")
    
    # AP uptime
    try:
        uptime_count = _create_uptime_metrics(registry, data, ap_name)
        metric_counts["uptime"] += uptime_count
        if debug:
            logger.debug(f"Created {uptime_count} uptime metrics for {ap_name}")
    except Exception as e:
        logger.warning(f"Failed to create uptime metrics: {str(e)}")
    
    # Timestamp metrics
    try:
        timestamp_count = _create_timestamp_metrics(registry, data, ap_name)
        metric_counts["timestamp"] += timestamp_count
        if debug:
            logger.debug(f"Created {timestamp_count} timestamp metrics for {ap_name}")
    except Exception as e:
        logger.warning(f"Failed to create timestamp metrics: {str(e)}")
    
    # Source derivation metrics (new)
    try:
        derivation_count = _create_source_derivation_metrics(registry, data, ap_name)
        metric_counts["derivation"] += derivation_count
        if debug:
            logger.debug(f"Created {derivation_count} derivation metrics for {ap_name}")
    except Exception as e:
        logger.warning(f"Failed to create derivation metrics: {str(e)}")
    
    # Raw data metrics (new)
    try:
        raw_data_count = _create_raw_data_metrics(registry, data, ap_name)
        metric_counts["raw_data"] += raw_data_count
        if debug:
            logger.debug(f"Created {raw_data_count} raw data metrics for {ap_name}")
    except Exception as e:
        logger.warning(f"Failed to create raw data metrics: {str(e)}")
    
    return metric_counts


def _get_ap_name(data: Dict[str, Any]) -> str:
    """
    Extract AP name from data.
    
    Args:
        data: Parsed GNSS data
        
    Returns:
        str: AP name string or empty string if not found
    """
    # Try different sources for AP name in priority order
    if data.get("main", {}).get("main_ap_name"):
        return data["main"]["main_ap_name"]
    
    if data.get("show_version", {}).get("ver_ap_name"):
        return data["show_version"]["ver_ap_name"]
    
    if data.get("metadata", {}).get("input_file"):
        # Try to extract AP name from filename
        filename = data["metadata"]["input_file"]
        
        # Simple extraction patterns for common filenames
        patterns = [
            r'putty-([^-\.]+)-([^-\.]+)-([^-\.]+)\.', # Match putty-location-type-apname.ext
            r'session-capture\.([^\.]+)\.', # Match session-capture.apname.domain.ext
            r'(\w+)-ap(\d+)\.', # Match location-apX
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename)
            if match:
                if 'putty-' in pattern:
                    return f"{match.group(2)}-{match.group(3)}"
                elif 'ap' in pattern:
                    return f"{match.group(1)}-ap{match.group(2)}"
                else:
                    return match.group(1)
    
    # Look for AP address in metadata as last resort
    if data.get("metadata", {}).get("ap_address"):
        return data["metadata"]["ap_address"]
        
    return ""


def _create_ap_info_metric(registry: Any, data: Dict[str, Any], ap_name: str) -> int:
    """
    Create AP info metric with device labels.
    
    Args:
        registry: Prometheus collector registry
        data: Parsed GNSS data
        ap_name: AP name for labels
        
    Returns:
        int: Number of metrics created
    """
    metric_count = 0
    
    # Extract AP model and serial from show_version or show_inventory
    ap_model = data.get("show_version", {}).get("ap_model", "unknown")
    ap_serial = data.get("show_version", {}).get("ap_serial_number")
    
    # If not found in show_version, try show_inventory
    if not ap_serial:
        ap_serial = data.get("show_inventory", {}).get("inv_ap_serial", "unknown")
    
    if not ap_model or ap_model == "unknown":
        ap_model = data.get("show_inventory", {}).get("inv_ap_pid", "unknown")
    
    # Set the info metric (constant value of 1, used for labels)
    g = Gauge('ap_gnss_info', 'Access Point information',
              ['ap_name', 'ap_model', 'ap_serial'], registry=registry)
    g.labels(ap_name=ap_name, ap_model=ap_model, ap_serial=ap_serial).set(1)
    metric_count += 1
    
    return metric_count


def _create_gnss_state_metrics(registry: Any, data: Dict[str, Any], ap_name: str) -> int:
    """
    Create GNSS state metrics.
    
    Args:
        registry: Prometheus collector registry
        data: Parsed GNSS data
        ap_name: AP name for labels
        
    Returns:
        int: Number of metrics created
    """
    metric_count = 0
    gnss_state_data = data.get("gnss_state", {})
    
    # GNSS state
    g_state = Gauge('ap_gnss_state', 'GNSS state (1=Started, 0=Not started)',
                   ['ap_name'], registry=registry)
    
    # Check if no GNSS detected
    if gnss_state_data.get("no_gnss_detected", False):
        g_state.labels(ap_name=ap_name).set(0)
        metric_count += 1
        return metric_count
    
    # GNSS state
    state_value = 1 if gnss_state_data.get("state") == "Started" else 0
    g_state.labels(ap_name=ap_name).set(state_value)
    metric_count += 1
    
    # Fix type
    g_fix = Gauge('ap_gnss_fix_type', 'GNSS fix type (0=No-Fix, 1=2D-Fix, 2=3D-Fix)',
                 ['ap_name'], registry=registry)
    
    fix_type = gnss_state_data.get("fix_type", "")
    fix_type_value = 0  # Default to No-Fix
    if fix_type == "3D-Fix":
        fix_type_value = 2
    elif fix_type == "2D-Fix":
        fix_type_value = 1
    g_fix.labels(ap_name=ap_name).set(fix_type_value)
    metric_count += 1
    
    # Valid fix
    g_valid = Gauge('ap_gnss_valid_fix', 'GNSS valid fix (1=true, 0=false)',
                   ['ap_name'], registry=registry)
    valid_fix = 1 if gnss_state_data.get("valid_fix", False) else 0
    g_valid.labels(ap_name=ap_name).set(valid_fix)
    metric_count += 1
    
    # External antenna
    g_ant = Gauge('ap_gnss_external_antenna', 'GNSS external antenna (1=true, 0=false)',
                 ['ap_name'], registry=registry)
    external_antenna = 1 if gnss_state_data.get("external_antenna", False) else 0
    g_ant.labels(ap_name=ap_name).set(external_antenna)
    metric_count += 1

    # Additional metrics from gnss_state
    # RangeRes metric
    if gnss_state_data.get("rangeres") is not None:
        g_rangeres = Gauge('ap_gnss_rangeres', 'GNSS range residual value',
                          ['ap_name'], registry=registry)
        g_rangeres.labels(ap_name=ap_name).set(gnss_state_data["rangeres"])
        metric_count += 1

    # GpGstRms metric
    if gnss_state_data.get("gpgstrms") is not None:
        g_gpgstrms = Gauge('ap_gnss_gpgstrms', 'GNSS GpGstRms value',
                          ['ap_name'], registry=registry)
        g_gpgstrms.labels(ap_name=ap_name).set(gnss_state_data["gpgstrms"])
        metric_count += 1

    # Fix time and last fix time already handled in timestamp metrics

    return metric_count


def _create_position_metrics(registry: Any, data: Dict[str, Any], ap_name: str) -> int:
    """
    Create position metrics from all available sources.
    
    Args:
        registry: Prometheus collector registry
        data: Parsed GNSS data
        ap_name: AP name for labels
        
    Returns:
        int: Number of metrics created
    """
    metric_count = 0
    
    # Create position gauges
    g_lat = Gauge('ap_gnss_latitude', 'GNSS latitude in degrees',
                 ['ap_name', 'source'], registry=registry)
    
    g_lon = Gauge('ap_gnss_longitude', 'GNSS longitude in degrees',
                 ['ap_name', 'source'], registry=registry)
    
    g_alt = Gauge('ap_gnss_altitude', 'GNSS altitude in meters',
                 ['ap_name', 'source', 'type'], registry=registry)
    
    g_horacc = Gauge('ap_gnss_horacc', 'GNSS horizontal accuracy in meters',
                    ['ap_name', 'source'], registry=registry)
    
    g_vertacc = Gauge('ap_gnss_vertacc', 'GNSS vertical accuracy in meters',
                     ['ap_name', 'source'], registry=registry)
    
    # Process main GNSS state position
    gnss_state = data.get("gnss_state", {})
    if gnss_state and not gnss_state.get("no_gnss_detected", False):
        pos_count = _add_position_source(g_lat, g_lon, g_alt, g_horacc, g_vertacc, 
                            gnss_state, ap_name, "gnss")
        metric_count += pos_count
    
    # Process GNSS PostProcessor position
    pp_data = data.get("gnss_postprocessor", {})
    if pp_data and not pp_data.get("not_available", False):
        pos_count = _add_position_source(g_lat, g_lon, g_alt, g_horacc, g_vertacc, 
                            pp_data, ap_name, "postprocessor")
        metric_count += pos_count
    
    # Process Cisco GNSS position
    cisco_data = data.get("cisco_gnss", {})
    if cisco_data and not cisco_data.get("not_available", False):
        pos_count = _add_position_source(g_lat, g_lon, g_alt, g_horacc, g_vertacc, 
                            cisco_data, ap_name, "cisco")
        metric_count += pos_count
    
    # Process last location acquired
    last_data = data.get("last_location_acquired", {})
    if last_data and not last_data.get("not_available", False):
        pos_count = _add_position_source(g_lat, g_lon, g_alt, g_horacc, g_vertacc, 
                            last_data, ap_name, "last")
        metric_count += pos_count
    
    return metric_count


def _add_position_source(g_lat, g_lon, g_alt, g_horacc, g_vertacc, 
                        source_data, ap_name, source_name) -> int:
    """
    Add position data from a specific source to the metrics.
    
    Args:
        g_lat: Latitude gauge
        g_lon: Longitude gauge
        g_alt: Altitude gauge
        g_horacc: Horizontal accuracy gauge
        g_vertacc: Vertical accuracy gauge
        source_data: Source-specific data dictionary
        ap_name: AP name
        source_name: Name of the source (gnss, postprocessor, cisco, last)
        
    Returns:
        int: Number of metrics created
    """
    metric_count = 0
    
    # Position metrics (latitude/longitude)
    latitude = source_data.get("latitude")
    longitude = source_data.get("longitude")
    
    if latitude is not None:
        g_lat.labels(ap_name=ap_name, source=source_name).set(latitude)
        metric_count += 1
    
    if longitude is not None:
        g_lon.labels(ap_name=ap_name, source=source_name).set(longitude)
        metric_count += 1
    
    # Altitude metrics
    altitude_msl = source_data.get("altitude_msl")
    altitude_hae = source_data.get("altitude_hae")
    
    if altitude_msl is not None:
        g_alt.labels(ap_name=ap_name, source=source_name, type="msl").set(altitude_msl)
        metric_count += 1
    
    if altitude_hae is not None:
        g_alt.labels(ap_name=ap_name, source=source_name, type="hae").set(altitude_hae)
        metric_count += 1
    
    # Accuracy metrics
    horacc = source_data.get("horacc")
    vertacc = source_data.get("vertacc")
    
    if horacc is not None:
        g_horacc.labels(ap_name=ap_name, source=source_name).set(horacc)
        metric_count += 1
    
    if vertacc is not None:
        g_vertacc.labels(ap_name=ap_name, source=source_name).set(vertacc)
        metric_count += 1
    
    return metric_count


def _create_satellite_metrics(registry: Any, data: Dict[str, Any], ap_name: str) -> int:
    """
    Create satellite metrics.
    
    Args:
        registry: Prometheus collector registry
        data: Parsed GNSS data
        ap_name: AP name for labels
        
    Returns:
        int: Number of metrics created
    """
    metric_count = 0
    gnss_state_data = data.get("gnss_state", {})
    
    # Satellite count metrics
    g_satcount = Gauge('ap_gnss_satellite_count', 'GNSS total number of satellites',
                      ['ap_name'], registry=registry)
    
    g_numsat = Gauge('ap_gnss_numsat', 'GNSS number of satellites used for fix',
                    ['ap_name'], registry=registry)
    
    satellite_count = gnss_state_data.get("satellitecount")
    numsat = gnss_state_data.get("numsat")
    
    if satellite_count is not None:
        g_satcount.labels(ap_name=ap_name).set(satellite_count)
        metric_count += 1
    
    if numsat is not None:
        g_numsat.labels(ap_name=ap_name).set(numsat)
        metric_count += 1
    
    # Constellation stats
    g_const = Gauge('ap_gnss_constellation_stats', 'GNSS constellation statistics',
                   ['ap_name', 'constellation', 'used', 'band'], registry=registry)
    
    satellites = data.get("satellites", [])
    
    # Count satellites by constellation, used status, and band
    constellation_counts = {}
    
    for sat in satellites:
        constellation = sat.get("constellation", "Unknown")
        used = "yes" if sat.get("used", "").lower() == "yes" else "no"
        band = sat.get("band", "unknown")
        
        key = (constellation, used, band)
        constellation_counts[key] = constellation_counts.get(key, 0) + 1
    
    # Set constellation metrics
    for (constellation, used, band), count in constellation_counts.items():
        g_const.labels(
            ap_name=ap_name,
            constellation=constellation,
            used=used,
            band=band
        ).set(count)
        metric_count += 1

    # Add individual satellite metrics
    # Define metrics for individual satellites
    g_sat_snr = Gauge('ap_gnss_satellite_snr', 'GNSS satellite signal-to-noise ratio (SNR)',
                    ['ap_name', 'constellation', 'prn', 'used'], registry=registry)
    
    g_sat_elevation = Gauge('ap_gnss_satellite_elevation', 'GNSS satellite elevation in degrees',
                          ['ap_name', 'constellation', 'prn', 'used'], registry=registry)
    
    g_sat_azimuth = Gauge('ap_gnss_satellite_azimuth', 'GNSS satellite azimuth in degrees',
                         ['ap_name', 'constellation', 'prn', 'used'], registry=registry)
    
    # Add per-satellite metrics
    for sat in satellites:
        constellation = sat.get("constellation", "Unknown")
        prn = sat.get("prn", sat.get("id", "unknown"))  # Some logs use 'id' instead of 'prn'
        used_status = "yes" if sat.get("used", "").lower() == "yes" else "no"
        
        # Add SNR/CN0 metric
        snr_value = sat.get("snr", sat.get("cn0"))  # Some logs use 'cn0' instead of 'snr'
        if snr_value is not None:
            g_sat_snr.labels(
                ap_name=ap_name,
                constellation=constellation,
                prn=str(prn),
                used=used_status
            ).set(snr_value)
            metric_count += 1
        
        # Add elevation metric
        elevation = sat.get("elev")
        if elevation is not None:
            g_sat_elevation.labels(
                ap_name=ap_name,
                constellation=constellation,
                prn=str(prn),
                used=used_status
            ).set(elevation)
            metric_count += 1
        
        # Add azimuth metric
        azimuth = sat.get("azim")
        if azimuth is not None:
            g_sat_azimuth.labels(
                ap_name=ap_name,
                constellation=constellation,
                prn=str(prn),
                used=used_status
            ).set(azimuth)
            metric_count += 1
    
    return metric_count


def _create_dop_metrics(registry: Any, data: Dict[str, Any], ap_name: str) -> int:
    """
    Create DOP (Dilution of Precision) metrics.
    
    Args:
        registry: Prometheus collector registry
        data: Parsed GNSS data
        ap_name: AP name for labels
        
    Returns:
        int: Number of metrics created
    """
    metric_count = 0
    gnss_state_data = data.get("gnss_state", {})
    
    # DOP gauge
    g_dop = Gauge('ap_gnss_dop', 'GNSS dilution of precision values',
                 ['ap_name', 'type'], registry=registry)
    
    # DOP values
    dop_fields = [
        "pdop", "hdop", "vdop", "ndop", "edop", "gdop", "tdop"
    ]
    
    for dop_type in dop_fields:
        value = gnss_state_data.get(dop_type)
        if value is not None:
            g_dop.labels(ap_name=ap_name, type=dop_type).set(value)
            metric_count += 1
    
    return metric_count


def _create_uptime_metrics(registry: Any, data: Dict[str, Any], ap_name: str) -> int:
    """
    Create AP uptime metrics.
    
    Args:
        registry: Prometheus collector registry
        data: Parsed GNSS data
        ap_name: AP name for labels
        
    Returns:
        int: Number of metrics created
    """
    metric_count = 0
    show_version = data.get("show_version", {})
    
    # Create uptime gauge
    g_uptime = Gauge('ap_uptime_seconds', 'AP uptime in seconds',
                    ['ap_name'], registry=registry)
    
    # Look for pre-calculated uptime seconds
    uptime_seconds = show_version.get("ver_uptime_seconds")
    
    # If not available, calculate from days, hours, minutes
    if uptime_seconds is None:
        days = show_version.get("ap_uptime_days")
        hours = show_version.get("ap_uptime_hours")
        minutes = show_version.get("ap_uptime_minutes")
        
        # Calculate only if we have all three components
        if days is not None and hours is not None and minutes is not None:
            try:
                uptime_seconds = (int(days) * 86400) + (int(hours) * 3600) + (int(minutes) * 60)
            except (ValueError, TypeError):
                uptime_seconds = None
    
    # Set the metric if we have uptime
    if uptime_seconds is not None:
        g_uptime.labels(ap_name=ap_name).set(uptime_seconds)
        metric_count += 1
    
    # Add individual uptime components as separate metrics
    g_uptime_components = Gauge('ap_uptime_component', 'AP uptime components',
                              ['ap_name', 'component'], registry=registry)
    
    for component in ["ap_uptime_days", "ap_uptime_hours", "ap_uptime_minutes"]:
        value = show_version.get(component)
        if value is not None:
            try:
                g_uptime_components.labels(
                    ap_name=ap_name, 
                    component=component.replace("ap_uptime_", "")
                ).set(int(value))
                metric_count += 1
            except (ValueError, TypeError):
                pass
    
    return metric_count


def _create_auth_handler(username: str, password: str):
    """
    Create an authentication handler for the Push Gateway.
    
    Args:
        username: Username for authentication
        password: Password for authentication
        
    Returns:
        function: Authentication handler function or None if not possible
    """
    try:
        import base64
        
        def auth_handler(url, method, timeout, headers, data):
            headers = headers.copy() if headers else []
            auth_value = base64.b64encode(
                f"{username}:{password}".encode()
            ).decode("utf-8")
            headers.append(("Authorization", f"Basic {auth_value}"))
            return url, method, timeout, headers, data
            
        # Return a function that returns the result of auth_handler
        def handler_wrapper(*args, **kwargs):
            return auth_handler(*args, **kwargs)
            
        return handler_wrapper
    except ImportError:
        # If base64 is not available (very unlikely), return None
        return None


def _create_metadata_metrics(registry: Any, data: Dict[str, Any], ap_name: str) -> int:
    """
    Create metrics from metadata information.
    
    Args:
        registry: Prometheus collector registry
        data: Parsed GNSS data
        ap_name: AP name for labels
        
    Returns:
        int: Number of metrics created
    """
    metric_count = 0
    metadata = data.get("metadata", {})
    
    # Skip if no metadata available
    if not metadata:
        return metric_count
    
    # Parser version info (as info metric with version as label)
    parser_version = metadata.get("parser_version")
    if parser_version:
        g_parser = Gauge('ap_gnss_parser_info', 'Parser information used for GNSS data collection',
                        ['ap_name', 'version'], registry=registry)
        g_parser.labels(ap_name=ap_name, version=parser_version).set(1)
        metric_count += 1
    
    # Collection timestamp (as Unix timestamp)
    collection_time_str = metadata.get("parse_time")
    if collection_time_str:
        try:
            # Convert ISO timestamp to Unix timestamp
            dt = datetime.fromisoformat(collection_time_str)
            unix_timestamp = dt.timestamp()
            
            g_collected = Gauge('ap_gnss_collection_timestamp', 'Time when GNSS data was collected',
                             ['ap_name'], registry=registry)
            g_collected.labels(ap_name=ap_name).set(unix_timestamp)
            metric_count += 1
        except (ValueError, TypeError):
            # Skip if timestamp format is invalid
            pass
    
    # Collection method
    collection_method = metadata.get("collection_method")
    if collection_method:
        g_method = Gauge('ap_gnss_collection_method', 'Method used to collect GNSS data',
                       ['ap_name', 'method'], registry=registry)
        g_method.labels(ap_name=ap_name, method=collection_method).set(1)
        metric_count += 1
    
    return metric_count


def _create_version_metrics(registry: Any, data: Dict[str, Any], ap_name: str) -> int:
    """
    Create metrics from AP version information.
    
    Args:
        registry: Prometheus collector registry
        data: Parsed GNSS data
        ap_name: AP name for labels
        
    Returns:
        int: Number of metrics created
    """
    metric_count = 0
    show_version = data.get("show_version", {})
    
    # Skip if no version data available
    if not show_version:
        return metric_count
    
    # AP version info as info metric with version as label
    ap_image = show_version.get("ap_running_image")
    if ap_image:
        g_version = Gauge('ap_running_image_info', 'AP running software version information',
                        ['ap_name', 'version', 'image_family'], registry=registry)
        image_family = show_version.get("ap_image_family", "unknown")
        g_version.labels(ap_name=ap_name, version=ap_image, image_family=image_family).set(1)
        metric_count += 1
    
    # Ethernet MAC address (as info metric)
    eth_mac = show_version.get("ethernet_mac_address")
    if eth_mac:
        g_mac = Gauge('ap_ethernet_mac_info', 'AP Ethernet MAC address information',
                    ['ap_name', 'mac_address'], registry=registry)
        g_mac.labels(ap_name=ap_name, mac_address=eth_mac).set(1)
        metric_count += 1
    
    # Cloud ID (as info metric)
    cloud_id = show_version.get("cloud_id")
    if cloud_id:
        g_cloud = Gauge('ap_cloud_id_info', 'AP Cloud ID information',
                      ['ap_name', 'cloud_id'], registry=registry)
        g_cloud.labels(ap_name=ap_name, cloud_id=cloud_id).set(1)
        metric_count += 1
    
    # Last reload information (as a timestamp)
    last_reload_time = show_version.get("last_reload_time")
    if last_reload_time:
        try:
            # Try to parse the reload time (format can vary)
            # Common format: "Mon Apr 21 16:13:20 UTC 2025"
            import datetime
            import time
            from dateutil import parser
            
            # Use dateutil to handle various date formats
            dt = parser.parse(last_reload_time)
            unix_timestamp = dt.timestamp()
            
            g_reload = Gauge('ap_last_reload_timestamp', 'AP last reload timestamp',
                           ['ap_name'], registry=registry)
            g_reload.labels(ap_name=ap_name).set(unix_timestamp)
            metric_count += 1
            
            # Also add reload reason as info metric
            reload_reason = show_version.get("last_reload_reason", "unknown")
            g_reload_reason = Gauge('ap_last_reload_reason', 'AP last reload reason',
                                  ['ap_name', 'reason'], registry=registry)
            g_reload_reason.labels(ap_name=ap_name, reason=reload_reason).set(1)
            metric_count += 1
            
        except (ImportError, ValueError, TypeError):
            # Skip if parsing fails or dateutil not available
            pass
    
    return metric_count


def _create_inventory_metrics(registry: Any, data: Dict[str, Any], ap_name: str) -> int:
    """
    Create metrics from AP inventory information.
    
    Args:
        registry: Prometheus collector registry
        data: Parsed GNSS data
        ap_name: AP name for labels
        
    Returns:
        int: Number of metrics created
    """
    metric_count = 0
    show_inventory = data.get("show_inventory", {})
    
    # Skip if no inventory data available
    if not show_inventory:
        return metric_count
    
    # AP device ID information
    ap_device_id = show_inventory.get("inv_ap_devid")
    if ap_device_id:
        g_devid = Gauge('ap_device_id_info', 'AP device ID information',
                      ['ap_name', 'device_id'], registry=registry)
        g_devid.labels(ap_name=ap_name, device_id=ap_device_id).set(1)
        metric_count += 1
    
    # USB information if available
    usb_detected = show_inventory.get("inv_usb_detected")
    if usb_detected is not None:
        # Create USB presence metric
        g_usb = Gauge('ap_usb_detected', 'USB device detected on AP (1=true, 0=false)',
                    ['ap_name'], registry=registry)
        g_usb.labels(ap_name=ap_name).set(1 if usb_detected else 0)
        metric_count += 1
        
        # If USB is detected, add more USB details
        if usb_detected:
            usb_status = show_inventory.get("inv_usb_status")
            usb_pid = show_inventory.get("inv_usb_pid")
            usb_vid = show_inventory.get("inv_usb_vid")
            usb_serial = show_inventory.get("inv_usb_serial")
            
            # Create USB info metric with all details as labels
            g_usb_info = Gauge('ap_usb_info', 'USB device information',
                             ['ap_name', 'status', 'pid', 'vid', 'manufacturer', 'serial'], 
                             registry=registry)
            
            g_usb_info.labels(
                ap_name=ap_name,
                status=usb_status or "unknown",
                pid=usb_pid or "unknown",
                vid=usb_vid or "unknown",
                manufacturer=show_inventory.get("inv_usb_manuf") or "unknown",
                serial=usb_serial or "unknown"
            ).set(1)
            metric_count += 1
            
            # USB power metric if available
            usb_power = show_inventory.get("inv_usb_max_power")
            if usb_power is not None:
                try:
                    # Convert to numeric value if possible
                    power_value = float(usb_power.replace("mA", "").strip())
                    g_usb_power = Gauge('ap_usb_max_power_ma', 'USB device maximum power in mA',
                                     ['ap_name'], registry=registry)
                    g_usb_power.labels(ap_name=ap_name).set(power_value)
                    metric_count += 1
                except (ValueError, AttributeError):
                    pass
    
    return metric_count


def _create_uncertainty_metrics(registry: Any, data: Dict[str, Any], ap_name: str) -> int:
    """
    Create uncertainty ellipse metrics from all available position sources.
    
    Args:
        registry: Prometheus collector registry
        data: Parsed GNSS data
        ap_name: AP name for labels
        
    Returns:
        int: Number of metrics created
    """
    metric_count = 0
    
    # Create uncertainty gauges
    g_major = Gauge('ap_gnss_uncertainty_ellipse_major_axis', 
                  'GNSS uncertainty ellipse major axis in meters',
                  ['ap_name', 'source'], registry=registry)
    
    g_minor = Gauge('ap_gnss_uncertainty_ellipse_minor_axis', 
                  'GNSS uncertainty ellipse minor axis in meters',
                  ['ap_name', 'source'], registry=registry)
    
    g_orient = Gauge('ap_gnss_uncertainty_ellipse_orientation', 
                   'GNSS uncertainty ellipse orientation in degrees',
                   ['ap_name', 'source'], registry=registry)
    
    # Process uncertainty from all sources
    sources = [
        ("gnss_state", "gnss"),
        ("gnss_postprocessor", "postprocessor"),
        ("cisco_gnss", "cisco"),
        ("last_location_acquired", "last")
    ]
    
    for source_key, source_name in sources:
        source_data = data.get(source_key, {})
        
        # Skip if source not available or no uncertainty data
        if not source_data or source_data.get("not_available", False):
            continue
            
        # Add uncertainty metrics if available
        major_axis = source_data.get("uncertainty_ellipse_major_axis")
        minor_axis = source_data.get("uncertainty_ellipse_minor_axis")
        orientation = source_data.get("uncertainty_ellipse_orientation")
        
        if major_axis is not None:
            g_major.labels(ap_name=ap_name, source=source_name).set(major_axis)
            metric_count += 1
            
        if minor_axis is not None:
            g_minor.labels(ap_name=ap_name, source=source_name).set(minor_axis)
            metric_count += 1
            
        if orientation is not None:
            g_orient.labels(ap_name=ap_name, source=source_name).set(orientation)
            metric_count += 1
    
    return metric_count


def _create_timestamp_metrics(registry: Any, data: Dict[str, Any], ap_name: str) -> int:
    """
    Create timestamp metrics from various data sources.
    
    Args:
        registry: Prometheus collector registry
        data: Parsed GNSS data
        ap_name: AP name for labels
        
    Returns:
        int: Number of metrics created
    """
    metric_count = 0
    
    # Create timestamp gauge
    g_timestamp = Gauge('ap_gnss_timestamp', 'Various GNSS timestamps as Unix epoch seconds',
                      ['ap_name', 'source', 'type'], registry=registry)
    
    # Add last export timestamp (current time)
    g_timestamp.labels(ap_name=ap_name, source="exporter", type="last_export").set(time.time())
    metric_count += 1
    
    # GNSS fix timestamps
    gnss_state_data = data.get("gnss_state", {})
    
    if gnss_state_data and not gnss_state_data.get("no_gnss_detected", False):
        # GNSS fix time and last fix time
        fix_time = gnss_state_data.get("gnss_fix_time")
        last_fix_time = gnss_state_data.get("last_fix_time")
        
        # Try to convert gnss_fix_time to timestamp if available
        if fix_time:
            try:
                from dateutil import parser
                dt = parser.parse(fix_time)
                g_timestamp.labels(ap_name=ap_name, source="gnss", type="fix_time").set(dt.timestamp())
                metric_count += 1
            except (ImportError, ValueError, TypeError):
                pass
        
        # Try to convert last_fix_time to timestamp if available
        if last_fix_time:
            try:
                from dateutil import parser
                dt = parser.parse(last_fix_time)
                g_timestamp.labels(ap_name=ap_name, source="gnss", type="last_fix_time").set(dt.timestamp())
                metric_count += 1
            except (ImportError, ValueError, TypeError):
                pass
    
    # Last location derivation time if available
    last_location = data.get("last_location_acquired", {})
    if last_location and not last_location.get("not_available", False):
        derivation_time = last_location.get("derivation_time")
        derivation_type = last_location.get("derivation_type", "unknown")
        
        if derivation_time:
            try:
                from dateutil import parser
                dt = parser.parse(derivation_time)
                g_timestamp.labels(
                    ap_name=ap_name, 
                    source="last_location", 
                    type=f"derivation_{derivation_type}"
                ).set(dt.timestamp())
                metric_count += 1
            except (ImportError, ValueError, TypeError):
                pass
    
    # Add show_clock time from main data
    main_data = data.get("main", {})
    if main_data:
        clock_time = main_data.get("show_clock_time")
        if clock_time:
            try:
                from dateutil import parser
                dt = parser.parse(clock_time)
                g_timestamp.labels(ap_name=ap_name, source="ap", type="current_time").set(dt.timestamp())
                metric_count += 1
            except (ImportError, ValueError, TypeError):
                pass
    
    return metric_count


def _create_source_derivation_metrics(registry: Any, data: Dict[str, Any], ap_name: str) -> int:
    """
    Create metrics for location source derivation information.
    
    Args:
        registry: Prometheus collector registry
        data: Parsed GNSS data
        ap_name: AP name for labels
        
    Returns:
        int: Number of metrics created
    """
    metric_count = 0
    last_location = data.get("last_location_acquired", {})
    
    # Skip if section not found or not available
    if not last_location or last_location.get("not_available", False):
        return metric_count
    
    # Create metrics for source derivation info
    g_derivation = Gauge('ap_gnss_location_derivation_info', 'GNSS location derivation information',
                        ['ap_name', 'derivation_type'], registry=registry)
    
    derivation_type = last_location.get("derivation_type")
    if derivation_type:
        g_derivation.labels(ap_name=ap_name, derivation_type=derivation_type).set(1)
        metric_count += 1
    
    # Add parser availability indicators
    for parser_section, section_name in [
        ("gnss_postprocessor", "gnss_pp_parser_found"),
        ("cisco_gnss", "cisco_gnss_parser_found"),
        ("last_location_acquired", "last_location_parser_found")
    ]:
        section_data = data.get(parser_section, {})
        if section_data and section_data.get(section_name) is not None:
            g_parser = Gauge(f'ap_gnss_{parser_section}_available', 
                            f'GNSS {parser_section} availability (1=available, 0=not available)',
                            ['ap_name'], registry=registry)
            g_parser.labels(ap_name=ap_name).set(1 if section_data.get(section_name) else 0)
            metric_count += 1
            
            # If parser found but data not available, set separate metric
            if section_data.get(section_name) and section_data.get("not_available", False):
                g_avail = Gauge(f'ap_gnss_{parser_section}_data_available', 
                               f'GNSS {parser_section} data availability (1=available, 0=not available)',
                               ['ap_name'], registry=registry)
                g_avail.labels(ap_name=ap_name).set(0)  # not available
                metric_count += 1
    
    return metric_count


def _create_raw_data_metrics(registry: Any, data: Dict[str, Any], ap_name: str) -> int:
    """
    Create metrics from raw data key-value pairs.
    
    Args:
        registry: Prometheus collector registry
        data: Parsed GNSS data
        ap_name: AP name for labels
        
    Returns:
        int: Number of metrics created
    """
    metric_count = 0
    raw_data = data.get("raw_data", {})
    
    # Skip if no raw data available
    if not raw_data:
        return metric_count
    
    # Create gauge for numeric raw data values
    g_raw = Gauge('ap_gnss_raw_data', 'GNSS raw data values',
                 ['ap_name', 'key'], registry=registry)
    
    # Create info gauge for non-numeric values
    g_raw_info = Gauge('ap_gnss_raw_data_info', 'GNSS raw data string values',
                      ['ap_name', 'key', 'value'], registry=registry)
    
    # Process each raw data item
    for key, value in raw_data.items():
        # Handle different value types
        if isinstance(value, (int, float)):
            # Numeric values get a gauge with the value
            g_raw.labels(ap_name=ap_name, key=key).set(value)
            metric_count += 1
        elif isinstance(value, bool):
            # Boolean values as 0/1 gauge
            g_raw.labels(ap_name=ap_name, key=key).set(1 if value else 0)
            metric_count += 1
        elif isinstance(value, str):
            # String values get an info metric with value as label
            g_raw_info.labels(ap_name=ap_name, key=key, value=value).set(1)
            metric_count += 1
    
    return metric_count