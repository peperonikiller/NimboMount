# Security Policy

> [!IMPORTANT]
> **AI-assisted development notice:** NimboMount's code was developed with AI assistance and has not undergone an independent security audit or complete end-to-end Windows/MEGA testing. NimboMount is experimental software. Do not rely on it as the only copy of important files.

## Supported versions

NimboMount is currently a development project. Security fixes are targeted at the latest source release; previous releases are not maintained.

| Version | Security support |
| --- | --- |
| `0.8.x` (latest development branch) | Best-effort fixes; no guaranteed response or release schedule |
| `0.7.x` and older | Not supported; upgrade to the latest version |

No version is currently certified, security-audited, or recommended for high-risk or business-critical use.

## Report a vulnerability privately

**Do not disclose exploitable details or secrets in a public GitHub issue or discussion.**

1. Open the repository's **Security** tab and use **Report a vulnerability** if GitHub private vulnerability reporting is enabled.
2. If that option is unavailable, contact the repository maintainer through a *private* contact method explicitly provided on the repository profile or project page. Do not assume public issues or discussions are private.
3. If no private reporting channel is available, avoid sharing exploit details publicly until a secure contact channel has been established.

When reporting, include (as safely as possible):

- The affected NimboMount version or commit, Windows version, and rclone/WinFsp versions.
- A concise description of the issue, its impact, and reproducible steps.
- Whether it requires login, local access, a malicious file, or a network attacker.
- Sanitized diagnostics and an explanation of which sensitive values were removed.
- A suggested mitigation, if known.

**Never include** MEGA passwords, 2FA recovery codes or one-time codes, session IDs, master keys, rclone configuration secrets, RC authentication tokens, or unredacted logs. Avoid attaching real private files or uploading complete VFS caches.

There is no guaranteed acknowledgement, triage, or remediation timeline at this development stage. Please allow the maintainer time to evaluate and coordinate a fix before publishing sensitive technical details.

## Security boundaries and important risks

### MEGA authentication and saved sessions

- NimboMount relies on rclone's MEGA backend for authentication and cloud operations.
- Authenticator-app one-time codes must not be persisted or replayed for unattended startup.
- Saved MEGA session IDs and master keys are **account-access secrets**, even if the password and 2FA code are not present. Treat anyone who obtains this material as potentially having access to the account.
- NimboMount aims to store saved credentials through the operating system's credential vault. Local malware or an attacker with access to the unlocked user account may still be able to access them. The vault is not a substitute for endpoint security.
- Revoke affected MEGA sessions, change credentials where appropriate, and sign in again if you suspect a session was exposed.

### Mounted files, caching, and data loss

- An apparently successful local write is **not proof** the file has reached MEGA. rclone's VFS write cache can hold pending or failed uploads.
- NimboMount's queue, retry, remote size/metadata checks, and conservative unmount gate provide safety signals, **not cryptographic end-to-end verification or a guarantee of durable remote storage**.
- Network loss, forced process termination, power failures, insufficient disk space, and cloud-service errors can leave writes pending or incomplete.
- Do not delete the local VFS cache, forcibly terminate NimboMount-owned rclone processes, or uninstall while writes are pending. Keep an independent backup of important files.
- Before relying on a cloud copy, verify the contents independently, preferably by downloading and comparing hashes where feasible.

### Local rclone control interface

- NimboMount uses rclone's remote-control interface for queue status and operations. This interface must remain bound to a local address and protected by access controls; **do not expose it to public networks**.
- Restrict access to diagnostic logs and application settings. Logs can contain filenames, directory structure, account identifiers, or secrets not caught by automated redaction.
- Never paste full diagnostic logs into public issues without manually checking and sanitizing them first.

### Dependencies and installer trust

- NimboMount uses third-party components, including **rclone**, **WinFsp**, **PySide6**, and Python libraries. Vulnerabilities may originate in those dependencies.
- Build from a trusted checkout and review the PowerShell installer-building scripts before execution. The build may download third-party binaries.
- Development builds and generated installers are currently unsigned; unsigned artifacts are not independently authenticated by a publisher signature. Prefer builds from a trusted repository and verify release checksums if published.
- Do not disable Windows security protections just to install or run NimboMount.

## Vulnerabilities and issues in scope

Examples of security issues worth reporting privately include credential or session-key leakage; authentication bypass; remote-control API exposure; unsafe filesystem handling or mount permissions; uncontrolled process execution; insecure updates or dependency downloads; privilege escalation; and crashes or data-corruption flaws that create a security impact.

For nonsecurity bugs such as cosmetic UI defects, ordinary connection failures, or feature requests, open a regular GitHub issue **after removing any private information**.

## Security updates

Security-related fixes, when available, will be documented in the project's changelog or GitHub releases. Users should review updates carefully and retain backups before upgrading.

This policy applies to the NimboMount project as distributed by its repository maintainer, not to MEGA, rclone, WinFsp, or other upstream projects. Report vulnerabilities in upstream components to their respective maintainers as well.
