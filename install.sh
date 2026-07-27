#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
BIN_DIR="${HOME}/.local/bin"
WAYBAR_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/waybar"
CONFIG="$WAYBAR_DIR/config.jsonc"
STYLE="$WAYBAR_DIR/style.css"

[[ -f "$CONFIG" ]] || { echo "Waybar config not found: $CONFIG" >&2; exit 1; }
[[ -f "$STYLE" ]] || { echo "Waybar stylesheet not found: $STYLE" >&2; exit 1; }
command -v busctl >/dev/null || { echo "busctl is required" >&2; exit 1; }

mkdir -p "$BIN_DIR"
install -m 0755 "$ROOT/bin/omarchy-fingerprint-status" "$BIN_DIR/omarchy-fingerprint-status"

timestamp=$(date +%s)
cp -a "$CONFIG" "$CONFIG.bak.$timestamp"
cp -a "$STYLE" "$STYLE.bak.$timestamp"

python3 - "$CONFIG" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
module = 'custom/fingerprint-status'
block = '''  "custom/fingerprint-status": {
    "exec": "$HOME/.local/bin/omarchy-fingerprint-status",
    "return-type": "json",
    "interval": 2,
    "tooltip": true,
    "on-click-right": "$HOME/.local/bin/omarchy-fingerprint-status diagnose"
  }'''

if f'"{module}"' not in text.split('"custom/fingerprint-status":', 1)[0]:
    marker = '"modules-right": ['
    start = text.find(marker)
    if start < 0:
        raise SystemExit('Could not find modules-right in Waybar config')
    insert = start + len(marker)
    text = text[:insert] + f'\n    "{module}",' + text[insert:]

if '"custom/fingerprint-status":' not in text:
    end = text.rfind('}')
    if end < 0:
        raise SystemExit('Waybar config does not have a closing brace')
    before = text[:end].rstrip()
    comma = '' if before.endswith('{') else ','
    text = before + comma + '\n' + block + '\n' + text[end:]

path.write_text(text)
PY

if ! grep -q 'omarchy-fingerprint-status: begin' "$STYLE"; then
  cat >> "$STYLE" <<'CSS'

/* omarchy-fingerprint-status: begin */
#custom-fingerprint-status {
  min-width: 12px;
  margin: 0 7.5px;
  font-weight: bold;
}

#custom-fingerprint-status.disabled {
  color: #8b949e;
  opacity: 0.55;
}

#custom-fingerprint-status.ready {
  color: #7ee787;
}

#custom-fingerprint-status.active {
  color: #58a6ff;
}

#custom-fingerprint-status.stuck {
  color: #ff7b72;
}
/* omarchy-fingerprint-status: end */
CSS
fi

if command -v omarchy >/dev/null 2>&1; then
  omarchy restart waybar
elif command -v pkill >/dev/null 2>&1; then
  pkill -SIGUSR2 waybar 2>/dev/null || true
fi

echo "Installed omarchy-fingerprint-status. Backups:"
echo "  $CONFIG.bak.$timestamp"
echo "  $STYLE.bak.$timestamp"
