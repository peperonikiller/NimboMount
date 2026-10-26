## 0.8.5 — Safety and validation audit (development)
- Validate saved boolean settings and mount-mode parameters instead of coercing values.
- Fail closed on invalid VFS upload counters, disk-space flags, missing transfer stats, and malformed error totals.
- Direct-write mode explicitly rejects queued retry operations and reports its limitations.
- Preserve cache data; best-effort rollback when immediate cache-mode remount fails.
- Harden Transfers tab against malformed queue and progress entries.
- Ensure final unmount safety snapshot errors have an actionable message.
- Add 11 regression tests for settings, data types, direct-mode behavior, and final safety checks.
- Update Windows workflow artifact version and README cautions.
- Automated tests do not establish live remote durability or Windows readiness.

## 0.8.4 — Cache mode control (development)
- Added persistent local VFS write caching checkbox.
- Safe immediate remount when no writes are pending. Pending uploads cannot be canceled safely through rclone VFS and block switching.

## 0.8.3 — Fix false unsafe-unmount warning

- Treat an omitted `core/stats.transferring` field as no active transfers, as documented by rclone.
- Still reject malformed statistics, active transfers, queued uploads, cache errors and other unsafe states.
- Add regression tests for idle stats and unsafe states.
- No changes to cache files, stored credentials or other rclone processes.

## 0.8.2 — independent bandwidth control and MEGA error guidance

- Separate upload and download speed dropdowns; dynamically applies `upload:download` via the existing authenticated rclone Remote Control endpoint.
- Unrestricted direction (`off`) is supported independently.
- Better diagnostics for unsupported symlinks and malformed/unavailable MEGA quota replies. No implicit relogin or destructive cache cleanup.
- Updated GUI tests and backend rate-validation tests.

# Changelog

## 0.8.1 — bandwidth UI visibility fix

- Added missing bandwidth preset dropdown and Apply limit button to Transfers tab.
- Controls are visible at all times and enabled once the mount is ready.
- Show API success/failure feedback without blocking the GUI; no second rclone process.
- Preserves existing transfer safety and startup checks.

## 0.8.0 — rclone integration and safer writes

- Safer normal-unmount gate combining VFS queue, cache status and transfer status across consecutive checks.
- Remote metadata (name/size) verification of observed uploads; explicitly not an end-to-end durability guarantee.
- Retry selected or all eligible uploads through rclone VFS queue controls.
- Manual directory refresh and runtime bandwidth limiter.
- Tests for retry operations, limit validation and safety-state failure.

## 0.7.1
- Single-instance guard for the application.
- Detection of existing NimboMount-owned rclone mounts.
- Duplicate mount and drive-letter collision protection.
- Normal shutdown rejects unmount when pending uploads are present or cannot be checked.

## 0.7.0
- Dark-themed GUI layout with Drive, Transfers, Diagnostics tabs.
- Mount readiness checks and 40-second status timeout.

## 0.6.3
- Tray retry/recovery and availability indicator.

## 0.6.2
- Custom app, tray and installer icon assets.
- More selective PyInstaller collection.

## 0.6.1
- Fixed Windows `--config nul` rejection by using a dedicated empty config file.

## 0.6.0
- Two-stage MEGA login UI and pre-mount authentication validation.

All versions are development releases; live MEGA/WinFsp integration remains unverified.
