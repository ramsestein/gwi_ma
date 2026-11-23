import json
import datetime
import os
from src.analysis import protocol_manager

def generate_markdown_doc(output_file="Protocol_Spec.md"):
    proto = protocol_manager.load_protocol()
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # Title & Meta
        f.write(f"# Protocol Specification: {proto.get('name', 'Unknown Device')}\n")
        f.write(f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        
        # 1. Connection Layer
        conn = proto.get('connection', {})
        f.write("## 1. Physical Layer & Connection\n")
        f.write("| Parameter | Value |\n")
        f.write("|-----------|-------|\n")
        f.write(f"| Port | `{conn.get('port', 'N/A')}` |\n")
        f.write(f"| Baud Rate | `{conn.get('baudrate', 9600)}` |\n")
        f.write(f"| Parity | `{conn.get('parity', 'N')}` |\n")
        f.write(f"| Stop Bits | `{conn.get('stopbits', 1)}` |\n")
        f.write(f"| Byte Size | `{conn.get('bytesize', 8)}` |\n\n")

        # 2. Packet Structure
        struct = proto.get('packet_structure', {})
        fixed_len = struct.get('fixed_length', 0)
        
        f.write("## 2. Packet Structure\n")
        f.write(f"- **Fixed Length:** {fixed_len} bytes\n")
        f.write(f"- **Header:** `{struct.get('header', 'None')}`\n")
        f.write(f"- **Footer:** `{struct.get('footer', 'None')}`\n")
        f.write(f"- **Checksum:** `{struct.get('checksum_algo', 'None')}`\n\n")
        
        # Packet Diagram
        if fixed_len and fixed_len < 64: # Don't draw massive packets
            f.write("### Packet Diagram\n")
            f.write("```text\n")
            
            # Create a map of Offset -> Content
            byte_map = [".."] * fixed_len
            
            # Mark Header
            header_hex = struct.get('header')
            if header_hex:
                h_bytes = bytes.fromhex(header_hex)
                for i in range(len(h_bytes)):
                    if i < fixed_len: byte_map[i] = "HD"
            
            # Mark Metrics
            metrics = proto.get('metrics', {})
            for name, m in metrics.items():
                off = m['offset']
                size = 1
                if 'UINT16' in m['type'] or 'INT16' in m['type']: size = 2
                elif 'FLOAT' in m['type']: size = 4
                
                label = name[:2].upper()
                for i in range(size):
                    if off+i < fixed_len: byte_map[off+i] = label
            
            # Draw Top Line
            f.write("+" + "---+" * fixed_len + "\n")
            
            # Draw Byte Indices
            row_idx = "|"
            for i in range(fixed_len):
                row_idx += f"{i:^3}|"
            f.write(row_idx + "\n")
            
            f.write("+" + "---+" * fixed_len + "\n")
            
            # Draw Content
            row_content = "|"
            for b in byte_map:
                row_content += f"{b:^3}|"
            f.write(row_content + "\n")
            
            f.write("+" + "---+" * fixed_len + "\n")
            f.write("```\n\n")

        # 3. Data Fields (Metrics)
        f.write("## 3. Data Fields (Metrics)\n")
        metrics = proto.get('metrics', {})
        if metrics:
            f.write("| Metric | Offset | Type | Scale | Unit |\n")
            f.write("|--------|--------|------|-------|------|\n")
            for name, m in metrics.items():
                f.write(f"| **{name}** | {m['offset']} | `{m['type']}` | x{m.get('scale', 1)} | {m.get('unit', '-')} |\n")
        else:
            f.write("*No metrics defined.*\n")
        f.write("\n")

        # 4. Waveforms
        f.write("## 4. Waveforms\n")
        waves = proto.get('waveforms', {})
        if waves:
            f.write("| Waveform | Offset | Type | Samples/Pkt |\n")
            f.write("|----------|--------|------|-------------|\n")
            for name, w in waves.items():
                f.write(f"| **{name}** | {w['offset']} | `{w['type']}` | {w.get('count', 1)} |\n")
        else:
            f.write("*No waveforms defined.*\n")
        f.write("\n")

        # 5. Alarms & Status
        f.write("## 5. Alarms & Status Flags\n")
        alarms = proto.get('alarms', [])
        if alarms and isinstance(alarms, list):
            f.write("| Alarm Name | Byte Offset | Bit Index | Trigger |\n")
            f.write("|------------|-------------|-----------|---------|\n")
            # Sort by offset then bit
            sorted_alarms = sorted(alarms, key=lambda x: (x['offset'], x['bit']))
            for a in sorted_alarms:
                f.write(f"| {a['name']} | {a['offset']} | {a['bit']} | 1 |\n")
        else:
            f.write("*No alarms defined.*\n")
        f.write("\n")
        
        # 6. Multiplexing
        f.write("## 6. Multiplexing / Validation\n")
        mux = proto.get('multiplexing', {})
        val = proto.get('validation', {})
        
        if mux:
            f.write(f"- **Strategy:** `{mux.get('strategy', 'None')}`\n")
            f.write(f"- **ID Offset:** {mux.get('id_offset', 'N/A')}\n")
            packets = mux.get('packets', {})
            if packets:
                f.write("### Packet Types\n")
                for pid, pdef in packets.items():
                    f.write(f"- **ID {pid}**: Length {pdef.get('length')} bytes\n")
        
        if val:
            f.write(f"- **Validation Algo:** `{val.get('algorithm', 'None')}`\n")
            f.write(f"- **Range:** {val.get('start', 0)} to {val.get('end', 'End')}\n")
            
        f.write("\n---\n")
        f.write("*Generated by VitalParser DocGenerator*")

    print(f"Documentation generated: {os.path.abspath(output_file)}")

if __name__ == "__main__":
    generate_markdown_doc()
