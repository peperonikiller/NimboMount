# NimboMount v0.7.1 — Windows-first MEGA drive mounting

**Development release.** The installer build is automated, but no Windows setup EXE has been built or end-to-end tested in this environment. The `.zip` is source plus Windows installer build tooling, not a compiled installer.

## Features

- Mount MEGA storage in Windows Explorer at a selectable free drive letter (`M:`, `N:`, etc.) with rclone + WinFsp.
- Qt desktop app, tray menu, live VFS upload queue and retry/error statistics, disk caching, graceful unmount, outage reporting, reconnection.
- First login supports MEGA email/password + authenticator 2FA. **2FA codes are never saved.**
- **MEGA session persistence (new):** on first validated login, rclone's MEGA backend can write `session_id` and `master_key` to a temporary writable rclone config. NimboMount reads both and stores the pair in the OS credential vault through `keyring`, then deletes the temporary config directory. Subsequent mounts supply the saved secrets to rclone's `session_id` / `master_key` settings, avoiding repeated 2FA prompts while the session remains valid. The saved session is effectively an account-access credential; keep Windows sign-in protected.
- Opt-in mount at Windows login (HKCU Run key) once a saved MEGA session exists. No plaintext session JSON is stored in `settings.json`.
- Password may optionally be saved via OS vault, but is not required for a successful session-based remount.

## Two-stage authentication

1. Enter your email and password, then click **Continue to sign in / Connect**.
2. If there is no saved session (or **Force fresh login** is selected), a *separate* screen asks for a fresh six-digit code from your authenticator app. Choose **Account has no 2FA** only for an account without 2FA.
3. Click **Verify & Mount**. NimboMount performs a **real rclone/MEGA authentication check** first. Only after successful authentication and session storage does it launch the filesystem mount process.
4. Later, an existing saved MEGA session is reused without a code, unless fresh login is explicitly requested. A rejected saved session is not silently replaced with password login: select Force fresh login, reenter your password, and provide a new authenticator code.

**Technical detail:** this is a two-step *interface*, not an actual server-generated challenge after password submission. The rclone MEGA backend expects the email, password and authenticator code together in one `MultiFactorLogin` call, so it cannot prove the password is valid before prompting for 2FA. The app intentionally waits for the code before sending a fresh login request. A failed code produces **Login failed** and never starts the mount. A successful sign-in is checked separately from WinFsp mount.

**Security:** OTPs are not stored. The authenticator field is masked and cleared immediately on submission. Passwords are optionally saved to the OS vault, only after successful login. Sensitive backend errors are generalized; never share raw unredacted rclone logs.

## First-time sign-in

1. Install the *built* Windows setup executable and launch NimboMount.
2. Enter email, password, and a current 2FA code (when MEGA 2FA is enabled).
3. Choose an unused drive letter; click **Connect & Mount**.
4. The first connection exchanges login credentials for MEGA session ID + master key, saved in Windows Credential Manager; the temporary OTP is discarded. Once mounted, enable **Launch and mount automatically at login**.
5. Reboot or reconnect: saved session keys are used, not an old 2FA code.

**Session expiry/revocation:** if MEGA revokes the session, NimboMount does not automatically defeat 2FA or silently re-login. An authenticated interactive re-login is necessary. Clearing Windows Credential Manager entries for `NimboMount MEGA session v1` revokes the local copy; for full remote revocation also terminate the session in your MEGA account security settings. If a fresh sign-in is required, delete the stale vault session and sign in again. Password and session master key are sensitive secrets.

**Security:** first-login rclone configuration temporarily contains an *obscured*, reversibly encoded password and the plaintext one-time code. It is destroyed with its containing temporary directory after validation. Backend session values are highly sensitive and are kept in Windows Credential Manager after validation. The mount subprocess environment necessarily contains session secrets and can potentially be inspected by same-user privileged processes. This is not a separate OAuth login. A machine compromised by malware cannot be considered secure.

**Implementation note:** secure persistence depends on rclone MEGA backend support for writing `session_id` and `master_key` into its config mapper (verified in upstream MEGA source). If an installed rclone version does not save these, NimboMount deliberately refuses to claim that persistence was configured. This needs a real account integration test on Windows.

## Build the one-click Windows installer

The **final Windows setup** bundles NimboMount, Python/PySide6, rclone and the WinFsp driver installer. End users need no Python, rclone, or separate WinFsp download. Installing WinFsp may require a Windows UAC administrator approval.

**Build option A — GitHub Actions:** push the entire project to your GitHub repository, open **Actions → Windows one-click installer → Run workflow**, and download the resulting artifact. It contains `NimboMount-0.7.1-windows-x64-setup.exe` if the Windows build succeeds.

**Build option B — local Windows PC:** install Python 3.12 and Inno Setup 6, then run PowerShell in this project directory:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1
```

When successful, find the installer at `dist\installers\NimboMount-0.7.1-windows-x64-setup.exe`. Build script downloads version-pinned rclone and WinFsp, checks SHA-256 and WinFsp signature, freezes the app with PyInstaller, and packages it with Inno Setup. Run setup once to install/upgrade the app. Installer unsigned; SmartScreen may warn.

## Limitations and safety

- **No Windows executable or installer included in this archive.** This machine is Linux; PyInstaller needs a real Windows build environment. CI workflow is provided but hasn't been executed.
- No live MEGA account login, 2FA, session restoration, driver mount, or WinFsp integration test was performed. Do not trust irreplaceable data to this development release.
- Cached writes can survive outages but do not guarantee remote durability. Do not uninstall, delete cache, or force-kill an active mount with unsynced uploads.
- If a saved MEGA session becomes invalid, you may need to remove it from Windows Credential Manager before re-authenticating interactively; automatic session-refresh flow is not yet implemented.
- Linux installer postponed; Linux source code remains available but this iteration targets Windows only.

Sources: https://rclone.org/mega/ · https://github.com/rclone/rclone/blob/master/backend/mega/mega.go · https://winfsp.dev/


### Windows build download fix (October 2026)
WinFsp 2026 Beta5 publishes `winfsp-2.2.26286.msi` (not the earlier `26194` filename).
The Windows build script checks its official SHA-256 hash, reuses verified downloads,
and retries interrupted downloads with `curl.exe`. If GitHub downloads remain blocked,
obtain the file from the official [WinFsp Beta5 release](https://github.com/winfsp/winfsp/releases/tag/v2.2B5),
place it at `build/windows-deps/winfsp-2.2.26286.msi`, and rerun the script.
The build still requires Windows, Python, and Inno Setup 6.

## Earlier changes: Diagnostics and 2FA recovery

- Enter a fresh **six-digit authenticator-app code** with your account password; entering a code now forces a fresh MEGA login rather than silently reusing a saved session. Alternatively select **Force fresh login**. Neither action saves the 2FA code.
- **Forget saved MEGA session** deletes the stored session secrets from the OS credential vault (does not revoke the remote MEGA session).
- **Mount diagnostics** shows the last 40 captured rclone stderr lines, including the exit code; use **Show rclone errors** to refresh. Capturing is continuous to avoid blocked pipe deadlocks. Sensitive configured values and conventional key=value secrets are redacted, but manually review diagnostics for private information before sharing.
- The app no longer silently discards rclone errors when the process exits.
- Note: An app error during validation may still appear as a summarized authentication/network error, rather than raw backend output.
- Run the installer build from the project folder with `powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1`; it now locates Inno Setup in `%LOCALAPPDATA%\Programs\Inno Setup 6` as well as Program Files. A Windows build remains required to produce the EXE.

## v0.6.1 — Windows mount fix

Fixes `CRITICAL: --config: Failed to set "nul" as config path`: Windows reserves
`NUL` as a device name and current rclone will not accept it for `--config`.
NimboMount now creates an empty, dedicated configuration file at
`%APPDATA%\NimboMount\empty-mount.conf` and supplies its path to rclone.
The file contains **no** credentials: mounted sessions are passed through
process environment variables. The file is reset to empty before every mount,
preventing loading of the user's unrelated rclone accounts.

Build the updated Windows installer on Windows from the extracted project:
`powershell -ExecutionPolicy Bypass -File .\packaging\windows\build.ps1`.
The `.zip` contains source/build tooling, not a prebuilt Windows `.exe`.


## v0.6.2: Windows icons and tray

NimboMount now ships with custom app and small-format system-tray artwork under `nimbomount/assets/`. The main window, taskbar app, installer, and uninstaller use the application icon. The tray icon shows a colored connection-status dot and exposes status, connect, unmount, and exit actions. Left-click or double-click the tray icon to show the window. Closing the window hides it to the tray without unmounting.

**Windows tray visibility:** NimboMount can publish an icon to the Windows notification area, but cannot force Windows to pin it in the visible taskbar. On Windows 11, open Settings → Personalization → Taskbar → Other system tray icons (or drag the icon from the tray overflow).

**Build:** Run `packaging\windows\build.ps1`. The build bundles icon assets, embeds the `.ico` into the executable, and avoids `--collect-all PySide6` (which previously pulled in unnecessary Qt development files). This release still needs end-to-end Windows installer and MEGA mount testing.

## v0.6.3 — Tray visibility recovery

On startup and every three seconds, NimboMount checks whether the OS tray is ready and republishes the icon if needed. This helps when Windows Explorer starts after NimboMount or restarts. The main window displays a tray availability indicator so you can distinguish an unavailable tray from Windows hiding the icon in the overflow menu (`^`). Windows controls pinned tray icon visibility; apps cannot force pinning.

If the indicator says active but you do not see the icon, open the taskbar's hidden icon menu or Windows Settings → Personalization → Taskbar → Other system tray icons and enable NimboMount. Exit any running NimboMount instance before installing/relaunching the newer version.

Rebuild with `powershell -ExecutionPolicy Bypass -File .\packaging\windows\build.ps1`. The ZIP is source/build tooling, **not** an already compiled Windows installer.

## v0.7.0 — Desktop UI refresh and mount-start readiness fix

The new three-tab layout separates **Drive** (sign-in, mount target, connection controls), **Transfers** (VFS cache and upload queue), and **Diagnostics** (sanitized rclone errors). A consistent dark palette, grouped settings, prominent connection status, indeterminate mount activity bar, and scrollable drive settings make the interface easier to use on smaller screens. Existing tray controls and cloud-drive artwork remain included.

**Root cause of the previously stuck “Mount starting” label:** the GUI's `_worker("probe", ...)` path deliberately suppressed successful probe signals, so even a successful remote connectivity check could not update the status to Online. The prior code also did not distinguish a running rclone process from a registered WinFsp drive. This release fixes success/failure signal dispatch and adds an explicit OS filesystem-readiness probe. On Windows the selected drive letter must actually appear in `GetLogicalDrives`; on Linux the target must become a mount point. The readiness phase runs asynchronously, checks once per second, and reports a 40-second deadline instead of displaying “Mount starting” indefinitely. A timeout preserves the rclone process and its cache for inspection; use the Diagnostics tab and avoid force-closing during pending writes. This **fixes the identified GUI logic bug** but does not guarantee every MEGA/WinFsp installation can mount successfully.

**Testing:** Source compiles and unit tests cover the probe-signal regression and mount readiness using mocked OS state. Live GUI, WinFsp, MEGA/2FA, and installer tests must still be run on Windows. The ZIP is source and build tooling, **not** a compiled Windows setup executable.

Build from the project directory in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\windows\build.ps1
```

Expected output on successful compilation: `dist\installers\NimboMount-0.7.0-windows-x64-setup.exe`.


## v0.7.1 — Single mount ownership and safe shutdown

- A per-user Qt lock prevents a second NimboMount GUI instance (including while hidden in the tray). It is released on normal exit and stale locks from dead processes can be reclaimed.
- Before starting a mount, NimboMount looks for a running **NimboMount-owned** rclone mount by matching both the private rclone remote and cache directory in process arguments. It refuses a second mount and reports the existing PID; it does **not** kill or take over the orphan. Unrelated rclone instances are not affected.
- Unmount/Exit checks rclone's VFS upload queue. If uploads are queued, or the queue cannot be checked, unmount is blocked to preserve cached writes. When clear, rclone receives a termination request and a bounded wait; it is never force-killed. Closing the window still hides it to the tray.
- On crash or power loss, re-open NimboMount, inspect diagnostics and pending cache, and clear/stop a confirmed orphan **only after** checking its writes have finished. Never manually erase the VFS cache to repair an orphan.
- These safeguards do not protect against OS shutdown/forced process termination or all in-flight writes; safe removal still requires verifying cloud upload completion. Windows integration tests are still outstanding.

Build with `powershell -ExecutionPolicy Bypass -File .\packaging\windows\build.ps1` on Windows. This archive is the source/build kit, not a compiled installer.
