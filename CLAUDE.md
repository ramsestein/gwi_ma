# gwi_ma

Toolkit to reverse engineer serial protocols of medical devices (see README.md).

## Current project: BIS VISTA → Masimo bridge

A Raspberry Pi sits between a BIS VISTA monitor and a Masimo concentrator. It
talks the BIS binary protocol (which carries the raw EEG), emulates the BIS ASCII
output towards Masimo, and forwards the EEG to a research PC. The binary protocol
is learnt by observing VitalRecorder talking to the BIS. Plan, phases and open
decisions: `docs/plan_puente_bis.md`. Read it before working on this project.

Key decisions so far:
- The two sides of the bridge are decoupled: the Pi keeps its own binary session
  with the BIS and answers Masimo from the latest values. No request-by-request
  translation.
- Learn ASCII first with a passive tap (RX-only adapters, TX unconnected) before
  touching anything.
- VitalRecorder `.vital` files are the ground truth for decoding.
- Which binary mode (Vista Binary or Legacy Binary) is still to be decided.

## Working model

- The Pi (Raspberry Pi 3B, aarch64, Python 3.13, 1 GB RAM) is driven over SSH
  from the user's Ubuntu PC. It does not run Claude. Keep code that runs on it
  dependent on the standard library and `pyserial` only.
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
