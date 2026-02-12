import json
import os

PROTOCOL_FILE = os.path.join("results", "protocol_definition.json")

DEFAULT_PROTOCOL = {
    "connection": {
        "port": None,
        "baudrate": 115200,
        "parity": "N",
        "stopbits": 1,
        "bytesize": 8
    },
    "packet_structure": {
        "header": None,  # Hex string
        "footer": None,
        "fixed_length": None,
        "checksum_algo": None
    },
    "metrics": {
        # "HR": {"offset": 10, "type": "uint8", "scale": 1}
    },
    "waveforms": {
        # "ECG": {"offset": 20, "type": "uint8", "count": 1, "scale": 1}
    },
    "validation": {
        # "algorithm": "sum_modulo_256", "range_start": 0, "range_end": -1, "checksum_offset": -1
    },
    "multiplexing": {},
    "alarms": {}
}

def load_protocol():
    if not os.path.exists(PROTOCOL_FILE):
        save_protocol(DEFAULT_PROTOCOL)
        return DEFAULT_PROTOCOL
    try:
        with open(PROTOCOL_FILE, 'r') as f:
            data = json.load(f)
            # Ensure new keys exist if loading old file
            for key in ["waveforms", "validation", "multiplexing", "alarms"]:
                if key not in data:
                    data[key] = {}
            return data
    except:
        return DEFAULT_PROTOCOL

def save_protocol(data):
    with open(PROTOCOL_FILE, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"Protocol definition updated in {PROTOCOL_FILE}")

def update_connection(port, baud, parity='N', stop=1, size=8):
    p = load_protocol()
    p['connection']['port'] = port
    p['connection']['baudrate'] = baud
    p['connection']['parity'] = parity
    p['connection']['stopbits'] = stop
    p['connection']['bytesize'] = size
    save_protocol(p)

def add_metric(name, offset, data_type, scale=1):
    p = load_protocol()
    p['metrics'][name] = {
        "offset": offset,
        "type": data_type,
        "scale": scale
    }
    save_protocol(p)

def add_waveform(name, offset, data_type, count=1, scale=1):
    p = load_protocol()
    p['waveforms'][name] = {
        "offset": offset,
        "type": data_type,
        "count": count,
        "scale": scale
    }
    save_protocol(p)

def set_validation(algorithm, range_end=-1, checksum_offset=-1):
    p = load_protocol()
    p['validation'] = {
        "algorithm": algorithm,
        "range_start": 0,
        "range_end": range_end,
        "checksum_offset": checksum_offset
    }
    save_protocol(p)

if __name__ == "__main__":
    # Test
    p = load_protocol()
    print(json.dumps(p, indent=2))
