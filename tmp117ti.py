# micropython
# import array

#   TMP117 Register Map
#   ADDRESS     TYPE    RESET       ACRONYM                 REGISTER NAME
#   00h         R       8000h       Temp_Result             Temperature result register
#   01h         R/W     0220h (1)   Configuration           Configuration register
#   02h         R/W     6000h (1)   THigh_Limit             Temperature high limit register
#   03h         R/W     8000h (1)   TLow_Limit              Temperature low limit register
#   04h         R/W     0000h       EEPROM_UL               EEPROM unlock register
#   05h         R/W     xxxxh (1)   EEPROM1                 EEPROM1 register
#   06h         R/W     xxxxh (1)   EEPROM2                 EEPROM2 register
#   07h         R/W     0000h (1)   Temp_Offset             Temperature offset register Go
#   08h         R/W     xxxxh (1)   EEPROM3                 EEPROM3 register
#   0Fh         R       0117h       Device_ID               Device ID register

#   (1) This value is stored in Electrically-Erasable, Programmable Read-Only Memory (EEPROM) during device
#   manufacturing. The device reset value can be changed by writing the relevant code in the EEPROM cells
#   (see the EEPROM Overview section).

# conversion modes
# 00: Continuous conversion (CC)
# 01: Shutdown (SD)
# 10: Continuous conversion (CC), Same as 00 (reads back = 00)
# 11: One-shot conversion (OS)


def _check_value(value, valid_range, error_msg):
    if value not in valid_range:
        raise ValueError(error_msg)
    return value


class TMP117:
    def __init__(self, bus, address: int = 0x48, conversion_mode: int = 2, conversion_cycle_time: int = 4,
                 average: int = 1):
        self.bus = bus
        self.bus_addr = address
        self.conv_mode = _check_value(conversion_mode, range(0, 4), f"Invalid conversion_mode value: {conversion_mode}")
        self.cct = _check_value(conversion_cycle_time, range(0, 8),
                                f"Invalid conversion_cycle_time value: {conversion_cycle_time}")
        self.avg = _check_value(average, range(0, 4), f"Invalid conversion_mode value: {average}")

    def _read_register(self, reg_addr, bytes_count=2) -> bytes:
        """считывает из регистра датчика значение.
        bytes_count - размер значения в байтах"""
        return self.bus.readfrom_mem(self.bus_addr, reg_addr, bytes_count)

    def _write_register(self, reg_addr, value: int, bytes_count=2, byte_order: str = "big") -> int:
        """записывает данные value в датчик, по адресу reg_addr.
        bytes_count - кол-во записываемых данных"""
        buf = value.to_bytes(bytes_count, byte_order)
        return self.bus.writeto_mem(self.bus_addr, reg_addr, buf)

    def get_id(self) -> int:
        pass

    def soft_reset(self):
        """Software reset sensor"""
        pass
