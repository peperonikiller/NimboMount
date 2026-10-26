"""Regression coverage for malformed settings, cache-off and write safety."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
try:
    import keyring
except ImportError:
    import sys, types
    sys.modules["keyring"] = types.SimpleNamespace(get_password=lambda *a: None,
        set_password=lambda *a: None, errors=types.SimpleNamespace(KeyringError=Exception, PasswordDeleteError=Exception))
from nimbomount import core
from nimbomount.core import Settings, MountEngine


class AuditRegressionTests(unittest.TestCase):
    def snapshot(self, cache=None, stats=None):
        return {"queue": [], "cache": cache if cache is not None else {
            "uploadsQueued": 0, "uploadsInProgress": 0, "erroredFiles": 0,
            "outOfSpace": False}, "stats": stats if stats is not None else {}}

    def test_settings_do_not_coerce_strings_to_booleans(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / 'settings.json'
            file.write_text('{"write_cache_enabled":"false","mount_at_login":"true","auto_reconnect":0,"email":12}')
            with patch.object(core, 'SETTINGS', file):
                setting = Settings.load()
            self.assertTrue(setting.write_cache_enabled)
            self.assertFalse(setting.mount_at_login)
            self.assertTrue(setting.auto_reconnect)
            self.assertEqual(setting.email, '')

    def test_settings_wrong_root_type_is_safe(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / 'settings.json'
            file.write_text('[]')
            with patch.object(core, 'SETTINGS', file):
                self.assertTrue(Settings.load().write_cache_enabled)

    def test_vfs_counters_must_be_nonnegative_integers(self):
        for counter in ('uploadsQueued', 'uploadsInProgress', 'erroredFiles'):
            for bad in (True, -1, None, '0', 1.5):
                snapshot = self.snapshot()
                snapshot['cache'][counter] = bad
                self.assertFalse(MountEngine._write_state(snapshot)[0], (counter, bad))

    def test_out_of_space_flag_must_be_bool(self):
        snapshot = self.snapshot()
        snapshot['cache']['outOfSpace'] = 'false'
        self.assertFalse(MountEngine._write_state(snapshot)[0])

    def test_direct_write_active_and_malformed_errors(self):
        for errors in (True, -1, '0', 1, None):
            self.assertFalse(MountEngine._write_state({'direct': True, 'stats': {'errors': errors}})[0])
        self.assertTrue(MountEngine._write_state({'direct': True, 'stats': {}})[0])
        self.assertFalse(MountEngine._write_state({'direct': True, 'stats': {'transferring': [1]}})[0])

    def test_cached_transfer_malformed_errors(self):
        for errors in (True, -1, '0', None):
            self.assertFalse(MountEngine._write_state(self.snapshot(stats={'errors': errors}))[0])

    def test_direct_mode_retry_not_allowed(self):
        engine = MountEngine()
        engine.transfer_snapshot = lambda: {'direct': True, 'queue': []}
        with self.assertRaisesRegex(RuntimeError, 'caching disabled'):
            engine.retry_upload(1)
        with self.assertRaisesRegex(RuntimeError, 'caching disabled'):
            engine.retry_all_queued()

    def test_invalid_mount_mode_rejected_without_process(self):
        engine = MountEngine()
        with self.assertRaises(ValueError):
            engine.mount('example@example.com', '', 'M:', write_cache_enabled='off')

    def test_snapshot_rejects_missing_stats(self):
        engine = MountEngine()
        engine.write_cache_enabled = True
        def rc(method):
            return {'vfs/queue': {'queue': []}, 'vfs/stats': {'diskCache': {
                'uploadsQueued': 0, 'uploadsInProgress': 0,
                'erroredFiles': 0, 'outOfSpace': False}},
                'core/stats': []}[method]
        engine.rc = rc
        with self.assertRaisesRegex(RuntimeError, 'valid VFS'):
            engine.transfer_snapshot()

    def test_unmount_check_parameters(self):
        engine = MountEngine()
        for checks, interval in ((True, 0), (0, 0), (31, 0), (2, -1), (2, True), (2, 61)):
            with self.assertRaises(ValueError):
                engine.verify_writes_for_unmount(checks=checks, interval=interval)

    def test_last_snapshot_failure_blocks_unmount(self):
        engine = MountEngine()
        engine.write_cache_enabled = False
        calls = iter([{'direct': True, 'stats': {}}, {'direct': True, 'stats': {}}, RuntimeError('RC offline')])
        def snapshot():
            value = next(calls)
            if isinstance(value, Exception):
                raise value
            return value
        engine.transfer_snapshot = snapshot
        with self.assertRaisesRegex(RuntimeError, 'final write state unavailable'):
            engine.verify_writes_for_unmount(checks=2, interval=0)

if __name__ == '__main__':
    unittest.main()
