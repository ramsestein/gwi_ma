# VitalParser Tool Reference
Use these tools by outputting the corresponding JSON function call.

## Connection Tools
- **serial_scanner**
  - *Description*: Lists available COM ports.
  - *Arguments*: "" (empty string)
- **baud_detector**
  - *Description*: Statistically detects baud rate.
  - *Arguments*: "<port>" (e.g., "COM3")
- **physical_forensics**
  - *Description*: Checks for inverted logic/TTL levels.
  - *Arguments*: "<port>"
- **handshake_replay**
  - *Description*: Replays a wake-up sequence defined in a config.
  - *Arguments*: "<port> <baud>" (e.g., "COM3 115200")

## Acquisition Tools
- **data_logger**
  - *Description*: Logs binary data to file.
  - *Arguments*: "<port> <baud>"
- **serial_ports**
  - *Description*: Lists USB-serial adapters (VID:PID, serial number, USB socket) and prints udev rules for fixed names.
  - *Arguments*: "" or "--udev ROLE=DEVICE [ROLE=DEVICE ...]"
- **serial_loopback**
  - *Description*: Loopback test between two ports joined by a null-modem cable: lost/corrupted frames and latency.
  - *Arguments*: "<port_a> <port_b> --baud 57600 [--sweep 9600,57600] [--both]"
- **serial_tap** (interactive, run it manually, not as a tool call)
  - *Description*: Timestamped capture of one or two ports: passive tap (never writes) or --bridge (forwards between them). Writes `<prefix>_timeline.csv`, `<prefix>_<NAME>.bin`, `<prefix>_summary.json`.
  - *Arguments*: "<port> [port2] --baud N [--names BIS,MASIMO] [--bridge] [--prefix dumps/x]"
- **pcap_extractor**
  - *Description*: Extracts serial stream from USBPcap file.
  - *Arguments*: "<pcap_file>"
- **usbpcap_conversation**
  - *Description*: Rebuilds the ordered, timestamped conversation (host->device / device->host) between a PC app and a USB-serial adapter from a USBPcap capture, and decodes the line settings the app used (baud, 8N1, DTR/RTS, flow control). Strips FTDI status bytes. Writes `<prefix>_timeline.csv`, `<prefix>_H2D.bin`, `<prefix>_D2H.bin`, `<prefix>_summary.json`. Use this instead of pcap_extractor for request/response protocols.
  - *Arguments*: "<pcap_file> [prefix] [--device BUS:ADDR] [--ftdi auto|on|off] [--gap-ms 5] [--show 40]"

## Framing Tools
- **framing_scanner**
  - *Description*: Detects SLIP, HDLC, ASCII, MIB signatures.
  - *Arguments*: "<capture_file>"
- **packet_finder**
  - *Description*: Finds fixed-header packets.
  - *Arguments*: "<capture_file>"
- **checksum_cracker**
  - *Description*: Brute-forces CRC algorithms.
  - *Arguments*: "<capture_file> <packet_size>"

## Analysis Tools
- **stat_analyzer**
  - *Description*: Autocorrelation to find periodic packet size.
  - *Arguments*: "<capture_file> <max_lag>" (default lag: 200)
- **ai_explorer**
  - *Description*: AI hypothesis engine for field meaning.
  - *Arguments*: "<capture_file> <packet_size>"
- **semantic_explorer**
  - *Description*: Visualizes value ranges and types.
  - *Arguments*: "<capture_file> <packet_size>"
- **entropy_analyzer**
  - *Description*: Heatmap of information density.
  - *Arguments*: "<capture_file> <packet_size>"
- **lut_detector**
  - *Description*: Finds lookup tables/enums.
  - *Arguments*: "<capture_file> <packet_size>"

## Signal Tools
- **visualizer**
  - *Description*: Plots raw byte values.
  - *Arguments*: "<capture_file>"
- **waveform_profiler**
  - *Description*: Profiles waveform data streams.
  - *Arguments*: "<capture_file> <packet_size> <offset>"
- **fft_analyzer**
  - *Description*: FFT frequency analysis.
  - *Arguments*: "<capture_file> <packet_size> <offset>"

## Active Simulation
- **command_fuzzer**
  - *Description*: Fuzzes commands to find reactions.
  - *Arguments*: "<port> <baud>"
- **session_fuzzer**
  - *Description*: Fuzzes session state.
  - *Arguments*: "<port> <baud>"

## Advanced Security
- **crypto_scanner**
  - *Description*: Detects encryption/compression.
  - *Arguments*: "<capture_file> <packet_size>"
- **complex_protocol**
  - *Description*: Analyzes multiplexing.
  - *Arguments*: "<capture_file> <packet_size>"

## Knowledge & Web
- **web_search**
  - *Description*: Searches DuckDuckGo.
  - *Arguments*: "<query>"
- **web_read**
  - *Description*: Reads text from a URL.
  - *Arguments*: "<url>"
- **update_knowledge**
  - *Description*: Saves finding to long-term memory.
  - *Arguments*: "<fact_string>"
- **generate_protocol**
  - *Description*: Saves final protocol definition to `results/`.
  - *Arguments*: "<filename> <json_string>"

