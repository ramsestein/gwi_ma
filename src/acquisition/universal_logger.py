import sys
import os
import json
import csv
import time
import datetime
import serial
import struct
try:
    from . import protocol_manager
    from . import checksum_utils
except ImportError:
    import protocol_manager
    import checksum_utils

def get_value(packet, offset, dtype):
    try:
        if offset >= len(packet):
            return None
            
        if dtype == 'UINT8':
            return packet[offset]
        elif dtype == 'UINT16_LE':
            if offset + 2 > len(packet): return None
            return struct.unpack('<H', packet[offset:offset+2])[0]
        elif dtype == 'UINT16_BE':
            if offset + 2 > len(packet): return None
            return struct.unpack('>H', packet[offset:offset+2])[0]
        # Add more types as needed (INT16, FLOAT, etc.)
        else:
            return None
    except:
        return None

def run_logger():
    proto = protocol_manager.load_protocol()
    
    conn = proto['connection']
    port = conn['port']
    baud = conn['baudrate']
    
    if not port:
        print("Error: Port not defined in protocol_definition.json")
        return

    # Protocol details
    header_hex = proto['packet_structure']['header']
    header_bytes = bytes.fromhex(header_hex) if header_hex else None
    chk_algo = proto['packet_structure']['checksum_algo'] # Legacy
    validation = proto.get('validation', {})
    fixed_len = proto['packet_structure']['fixed_length']
    
    metrics = proto.get('metrics', {})
    waveforms = proto.get('waveforms', {})
    
    print(f"Connecting to {port} @ {baud}...")
    try:
        ser = serial.Serial(
            port, 
            baud, 
            parity=conn.get('parity', 'N'),
            stopbits=conn.get('stopbits', 1),
            bytesize=conn.get('bytesize', 8),
            timeout=1
        )
    except serial.SerialException as e:
        print(f"Connection failed: {e}")
        return

    # Session Metadata
    session_id = timestamp_str
    session_meta = {
        "session_id": session_id,
        "start_time": datetime.datetime.now().isoformat(),
        "config": proto,
        "performance": {
            "packet_loss": 0,
            "crc_errors": 0,
            "total_packets": 0
        }
    }
    meta_filename = os.path.join("results", f"session_{session_id}.json")
    with open(meta_filename, 'w') as f:
        json.dump(session_meta, f, indent=4)
    print(f"Session stored in {meta_filename}")

    # Prepare CSVs
    print(f"Logging metrics to {csv_filename}...")
    if waveforms:
        print(f"Logging waveforms to {wave_filename}...")

    print("Press Ctrl+C to stop.")
    
    # High-Res Timing
    base_perf_time = time.perf_counter()
    base_wall_time = datetime.datetime.now()

    try:
        with open(csv_filename, 'w', newline='') as csvfile, \
             open(wave_filename, 'w', newline='') as wavefile:
            
            # Add PerfTimestamp and Quality flags to CSV
            fieldnames = ['Timestamp', 'PerfTimestamp', 'Alarms', 'SQI'] + list(metrics.keys())
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            
            wave_writer = None
            if waveforms:
                wave_writer = csv.writer(wavefile)
                wave_writer.writerow(['Timestamp', 'PerfTimestamp', 'Waveform', 'SampleIndex', 'Value'])

            buffer = b""
            packet_count = 0
            crc_errors = 0
            
            while True:
                try:
                    if not ser.is_open:
                        print("Reconnecting...")
                        ser.open()
                        time.sleep(1)

                    if ser.in_waiting > 0:
                        buffer += ser.read(ser.in_waiting)
                    else:
                        time.sleep(0.01)
                        continue
                        
                    # Inner Processing Loop
                    while len(buffer) > 0:
                        # Determine Packet Type & Length
                        current_packet_len = fixed_len
                        packet_type_def = None
                        is_multiplexed = False
                        
                        if 'multiplexing' in proto and proto['multiplexing'].get('packets'):
                            is_multiplexed = True
                            mux = proto['multiplexing']
                            id_offset = mux.get('id_offset', 0)
                            
                            if len(buffer) <= id_offset:
                                break # Need more data
                                
                            pkt_id = buffer[id_offset]
                            pkt_id_hex = f"0x{pkt_id:02X}"
                            
                            if pkt_id_hex in mux['packets']:
                                packet_type_def = mux['packets'][pkt_id_hex]
                                current_packet_len = packet_type_def.get('length', fixed_len)
                            else:
                                # Unknown ID - Scan forward/Drop byte
                                buffer = buffer[1:]
                                continue
                        
                        # Check Sync Pattern if defined (Override or Pre-check)
                        if header_bytes and not is_multiplexed:
                             idx = buffer.find(header_bytes)
                             if idx == -1:
                                 # Keep last few bytes in case split header
                                 buffer = buffer[-len(header_bytes):]
                                 break
                             if idx > 0:
                                 buffer = buffer[idx:]
                        
                        if len(buffer) < current_packet_len:
                            break # Need more data
                            
                        # Extract Packet
                        packet = buffer[:current_packet_len]
                        buffer = buffer[current_packet_len:]
                        
                        # Validation
                        if validation and validation.get('algorithm'):
                            if not checksum_utils.validate_packet(packet, validation):
                                print(f"CRC Fail #{packet_count+1}")
                                crc_errors += 1
                                session_meta['performance']['crc_errors'] = crc_errors
                                continue
                        
                        packet_count += 1
                        session_meta['performance']['total_packets'] = packet_count
                        
                        # Timestamping
                        now_perf = time.perf_counter()
                        elapsed = now_perf - base_perf_time
                        current_wall_time = (base_wall_time + datetime.timedelta(seconds=elapsed)).isoformat()
                        
                        # Active Definitions
                        active_metrics = packet_type_def['metrics'] if packet_type_def else metrics
                        active_waveforms = packet_type_def['waveforms'] if packet_type_def else waveforms
                        
                        # Metrics
                        if active_metrics:
                            row = {
                                'Timestamp': current_wall_time,
                                'PerfTimestamp': f"{elapsed:.6f}",
                                'SQI': 100 # Placeholder for calc
                            }
                            # Alarms
                            alarms = proto.get('alarms', [])
                            current_alarms = []
                            if isinstance(alarms, list):
                                for alarm in alarms:
                                    a_off = alarm['offset']
                                    a_bit = alarm['bit']
                                    if a_off < len(packet):
                                        if (packet[a_off] >> a_bit) & 1:
                                            current_alarms.append(alarm['name'])
                            if current_alarms:
                                row['Alarms'] = "|".join(current_alarms)
                                
                            for name, meta in active_metrics.items():
                                val = get_value(packet, meta['offset'], meta['type'])
                                if val is not None:
                                    row[name] = val * meta.get('scale', 1)
                            writer.writerow(row)
                            
                        # Waveforms
                        if wave_writer and active_waveforms:
                            for name, meta in active_waveforms.items():
                                offset = meta['offset']
                                count = meta.get('count', 1)
                                base_type = meta['type']
                                scale = meta.get('scale', 1)
                                size = 1
                                if 'UINT16' in base_type: size = 2
                                elif 'INT16' in base_type: size = 2
                                
                                for i in range(count):
                                    sample_offset = offset + (i * size)
                                    val = get_value(packet, sample_offset, base_type)
                                    if val is not None:
                                        # Calculate exact sample time if frequency known? 
                                        # For now share packet time
                                        wave_writer.writerow([
                                            current_wall_time, 
                                            f"{elapsed:.6f}", 
                                            name, 
                                            i, 
                                            val * scale
                                        ])

                        if packet_count % 10 == 0:
                            print(f"Logged {packet_count} | CRC Errors: {crc_errors}", end='\r')
                
                except serial.SerialException:
                     print("\nSerial Connection Lost! Reconnecting...")
                     ser.close()
                     time.sleep(2)
                except Exception as e:
                     print(f"\nError in loop: {e}")
                     time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopped.")
        # Update final meta
        session_meta['end_time'] = datetime.datetime.now().isoformat()
        with open(meta_filename, 'w') as f:
            json.dump(session_meta, f, indent=4)

    finally:
        if ser.is_open:
            ser.close()

if __name__ == "__main__":
    run_logger()
