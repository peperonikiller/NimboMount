import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
try:
    import keyring
except ImportError:
    import sys, types
    sys.modules["keyring"] = types.SimpleNamespace(get_password=lambda *a: None, set_password=lambda *a: None)
from nimbomount.core import Settings, MountEngine

class CacheSettingsTests(unittest.TestCase):
    def test_default_enabled(self):
        self.assertTrue(Settings().write_cache_enabled)
    def test_persist_off(self):
        with tempfile.TemporaryDirectory() as d:
            from nimbomount import core
            with patch.object(core, "BASE", Path(d)), patch.object(core, "SETTINGS", Path(d)/"settings.json"):
                settings = Settings(write_cache_enabled=False)
                settings.save()
                self.assertFalse(Settings.load().write_cache_enabled)
    def test_direct_mode_idle_and_busy(self):
        self.assertTrue(MountEngine._write_state({"direct": True, "stats": {}})[0])
        self.assertFalse(MountEngine._write_state({"direct": True, "stats": {"transferring": [{"name": "x"}]}})[0])
        self.assertFalse(MountEngine._write_state({"direct": True, "stats": {"errors": 1}})[0])
    def test_mount_mode_arg_source(self):
        import inspect
        src = inspect.getsource(MountEngine.mount)
        self.assertIn('"full" if write_cache_enabled else "off"', src)

if __name__ == "__main__":
    unittest.main()
