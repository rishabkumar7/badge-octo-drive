#!/usr/bin/env python3
"""Install Octo Drive onto a GitHub Universe 2026 badge connected over USB.

    python install.py                 # find the badge, deploy, verify
    python install.py --port PORT     # use a specific serial port
    python install.py --volume PATH   # badge already in mass-storage mode

The script switches the badge into USB mass-storage mode over serial, copies
octo_drive/ to apps/octo_drive/ on the BADGER volume, ejects it, waits for the
badge to come back as a serial device and checks the installed files.
Requires Python 3.8+ and mpremote (pip install mpremote).
"""

import argparse
import os
import platform
import shutil
import string
import subprocess
import sys
import time
from pathlib import Path

APP_NAME = "octo_drive"
SOURCE = Path(__file__).resolve().parent / APP_NAME
VOLUME_LABEL = "BADGER"
USB_ID = "2e8a:1101"
SYSTEM = platform.system()


def log(message):
    print(f"[octo-drive] {message}", flush=True)


def fail(message):
    print(f"[octo-drive] ERROR: {message}", file=sys.stderr, flush=True)
    sys.exit(1)


MPREMOTE = [shutil.which("mpremote")] if shutil.which("mpremote") else [sys.executable, "-m", "mpremote"]


def mpremote(*args, timeout=30, check=True):
    cmd = [*MPREMOTE, *args]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        if check:
            fail(f"timed out running: mpremote {' '.join(args)}")
        return None
    if check and result.returncode != 0:
        fail(f"mpremote {' '.join(args)} failed:\n{result.stdout}{result.stderr}")
    return result


def find_port():
    result = mpremote("devs")
    for line in result.stdout.splitlines():
        if USB_ID in line:
            return line.split()[0]
    return None


def wait_for_port(timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        port = find_port()
        if port:
            return port
        time.sleep(1)
    return None


def volume_candidates():
    if SYSTEM == "Darwin":
        yield Path("/Volumes") / VOLUME_LABEL
    elif SYSTEM == "Windows":
        for letter in string.ascii_uppercase:
            root = Path(f"{letter}:\\")
            try:
                if root.exists() and windows_label(letter) == VOLUME_LABEL:
                    yield root
            except OSError:
                pass
    else:
        user = os.environ.get("USER", "")
        for base in (f"/media/{user}", f"/run/media/{user}", "/media", "/mnt"):
            yield Path(base) / VOLUME_LABEL


def windows_label(letter):
    import ctypes

    buffer = ctypes.create_unicode_buffer(261)
    ok = ctypes.windll.kernel32.GetVolumeInformationW(f"{letter}:\\", buffer, 261, None, None, None, None, 0)
    return buffer.value if ok else None


def find_volume():
    for path in volume_candidates():
        if (path / "apps").is_dir() and (path / "main.py").is_file():
            return path
    return None


def wait_for_volume(timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        volume = find_volume()
        if volume:
            return volume
        time.sleep(1)
    return None


def ignore(_directory, names):
    return [n for n in names if n == "__pycache__" or n.startswith(".") or n.endswith(".pyc")]


def copy_app(volume):
    dest = volume / "apps" / APP_NAME
    if dest.exists():
        log(f"removing previous install at {dest}")
        shutil.rmtree(dest)
    # copyfile avoids macOS AppleDouble (._*) metadata files on the FAT volume.
    shutil.copytree(SOURCE, dest, ignore=ignore, copy_function=shutil.copyfile)
    for leftover in dest.rglob("._*"):
        leftover.unlink()
    if hasattr(os, "sync"):
        os.sync()
    files = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file())
    log(f"copied {len(files)} files to {dest}")
    return files


def eject(volume):
    log(f"ejecting {volume}")
    if SYSTEM == "Darwin":
        cmd = ["diskutil", "eject", str(volume)]
    elif SYSTEM == "Windows":
        drive = str(volume)[:2]
        script = f"(New-Object -ComObject Shell.Application).Namespace(17).ParseName('{drive}').InvokeVerb('Eject')"
        cmd = ["powershell", "-NoProfile", "-Command", script]
    else:
        cmd = ["eject", str(volume)] if shutil.which("eject") else ["umount", str(volume)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"automatic eject failed ({result.stderr.strip()}); eject the {VOLUME_LABEL} drive manually")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", help="badge serial port (default: auto-detect)")
    parser.add_argument("--volume", help="path to the BADGER volume if already in mass-storage mode")
    args = parser.parse_args()

    if not (SOURCE / "__init__.py").is_file():
        fail(f"cannot find the app at {SOURCE}")
    probe = mpremote("version", check=False)
    if probe is None or probe.returncode != 0:
        fail("mpremote is not available; run: python -m pip install mpremote")

    volume = Path(args.volume) if args.volume else find_volume()
    if volume:
        log(f"badge is already in mass-storage mode at {volume}")
    else:
        port = args.port or find_port()
        if not port:
            fail(
                "no badge found. Connect it with a data-capable USB-C cable, close Thonny, "
                "Web Serial pages and other mpremote sessions, then retry. Alternatively, "
                "double-tap the badge reset button and rerun with --volume <path to BADGER>."
            )
        log(f"found badge on {port}; switching to mass-storage mode")
        mpremote("connect", port, "exec", "import powman; powman.reset_into_msc()", timeout=15, check=False)
        volume = wait_for_volume(30)
        if not volume:
            fail(
                f"the {VOLUME_LABEL} volume did not appear. Double-tap the badge reset button "
                "(or launch the Mass Storage app), then rerun with --volume <path to BADGER>."
            )
        log(f"mounted at {volume}")

    expected = copy_app(volume)
    eject(volume)

    log("waiting for the badge to restart")
    port = wait_for_port(45)
    if not port:
        log("badge did not return as a serial device; press its reset button. Install copied but unverified.")
        return
    time.sleep(1)
    remote = f"/system/apps/{APP_NAME}"
    check = (
        "import os\n"
        "def walk(p, r=''):\n"
        "    for e in os.ilistdir(p):\n"
        "        n = r + e[0]\n"
        "        if e[1] == 0x4000: walk(p + '/' + e[0], n + '/')\n"
        "        else: print(n)\n"
        f"walk('{remote}')\n"
    )
    result = mpremote("connect", port, "exec", check, check=False)
    found = sorted(line.strip() for line in (result.stdout if result else "").splitlines() if line.strip())
    missing = [f for f in expected if f not in found]
    mpremote("connect", port, "reset", check=False)
    if missing:
        fail(f"installed files missing on the badge: {', '.join(missing)}")
    log(f"verified {len(found)} files in {remote}. Octo Drive is in the badge menu - have fun!")


if __name__ == "__main__":
    main()
