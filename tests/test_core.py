import unittest
import tempfile
from pathlib import Path
import sys
import types
try:
    import keyring
except ImportError:
    sys.modules["keyring"] = types.SimpleNamespace(get_password=lambda *a: None, set_password=lambda *a: None)
from unittest.mock import patch
from nimbomount.core import Settings, _clean_error, MountEngine

class BasicTests(unittest.TestCase):
    def test_settings_default(self):
        s = Settings()
        self.assertFalse(s.mount_at_login)
        self.assertTrue(s.auto_reconnect)
    def test_error_redaction(self):
        self.assertNotIn('secret', _clean_error('authentication failed secret'))
    def test_mount_config_is_real_empty_file(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("nimbomount.core.BASE", Path(directory)):
                config = MountEngine()._empty_mount_config()
                self.assertTrue(config.is_file())
                self.assertEqual(config.read_bytes(), b"")
                self.assertNotEqual(config.name.lower(), "nul")
                # Existing file content is overwritten, not reused as config.
                config.write_text("[other_remote]\ntype = local\n")
                self.assertEqual(MountEngine()._empty_mount_config().read_bytes(), b"")

    def test_not_running_rc(self):
        with self.assertRaises(RuntimeError):
            MountEngine().rc('vfs/queue')

if __name__ == '__main__':
    unittest.main()
