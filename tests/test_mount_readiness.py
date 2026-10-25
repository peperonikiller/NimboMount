"""Regression coverage for stale 'Mount starting' state."""
import unittest
from pathlib import Path
from unittest.mock import patch
from nimbomount.core import MountEngine


class MountReadinessTests(unittest.TestCase):
    def test_mount_not_started(self):
        engine = MountEngine()
        ready, message = engine.mount_ready()
        self.assertFalse(ready)
        self.assertIn('rclone exited', message)

    def test_linux_directory_alone_not_a_mount(self):
        engine = MountEngine()
        engine.point = '/tmp/nimbomount-not-a-fuse-mount'
        with patch('nimbomount.core.IS_WIN', False), patch.object(engine, 'alive', return_value=True), patch('os.path.ismount', return_value=False):
            ready, message = engine.mount_ready()
        self.assertFalse(ready)
        self.assertIn('Waiting', message)

    def test_linux_mount_registered(self):
        engine = MountEngine()
        engine.point = '/tmp/nimbomount-test'
        with patch('nimbomount.core.IS_WIN', False), patch.object(engine, 'alive', return_value=True), patch('os.path.ismount', return_value=True):
            ready, message = engine.mount_ready()
        self.assertTrue(ready)

    def test_probe_worker_emits_success_in_source(self):
        text = (Path(__file__).parent.parent / 'nimbomount' / 'gui.py').read_text(encoding='utf-8')
        self.assertIn('self.events.result.emit(operation, True, "")', text)
        self.assertIn('elif op == "ready":', text)
        self.assertIn('self.engine.mount_ready()', text)
        self.assertNotIn('if operation != "probe":', text)

if __name__ == '__main__':
    unittest.main()
