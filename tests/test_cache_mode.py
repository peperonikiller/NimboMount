import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
try:
    import keyring
except ImportError:
    import sys, types
    sys.modules["keyring"] = types.SimpleNamespace(get_password=lambda *a: None, set_password=lambda *a: None)
from nimbomount.core import Settings, MountEngine, throughput_mount_args

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
        self.assertIn("throughput_mount_args(write_cache_enabled)", src)
    def test_cached_mount_reads_in_parallel(self):
        args = throughput_mount_args(True)
        self.assertEqual(args[args.index("--transfers") + 1], "8")
        self.assertEqual(args[args.index("--vfs-write-back") + 1], "5s")
        self.assertEqual(args[args.index("--buffer-size") + 1], "32M")
        self.assertEqual(args[args.index("--vfs-read-ahead") + 1], "128M")
        self.assertEqual(args[args.index("--vfs-read-chunk-size") + 1], "8M")
        self.assertEqual(args[args.index("--vfs-read-chunk-streams") + 1], "4")
    def test_direct_mount_skips_disk_readahead(self):
        args = throughput_mount_args(False)
        self.assertEqual(args[args.index("--transfers") + 1], "8")
        self.assertEqual(args[args.index("--vfs-write-back") + 1], "5s")
        self.assertNotIn("--vfs-read-ahead", args)
        self.assertNotIn("--vfs-read-chunk-streams", args)
    def test_throughput_mode_must_be_bool(self):
        with self.assertRaises(ValueError):
            throughput_mount_args("full")

if __name__ == "__main__":
    unittest.main()
