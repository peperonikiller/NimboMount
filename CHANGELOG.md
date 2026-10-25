# Changelog

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
