# AP GNSS Stats

Tools for parsing and analyzing GNSS (Global Navigation Satellite System) statistics from Cisco Wi-Fi Access Points.

## Overview

This project provides utilities to:

1. Parse the output from the `show gnss info` CLI command from Cisco APs
2. Generate structured JSON data from the parsed information
3. Analyze GNSS statistics for network administrators

## Installation

```bash
# Clone the repository
git clone https://github.com/lukejenkins/ap-gnss-stats.git
cd ap-gnss-stats

# Install the package
pip install -e .
```

## Usage

Parsing log files
To parse GNSS info from log files:

```bash
parse-gnss-logs path/to/logfile1.txt path/to/logfile2.txt -o output_directory
```

Options:

* -o, --output-dir: Directory to save output JSON files (default: "output")
* -d, --debug: Enable debug logging
* -l, --log-file FILE: Save debug logs to a file
* -v, --version: Show version information and exit

## Example

```bash
parse-gnss-logs examples/public/20250421-101648-putty-example-outdoor-ap1.txt -d -l debug.log
```

## Output Format

The tool generates JSON files with the following structure:

```json
{
  "tool": {
    "name": "ap-gnss-stats",
    "version": "0.1.0",
    "parser": "GnssInfoParser",
    "parser_version": "0.1.0"
  },
  "timestamp": "2025-04-28T22:13:29",
  "file_metadata": {
    "filename": "20250421-101648-putty-example-outdoor-ap1.txt",
    "file_path": "examples/public/20250421-101648-putty-example-outdoor-ap1.txt",
    "file_created": "2025-04-21T10:16:48",
    "file_modified": "2025-04-21T10:16:48"
  },
  "ap_data": {
    "ap_name": "AP-Outdoor-East",
    "model": "C9166I",
    "mac_address": "00:1A:2B:3C:4D:5E",
    "ip_address": "192.168.100.25",
    "location": "East Campus Building, Roof",
    "gnss_status": "Active and tracking",
    "latitude": 37.4219,
    "longitude": -122.0841,
    "altitude_meters": 32.5,
    "satellites_count": 12,
    "gnss_timestamp": "2025-04-21 09:45:32",
    "location_quality": "Excellent",
    "hdop": 0.9,
    "vdop": 1.1,
    "last_update": "3 seconds ago",
    "satellites": [
      {
        "id": 1,
        "type": "GPS",
        "snr_db": 38,
        "azimuth": 125,
        "elevation": 65,
        "used": true
      },
      // ... remaining satellites omitted for brevity
    ]
  }
}
```

## Development

Private examples should be placed in examples/private/ directory, which is excluded from git tracking.

Running tests

```bash
python -m unittest discover tests
```

Or using pytest:

```bash
pytest tests/
```

## Next Phase

The next phase of development will include a tool to connect to Cisco APs via SSH using netmiko to collect live GNSS data.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
