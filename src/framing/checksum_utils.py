def calculate_checksum(data, algorithm):
    """
    Calculates checksum for byte data based on the specified algorithm.
    Supported algorithms: 'sum_modulo_256', 'xor', 'crc8', 'twos_complement'
    """
    if algorithm == 'sum_modulo_256':
        return sum(data) % 256
    elif algorithm == 'xor':
        chk = 0
        for b in data:
            chk ^= b
        return chk
    elif algorithm == 'twos_complement':
        return (256 - (sum(data) % 256)) % 256
    elif algorithm == 'crc8':
        # Simple CRC-8 implementation (Polynomial 0x07)
        crc = 0
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = (crc << 1) ^ 0x07
                else:
                    crc <<= 1
            crc &= 0xFF
        return crc
    else:
        return 0

def validate_packet(packet, validation_config):
    """
    Validates a packet against a validation configuration.
    Config structure:
    {
        "algorithm": "sum_modulo_256",
        "range_start": 0,
        "range_end": -1, # Relative to packet end (e.g. -1 excludes last byte)
        "checksum_offset": -1 # Where the checksum byte is located
    }
    """
    if not validation_config:
        return True # specific validation not configured, pass throug

    algo = validation_config.get('algorithm', 'sum_modulo_256')
    start = validation_config.get('range_start', 0)
    end = validation_config.get('range_end', -1)
    chk_offset = validation_config.get('checksum_offset', -1)

    # Handle negative indices
    pkt_len = len(packet)
    if end < 0: end += pkt_len
    if chk_offset < 0: chk_offset += pkt_len

    if chk_offset >= pkt_len or start >= pkt_len or end > pkt_len:
        return False # Invalid config for this packet size

    # Extract checksum from packet
    expected_chk = packet[chk_offset]
    
    # Calculate actual checksum
    # Note: range_end is usually exclusive in Python slice, so we use it directly if config assumes standard slicing
    # If the user means "include byte at index X", we might need +1.
    # Let's assume standard python slice semantics for range_end in config for now, 
    # but often protocols exclude the checksum byte itself.
    
    data_to_check = packet[start:end]
    calculated_chk = calculate_checksum(data_to_check, algo)

    return calculated_chk == expected_chk
