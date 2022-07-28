# micropython
# MIT license
# Copyright (c) 2022 Roman Shevchik   goctaprog@gmail.com
import micropython
import ustruct
from sensor_pack import bus_service
from sensor_pack.base_sensor import BaseSensor, Iterator

# Please read this before use!: https://www.ti.com/product/TMP117


@micropython.native
def _check_value(value: int, valid_range, error_msg: str) -> int:
    if value not in valid_range:
        raise ValueError(error_msg)
    return value


class TMP117(BaseSensor, Iterator):
    __scale = 7.8125E-3

    def __init__(self, adapter: bus_service.BusAdapter, address: int = 0x48,
                 conversion_mode: int = 2, conversion_cycle_time: int = 4,
                 average: int = 1):
        super().__init__(adapter, address)
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
        return self.adapter.read_register(self.address, reg_addr, bytes_count)

    def _write_register(self, reg_addr, value: int, bytes_count=2, byte_order: str = "big") -> int:
        """записывает данные value в датчик, по адресу reg_addr.
        bytes_count - кол-во записываемых данных"""
        return self.adapter.write_register(self.address, reg_addr, value, bytes_count, byte_order)

    def _get_config_reg(self) -> int:
        """read config from register (2 byte)"""
        reg_val = self._read_register(0x01, 2)
        return int(ustruct.unpack(">H", reg_val)[0])

    def _set_config_reg(self, cfg: int) -> int:
        """write config to register (2 byte)"""
        return self._write_register(0x01, cfg)

    @micropython.native
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

    @micropython.native
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
        """set temperature offset to sensor.
        Большая просьба к читателям: значение смещения не должно превышать разумного значения.
        Например +/- 10. Контролируйте это самостоятельно!
        A big request to readers: the offset value should not exceed a reasonable value.
        For example +/- 10.
        Control it yourself!
        """
        reg_val = int(offset // TMP117.__scale)
        return self._write_register(0x07, reg_val)

    def get_temperature_offset(self) -> float:
        """set temperature offset from sensor"""
        reg_val = self._read_register(0x07, 2)
        return TMP117.__scale * int(ustruct.unpack(">h", reg_val)[0])

    def get_id(self) -> int:
        """Возвращает идентификатор датчика. Правильное значение - 0х55.
        Returns the ID of the sensor. The correct value is 0x55."""
        res = self._read_register(0x0F, 2)
        return int(ustruct.unpack(">H", res)[0])

    @micropython.native
    def get_temperature(self):
        """return temperature most recent conversion"""
        reg_val = self._read_register(0x00, 2)
        return TMP117.__scale * int(ustruct.unpack(">h", reg_val)[0])

    def soft_reset(self):
        """программный сброс датчика.
        software reset of the sensor"""
        config = self._get_config_reg()
        self._set_config_reg(config | 0x01)

    def __next__(self):
        """Удобное чтение температуры с помощью итератора"""
        return self.get_temperature()
