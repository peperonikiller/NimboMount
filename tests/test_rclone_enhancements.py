import unittest
from unittest.mock import Mock
from nimbomount.core import MountEngine

class RcloneFeaturesTests(unittest.TestCase):
    def test_retry_all_skips_active_and_invalid_ids(self):
        engine = MountEngine()
        engine.transfer_snapshot = Mock(return_value={"queue": [
            {"id": 1, "uploading": False}, {"id": 2, "uploading": True},
            {"id": 3, "uploading": False}, {"id": "4", "uploading": False}]})
        engine.rc = Mock(return_value={})
        self.assertEqual(engine.retry_all_queued(), 2)
        self.assertEqual(engine.rc.call_count, 2)
        engine.rc.assert_any_call("vfs/queue-set-expiry", {"id": 1, "expiry": -1000000000})

    def test_refresh_uses_vfs(self):
        engine = MountEngine(); engine.rc = Mock(return_value={})
        engine.refresh_cloud()
        engine.rc.assert_called_once_with("vfs/refresh", {"dir": "", "recursive": False})

    def test_speed_limit_validate(self):
        engine = MountEngine(); engine.rc = Mock(return_value={})
        engine.set_bandwidth_limit("5M")
        engine.rc.assert_called_once_with("core/bwlimit", {"rate": "5M"})
        with self.assertRaises(ValueError):
            engine.set_bandwidth_limit("1M;shutdown")

    def test_write_gate_blocks_unknown_cache(self):
        ok, _ = MountEngine._write_state({"queue": [], "cache": {}})
        self.assertFalse(ok)

if __name__ == '__main__': unittest.main()
