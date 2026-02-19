#!/bin/sh
set -e

# Fix ownership of the data volume mount point.
# Required because existing named volumes from prior runs may have root ownership.
# Docker Compose does not support per-volume user mapping.
# If the directory is already owned by appuser (999), chown is a no-op.
chown -R 999:999 /app/data

# Drop privileges and exec the CMD (which becomes PID 1).
# setpriv is part of util-linux, included in Debian slim images.
exec setpriv --reuid=999 --regid=999 --init-groups "$@"
