import os
import json
from netmiko import ConnectHandler
import logging
import re
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Directory configurations
LOG_DIR = os.getenv("LOG_DIR", "gnss_logs")  # Read from .env or use default
DATA_DIR = os.getenv("DATA_DIR", "gnss_data")  # Read from .env or use default
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger("gnss_gatherer")

# Helper function to generate filenames
def create_filename(prefix, hostname, ext, dir_=LOG_DIR):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_host = hostname.replace(":", "_").replace("/", "_")
    return os.path.join(dir_, f"{prefix}_{safe_host}_{timestamp}.{ext}")

def latest_json_filename(hostname):
    safe_host = hostname.replace(":", "_").replace("/", "_")
    return os.path.join(DATA_DIR, f"latest_gnss_data_{safe_host}.json")

# Function to connect to the device and retrieve GNSS info
def get_gnss_info(device):
    try:
        logger.info(f"Connecting to {device['host']} via SSH...")
        with ConnectHandler(**device) as conn:
            # Switch to Privileged EXEC mode
            conn.enable()
            logger.info("Switched to Privileged EXEC mode.")

            # Run the command
            output = conn.send_command("show gnss info")

            # Log raw SSH session
            ssh_log_file = create_filename("ssh_session_log", device['host'], "txt")
            with open(ssh_log_file, "w") as f:
                f.write(output)
            logger.info(f"SSH session logged to {ssh_log_file}")
            return output
    except Exception as e:
        logger.error(f"Error connecting to device: {e}")
        return None

# Function to parse GNSS output
def parse_gnss_info(output):
    main_metrics = {
        'state': "",
        'external_antenna': "",
        'fix_type': "",
        'valid_fix': "",
        'latitude': "",
        'longitude': "",
        'altitude_msl': "",
        'altitude_hae': "",
        'horacc': "",
        'vertacc': "",
        'satellite_count': "",
        'satellites_used': "",
        'hdop': "",
        'vdop': "",
        'pdop': ""
    }
    pp_metrics = {
        'latitude': "",
        'longitude': "",
        'horacc': "",
        'hdop': "",
        'major_axis': "",
        'minor_axis': "",
        'orientation': "",
        'altitude_msl': "",
        'altitude_hae': "",
        'vertacc': ""
    }
    last_loc_metrics = {
        'latitude': "",
        'longitude': "",
        'horacc': "",
        'hdop': "",
        'major_axis': "",
        'minor_axis': "",
        'orientation': "",
        'altitude_msl': "",
        'altitude_hae': "",
        'vertacc': "",
        'derivation_type': "",
        'age': "",
    }

    try:
        lines = output.splitlines()
        section = "main"  # Tracks which section we're parsing
        timestamp_last_loc = None

        for line in lines:
            line = line.strip()

            # Section transitions
            if "GNSS_PostProcessor:" in line:
                section = "pp"
                continue
            elif "Last Location Acquired:" in line:
                section = "last_loc"
                continue

            # Main GNSS data
            if section == "main":
                if "GnssState:" in line:
                    main_metrics['state'] = 1 if "Started" in line else 0
                elif "ExternalAntenna:" in line:
                    main_metrics['external_antenna'] = 1 if "true" in line.lower() else 0
                elif "Fix:" in line:
                    main_metrics['fix_type'] = 2 if "3D-Fix" in line else 1 if "2D-Fix" in line else 0
                    main_metrics['valid_fix'] = 1 if "ValidFix: true" in line else 0
                elif "Latitude:" in line and "Longitude:" in line:
                    parts = line.split()
                    main_metrics['latitude'] = float(parts[1])
                    main_metrics['longitude'] = float(parts[3])
                elif "Altitude MSL:" in line:
                    main_metrics['altitude_msl'] = float(re.search(r"MSL:\s+([\d.]+)", line).group(1))
                    main_metrics['altitude_hae'] = float(re.search(r"HAE:\s+([\d.]+)", line).group(1))
                    main_metrics['vertacc'] = float(re.search(r"VertAcc:\s+([\d.]+)", line).group(1))
                elif "NumSat:" in line:
                    main_metrics['satellite_count'] = int(re.search(r"NumSat:\s+(\d+)", line).group(1))
                elif "pDOP:" in line:
                    main_metrics['pdop'] = float(re.search(r"pDOP:\s+([\d.]+)", line).group(1))
                    main_metrics['hdop'] = float(re.search(r"hDOP:\s+([\d.]+)", line).group(1))
                    main_metrics['vdop'] = float(re.search(r"vDOP:\s+([\d.]+)", line).group(1))

            # PostProcessor GNSS data
            elif section == "pp":
                if "Latitude:" in line and "Longitude:" in line:
                    parts = line.split()
                    pp_metrics['latitude'] = float(parts[1])
                    pp_metrics['longitude'] = float(parts[3])
                elif "Altitude MSL:" in line:
                    pp_metrics['altitude_msl'] = float(re.search(r"MSL:\s+([\d.]+)", line).group(1))
                    pp_metrics['altitude_hae'] = float(re.search(r"HAE:\s+([\d.]+)", line).group(1))
                    pp_metrics['vertacc'] = float(re.search(r"VertAcc:\s+([\d.]+)", line).group(1))
                elif "Major axis:" in line:
                    pp_metrics['major_axis'] = float(re.search(r"Major axis:\s+([\d.]+)", line).group(1))
                    pp_metrics['minor_axis'] = float(re.search(r"Minor axis:\s+([\d.]+)", line).group(1))
                    pp_metrics['orientation'] = float(re.search(r"Orientation:\s+([\d.]+)", line).group(1))
                elif "HorAcc:" in line:
                    pp_metrics['horacc'] = float(re.search(r"HorAcc:\s+([\d.]+)", line).group(1))
                    pp_metrics['hdop'] = float(re.search(r"hDOP:\s+([\d.]+)", line).group(1))

            # Last Location Acquired data
            elif section == "last_loc":
                if "Latitude:" in line and "Longitude:" in line:
                    parts = line.split()
                    last_loc_metrics['latitude'] = float(parts[1])
                    last_loc_metrics['longitude'] = float(parts[3])
                elif "Altitude MSL:" in line:
                    last_loc_metrics['altitude_msl'] = float(re.search(r"MSL:\s+([\d.]+)", line).group(1))
                    last_loc_metrics['altitude_hae'] = float(re.search(r"HAE:\s+([\d.]+)", line).group(1))
                    last_loc_metrics['vertacc'] = float(re.search(r"VertAcc:\s+([\d.]+)", line).group(1))
                elif "Major axis:" in line:
                    last_loc_metrics['major_axis'] = float(re.search(r"Major axis:\s+([\d.]+)", line).group(1))
                    last_loc_metrics['minor_axis'] = float(re.search(r"Minor axis:\s+([\d.]+)", line).group(1))
                    last_loc_metrics['orientation'] = float(re.search(r"Orientation:\s+([\d.]+)", line).group(1))
                elif "HorAcc:" in line:
                    last_loc_metrics['horacc'] = float(re.search(r"HorAcc:\s+([\d.]+)", line).group(1))
                    last_loc_metrics['hdop'] = float(re.search(r"hDOP:\s+([\d.]+)", line).group(1))
                elif "Derivation Type:" in line:
                    derivation = line.split(":")[-1].strip()
                    if derivation == "GNSS":
                        last_loc_metrics['derivation_type'] = 1
                    elif derivation == "GNSS_PostProcessor":
                        last_loc_metrics['derivation_type'] = 2
                elif "Time:" in line:
                    match = re.search(r"Time:\s*([\d-]+\s+[\d:]+)", line)
                    if match:
                        timestamp_last_loc = match.group(1)

        # Calculate age for last location, if timestamp is found
        if timestamp_last_loc:
            try:
                last_time = datetime.strptime(timestamp_last_loc, "%Y-%m-%d %H:%M:%S")
                age_seconds = (datetime.now() - last_time).total_seconds()
                last_loc_metrics['age'] = age_seconds
            except Exception as e:
                logger.warning(f"Could not parse last location time: {e}")

        # Satellite used counting (from table)
        satellites_used = 0
        in_table = False
        for line in lines:
            if in_table:
                if not line.strip() or "GNSS_PostProcessor" in line:
                    break
                if re.search(r'\w+\s+\d+\s+\d+\s+\d+\s+\d+\s+\w+\s+Yes', line):
                    satellites_used += 1
            elif "Const.    SatId CNO   Elev. Azim. Signal  Used  Health" in line:
                in_table = True
        main_metrics['satellites_used'] = satellites_used

        return main_metrics, pp_metrics, last_loc_metrics
    except Exception as e:
        logger.error(f"Error parsing GNSS info: {e}")
        return main_metrics, pp_metrics, last_loc_metrics

# Save the latest parsed data to a JSON file
def save_latest_json(parsed_data, hostname):
    filename = latest_json_filename(hostname)
    try:
        with open(filename, "w") as f:
            json.dump(parsed_data, f, indent=4)
        logger.info(f"Latest parsed data saved to {filename}")
    except Exception as e:
        logger.error(f"Error saving parsed data to JSON file: {e}")

# Save a timestamped copy of the parsed data
def save_timestamped_json(parsed_data, hostname):
    timestamp_file = create_filename("parsed_gnss_data", hostname, "json", DATA_DIR)
    try:
        with open(timestamp_file, "w") as f:
            json.dump(parsed_data, f, indent=4)
        logger.info(f"Timestamped parsed data saved to {timestamp_file}")
    except Exception as e:
        logger.error(f"Error saving timestamped parsed data to JSON file: {e}")

# Main entry point
def main():
    # Retrieve variables from environment or prompt the user
    device = {
        'device_type': 'cisco_ios',
        'host': os.getenv('AP_HOST') or input("Enter the device IP/hostname: "),
        'username': os.getenv('AP_USERNAME') or input("Enter the username: "),
        'password': os.getenv('AP_PASSWORD') or input("Enter the password: "),
        'secret': os.getenv('AP_SECRET') or input("Enter the enable password: "),
        'timeout': int(os.getenv('AP_TIMEOUT', 20)),  # Default timeout is 20 seconds
    }

    output = get_gnss_info(device)
    if output:
        main_metrics, pp_metrics, last_loc_metrics = parse_gnss_info(output)
        parsed_data = {
            "main_metrics": main_metrics,
            "pp_metrics": pp_metrics,
            "last_loc_metrics": last_loc_metrics,
            "timestamp": datetime.now().isoformat(),
        }
        # Save a timestamped full log for auditing (in LOG_DIR)
        log_file = create_filename("parsed_gnss_data", device['host'], "json", LOG_DIR)
        with open(log_file, "w") as f:
            json.dump(parsed_data, f, indent=4)
        # Save the latest data for the exporter
        save_latest_json(parsed_data, device['host'])
        # Save a timestamped JSON copy in DATA_DIR as requested
        save_timestamped_json(parsed_data, device['host'])
    else:
        logger.error("No output received from device.")

if __name__ == "__main__":
    main()
