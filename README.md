# omarchy-fingerprint-status

A small fingerprint-reader health helper for [Omarchy](https://omarchy.org). It provides JSON status for a bar indicator, plus reader tests and management menus.

It helps make stuck `fprintd` sessions visible instead of leaving you to discover them when authentication stops working.

## States

| Color | Class | Meaning |
|---|---|---|
| Gray | `disabled` | No reader was found, or `fprintd` is masked/failed |
| Green | `ready` | Reader detected and ready |
| Blue | `active` | Reader is waiting for or sensing a fingerprint |
| Red | `stuck` | Reader stayed active too long, is already claimed, or reported that it is busy |

Hover the icon for the device name, current reason, last observed use, last fingerprint issue, and click shortcuts.

## Click actions

| Input | Action |
|---|---|
| Left-click | Open a floating terminal and run an interactive `fprintd-verify` test |
| Middle-click | Clear the indicator's saved status/error history |
| Right-click | Open the fingerprint test, enrollment, replacement, reset, diagnosis, and service actions |

The actions menu can:

- **Add fingerprint** — choose a finger and enroll it with `fprintd-enroll`.
- **Replace fingerprint** — see only currently registered fingers, choose one, confirm the replacement, then enroll it again without deleting the saved print first.
- **Reset all fingerprints** — confirm deletion of every saved print for the current user. Add a new fingerprint afterward to enroll again.
- **Restart fprintd service** — run `sudo systemctl restart fprintd.service` when the reader itself is stuck.

Enrollment, replacement, fingerprint reset, testing, diagnosis, and service restart open in a floating terminal so prompts and scan progress remain visible. Successful management actions also clear stale indicator history.

The equivalent terminal commands are:

```bash
omarchy-fingerprint-status test
omarchy-fingerprint-status diagnose
omarchy-fingerprint-status clear
omarchy-fingerprint-status enroll right-index-finger
omarchy-fingerprint-status replace right-index-finger
omarchy-fingerprint-status reset-fingerprints
omarchy-fingerprint-status reset
omarchy-fingerprint-status menu
```

Valid finger names are `left-thumb`, `left-index-finger`, `left-middle-finger`,
`left-ring-finger`, `left-little-finger`, and their `right-*` equivalents.

## Omarchy Quattro

Current `main` supports the Quattro native menu for fingerprint actions. The status command
continues to print JSON suitable for a bar module:

```bash
omarchy-fingerprint-status status
```

The repository installer below configures **Waybar**. Omarchy Quattro uses its Quickshell bar,
so `./install.sh` is for Waybar setups and does not install a Quickshell widget. On Quattro,
install the helper itself with `install -Dm755 bin/omarchy-fingerprint-status ~/.local/bin/omarchy-fingerprint-status`
and configure a shell widget separately. Ben’s personal Quattro widget and bar configuration are
saved in the private [omarchy-desktop-config](https://github.com/dataforxyz/omarchy-desktop-config) repository.

The previous pre-Quattro source is preserved at
[`archive/pre-quattro-20261115`](https://github.com/dataforxyz/omarchy-fingerprint-status/tree/archive/pre-quattro-20261115).
After cloning, use `git switch --detach archive/pre-quattro-20261115` to inspect it. This is a
historical archive, not a maintained compatibility branch.

## Install

```bash
git clone https://github.com/dataforxyz/omarchy-fingerprint-status.git
cd omarchy-fingerprint-status
./install.sh
```

The installer:

- installs `omarchy-fingerprint-status` to `~/.local/bin/`
- backs up `~/.config/waybar/config.jsonc` and `style.css`
- adds the custom module to `modules-right`
- adds state colors to Waybar CSS
- restarts Waybar through `omarchy restart waybar`

No root privileges or extra Python packages are required. Runtime dependencies are Python 3, `systemd`/`busctl`, `journalctl`, `fprintd`, and Waybar.

## Configuration

The defaults are intentionally conservative:

```bash
# Seconds continuously active before blue becomes red (default: 30)
export OMARCHY_FINGERPRINT_ACTIVE_TIMEOUT=30

# Seconds a "claimed" or "busy" journal event remains red (default: 300)
export OMARCHY_FINGERPRINT_ERROR_TTL=300
```

Set these in the environment inherited by Waybar, then restart Waybar.

## How detection works

The module reads the standard `net.reactivated.Fprint` D-Bus device properties:

- `finger-needed`
- `finger-present`
- device `name`

It also checks recent `fprintd.service` journal messages for the common stuck-reader symptoms “already claimed” and “still busy with another operation.” State is saved under `$XDG_STATE_HOME/omarchy-fingerprint-status/` so elapsed active time and last use survive individual Waybar polls.

The D-Bus API does not expose a public `claimed` property. Consequently, a silent stale claim can only be identified after `fprintd` reports it as already claimed/busy, or while the reader remains in its active state.

## Development

```bash
python3 -m unittest discover -s tests -v
```

## License

MIT
