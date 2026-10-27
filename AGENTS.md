# Agent instructions

This repository contains **Octo Drive**, an original MicroPython arcade road
racer for the GitHub Universe 2026 badge (RP2350B, USB ID `2e8a:1101`). The
badge app is the `octo_drive/` folder.

## Deploying to a connected badge

1. Check for Python 3.8+ and `mpremote`.
2. Run `mpremote devs` and find the device containing `2e8a:1101`. Never run
   serial commands in parallel.
3. From the repository root, run `python3 install.py`. Use `--port <port>` if
   more than one badge is connected.
4. The installer enters mass-storage mode, replaces only
   `apps/octo_drive/`, ejects the BADGER volume, verifies every installed file,
   and resets the badge.
5. On success, report that Octo Drive is in the badge menu. Controls are:
   Left/Right to steer, A or Up to accelerate, B or Down to brake, Menu to
   pause, and Home to quit.

If automatic mass-storage mode is unavailable, double-tap reset or open the
Mass Storage app, then run `python3 install.py --volume <BADGER path>`.

Only write to `apps/octo_drive/` on the badge. Do not modify `main.py`,
`secrets.py`, other apps, or anything under `/state`.

## Development

- Run `python3 -m unittest discover -s tests` and keep the suite passing.
- Keep badge-independent physics, traffic, scoring and track rules in
  `octo_drive/game.py`.
- Keep rendering in `octo_drive/render.py` compatible with LORES (160x120)
  and the badge runtime globals.
- Use `badge.pressed()`, `badge.held()` and `badge.ticks_delta`; do not import
  `badge`.
- Save state with `badgeware.State.load/save("octo_drive", ...)`.
- Keep the game original. Do not copy commercial game names, tracks, vehicle
  designs, code, audio or artwork.
- The Mona driver uses row 0, column 0 of `octo_drive/assets/players.png`,
  copied from Super Mona. Preserve `octo_drive/assets/LICENSE.txt` and the
  README attribution when changing or redistributing it.
- Regenerate the 24x24 icon with
  `python3 tools/build_octodrive_assets.py`; do not hand-edit it.
- `octo_drive/README.md` must begin with a one-sentence description because
  the badge menu uses it.
