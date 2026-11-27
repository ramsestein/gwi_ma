"""
Check that a machine is ready for the BIS translator work.

On the Windows capture PC it checks Python, the packages, git, Wireshark,
USBPcap, VitalRecorder and the serial adapters. On the Pi it checks Python,
pyserial, the serial adapters and access to them (group dialout).

Paste the output back when asking for help. Exit code 1 if something required
is missing.

Usage:
  python -m src.utils.check_setup [--role pc|pi]
"""
import argparse
import importlib.metadata
import os
import platform
import shutil
import sys
from typing import Callable, Dict, Iterable, List, Optional, Tuple

OK, WARN, FAIL = "OK", "WARN", "FAIL"
Result = Tuple[str, str]

KNOWN_CHIPS = {
    0x0403: "FTDI",
    0x067B: "Prolific PL2303",
    0x0557: "ATEN (Prolific)",
    0x10C4: "Silicon Labs CP210x",
    0x1A86: "WCH CH340/CH341",
}

PC_PACKAGES = [("pyserial", True), ("numpy", True), ("scipy", True), ("matplotlib", True), ("vitaldb", False)]
PI_PACKAGES = [("pyserial", True)]


def check_python(version_info=sys.version_info) -> List[Result]:
    text = f"Python {version_info[0]}.{version_info[1]}.{version_info[2]}"
    if tuple(version_info[:2]) < (3, 9):
        return [(FAIL, f"{text}: need 3.9 or newer")]
    return [(OK, text)]


def check_repo(cwd: str, exists: Callable[[str], bool] = os.path.exists) -> List[Result]:
    if exists(os.path.join(cwd, "src", "acquisition", "serial_tap.py")):
        return [(OK, f"gwi_ma repository at {cwd}")]
    return [(FAIL, f"{cwd} is not the gwi_ma folder: run the tools from the repository root")]


def check_packages(role: str, version_of: Callable[[str], str] = importlib.metadata.version) -> List[Result]:
    results = []
    for name, required in (PC_PACKAGES if role == "pc" else PI_PACKAGES):
        try:
            results.append((OK, f"{name} {version_of(name)}"))
        except importlib.metadata.PackageNotFoundError:
            if required:
                results.append((FAIL, f"{name} not installed: python -m pip install {name}"))
            else:
                results.append((WARN, f"{name} not installed (needed later to read .vital files): "
                                      f"python -m pip install {name}"))
    return results


def check_git(which: Callable[[str], Optional[str]] = shutil.which) -> List[Result]:
    path = which("git")
    return [(OK, f"git at {path}")] if path else [(WARN, "git not found: needed to update the repository")]


def check_ports(ports: Iterable) -> List[Result]:
    usb = [p for p in ports if getattr(p, "vid", None) is not None]
    if not usb:
        return [(WARN, "no USB-serial adapter connected (plug it in to check it)")]
    results = []
    for p in usb:
        chip = KNOWN_CHIPS.get(p.vid, "unknown chip")
        serial_number = getattr(p, "serial_number", None) or "none"
        results.append((OK, f"{p.device}: {p.vid:04X}:{p.pid:04X} {chip}, serial {serial_number}, "
                            f"{getattr(p, 'description', '') or ''}".rstrip(", ")))
        if p.vid == 0x067B:
            results.append((WARN, f"{p.device}: Prolific adapters with old or counterfeit chips stop working "
                                  f"with recent Windows drivers; if it shows a warning in Device Manager, "
                                  f"use an FTDI adapter"))
    return results


def _find_dir(roots: List[str], name_parts: Tuple[str, ...], isdir, listdir) -> Optional[str]:
    for root in roots:
        if not root or not isdir(root):
            continue
        try:
            entries = listdir(root)
        except OSError:
            continue
        for entry in entries:
            low = entry.lower().replace(" ", "")
            if all(part in low for part in name_parts) and isdir(os.path.join(root, entry)):
                return os.path.join(root, entry)
    return None


def check_windows_apps(environ: Dict[str, str], isfile=os.path.isfile, isdir=os.path.isdir,
                       listdir=os.listdir) -> List[Result]:
    results = []
    program_files = [environ.get("ProgramFiles", r"C:\Program Files"),
                     environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")]
    local_programs = os.path.join(environ.get("LOCALAPPDATA", ""), "Programs") if environ.get("LOCALAPPDATA") else ""

    wireshark = next((os.path.join(pf, "Wireshark") for pf in program_files
                      if isfile(os.path.join(pf, "Wireshark", "Wireshark.exe"))), None)
    if wireshark:
        results.append((OK, f"Wireshark at {wireshark}"))
    else:
        results.append((FAIL, "Wireshark not found: install it from wireshark.org (tick USBPcap in the installer)"))

    usbpcap_paths = [os.path.join(pf, "USBPcap", "USBPcapCMD.exe") for pf in program_files]
    if wireshark:
        usbpcap_paths.append(os.path.join(wireshark, "extcap", "USBPcapCMD.exe"))
    usbpcap = next((p for p in usbpcap_paths if isfile(p)), None)
    if usbpcap:
        results.append((OK, f"USBPcap at {usbpcap}"))
    else:
        results.append((FAIL, "USBPcap not found: re-run the Wireshark installer and tick USBPcap, then reboot"))

    vital = _find_dir(program_files + [local_programs], ("vital", "recorder"), isdir, listdir)
    if vital:
        results.append((OK, f"VitalRecorder at {vital}"))
    else:
        results.append((WARN, "VitalRecorder not found in the usual folders (fine if it is installed elsewhere)"))
    return results


def check_linux_serial_access(group_names: Iterable[str], is_root: bool) -> List[Result]:
    if is_root or "dialout" in group_names:
        return [(OK, "access to serial ports (group dialout)")]
    return [(FAIL, "no access to serial ports: sudo usermod -aG dialout $USER, then log in again")]


def _linux_groups() -> List[str]:
    import grp
    return [grp.getgrgid(g).gr_name for g in os.getgroups()]


def default_role(system: str, machine: str) -> str:
    return "pi" if system == "Linux" and machine in ("aarch64", "armv7l", "armv6l") else "pc"


def run_checks(role: str) -> List[Result]:
    from serial.tools import list_ports  # imported here so a missing pyserial is reported, not a crash

    system = platform.system()
    results = [(OK, f"{system} {platform.release()} ({platform.machine()}), role {role}")]
    results += check_python()
    results += check_repo(os.getcwd())
    results += check_packages(role)
    results += check_git()
    if system == "Windows" and role == "pc":
        results += check_windows_apps(dict(os.environ))
    if system == "Linux":
        results += check_linux_serial_access(_linux_groups(), os.geteuid() == 0)
    results += check_ports(list_ports.comports())
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check that this machine is ready for the BIS translator work.")
    parser.add_argument("--role", choices=["pc", "pi"],
                        help="pc = Windows capture/analysis PC, pi = Raspberry Pi (default: guessed)")
    args = parser.parse_args(argv)
    role = args.role or default_role(platform.system(), platform.machine())

    try:
        results = run_checks(role)
    except ImportError:
        print("[FAIL] pyserial not installed: python -m pip install pyserial")
        return 1

    for level, message in results:
        print(f"[{level}] {message}")
    failures = sum(1 for level, _ in results if level == FAIL)
    print(f"\n{failures} problem(s) to fix." if failures else "\nAll required checks passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
