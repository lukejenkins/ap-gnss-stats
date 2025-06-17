# CSV Export Debugging Guide

## Problem
You're seeing "CSV export successful" messages, but the CSV file doesn't seem to exist or contain the expected data.

## Enhanced Debugging Features

### 1. Basic CSV Debug Information (Always Available)
The SSH collector now shows enhanced verification information after every CSV export:

```bash
python -m ap_gnss_stats.bin.ap_ssh_collector -a your-ap.example.com -u username --csv
```

This will show:
- Absolute file path
- File existence verification
- File size
- Row and column counts
- Directory contents if file is missing

### 2. Verbose CSV Debug Mode
For detailed debugging, use the `--csv-debug` flag:

```bash
python -m ap_gnss_stats.bin.ap_ssh_collector -a your-ap.example.com -u username --csv --csv-debug
```

This provides:
- Environment information (Python version, working directory, user, disk space)
- Directory permissions checking
- Step-by-step file creation process
- Detailed error tracebacks
- File verification with content samples

### 3. Standalone CSV Debug Tool
Use the dedicated debug script to test CSV functionality:

```bash
# Test with default output location
python debug_csv_export.py

# Test with specific output file
python debug_csv_export.py -o /path/to/test.csv

# Test append mode
python debug_csv_export.py -o /path/to/test.csv --append
```

## Common Issues and Solutions

### Issue 1: "File doesn't exist after export"
**Symptoms:** CSV export reports success but file is missing

**Debug steps:**
1. Run with `--csv-debug` to see detailed path information
2. Check if the output directory has write permissions
3. Verify disk space availability
4. Look for permission errors in the debug output

### Issue 2: "Permission denied"
**Symptoms:** Export fails with permission errors

**Solutions:**
- Ensure the output directory exists and is writable
- Try using a different output directory: `--csv-output ~/Documents/ap_data.csv`
- Check that you have permission to create files in the target directory

### Issue 3: "File created but empty"
**Symptoms:** CSV file exists but has no data

**Debug steps:**
1. Check the "Number of AP records to export" in debug output
2. Verify that APs were successfully connected and parsed
3. Look for parsing errors in the main output

### Issue 4: "Append mode not working"
**Symptoms:** Data isn't being appended to existing files

**Debug steps:**
1. Use `--csv-debug` to see existing file analysis
2. Check if the existing file has a proper CSV header
3. Verify file permissions allow appending

## Example Debug Commands

### Debug a specific AP with verbose output:
```bash
python -m ap_gnss_stats.bin.ap_ssh_collector \
  -a your-ap.example.com \
  -u admin \
  --csv \
  --csv-output output/debug_test.csv \
  --csv-debug
```

### Test CSV export without connecting to APs:
```bash
python debug_csv_export.py -o output/standalone_test.csv
```

### Debug append mode:
```bash
# First export
python debug_csv_export.py -o output/append_test.csv

# Second export (append)
python debug_csv_export.py -o output/append_test.csv --append
```

## Understanding Debug Output

The debug output includes several sections:

1. **Environment Debug** - Shows Python version, working directory, user, disk space
2. **File Path Analysis** - Shows absolute paths and directory information
3. **Permission Checks** - Verifies read/write permissions
4. **Export Process** - Step-by-step CSV creation process
5. **Post-Export Verification** - Confirms file creation and content

## Getting Help

If you're still experiencing issues after running the debug tools:

1. Save the complete debug output to a file:
   ```bash
   python -m ap_gnss_stats.bin.ap_ssh_collector ... --csv-debug 2>&1 | tee debug_output.txt
   ```

2. Include the following information when reporting issues:
   - Complete debug output
   - Operating system and Python version
   - Target output directory and permissions
   - Whether the issue occurs with all APs or specific ones

## Quick Fixes

### Try these first:
1. Use an absolute path for output: `--csv-output /Users/username/ap_data.csv`
2. Ensure the output directory exists: `mkdir -p output`
3. Test with a simple filename in your home directory: `--csv-output ~/test.csv`
4. Run the standalone debug tool to verify CSV functionality works independently
