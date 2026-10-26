"""Regression tests for two independent bandwidth controls."""
from pathlib import Path
import unittest
GUI = (Path(__file__).resolve().parents[1] / "nimbomount" / "gui.py").read_text()

class BandwidthGuiTests(unittest.TestCase):
    def test_both_controls_visible(self):
        self.assertIn('transfers_layout.addWidget(bandwidth_group)', GUI)
        self.assertIn('self.upload_limit_combo = QComboBox()', GUI)
        self.assertIn('self.download_limit_combo = QComboBox()', GUI)
        self.assertIn('self.bandwidth_apply = QPushButton("Apply limit")', GUI)
    def test_worker_uses_both_values(self):
        self.assertIn('self.engine.set_bandwidth_limits(upload_rate, download_rate)', GUI)
    def test_readiness_gates_both(self):
        self.assertIn('self.upload_limit_combo.setEnabled(bandwidth_ready)', GUI)
        self.assertIn('self.download_limit_combo.setEnabled(bandwidth_ready)', GUI)
if __name__ == "__main__": unittest.main()
