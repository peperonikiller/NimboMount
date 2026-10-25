import unittest
from pathlib import Path

class TraySourceTests(unittest.TestCase):
    def test_retries_on_explorer_start(self):
        code = (Path(__file__).resolve().parents[1] / "nimbomount" / "gui.py").read_text()
        self.assertIn("self.tray_timer.timeout.connect(self.ensure_tray_visible)", code)
        self.assertIn("self.tray_timer.start()", code)
        self.assertIn("self.tray.show()", code)
        self.assertIn("System tray: active", code)
