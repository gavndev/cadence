#!/bin/sh
set -eu

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
CONFIG_DIR="${CADENCE_CONFIG:-/config}"
BUILTIN_DIR="${CADENCE_BUILTIN_LIBRARY:-}"
MUSIC_DIR="${CADENCE_MUSIC_LIBRARY:-}"

mkdir -p "$CONFIG_DIR"
if [ -n "$BUILTIN_DIR" ]; then
  mkdir -p "$BUILTIN_DIR"
fi

if [ "$(id -u)" = "0" ] && [ "$PUID" != "0" ]; then
  if ! getent group "$PGID" >/dev/null 2>&1; then
    groupadd -o -g "$PGID" cadence
  fi
  group_name="$(getent group "$PGID" | cut -d: -f1)"
  if ! getent passwd "$PUID" >/dev/null 2>&1; then
    useradd -o -u "$PUID" -g "$group_name" -d /app -s /usr/sbin/nologin cadence
  fi
  user_name="$(getent passwd "$PUID" | cut -d: -f1)"
  chown "$user_name:$group_name" "$CONFIG_DIR"
  if [ -n "$BUILTIN_DIR" ] && [ -d "$BUILTIN_DIR" ]; then
    chown "$user_name:$group_name" "$BUILTIN_DIR"
  fi
  if [ -n "$MUSIC_DIR" ] && [ -d "$MUSIC_DIR" ]; then
    chown "$user_name:$group_name" "$MUSIC_DIR"
  fi
  exec gosu "$user_name" "$@"
fi

exec "$@"
