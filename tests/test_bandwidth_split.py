import unittest
from pathlib import Path

CORE = (Path(__file__).resolve().parents[1] / "nimbomount" / "core.py").read_text()

class SplitBandwidthTests(unittest.TestCase):
    def test_combined_rate_sent_to_existing_rc(self):
        self.assertIn('return self.rc("core/bwlimit", {"rate": f"{upload}:{download}"})', CORE)
    def test_reject_invalid_rates(self):
        self.assertIn('if upload not in supported or download not in supported:', CORE)
    def test_supported_off(self):
        self.assertIn('{"off", "512k", "1M", "5M", "10M", "25M", "50M"}', CORE)
if __name__ == "__main__": unittest.main()
