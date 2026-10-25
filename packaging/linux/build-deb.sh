#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
python3 -m pip install -r requirements.txt pyinstaller
python3 -m PyInstaller --clean --noconfirm --onedir --windowed --name NimboMount --collect-all keyring --collect-all PySide6 launcher.py
pkg="$(mktemp -d)"
trap 'rm -rf "$pkg"' EXIT
mkdir -p "$pkg/DEBIAN" "$pkg/opt/nimbomount" "$pkg/usr/bin" "$pkg/usr/share/applications" dist/installers
cp -a dist/NimboMount/. "$pkg/opt/nimbomount/"
cat > "$pkg/DEBIAN/control" <<CTRL
Package: nimbomount
Version: 0.2.0
Section: utils
Priority: optional
Architecture: $(dpkg --print-architecture)
Maintainer: NimboMount Project <noreply@example.invalid>
Depends: rclone, fuse3, libsecret-1-0
Description: Mount MEGA cloud drives with a system tray and transfer queue
 NimboMount uses rclone VFS and the desktop secret service for saved credentials.
CTRL
cat > "$pkg/usr/bin/nimbomount" <<'SH'
#!/bin/sh
exec /opt/nimbomount/NimboMount "$@"
SH
chmod +x "$pkg/usr/bin/nimbomount"
cat > "$pkg/usr/share/applications/nimbomount.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=NimboMount
Comment=Mount MEGA cloud storage
Exec=nimbomount
Terminal=false
Categories=Network;Utility;
DESKTOP
dpkg-deb --build --root-owner-group "$pkg" "dist/installers/nimbomount_0.2.0_$(dpkg --print-architecture).deb"
