# micropython
# MIT license
# Copyright (c) 2022 Roman Shevchik   goctaprog@gmail.com
import ustruct


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
    __scale = 7.8125E-3

    def __init__(self, bus, address: int = 0x48, conversion_mode: int = 2, conversion_cycle_time: int = 4,
                 average: int = 1):
        self.bus = bus
        self.bus_addr = address
        self.conversion_mode = _check_value(conversion_mode, range(0, 4),
                                            f"Invalid conversion_mode value: {conversion_mode}")
        self.conversion_cycle_time = _check_value(conversion_cycle_time, range(0, 8),
                                                  f"Invalid conversion_cycle_time value: {conversion_cycle_time}")
        self.average = _check_value(average, range(0, 4), f"Invalid conversion_mode value: {average}")
        self.DR_Alert = self.POL = self.T_nA = False
        self.data_ready = self.low_alert = self.high_alert = False
        #
        self.set_config()

    def _read_register(self, reg_addr, bytes_count=2) -> bytes:
        """считывает из регистра датчика значение.
        bytes_count - размер значения в байтах"""
        return self.bus.readfrom_mem(self.bus_addr, reg_addr, bytes_count)

    def _write_register(self, reg_addr, value: int, bytes_count=2, byte_order: str = "big") -> int:
        """записывает данные value в датчик, по адресу reg_addr.
        bytes_count - кол-во записываемых данных"""
        buf = value.to_bytes(bytes_count, byte_order)
        return self.bus.writeto_mem(self.bus_addr, reg_addr, buf)

    def _get_config_reg(self) -> int:
        """read config from register (2 byte)"""
        reg_val = self._read_register(0x01, 2)
        return int(ustruct.unpack(">H", reg_val)[0])

    def _set_config_reg(self, cfg: int) -> int:
        """write config to register (2 byte)"""
        return self._write_register(0x01, cfg)

    def _get_config(self) -> int:
        """читает настройки датчика из регистра.
        сохраняет их в полях экземпляра класса"""
        config = self._get_config_reg()
        self.DR_Alert = config & (0x01 << 2)
        self.POL = config & (0x01 << 3)
        self.T_nA = config & (0x01 << 4)
        self.average = (config & (0b11 << 5)) >> 5
        self.conversion_cycle_time = (config & (0b111 << 7)) >> 7
        self.conversion_mode = (config & (0b11 << 10)) >> 10
        self.data_ready = config & (0x01 << 13)
        self.low_alert = config & (0x01 << 14)
        self.high_alert = config & (0x01 << 15)
        #
        return config

    def set_config(self):
        """write current settings to sensor"""
        tmp = 0
        tmp |= int(self.DR_Alert) << 2
        tmp |= int(self.POL) << 3
        tmp |= int(self.T_nA) << 4
        tmp |= int(self.average) << 5
        tmp |= int(self.conversion_cycle_time) << 7
        tmp |= int(self.conversion_mode) << 10
        #
        self._set_config_reg(tmp)

    def set_temperature_offset(self, offset: float) -> int:
        reg_val = int(offset // TMP117.__scale)
        return self._write_register(0x07, reg_val)

    def get_temperature_offset(self) -> float:
        reg_val = self._read_register(0x07, 2)
        return TMP117.__scale * int(ustruct.unpack(">h", reg_val)[0])

    def get_id(self) -> int:
        """Возвращает идентификатор датчика. Правильное значение - 0х55.
        Returns the ID of the sensor. The correct value is 0x55."""
        res = self._read_register(0x0F, 2)
        return int(ustruct.unpack(">H", res)[0])

    def get_temperature(self):
        """return temperature most recent conversion"""
        reg_val = self._read_register(0x00, 2)
        return TMP117.__scale * int(ustruct.unpack(">h", reg_val)[0])

    def soft_reset(self):
        """программный сброс датчика.
        software reset of the sensor"""
        config = self._get_config_reg()
        self._set_config_reg(config | 0x01)
