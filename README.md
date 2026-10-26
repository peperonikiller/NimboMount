> [!IMPORTANT]
> **AI-generated software disclaimer:** NimboMount was written with the assistance of artificial intelligence (AI). Its source code, security properties, and behavior have **not** been independently audited or fully validated on Windows with a live MEGA account. Review the code and test carefully before relying on it for important files. Use at your own risk.

# NimboMount

**Mount MEGA cloud storage as a drive on your desktop.**

NimboMount is an experimental, open-source-ready Python/Qt desktop application that uses [rclone](https://rclone.org/) to expose a MEGA cloud account as a mounted filesystem. The current release focuses on Windows drive letters through [WinFsp](https://winfsp.dev/); the Linux codebase is included, but Linux packaging is not a release target yet.

**Current version:** `0.8.5` · **Status:** development / unverified end-to-end · **Release format:** source code and installer build scripts (not a compiled installer).

![NimboMount app icon](nimbomount/assets/app.png)

## Features

- **MEGA account mounting:** select a free Windows drive letter and access files through Windows Explorer.
- **Two-step login UI:** email/password, then authenticator-app code for 2FA-enabled accounts. Underlying rclone authentication submits these credentials together; the first screen is **not** a server-authenticated first step.
- **Saved sessions:** reuses MEGA session data protected by the OS credential vault, avoiding repeated OTP prompts while the session remains valid. Session values are powerful account-access secrets; OTP codes are not saved.
- **System tray:** cloud-drive icon, status indicator, show/hide, connect, unmount, and exit controls. Windows may place the icon in the hidden-icons overflow.
- **Transfer view:** VFS queue, upload progress when available, cached-write status, retry attempts, cache errors, and diagnostics.
- **Retry controls:** prioritize an individual or all eligible queued uploads through rclone's supported VFS queue controls. These controls cannot resurrect files that are no longer present in rclone's queue.
- **Conservative unmount gate:** refuses a normal unmount if queue, in-flight transfer, cache, remote metadata, or health checks indicate uncertainty. Remote size checks are **not** cryptographic proof of write durability.
- **Extra rclone controls:** refresh cloud directory cache and adjust live bandwidth limits in **Transfers → Transfer bandwidth**. Select a preset and click **Apply limit** after the drive is mounted. Upload and download presets are independent and are not persisted between mounts.
- **Mount protection:** prevent multiple NimboMount GUI instances and duplicate NimboMount-owned mounts; do not indiscriminately kill unrelated rclone processes.
- **Outage handling and diagnostics:** capture sanitized rclone errors, display connection failures, and keep write cache available for recovery.

## Requirements

### End-user Windows installation

A successful build of the Windows setup executable is designed to include the NimboMount app and rclone, and install WinFsp if needed. You will need Windows 10/11 x64 and administrator approval for WinFsp installation. **No compiled setup executable is contained in this source archive.**

### Developer build on Windows

- Windows x64
- Python 3.12 (recommended for the included GitHub Actions workflow)
- [Inno Setup 6](https://jrsoftware.org/isinfo.php)
- Internet access to download pinned rclone and WinFsp dependencies during building

## Build a Windows installer

Clone the repository or download its source, open PowerShell in the repository root, and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\windows\build.ps1
```

If successful, the installer is generated at:

```text
dist\installers\NimboMount-0.8.5-windows-x64-setup.exe
```

Alternatively, choose **Actions → Windows one-click installer → Run workflow** in GitHub. Download the built executable from that workflow's artifact after a successful run. The CI workflow builds on Windows and is **not** a substitute for testing the installed application.

The installer is unsigned. Windows SmartScreen may warn about an unknown publisher. Verify downloaded third-party installers and inspect the build scripts before running.

## Run from source

For development, install Python dependencies:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m nimbomount
```

Source-mode mounting additionally requires [rclone](https://rclone.org/downloads/) on your PATH and [WinFsp](https://winfsp.dev/) installed. The exact minimum rclone version should be validated against the current backend and RC methods before using other versions.

## Connecting a MEGA account

1. Open NimboMount, enter your account email/password, and choose an unused drive letter.
2. For a new login with MEGA 2FA enabled, proceed to the authenticator screen and enter a **fresh** six-digit code.
3. Authentication is checked before the filesystem mount starts. After successful login, a reusable MEGA session can be stored in the OS vault.
4. Once the mount is ready, the drive should appear in Explorer. Check **Diagnostics** if mounting times out or rclone exits.
5. For an invalidated session, choose **Force fresh login** and authenticate again. NimboMount does not intentionally bypass MEGA's 2FA requirement.

## Transfer safety and retry behavior

NimboMount uses rclone's VFS queue, stats, and control API to display transfers and gate normal unmounting. It uses `vfs/queue-set-expiry` to make eligible pending items retry sooner; it does **not** directly edit recovery cache files. A remote metadata match is an additional check, **not a guarantee of full remote durability**. Unobserved, concurrently modified, or externally opened files might not be individually verified.

**If writes are pending or their state cannot be verified:** leave NimboMount running; do not uninstall it, delete its cache, or force-kill rclone. Failed entries no longer present in rclone's upload queue require separate recovery procedures. Power loss, forced termination, and OS shutdown can still interrupt writes.

## v0.8.5 audit notes

This release tightens type validation on persisted settings, rclone VFS statistics, transfer
error counters, and mount-mode arguments. A malformed statistics response now prevents a
normal unmount rather than allowing an uncertain write state. In direct-write mode (`off`),
queued retry is explicitly unavailable and the transfer view reports this limitation.
If a cache-mode remount fails, NimboMount attempts to restore the previous mode without
removing the local recovery cache; an unsuccessful recovery is reported for manual action.

**Important limitations:** In direct-write mode, rclone's idle transfer counters cannot
prove that an application successfully wrote every byte, and cannot retry application
write errors after the fact. Close files, check your source program's errors, and verify
critical remote copies before unmounting. Switching modes closes/remounts the filesystem,
so close open handles before using the checkbox. A full Windows/MEGA/WinFsp integration
and crash-recovery test has **not** been completed.

## Project layout

```text
.github/workflows/       Automated tests and Windows installer CI
nimbomount/             Desktop application and backend logic
nimbomount/assets/      App and tray artwork
packaging/windows/      Inno Setup and PowerShell packaging
packaging/linux/        Experimental Linux packaging script
tests/                  Python unit tests
launcher.py             Packaging entry point
requirements.txt        Python dependencies
CHANGELOG.md            Version history
CONTRIBUTING.md         Contributor guidance
SECURITY.md             Vulnerability reporting guidance
```

## Testing

```powershell
py -3.12 -m pip install -r requirements.txt
py -3.12 -m unittest discover -s tests -v
```

The automated checks mostly test isolated Python logic and mocked OS/backend behavior. **Windows mounting, MEGA 2FA, transfer recovery, WinFsp installation, and installer execution have not been fully tested end-to-end.** See [CHANGELOG.md](CHANGELOG.md) for release history.

## Security and privacy

- Treat saved MEGA session ID and master key as sensitive credentials.
- NimboMount uses the platform credential vault via `keyring` for saved secrets and does not intentionally persist authenticator codes.
- During fresh authentication, rclone may receive credentials through temporary configuration/environment mechanisms; review the implementation and restrict access to your machine.
- Logs are best-effort sanitized, **not guaranteed secret-free**. Inspect before filing public issues.
- Report security concerns using [SECURITY.md](SECURITY.md); avoid posting credentials, recovery keys, tokens, or raw sensitive logs.

## Known limitations

- Development release; no formal security audit or independent Windows/MEGA integration certification.
- Full byte-for-byte write durability or remote cryptographic verification is not implemented.
- Retry applies to rclone VFS queue entries that remain eligible for retry.
- Windows can hide notification icons in its overflow area.
- Linux installer work is deferred; Linux support is not yet validated as a packaged release.
- Installer signing and a prebuilt Windows setup download are not provided by this source archive.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) for setup and contribution conventions. Issues and pull requests are welcome, especially for reproducible Windows/WinFsp and MEGA integration tests.

## License

**No license has been selected yet.** Until a license is added, do not assume permission to reuse, redistribute, or modify this code beyond what applicable law otherwise permits. Repository maintainers should choose a license before inviting third-party code reuse.

## Acknowledgments

NimboMount integrates with independent projects [rclone](https://rclone.org/), [WinFsp](https://winfsp.dev/), [PySide6](https://doc.qt.io/qtforpython-6/), and [MEGA](https://mega.nz/). NimboMount is not an official MEGA or rclone product.

### Bandwidth limits (v0.8.5)

Open **Transfers** and choose independent **Upload** and **Download** caps, then click **Apply limit**. Limits take effect on the running rclone mount, without remounting. A cap of *Unlimited* is `off`. Rates are expressed in **bytes per second**, not bits. The limits apply only to the active mount and reset when its process restarts.

### Troubleshooting MEGA quota and symlink messages

- `symlinks not supported without the --links flag: /`: usually a nonfatal message. NimboMount does not enable link translation automatically because it changes how symbolic links are stored.
- `Statfs failed: failed to get Mega Quota: unexpected end of JSON input`: rclone could not decode MEGA's quota response. It does **not** prove a failed 2FA login. Verify whether the drive can still list/read files, check MEGA's service status and network, and retry once connectivity recovers. The app preserves cached writes and your saved session. Some WinFsp quota/free-space displays may be affected even when directory listing works.
- Avoid forced shutdown or deleting your rclone VFS cache if uploads remain pending.

### v0.8.5: false active-transfer warning

If unmounting in older versions displayed “Active-transfer statistics unavailable”,
this may have been caused by a valid `core/stats` response omitting the
optional `transferring` field while idle. v0.8.5 accepts that response while
still refusing to unmount if queued writes, active uploads, cache errors, or
malformed safety statistics are present. This is not a guarantee of remote
byte-for-byte durability; keep independent backups of important files.


## Changing local cache mode

In **Drive → Preferences**, toggle **Enable local file caching**. If the drive is mounted, NimboMount verifies that uploads have finished and prompts to unmount/remount immediately. If pending uploads or errors exist, it refuses the switch and keeps the existing mount and recovery cache. rclone does **not** support safely changing VFS cache modes in-place or canceling all cached writes without potential data loss.

Disabling caching uses `--vfs-cache-mode off`: uploads stream directly and failed uploads cannot be retried through the VFS queue; some Windows file operations may not work. This does not disable directory metadata caching or small in-memory buffers.
