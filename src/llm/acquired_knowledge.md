# Acquired Knowledge: IntelliVue MX750 Protocol

## 1. Physical Layer
- **Baud Rate**: 115200 bps
- **Parity**: None
- **Stop Bits**: 1
- **Flow Control**: None detected.

## 2. Framing & Transport
- **Protocol**: SLIP (Serial Line Internet Protocol)
- **Framing Bytes**: 
  - `0xC0` (END)
  - `0xDB` (ESC)
  - `0xDB 0xDC` -> `0xC0`
  - `0xDB 0xDD` -> `0xDB`

## 3. Session Layer (Handshake)
- **Wakeup Sequence**: `0x11 0x01` (Session Header)
- **Extended Poll**: `0x09 0x01`
- **Assoc Req**: `0x0D 0x01`

## 4. Application Layer (Semantics)
- **F13B Packet**: Contains numeric vital signs.
- **Waveforms**: Found in specific OID ranges.
- **Checksum**: CRC-16 (Modbus/X25 variant).

## 5. Security
- Use of specific association request frames to unlock extended data.
