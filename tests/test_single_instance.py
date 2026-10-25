import unittest
from unittest.mock import patch, MagicMock
from nimbomount.core import MountEngine, nimbomount_rclone_processes, CACHE

class OwnershipTests(unittest.TestCase):
    @patch('nimbomount.core.psutil.process_iter')
    def test_only_our_mount_is_detected(self, iterator):
        def proc(pid, name, argv):
            p = MagicMock()
            p.info = {'pid':pid, 'name':name, 'cmdline':argv, 'create_time':1.0}
            return p
        iterator.return_value = [
            proc(1,'rclone.exe',['rclone','mount','something:', 'Q:', '--cache-dir', str(CACHE)]),
            proc(2,'rclone.exe',['rclone','mount','nimbo_mega:', 'M:', '--cache-dir', str(CACHE)]),
            proc(3,'unrelated.exe',['unrelated','mount','nimbo_mega:', 'N:', '--cache-dir', str(CACHE)]),
        ]
        self.assertEqual([p['pid'] for p in nimbomount_rclone_processes()], [2])
        self.assertEqual(nimbomount_rclone_processes(exclude_pid=2), [])

    def test_pending_queue_blocks_unmount(self):
        eng = MountEngine()
        proc = MagicMock()
        proc.poll.return_value = None
        eng.proc = proc
        with patch.object(eng, 'rc', return_value={'queue':[{'name':'a'}]}):
            with self.assertRaisesRegex(RuntimeError, 'pending'):
                eng.stop()
        proc.terminate.assert_not_called()

    def test_queue_error_blocks_unmount(self):
        eng = MountEngine()
        proc = MagicMock()
        proc.poll.return_value = None
        eng.proc = proc
        with patch.object(eng, 'rc', side_effect=TimeoutError('temporarily offline')):
            with self.assertRaisesRegex(RuntimeError, 'Cannot safely unmount'):
                eng.stop()
        proc.terminate.assert_not_called()

    def test_empty_queue_requests_graceful_stop(self):
        eng = MountEngine()
        proc = MagicMock()
        proc.poll.return_value = None
        eng.proc = proc
        with patch.object(eng, 'rc', return_value={'queue':[]}):
            eng.stop()
        proc.terminate.assert_called_once()
        proc.wait.assert_called_once()
        self.assertIsNone(eng.proc)

if __name__ == '__main__':
    unittest.main()
