import base64
import json
import unittest
import sys
import types
from unittest.mock import patch
from nimbomount import core


class SessionTests(unittest.TestCase):
    def test_session_roundtrip(self):
        vault = {}
        fake_fail = types.ModuleType('keyring.backends.fail')
        fake_fail.Keyring = type('FailKeyring', (), {})
        with patch.dict(sys.modules, {'keyring.backends': types.ModuleType('keyring.backends'), 'keyring.backends.fail': fake_fail}), \
             patch.object(core.keyring, 'get_keyring', create=True, return_value=object()), \
             patch.object(core.keyring, 'get_password', side_effect=lambda service, email: vault.get((service, email))), \
             patch.object(core.keyring, 'set_password', side_effect=lambda service, email, data: vault.__setitem__((service, email), data)):
            session = {'session_id': 'session-secret', 'master_key': base64.b64encode(b'key').decode()}
            core.save_session('Me@Example.org', session)
            self.assertEqual(core.get_session('me@example.org'), session)
            self.assertEqual(len(vault), 1)
            self.assertNotIn('2fa', next(iter(vault.values())).lower())

    def test_incomplete_session_rejected(self):
        with patch.object(core.keyring, 'get_password', return_value=json.dumps({'session_id': 'id'})):
            self.assertIsNone(core.get_session('me@example.org'))

    def test_mount_uses_session_not_otp(self):
        session = {'session_id': 'id', 'master_key': base64.b64encode(b'key').decode()}
        class FakeProc:
            def poll(self): return None
        class Result:
            returncode = 0
            stdout = 'obscured-pass'
        with patch.object(core, 'get_session', return_value=session), \
             patch.object(core.MountEngine, 'prerequisites'), \
             patch.object(core.MountEngine, '_run', return_value=Result()), \
             patch.object(core.subprocess, 'Popen', return_value=FakeProc()), \
             patch.object(core, 'IS_WIN', True), \
             patch.object(core, 'available_letters', return_value=['M:']), \
             patch.object(core, '_startupinfo', return_value=None), \
             patch.object(core.subprocess, 'CREATE_NO_WINDOW', 0, create=True):
            engine = core.MountEngine()
            engine.binary = 'rclone.exe'
            engine.mount('me@example.org', '', 'M:')
            self.assertEqual(engine._env['RCLONE_CONFIG_NIMBO_MEGA_SESSION_ID'], 'id')
            self.assertNotIn('RCLONE_CONFIG_NIMBO_MEGA_2FA', engine._env)

if __name__ == '__main__':
    unittest.main()
