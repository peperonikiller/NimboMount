"""Register startup-at-user-login. No administrator privileges required."""
from __future__ import annotations
import os
import sys
import shlex
from pathlib import Path

APP_ID = 'NimboMount'

def launch_command() -> list[str]:
    if getattr(sys, 'frozen', False):
        return [sys.executable]
    return [sys.executable, '-m', 'nimbomount']

def set_login_startup(enabled: bool):
    if sys.platform == 'win32':
        import winreg
        path = r'Software\Microsoft\Windows\CurrentVersion\Run'
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                import subprocess
                command = subprocess.list2cmdline(launch_command())
                winreg.SetValueEx(key, APP_ID, 0, winreg.REG_SZ, command + ' --minimized')
            else:
                try: winreg.DeleteValue(key, APP_ID)
                except FileNotFoundError: pass
    elif sys.platform.startswith('linux'):
        target = Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))/'autostart'/'nimbomount.desktop'
        if enabled:
            target.parent.mkdir(parents=True, exist_ok=True)
            # Desktop Exec token quoting per desktop file convention; filenames with quotes escaped.
            command = ' '.join('"'+arg.replace('\\','\\\\').replace('"','\\"')+'"' for arg in launch_command())
            target.write_text('[Desktop Entry]\nType=Application\nName=NimboMount\nExec='+command+' --minimized\nTerminal=false\nX-GNOME-Autostart-enabled=true\n', encoding='utf-8')
            os.chmod(target, 0o600)
        else:
            target.unlink(missing_ok=True)
    else:
        raise RuntimeError('Unsupported OS')
