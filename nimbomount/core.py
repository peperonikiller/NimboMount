"""NimboMount engine. Never puts the MEGA password on the command line."""
from __future__ import annotations
import configparser
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import threading
import secrets
import socket
import base64
import sys
import urllib.request
import urllib.error
import time
import psutil
from collections import deque
from dataclasses import dataclass
from pathlib import Path
import keyring

APP = "NimboMount"
REMOTE = "nimbo_mega"
IS_WIN = platform.system() == "Windows"
BASE = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / APP if IS_WIN else Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "nimbomount"
CACHE = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / APP / "cache" if IS_WIN else Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "nimbomount"
SETTINGS = BASE / "settings.json"


def _find_rclone() -> str | None:
    """Prefer shipped binary, then system installed rclone; no PATH requirement."""
    if IS_WIN:
        locations = [Path(sys.executable).resolve().parent / "rclone.exe"]
        if hasattr(sys, "_MEIPASS"):
            locations.append(Path(sys._MEIPASS) / "rclone.exe")
        for exe in locations:
            if exe.is_file():
                return str(exe)
    return shutil.which("rclone")


def private_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)
    if not IS_WIN:
        os.chmod(p, 0o700)


def available_letters() -> list[str]:
    if not IS_WIN:
        return []
    import ctypes
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    return [f"{chr(n)}:" for n in range(ord('D'), ord('Z') + 1) if not mask & (1 << (n - ord('A')))]


def default_point() -> str:
    return "M:" if IS_WIN else str(Path.home() / "NimboMount")


@dataclass
class Settings:
    email: str = ""
    mountpoint: str = ""
    auto_reconnect: bool = True
    mount_at_login: bool = False

    @classmethod
    def load(cls):
        try:
            raw = json.loads(SETTINGS.read_text(encoding="utf-8"))
            return cls(email=str(raw.get("email", "")), mountpoint=str(raw.get("mountpoint", "")), auto_reconnect=bool(raw.get("auto_reconnect", True)), mount_at_login=bool(raw.get("mount_at_login", False)))
        except (OSError, ValueError, TypeError):
            return cls()

    def save(self):
        private_dir(BASE)
        tmp = SETTINGS.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.__dict__, indent=2), encoding="utf-8")
        if not IS_WIN:
            os.chmod(tmp, 0o600)
        tmp.replace(SETTINGS)


SESSION_SERVICE = "NimboMount MEGA session v1"


def get_session(email: str) -> dict | None:
    """OS credential vault only; session ID AND master key are bearer secrets."""
    try:
        raw = keyring.get_password(SESSION_SERVICE, email.casefold())
        value = json.loads(raw) if raw else None
        if isinstance(value, dict) and value.get("session_id") and value.get("master_key"):
            base64.b64decode(value["master_key"], validate=True)
            return value
    except (ValueError, TypeError, keyring.errors.KeyringError):
        pass
    return None


def save_session(email: str, session: dict) -> None:
    from keyring.backends.fail import Keyring as FailKeyring
    if isinstance(keyring.get_keyring(), FailKeyring):
        raise RuntimeError("No secure credential vault is available; session cannot be saved")
    if not session.get("session_id") or not session.get("master_key"):
        raise ValueError("Missing MEGA session keys")
    base64.b64decode(session["master_key"], validate=True)
    keyring.set_password(SESSION_SERVICE, email.casefold(), json.dumps(session))


def forget_session(email: str) -> None:
    try:
        keyring.delete_password(SESSION_SERVICE, email.casefold())
    except keyring.errors.PasswordDeleteError:
        pass




def nimbomount_rclone_processes(exclude_pid: int | None = None) -> list[dict]:
    """Identify existing NimboMount mount processes; never kill unrelated rclone jobs.

    Identification requires BOTH our private remote name and private cache directory
    in the command line. An inaccessible process is ignored, not terminated.
    """
    found = []
    cache_key = str(CACHE).replace("/", "\\").casefold()
    for proc in psutil.process_iter(attrs=["pid", "name", "cmdline", "create_time"]):
        try:
            info = proc.info
            if info["pid"] == exclude_pid or not (info.get("name") or "").lower().startswith("rclone"):
                continue
            args = info.get("cmdline") or []
            normalized = [str(a).replace("/", "\\").casefold() for a in args]
            if "mount" not in normalized or f"{REMOTE}:" not in normalized:
                continue
            if cache_key not in normalized:
                continue
            mount_index = normalized.index("mount")
            try:
                target = args[mount_index + 2]
            except IndexError:
                target = "unknown"
            found.append({"pid": info["pid"], "target": target,
                          "create_time": info.get("create_time")})
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
            continue
    return found

class MountEngine:
    def __init__(self):
        self.binary = _find_rclone()
        self.proc: subprocess.Popen | None = None
        self.config_path: Path | None = None
        self._lock = threading.RLock()
        self.last_error = ""
        self.point = ""
        self.rc_port = None
        self.rc_user = None
        self.rc_secret = None
        self._env = None
        self._logs = deque(maxlen=100)
        self._log_thread = None
        self._log_lock = threading.Lock()

    def prerequisites(self):
        if not self.binary:
            raise RuntimeError("rclone not found. Install rclone and add it to PATH.")
        if IS_WIN:
            # WinFsp's availability is best confirmed by the actual mount attempt.
            return
        if not Path("/dev/fuse").exists():
            raise RuntimeError("/dev/fuse unavailable. Install/configure FUSE 3 and permit your user to access it.")

    def _run(self, args: list[str], *, timeout=35, input_text=None, config=None, env=None):
        cmd = [self.binary, *( ["--config", str(config)] if config else []), *args]
        return subprocess.run(cmd, text=True, input=input_text, capture_output=True, timeout=timeout,
                              startupinfo=_startupinfo(), env=env)

    def _config(self, email: str, password: str, otp: str = "") -> Path:
        # rclone obscure - reads password on stdin, not command-line args.
        obscured = self._run(["obscure", "-"], input_text=password + "\n", timeout=15)
        if obscured.returncode:
            raise RuntimeError("Unable to securely prepare MEGA credentials: " + obscured.stderr[-400:])
        parser = configparser.ConfigParser(interpolation=None)
        parser[REMOTE] = {"type": "mega", "user": email, "pass": obscured.stdout.strip(), "use_https": "true"}
        if otp:
            parser[REMOTE]["2fa"] = otp
        private_dir(BASE)
        fd, pathname = tempfile.mkstemp(prefix="mega-", suffix=".conf", dir=str(BASE))
        p = Path(pathname)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                parser.write(handle)
            if not IS_WIN:
                os.chmod(p, 0o600)
            return p
        except Exception:
            p.unlink(missing_ok=True)
            raise

    def validate(self, email: str, password: str, otp: str = "") -> None:
        """Obtain reusable MEGA session secrets after real password + TOTP login.

        Backend writes session_id/master_key into its writable config mapper.
        Temporary configuration stays in a short-lived directory which is removed
        (including rclone-created backup files) before returning.
        """
        self.prerequisites()
        private_dir(BASE)
        with tempfile.TemporaryDirectory(prefix="nimbo-auth-", dir=str(BASE)) as directory:
            config = Path(directory) / "auth.conf"
            obscured = self._run(["obscure", "-"], input_text=password + "\n", timeout=15)
            if obscured.returncode:
                raise RuntimeError("Could not prepare login credentials")
            parser = configparser.ConfigParser(interpolation=None)
            parser[REMOTE] = {"type": "mega", "user": email,
                              "pass": obscured.stdout.strip(), "use_https": "true"}
            if otp:
                parser[REMOTE]["2fa"] = otp
            with config.open("w", encoding="utf-8") as output:
                parser.write(output)
            if not IS_WIN:
                os.chmod(config, 0o600)
            result = self._run(["lsf", REMOTE + ":", "--max-depth", "1", "--retries", "1",
                                "--low-level-retries", "1", "--contimeout", "10s", "--timeout", "20s"],
                               config=config, timeout=40)
            if result.returncode:
                raise RuntimeError(_clean_error(result.stderr))
            parser.read(config, encoding="utf-8")
            session = {"session_id": parser.get(REMOTE, "session_id", fallback=""),
                       "master_key": parser.get(REMOTE, "master_key", fallback="")}
            if not all(session.values()):
                raise RuntimeError("MEGA login succeeded, but this rclone build did not persist session keys. "
                                   "Unattended reconnection is unavailable; update rclone.")
            save_session(email, session)

    def _empty_mount_config(self) -> Path:
        """Dedicated empty rclone config; os.devnull is invalid as --config on Windows.

        This file contains no passwords, OTPs, or MEGA session data. Cloud
        credentials are supplied separately through the child environment.
        """
        private_dir(BASE)
        config = BASE / "empty-mount.conf"
        config.write_text("", encoding="utf-8")
        if not IS_WIN:
            os.chmod(config, 0o600)
        return config

    def mount(self, email: str, password: str, mountpoint: str, otp: str = "", force_login: bool = False) -> None:
        with self._lock:
            self.prerequisites()
            existing = nimbomount_rclone_processes(exclude_pid=self.proc.pid if self.proc else None)
            if existing:
                detail = ", ".join(f"PID {x['pid']} ({x['target']})" for x in existing)
                raise RuntimeError("An existing NimboMount rclone mount was detected: " + detail + ". Unmount it before connecting again; no process was terminated.")
            if self.proc is not None and self.proc.poll() is None:
                raise RuntimeError("Drive is already mounted.")
            if not email or (not password and not get_session(email)):
                raise ValueError("Sign in with your MEGA password and a current 2FA code first.")
            if IS_WIN:
                if not re.fullmatch(r"[D-Zd-z]:", mountpoint):
                    raise ValueError("Choose a drive letter from D: through Z:.")
                if mountpoint.upper() not in available_letters():
                    raise ValueError(f"{mountpoint} is already assigned to another drive.")
            else:
                p = Path(mountpoint).expanduser().resolve()
                if not p.is_absolute() or p == Path("/"):
                    raise ValueError("Choose a dedicated absolute mount directory.")
                p.mkdir(parents=True, exist_ok=True)
                if any(p.iterdir()):
                    raise ValueError("Linux mount directory must be empty.")
                mountpoint = str(p)
            private_dir(CACHE)
            session = None if (force_login or otp) else get_session(email)
            if session is None:
                if not password:
                    raise RuntimeError("No saved MEGA session. Log in with your password and 2FA code.")
                self.validate(email, password, otp)
                session = get_session(email)
                if session is None:
                    raise RuntimeError("Could not save MEGA session into the credential vault")
            # Keep obscured configuration in child environment, not a persistent plaintext config file.
            # Rclone's obscure is reversible and is NOT encryption.
            obscured = self._run(["obscure", "-"], input_text="session-reconnect-placeholder\n", timeout=15)
            if obscured.returncode:
                raise RuntimeError("Could not prepare MEGA credentials")
            self._env = os.environ.copy()
            self._env.update({"RCLONE_CONFIG_NIMBO_MEGA_TYPE": "mega",
                              "RCLONE_CONFIG_NIMBO_MEGA_USER": email,
                              "RCLONE_CONFIG_NIMBO_MEGA_PASS": obscured.stdout.strip(),
                              "RCLONE_CONFIG_NIMBO_MEGA_USE_HTTPS": "true"})
            self._env["RCLONE_CONFIG_NIMBO_MEGA_SESSION_ID"] = session["session_id"]
            self._env["RCLONE_CONFIG_NIMBO_MEGA_MASTER_KEY"] = session["master_key"]
            # Never forward or persist the one-time authentication code on reconnect.
            # RC API is local-only and HTTP Basic authenticated with a fresh random secret.
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                self.rc_port = sock.getsockname()[1]
            self.rc_user = "nimbo"
            self.rc_secret = secrets.token_urlsafe(32)
            self._env["RCLONE_RC_USER"] = self.rc_user
            self._env["RCLONE_RC_PASS"] = self.rc_secret
            args = [self.binary, "--config", str(self._empty_mount_config()), "mount", REMOTE + ":", mountpoint,
                    "--rc", "--rc-addr", f"127.0.0.1:{self.rc_port}",
                    "--vfs-cache-mode", "full", "--cache-dir", str(CACHE),
                    "--vfs-write-back", "30s", "--vfs-cache-max-age", "87600h",
                    "--dir-cache-time", "2m", "--poll-interval", "0",
                    "--contimeout", "10s", "--timeout", "30s", "--retries", "3",
                    "--low-level-retries", "3", "--log-level", "ERROR"]
            if IS_WIN:
                args += ["--volname", "NimboMount MEGA"]
            try:
                with self._log_lock:
                    self._logs.clear()
                self.proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                             stderr=subprocess.PIPE, startupinfo=_startupinfo(),
                                             creationflags=subprocess.CREATE_NO_WINDOW if IS_WIN else 0, env=self._env)
                proc = self.proc
                self._log_thread = threading.Thread(target=self._capture_errors, args=(proc,), daemon=True)
                self._log_thread.start()
                self.point = mountpoint
                self._observed_writes = {}
                self.last_error = ""
            except Exception:
                self._delete_config()
                raise

    def _capture_errors(self, proc):
        """Continuously drain stderr to prevent rclone blocking on full pipe."""
        try:
            if not getattr(proc, "stderr", None):
                return
            for line in iter(proc.stderr.readline, b""):
                cleaned = sanitize_diagnostic(line.decode("utf-8", errors="replace"), self._env)
                if cleaned:
                    with self._log_lock:
                        self._logs.append(cleaned)
        except (OSError, ValueError):
            pass
        finally:
            try:
                if getattr(proc, "stderr", None):
                    proc.stderr.close()
            except (OSError, ValueError):
                pass

    def diagnostics(self) -> str:
        with self._log_lock:
            lines = list(self._logs)
        return "\n".join(lines[-40:]) or "No rclone error output was captured. Check WinFsp installation and drive letter."

    def exit_diagnostic(self) -> str:
        proc = self.proc
        if proc is not None and proc.poll() is not None and self._log_thread:
            self._log_thread.join(timeout=1)
        code = proc.returncode if proc is not None else None
        detail = self.diagnostics()
        self.last_error = f"rclone exited (code {code}).\n{detail}"
        return self.last_error

    def mount_ready(self) -> tuple[bool, str]:
        """Check that OS exposes the mount, not just that rclone is alive."""
        if not self.alive():
            return False, self.exit_diagnostic()
        if not self.point:
            return False, "No mount target was selected"
        if IS_WIN:
            import ctypes
            letter = self.point[0].upper()
            mask = ctypes.windll.kernel32.GetLogicalDrives()
            if not mask & (1 << (ord(letter) - ord('A'))):
                return False, f"Waiting for {letter}: to appear in Windows Explorer"
        else:
            path = os.path.realpath(self.point)
            if not os.path.ismount(path):
                return False, f"Waiting for {path} to become a filesystem mount"
        return True, "Mount is registered with the OS"

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def health(self) -> tuple[bool, str]:
        """Actual remote API probe; no dependency on public ping/DNS alone."""
        if not self.alive() or not self._env:
            return False, "Mount process stopped"
        try:
            p = self._run(["lsf", REMOTE + ":", "--max-depth", "1", "--retries", "1",
                           "--low-level-retries", "1", "--contimeout", "8s", "--timeout", "15s"],
                          config=None, timeout=28, env=self._env)
            return (True, "Connected") if p.returncode == 0 else (False, _clean_error(p.stderr))
        except (subprocess.TimeoutExpired, OSError) as exc:
            return False, f"MEGA unreachable: {type(exc).__name__}"

    def rc(self, command: str, params: dict | None = None) -> dict:
        """Query this mount's authenticated, loopback-only rclone RC endpoint."""
        with self._lock:
            if not self.alive() or not self.rc_port or not self.rc_secret:
                raise RuntimeError("Mount is not active")
            port, user, secret = self.rc_port, self.rc_user, self.rc_secret
        req = urllib.request.Request(f"http://127.0.0.1:{port}/{command}",
                                     data=json.dumps(params or {}).encode("utf-8"), headers={
                                         "Content-Type": "application/json",
                                         "Authorization": "Basic " + base64.b64encode(f"{user}:{secret}".encode()).decode()})
        with urllib.request.urlopen(req, timeout=4) as reply:
            return json.load(reply)

    def transfer_snapshot(self) -> dict:
        """Read all VFS durability counters; never default a missing counter to zero."""
        queue_payload = self.rc("vfs/queue")
        vfs_payload = self.rc("vfs/stats")
        stats = self.rc("core/stats")
        queue = queue_payload.get("queue")
        cache = vfs_payload.get("diskCache")
        if not isinstance(queue, list) or not isinstance(cache, dict):
            raise RuntimeError("rclone did not return VFS queue and disk-cache statistics")
        required = ("uploadsQueued", "uploadsInProgress", "erroredFiles", "outOfSpace")
        if any(key not in cache for key in required):
            raise RuntimeError("rclone did not return all required write safety counters")
        with self._lock:
            # Track every queued item seen during this mount. On completion it must
            # also exist on the remote with the same size before we consider it verified.
            if not hasattr(self, "_observed_writes"):
                self._observed_writes = {}
            for item in queue:
                name = item.get("name")
                size = item.get("size")
                if isinstance(name, str) and name and isinstance(size, int):
                    self._observed_writes[name] = size
        return {"queue": queue, "cache": cache, "stats": stats, "collected": time.time()}

    @staticmethod
    def _write_state(snapshot: dict) -> tuple[bool, str]:
        """Fail closed for every unknown, busy or errored cache state."""
        cache = snapshot.get("cache")
        queue = snapshot.get("queue")
        if not isinstance(cache, dict) or not isinstance(queue, list):
            return False, "Upload queue or cache status is unavailable"
        for key in ("uploadsQueued", "uploadsInProgress", "erroredFiles", "outOfSpace"):
            if key not in cache:
                return False, f"Missing rclone VFS counter: {key}"
        if cache["outOfSpace"]:
            return False, "VFS cache reports insufficient disk space"
        if cache["erroredFiles"]:
            return False, f"VFS cache reports {cache['erroredFiles']} errored file(s)"
        if queue or cache["uploadsQueued"] or cache["uploadsInProgress"]:
            return False, (f"Uploads pending: {len(queue)} visible, "
                           f"{cache['uploadsQueued']} queued, {cache['uploadsInProgress']} active")
        stats = snapshot.get("stats")
        if not isinstance(stats, dict) or not isinstance(stats.get("transferring"), list):
            return False, "Active-transfer statistics unavailable"
        if stats["transferring"]:
            return False, "Transfers are still active"
        if stats.get("errors", 0):
            return False, "rclone transfer statistics report errors"
        return True, "VFS cache is idle and reports no pending or errored writes"

    def retry_upload(self, item_id: int) -> None:
        """Prioritize a real queued write; never rewrite/remove cache files."""
        if isinstance(item_id, bool) or not isinstance(item_id, int):
            raise ValueError("Select a valid upload")
        queue = self.transfer_snapshot()["queue"]
        item = next((x for x in queue if x.get("id") == item_id), None)
        if item is None:
            raise RuntimeError("Upload no longer exists in the queue; refresh transfers")
        if item.get("uploading"):
            raise RuntimeError("This file is already uploading")
        self.rc("vfs/queue-set-expiry", {"id": item_id, "expiry": -1000000000})

    def retry_all_queued(self) -> int:
        """Move pending and retrying writes to the front of rclone's VFS queue."""
        queue = self.transfer_snapshot()["queue"]
        ids = [x["id"] for x in queue
               if isinstance(x.get("id"), int) and not isinstance(x.get("id"), bool)
               and not x.get("uploading")]
        for item_id in ids:
            self.rc("vfs/queue-set-expiry", {"id": item_id, "expiry": -1000000000})
        return len(ids)

    def refresh_cloud(self) -> None:
        """Invalidate and reload the mounted root's directory cache."""
        self.rc("vfs/refresh", {"dir": "", "recursive": False})

    def set_bandwidth_limit(self, rate: str) -> dict:
        """Set transfer speed on the owned mount, not globally on the computer."""
        if rate not in ("off", "512k", "1M", "5M", "10M", "25M", "50M"):
            raise ValueError("Unsupported speed limit")
        return self.rc("core/bwlimit", {"rate": rate})

    def _verify_observed_remote(self) -> None:
        """Metadata confirmation of files observed in the live queue.

        This is not a content hash or server durability guarantee. Files not seen
        by the polling loop cannot be verified by this method.
        """
        with self._lock:
            observed = dict(getattr(self, "_observed_writes", {}))
        for name, expected_size in observed.items():
            path = name.lstrip("/")
            if path.startswith("../") or not path:
                raise RuntimeError("Unsafe upload path found; refusing to unmount")
            result = self.rc("operations/stat", {"fs": REMOTE + ":", "remote": path})
            item = result.get("item")
            if not isinstance(item, dict) or item.get("Size") != expected_size:
                raise RuntimeError(f"Remote copy not confirmed for {name}; mount remains active")

    def verify_writes_for_unmount(self, *, checks: int = 3, interval: float = 1.5) -> None:
        """Require several consecutive clean snapshots and remote metadata checks.

        Conservative, best-effort safety gate; not a proof of physical durability.
        """
        if checks < 2:
            raise ValueError("At least two independent checks required")
        for i in range(checks):
            try:
                snapshot = self.transfer_snapshot()
            except Exception as exc:
                raise RuntimeError("Cannot safely unmount: write state is unavailable; mount and cache retained") from exc
            good, reason = self._write_state(snapshot)
            if not good:
                raise RuntimeError("Cannot safely unmount: " + reason + ". Mount and cache retained.")
            if i < checks - 1:
                time.sleep(interval)
        self._verify_observed_remote()
        # Race reduction: check state again after remote metadata requests.
        good, reason = self._write_state(self.transfer_snapshot())
        if not good:
            raise RuntimeError("Unmount interrupted by new writes: " + reason)

    def pending_uploads(self) -> int:
        return len(self.transfer_snapshot()["queue"])

    def stop(self) -> None:
        """Refuse normal unmount until cache is quiet and observed writes verified."""
        with self._lock:
            if self.proc and self.proc.poll() is None:
                self.verify_writes_for_unmount()
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    raise RuntimeError("rclone has not exited. Mount/cache retained; no force kill attempted.")
            self.proc = None
            self.point = ""
            self._delete_config()

    def cleanup(self):
        if self.proc is not None and self.proc.poll() is not None:
            self.proc = None
            self.point = ""
            self._delete_config()

    def _delete_config(self):
        if self.config_path:
            self.config_path.unlink(missing_ok=True)
            self.config_path = None
        self._env = None
        self.rc_user = None
        self.rc_secret = None
        self.rc_port = None


def sanitize_diagnostic(message: str, env: dict | None = None) -> str:
    """Redact all known credential values and common key/value credential syntax."""
    result = message.strip()[:2000]
    if env:
        for name, value in env.items():
            if (name.startswith("RCLONE_CONFIG_NIMBO_MEGA_") or name == "RCLONE_RC_PASS") and value and name not in ("RCLONE_CONFIG_NIMBO_MEGA_TYPE", "RCLONE_CONFIG_NIMBO_MEGA_USE_HTTPS"):
                result = result.replace(str(value), "[REDACTED]")
    result = re.sub(r"(?i)\b(session[_ -]?id|master[_ -]?key|pass(?:word)?|2fa|otp|token|authorization)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]", result)
    return result

def _clean_error(stderr: str) -> str:
    # Avoid displaying sensitive raw error logs, which may contain identifiers.
    s = stderr.lower()
    if "two-factor" in s or "2fa" in s or "multi-factor" in s:
        return "MEGA requires a valid current 2FA code."
    if "login" in s or "password" in s or "authentication" in s:
        return "MEGA authentication failed. Check credentials and current 2FA code."
    if "timeout" in s or "network" in s or "connection" in s or "no such host" in s:
        return "Network or MEGA service unavailable. Retry when connectivity returns."
    if "bandwidth" in s or "quota" in s:
        return "MEGA transfer quota or bandwidth limit reached."
    return "MEGA operation failed. Check network access, login, quota, and diagnostic logs."


def _startupinfo():
    if not IS_WIN:
        return None
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return info


def save_password(email: str, password: str):
    from keyring.backends.fail import Keyring as FailKeyring
    if isinstance(keyring.get_keyring(), FailKeyring):
        raise RuntimeError("No secure operating-system credential vault is available")
    keyring.set_password(APP, email, password)


def get_password(email: str) -> str:
    return keyring.get_password(APP, email) or ""
