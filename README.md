> [!IMPORTANT]
> **AI-generated software disclaimer:** NimboMount was written with the assistance of artificial intelligence (AI). Its source code, security properties, and behavior have **not** been independently audited or fully validated on Windows with a live MEGA account. Review the code and test carefully before relying on it for important files. Use at your own risk.

# NimboMount

**Mount MEGA cloud storage as a drive on your desktop.**

NimboMount is an experimental, open-source-ready Python/Qt desktop application that uses [rclone](https://rclone.org/) to expose a MEGA cloud account as a mounted filesystem. The current release focuses on Windows drive letters through [WinFsp](https://winfsp.dev/); the Linux codebase is included, but Linux packaging is not a release target yet.

**Current version:** `0.8.0` · **Status:** development / unverified end-to-end · **Release format:** source code and installer build scripts (not a compiled installer).

![NimboMount app icon](nimbomount/assets/app.png)

## Features

- **MEGA account mounting:** select a free Windows drive letter and access files through Windows Explorer.
- **Two-step login UI:** email/password, then authenticator-app code for 2FA-enabled accounts. Underlying rclone authentication submits these credentials together; the first screen is **not** a server-authenticated first step.
- **Saved sessions:** reuses MEGA session data protected by the OS credential vault, avoiding repeated OTP prompts while the session remains valid. Session values are powerful account-access secrets; OTP codes are not saved.
- **System tray:** cloud-drive icon, status indicator, show/hide, connect, unmount, and exit controls. Windows may place the icon in the hidden-icons overflow.
- **Transfer view:** VFS queue, upload progress when available, cached-write status, retry attempts, cache errors, and diagnostics.
- **Retry controls:** prioritize an individual or all eligible queued uploads through rclone's supported VFS queue controls. These controls cannot resurrect files that are no longer present in rclone's queue.
- **Conservative unmount gate:** refuses a normal unmount if queue, in-flight transfer, cache, remote metadata, or health checks indicate uncertainty. Remote size checks are **not** cryptographic proof of write durability.
- **Extra rclone controls:** refresh cloud directory cache and adjust live bandwidth limits.
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
dist\installers\NimboMount-0.8.0-windows-x64-setup.exe
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
