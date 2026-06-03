"""Pure helpers for Modbus RTU CRC16 handling."""

CRC_INITIAL = 0xFFFF
CRC_POLYNOMIAL = 0xA001


def compute_crc(data: bytes) -> int:
    """Return the Modbus RTU CRC16 for data as an integer."""
    crc = CRC_INITIAL

    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ CRC_POLYNOMIAL
            else:
                crc >>= 1

    return crc & 0xFFFF


def crc_to_bytes(crc: int) -> bytes:
    """Return CRC bytes in Modbus RTU wire order: low byte, high byte."""
    if not 0 <= crc <= 0xFFFF:
        raise ValueError("CRC must be in range 0..65535")

    return bytes((crc & 0xFF, (crc >> 8) & 0xFF))


def append_crc(data: bytes) -> bytes:
    """Return data with its Modbus RTU CRC appended."""
    return data + crc_to_bytes(compute_crc(data))


def verify_crc(frame: bytes) -> bool:
    """Return True when a complete RTU frame has a valid CRC."""
    if len(frame) < 3:
        return False

    payload = frame[:-2]
    received_crc = frame[-2] | (frame[-1] << 8)
    return compute_crc(payload) == received_crc


def strip_crc(frame: bytes) -> bytes:
    """Return frame payload without CRC, or raise ValueError if invalid."""
    if len(frame) < 3:
        raise ValueError("RTU frame must contain payload and CRC")
    if not verify_crc(frame):
        raise ValueError("Invalid Modbus RTU CRC")

    return frame[:-2]
