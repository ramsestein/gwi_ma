# gwi_ma

Toolkit to reverse engineer serial protocols of medical devices (see README.md).

## Current project: BIS VISTA → Masimo bridge

A Raspberry Pi acts as a translator with three USB-RS232 ports: port 1 talks the
BIS binary protocol (which carries the raw EEG) as the BIS host; port 2 emulates
the BIS ASCII output towards a Masimo concentrator; port 3 emulates a BIS in Vista
Binary so the research PCs keep their current VitalRecorder setup (decided;
Vista Binary vs Legacy Binary still open). Captures are done on a Windows PC with
VitalRecorder and Wireshark + USBPcap, and the translator is prototyped on that
PC (BIS <-> PC <-> Masimo) before moving to the Pi. Plan, phases and open
decisions: `docs/plan_puente_bis.md`. Windows setup: `docs/preparar_windows.md`.
Read them before working on this project.

Key decisions so far:
- The Pi is the only host of the BIS. Ports 2 and 3 are served from the Pi's
  latest data; no request-by-request translation, so Masimo never depends on the
  research PC.
- Protocols are learnt with only a PC and the BIS (no Masimo yet): ASCII by
  logging what the BIS emits, binary by capturing VitalRecorder's USB traffic.
- VitalRecorder `.vital` files are the ground truth for decoding.
- Which binary mode (Vista Binary or Legacy Binary) is still to be decided.
- Masimo acceptance of the emulated ASCII is validated only once a Masimo unit
  is available.

## Working model

- The Pi (Raspberry Pi 3B, aarch64, Python 3.13, 1 GB RAM) is driven over SSH
  from the user's Ubuntu PC. It does not run Claude.
- Capture and translator code must run on both Windows (COM ports) and the Pi
  (/dev/tty*), with only the standard library and `pyserial`.
- Cloud sessions cannot reach the Pi. Write code here, push to `main`, and the
  user pulls and runs it, pasting the output back.
- Commit straight to `main`.

## Rules

- This repository is public. Never commit captures, `.vital` files, patient data,
  IP addresses or hospital names. `dumps/` and `capture_*` are gitignored.
- Run tools from the repo root as modules: `python -m src.<layer>.<tool>`.
- Imports between packages are absolute (`from src.analysis import protocol_manager`).
- Tests: `python -m pytest -q tests`. New tools get unittest-style tests, with
  pty or synthetic data instead of real ports.
