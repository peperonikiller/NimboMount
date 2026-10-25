# Security policy

NimboMount v0.7.1 is a development release and has not completed live Windows/MEGA integration testing. Do not use it for irreplaceable files.

**Do not submit credentials, session IDs, master keys, authenticator codes, or raw logs containing secrets in public issues.**

If you find a security issue, contact the repository maintainer privately through a contact method they choose to publish; do not post exploit details in public issues.

Saved MEGA session material grants account access and is stored through the host OS credential vault. Normal shutdown aims to protect queued writes, but an empty queue is not proof of durable remote storage.
