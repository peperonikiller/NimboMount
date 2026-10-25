import unittest
from unittest.mock import patch
from nimbomount import core

class DiagnosticTests(unittest.TestCase):
    def test_redaction(self):
        line = 'ERROR session_id=abcd 2fa:123456 password=secret'
        cleaned = core.sanitize_diagnostic(line, {'RCLONE_CONFIG_NIMBO_MEGA_SESSION_ID':'abcd'})
        for secret in ('abcd', '123456', 'secret'):
            self.assertNotIn(secret, cleaned)

    def test_fresh_login_overrides_saved_session(self):
        engine = core.MountEngine()
        engine.binary = 'rclone'
        with patch.object(core, 'get_session', return_value={'session_id':'old', 'master_key':'eA=='}), \
             patch.object(engine, 'prerequisites'), \
             patch.object(engine, 'validate', side_effect=RuntimeError('fresh login invoked')):
            with self.assertRaisesRegex(RuntimeError, 'fresh login invoked'):
                engine.mount('email@example.com', 'password', '/tmp/nimbomount-test', '123456')

if __name__ == '__main__': unittest.main()
