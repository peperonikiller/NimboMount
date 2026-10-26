import unittest
from nimbomount.core import MountEngine


class UnmountStatsTests(unittest.TestCase):
    def snapshot(self, stats):
        return {
            "queue": [],
            "cache": {"uploadsQueued": 0, "uploadsInProgress": 0,
                      "erroredFiles": 0, "outOfSpace": False},
            "stats": stats,
        }

    def test_missing_transferring_is_normal_idle_state(self):
        ok, reason = MountEngine._write_state(self.snapshot({"errors": 0}))
        self.assertTrue(ok, reason)

    def test_empty_transferring_is_normal_idle_state(self):
        ok, reason = MountEngine._write_state(self.snapshot({"errors": 0, "transferring": []}))
        self.assertTrue(ok, reason)

    def test_present_transfers_block(self):
        ok, _ = MountEngine._write_state(self.snapshot({"errors": 0, "transferring": [{"name": "file"}]}))
        self.assertFalse(ok)

    def test_malformed_transferring_blocks(self):
        ok, _ = MountEngine._write_state(self.snapshot({"errors": 0, "transferring": None}))
        self.assertFalse(ok)

    def test_failed_or_missing_stats_block(self):
        for value in [None, "error", []]:
            ok, _ = MountEngine._write_state(self.snapshot(value))
            self.assertFalse(ok)

    def test_errors_and_vfs_writes_still_block(self):
        ok, _ = MountEngine._write_state(self.snapshot({"errors": 1}))
        self.assertFalse(ok)
        payload = self.snapshot({"errors": 0})
        payload["cache"]["uploadsQueued"] = 1
        ok, _ = MountEngine._write_state(payload)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
