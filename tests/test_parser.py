"""
Unit tests for the GNSS Info Parser.
"""
import unittest
import os
from ap_gnss_stats.lib.parser import GnssInfoParser

class TestGnssInfoParser(unittest.TestCase):
    """Tests for the GNSS Info Parser."""
    
    def setUp(self):
        self.parser = GnssInfoParser()
        
        # Sample GNSS info text for testing
        self.sample_text = """
AP Name : AP-Building1-Floor3
AP Model : C9166I
MAC Address : 00:11:22:33:44:55
IP Address : 192.168.1.100
AP Location : Building 1, 3rd Floor, North Wing

GNSS Status : Active and tracking
Latitude : 37.7749
Longitude : -122.4194
Altitude : 12.5 m
Number of Satellites : 8
Time Stamp : 2023-07-15 13:45:22
"""
    
    def test_parse_text(self):
        """Test parsing of sample text."""
        result = self.parser.parse_text(self.sample_text)
        
        # Check basic information parsing
        self.assertEqual(result["ap_name"], "AP-Building1-Floor3")
        self.assertEqual(result["model"], "C9166I")
        self.assertEqual(result["mac_address"], "00:11:22:33:44:55")
        self.assertEqual(result["ip_address"], "192.168.1.100")
        self.assertEqual(result["location"], "Building 1, 3rd Floor, North Wing")
        
        # Check GNSS specific information
        self.assertEqual(result["gnss_status"], "Active and tracking")
        self.assertEqual(result["latitude"], 37.7749)
        self.assertEqual(result["longitude"], -122.4194)
        self.assertEqual(result["altitude_meters"], 12.5)
        self.assertEqual(result["satellites_count"], 8)
        self.assertEqual(result["gnss_timestamp"], "2023-07-15 13:45:22")

if __name__ == "__main__":
    unittest.main()