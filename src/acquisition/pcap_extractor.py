"""
Generic USBPcap Serial Extractor

Parses a .pcapng file (from Wireshark/USBPcap) and extracts the data payload
from USB Bulk transfers. It automatically identifies the most active OUT (PC->Device)
and IN (Device->PC) endpoints to reconstruct the serial stream.

Usage:
    python src/pcap_extractor.py <capture.pcapng> [output_prefix]
"""
import struct
import sys
import os

def parse_usbpcap_header(data):
    """Parse a USBPcap packet header."""
    if len(data) < 27:
        return None
    
    header_len = struct.unpack_from('<H', data, 0)[0]
    info = data[16]
    endpoint = data[21]
    transfer_type = data[22] # 1=ISO, 2=INT/CTRL, 3=BULK
    data_length = struct.unpack_from('<I', data, 23)[0]

    return {
        'header_len': header_len,
        'info': info,
        'endpoint': endpoint,
        'transfer_type': transfer_type,
        'data_length': data_length,
        'direction': 'IN' if (info & 1) else 'OUT'
    }

def analyze_pcapng(filepath):
    print(f"Loading {filepath}...")
    with open(filepath, 'rb') as f:
        raw = f.read()

    pos = 0
    packets = []
    
    # Simple Block Parser
    while pos < len(raw) - 12:
        block_type = struct.unpack_from('<I', raw, pos)[0]
        block_len = struct.unpack_from('<I', raw, pos + 4)[0]
        
        if block_len < 12 or pos + block_len > len(raw):
            break
            
        # Enhanced Packet Block (EPB) = 0x00000006
        if block_type == 6:
            cap_len = struct.unpack_from('<I', raw, pos + 20)[0]
            pkt_data = raw[pos + 28 : pos + 28 + cap_len]
            
            hdr = parse_usbpcap_header(pkt_data)
            if hdr and hdr['data_length'] > 0:
                # Extract payload
                payload = pkt_data[hdr['header_len'] : hdr['header_len'] + hdr['data_length']]
                if len(payload) > 0:
                    hdr['payload'] = payload
                    packets.append(hdr)

        pos += block_len
        if pos % 4 != 0: pos += 4 - (pos % 4) # Padding

    print(f"Found {len(packets)} packets with payload.")
    return packets

def extract_streams(packets, out_prefix):
    # Statistics per endpoint
    eps = {}
    for p in packets:
        ep = p['endpoint']
        d = p['direction']
        t = p['transfer_type']
        label = f"EP_{ep:02X}_{d}"
        
        if label not in eps:
            eps[label] = {'count':0, 'bytes':0, 'type':t, 'payloads': []}
        
        eps[label]['count'] += 1
        eps[label]['bytes'] += len(p['payload'])
        eps[label]['payloads'].append(p['payload'])

    print("\nEndpoint Statistics:")
    for label, stats in sorted(eps.items()):
        ttype = {1:'ISO', 2:'CTRL', 3:'BULK'}.get(stats['type'], 'UNK')
        print(f"  {label} ({ttype}): {stats['count']} packets, {stats['bytes']} bytes")

    # Filter for BULK transfers (usually serial data)
    bulk_eps = [k for k,v in eps.items() if v['type'] == 3 or (v['type']==2 and v['bytes']>100)]
    
    if not bulk_eps:
        print("No obvious BULK data endpoints found.")
        return

    # Extract best candidates
    # Usually lowest IN endpoint and lowest OUT endpoint are the data pipes
    print("\nExtracting streams:")
    
    for label in bulk_eps:
        filename = f"{out_prefix}_{label}.bin"
        data = b''.join(eps[label]['payloads'])
        with open(filename, 'wb') as f:
            f.write(data)
        print(f"  -> {filename} ({len(data)} bytes)")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python src/pcap_extractor.py <file.pcapng> [output_prefix]")
        sys.exit(1)
        
    pcap_file = sys.argv[1]
    prefix = sys.argv[2] if len(sys.argv) > 2 else "dumps/extracted"
    
    os.makedirs(os.path.dirname(prefix) if os.path.dirname(prefix) else ".", exist_ok=True)
    
    pkts = analyze_pcapng(pcap_file)
    extract_streams(pkts, prefix)
