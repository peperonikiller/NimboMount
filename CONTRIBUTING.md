# Contributing to NimboMount

This is an experimental Windows-first cloud mounting client. Please open an issue before starting major changes.

## Local development

1. Use Python 3.12 on Windows.
2. Run `python -m venv .venv` and activate it.
3. Run `python -m pip install -r requirements.txt`.
4. Run `python -m unittest discover -s tests -v`.
5. Start with `python launcher.py` (rclone and WinFsp are required for mounting).

## Changes

- Do not commit credentials, temporary MEGA sessions, local caches, or raw authentication logs.
- Include regression tests for authentication, mount lifecycle, or shutdown changes.
- Never terminate an rclone process without verifying that NimboMount owns it.
- Test changes involving writes, cache flush, login, and mounting on a disposable MEGA account first.
