# CSV Export Feature Documentation

## Overview

The AP GNSS Stats SSH Collector now includes comprehensive CSV export functionality that allows you to export collected GNSS data to CSV format for analysis in spreadsheet applications, databases, or data analysis tools.

## Features

- **Automatic CSV Export**: Export parsed GNSS data from successful AP connections to CSV format
- **Append Mode**: Append new data to existing CSV files for continuous data collection
- **Flexible Output**: Specify custom output file paths or use auto-generated timestamped filenames
- **Column Standardization**: Consistent column structure across all exports with flattened data hierarchy
- **Error Handling**: Robust error handling with detailed logging and user feedback

## Usage

### Basic CSV Export

Enable CSV export with default settings:

```bash
python -m ap_gnss_stats.bin.ap_ssh_collector -a ap1.example.com -u admin --csv
```

This will:

- Export successful AP data to a timestamped CSV file (e.g., `ap_gnss_export_20250529-143022.csv`)
- Overwrite any existing file with the same name
- Include all parsed GNSS data in flattened column format

### Custom Output File

Specify a custom output file path:

```bash
python -m ap_gnss_stats.bin.ap_ssh_collector -a ap1.example.com -u admin --csv --csv-output "my_ap_data.csv"
```

### Append Mode

Append new data to an existing CSV file:

```bash
python -m ap_gnss_stats.bin.ap_ssh_collector -a ap2.example.com -u admin --csv --csv-output "my_ap_data.csv" --csv-append
```

This will:

- Add new AP data as additional rows to the existing CSV file
- Preserve the existing column structure
- Skip writing a new header row

### Multiple APs with CSV Export

Process multiple APs and export all successful results to CSV:

```bash
python -m ap_gnss_stats.bin.ap_ssh_collector -f ap_list.txt -u admin --csv --csv-output "site_survey_data.csv"
```

### Environment Variable Configuration

Configure CSV export defaults using environment variables:

```bash
# Enable CSV export by default
export AP_CSV_ENABLED=true

# Set default output file
export AP_CSV_OUTPUT_FILE="daily_ap_data.csv"

# Enable append mode by default
export AP_CSV_APPEND_MODE=true
```

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--csv` | Enable CSV export | `false` |
| `--csv-output CSV_OUTPUT` | Output CSV file path | Auto-generated with timestamp |
| `--csv-append` | Append to existing CSV file instead of overwriting | `false` |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AP_CSV_ENABLED` | Enable CSV export by default | `false` |
| `AP_CSV_OUTPUT_FILE` | Default output CSV file path | `None` |
| `AP_CSV_APPEND_MODE` | Enable append mode by default | `false` |

## CSV Output Format

### Column Structure

The CSV export flattens the hierarchical JSON data into columns using dot notation:

- **Basic fields**: `ap_name`, `show_clock_time`
- **GNSS State**: `gnss_state_latitude`, `gnss_state_longitude`, `gnss_state_altitude_msl`, etc.
- **Satellite data**: `satellites_total_count`, `satellites_gps_used`, `satellites_elevation_avg`, etc.
- **Version info**: `show_version_ap_model`, `show_version_ap_serial_number`, etc.
- **Metadata**: `metadata_parse_time`, `metadata_parser_version`, `metadata_input_file`

### Sample Output

```csv
ap_name,gnss_state_latitude,gnss_state_longitude,gnss_state_altitude_msl,gnss_state_fix_type,satellites_total_count,satellites_used_count,show_version_ap_model
test-ap-1,40.12345,-111.98765,1425.5,3D-Fix,12,8,AIR-AP2802I-B-K9
test-ap-2,40.12567,-111.98543,1430.2,3D-Fix,14,10,AIR-AP2802I-B-K9
```

## Data Processing

### Successful vs Failed APs

- Only data from successful AP connections is included in CSV export
- Failed connections are logged but excluded from CSV output
- Summary shows count of successful vs failed APs

### Data Validation

- The CSV exporter validates all data before export
- Invalid or missing data is handled gracefully with empty values
- Numeric data is preserved with appropriate precision

### Column Consistency

- All CSV files maintain consistent column structure
- New columns are automatically added for new data fields
- Append mode preserves existing column structure

## Integration Examples

### Daily Data Collection

```bash
#!/bin/bash
# Daily AP data collection script

DATE=$(date +%Y%m%d)
CSV_FILE="daily_ap_data_${DATE}.csv"

python -m ap_gnss_stats.bin.ap_ssh_collector \
    -f /etc/ap_gnss_stats/ap_list.txt \
    -u "$AP_USERNAME" \
    -p "$AP_PASSWORD" \
    --csv \
    --csv-output "$CSV_FILE"

echo "Daily collection complete: $CSV_FILE"
```

### Continuous Monitoring

```bash
#!/bin/bash
# Continuous monitoring with append mode

CSV_FILE="continuous_ap_monitoring.csv"

python -m ap_gnss_stats.bin.ap_ssh_collector \
    -f /etc/ap_gnss_stats/ap_list.txt \
    -u "$AP_USERNAME" \
    -p "$AP_PASSWORD" \
    --csv \
    --csv-output "$CSV_FILE" \
    --csv-append
```

### Site Survey Data Collection

```bash
#!/bin/bash
# Site survey data collection

SITE_NAME="$1"
CSV_FILE="site_survey_${SITE_NAME}_$(date +%Y%m%d).csv"

python -m ap_gnss_stats.bin.ap_ssh_collector \
    -f "sites/${SITE_NAME}_aps.txt" \
    -u "$AP_USERNAME" \
    -p "$AP_PASSWORD" \
    --csv \
    --csv-output "$CSV_FILE" \
    --concurrent 5

echo "Site survey complete for $SITE_NAME: $CSV_FILE"
```

## Error Handling

### Common Issues and Solutions

1. **Permission Denied**

   ```plaintext
   Error: Permission denied writing to CSV file
   Solution: Check file permissions and directory write access
   ```

2. **File Locked**

   ```plaintext
   Error: CSV file is locked by another process
   Solution: Close the file in Excel or other applications
   ```

3. **No Successful Data**

   ```plaintext
   Warning: CSV export skipped - no successful AP data to export
   Solution: Check AP connectivity and authentication
   ```

4. **Append Mode Column Mismatch**

   ```plaintext
   Warning: Could not read existing CSV header. Will overwrite file.
   Solution: Ensure existing CSV file has valid header row
   ```

### Troubleshooting

Enable verbose logging to troubleshoot CSV export issues:

```bash
python -m ap_gnss_stats.bin.ap_ssh_collector \
    -a ap1.example.com \
    -u admin \
    --csv \
    --csv-output debug_export.csv \
    -l debug_logs/
```

Check the session log files in the `debug_logs/` directory for detailed error information.

## Performance Considerations

### File Size

- Each AP record typically generates 1-2 KB of CSV data
- Large deployments (100+ APs) will generate substantial CSV files
- Consider splitting data by date or site for manageability

### Memory Usage

- CSV export processes all successful results in memory before writing
- For very large AP lists (1000+ APs), monitor memory usage
- Consider processing in batches if memory constraints exist

### Disk Space

- Monitor disk space when using append mode for continuous collection
- Implement log rotation for long-running data collection

## Data Analysis Examples

### Excel Analysis

Open the CSV file in Microsoft Excel for:

- Sorting and filtering AP data
- Creating charts and graphs
- Calculating statistics and averages
- Generating reports

### Python Analysis

```python
import pandas as pd

# Load CSV data
df = pd.read_csv('ap_gnss_export.csv')

# Basic statistics
print(df['gnss_state_latitude'].describe())
print(df['satellites_used_count'].mean())

# Filter APs with good GPS fix
good_fix = df[df['gnss_state_fix_type'] == '3D-Fix']
print(f"APs with 3D fix: {len(good_fix)}")

# Plot satellite count distribution
import matplotlib.pyplot as plt
df['satellites_used_count'].hist()
plt.xlabel('Satellites Used')
plt.ylabel('Count')
plt.title('Distribution of Satellites Used')
plt.show()
```

### Database Import

```sql
-- Import CSV data into PostgreSQL
CREATE TABLE ap_gnss_data (
    ap_name VARCHAR(100),
    gnss_state_latitude DECIMAL(10,8),
    gnss_state_longitude DECIMAL(11,8),
    gnss_state_altitude_msl DECIMAL(8,3),
    gnss_state_fix_type VARCHAR(20),
    satellites_total_count INTEGER,
    satellites_used_count INTEGER,
    -- Add other columns as needed
    metadata_parse_time TIMESTAMP
);

COPY ap_gnss_data FROM '/path/to/ap_gnss_export.csv' 
WITH (FORMAT csv, HEADER true);
```

## Best Practices

1. **Regular Backups**: Backup CSV files regularly for important data
2. **Consistent Naming**: Use consistent naming conventions for CSV files
3. **Data Validation**: Validate CSV data after import to external systems
4. **Version Control**: Consider versioning for critical data collections
5. **Documentation**: Document the purpose and content of each CSV export

## Related Features

- **Prometheus Export**: Export metrics to Prometheus for monitoring
- **JSON Output**: Raw JSON output for programmatic processing
- **Session Logging**: Detailed SSH session logs for troubleshooting

For more information on these features, see the main project documentation.
