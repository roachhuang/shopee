#!/usr/bin/env bash
# Install the boost + session-check user timers, pointing them at this repo.
# Re-run after moving the repo; safe to run repeatedly.
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
dest="$HOME/.config/systemd/user"

if [[ ! -x "$repo/.venv/bin/python" ]]; then
    echo "No venv at $repo/.venv -- run 'uv sync' in $repo first." >&2
    exit 1
fi

mkdir -p "$dest"
for unit in shopee-boost.service shopee-boost.timer \
            shopee-session-check.service shopee-session-check.timer; do
    sed "s|@REPO@|$repo|g" "$repo/systemd/$unit" > "$dest/$unit"
done

systemctl --user daemon-reload
systemctl --user enable --now shopee-boost.timer shopee-session-check.timer
systemctl --user list-timers 'shopee-*'
