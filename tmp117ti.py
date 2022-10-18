# micropython
# MIT license
# Copyright (c) 2022 Roman Shevchik   goctaprog@gmail.com
import micropython
from sensor_pack import bus_service
from sensor_pack.base_sensor import BaseSensor, Iterator, check_value


# Please read this before use!: https://www.ti.com/product/TMP117


class TMP117(BaseSensor, Iterator):
    __scale = 7.8125E-3

    def __init__(self, adapter: bus_service.BusAdapter, address: int = 0x48,
                 conversion_mode: int = 2, conversion_cycle_time: int = 4,
                 average: int = 1):
        """conversion_mode:
            00: Continuous conversion (CC)
            01: Shutdown (SD)
            10: Continuous conversion (CC), Same as 00
            11: One-shot conversion (OS)

        conversion_cycle_time   0..7:
            время ожидания между преобразованиями.
            See Table 7-7 for the standby time between conversions.

        average (Conversion averaging modes):
            00: No averaging
            01: 8 Averaged conversions
            10: 32 averaged conversions
            11: 64 averaged conversions
            """
        super().__init__(adapter, address, True)
        self.conversion_mode = check_value(conversion_mode, range(0, 4),
                                           f"Invalid conversion_mode value: {conversion_mode}")
        self.conversion_cycle_time = check_value(conversion_cycle_time, range(0, 8),
                                                 f"Invalid conversion_cycle_time value: {conversion_cycle_time}")
        self.average = check_value(average, range(0, 4), f"Invalid conversion_mode value: {average}")
        self.DR_Alert = self.POL = self.T_nA = False
        self.data_ready = self.low_alert = self.high_alert = False
        #
        self.set_config()

    @micropython.native
    def get_conversion_cycle_time(self) -> int:
        """возвращает время преобразования температуры датчиком
        в зависимости от его настроек"""
        _ = check_value(self.conversion_cycle_time, range(0, 8),
                        f"Invalid conversion cycle time value: {self.conversion_cycle_time}")
        _ = check_value(self.average, range(0, 4),
                        f"Invalid conversion averaging mode value: {self.average}")
        avg_0 = 16, 125, 250, 500, 1000, 4000, 8000, 16000  # in [ms]
        if 0x03 == self.conversion_mode:    # One-shot conversion mode
            # Когда биты MOD[1:0] в регистре конфигурации установлены на 11, TMP117 будет выполнять преобразование
            # температуры, называемое однократным преобразованием. После того, как устройство завершит однократное
            # преобразование, оно переходит в режим отключения с низким энергопотреблением. Однократный цикл
            # преобразования, в отличие от непрерывного режима преобразования, состоит только из активного времени
            # преобразования и не имеет периода ожидания. Таким образом, продолжительность однократного преобразования
            # зависит только от битовых настроек AVG. Биты CONV не влияют на продолжительность
            # однократного преобразования.
            s_shot = 16, 125, 500, 1000
            return s_shot[self.average]
        if self.average < 2:
            if 0 == self.conversion_cycle_time and 1 == self.average:
                return 125
            return avg_0[self.conversion_cycle_time]
        # average >= 2
        if self.conversion_cycle_time < 4:
            return 500 * (self.average - 2)
        # conversion_cycle_time >= 4
        return avg_0[self.conversion_cycle_time]

    def __del__(self):
        self.conversion_mode = 0x01     # Shutdown (SD)
        self.set_config()

    def _read_register(self, reg_addr, bytes_count=2) -> bytes:
        """считывает из регистра датчика значение.
        bytes_count - размер значения в байтах"""
        return self.adapter.read_register(self.address, reg_addr, bytes_count)

    def _write_register(self, reg_addr, value: int, bytes_count=2) -> int:
        """записывает данные value в датчик, по адресу reg_addr.
        bytes_count - кол-во записываемых данных"""
        byte_order = self._get_byteorder_as_str()[0]
        return self.adapter.write_register(self.address, reg_addr, value, bytes_count, byte_order)

    def _get_config_reg(self) -> int:
        """read config from register (2 byte)"""
        reg_val = self._read_register(0x01, 2)
        config = self.unpack("H", reg_val)[0]
        return config

    def _set_config_reg(self, cfg: int) -> int:
        """write config to register (2 byte)"""
        return self._write_register(0x01, cfg)

    @micropython.native
    def get_config(self) -> int:
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
        return TMP117.__scale * self.unpack("h", reg_val)[0]

    def get_id(self) -> int:
        """Возвращает идентификатор датчика. Правильное значение - 0х55.
        Returns the ID of the sensor. The correct value is 0x55."""
        res = self._read_register(0x0F, 2)
        return self.unpack("H", res)[0]

    def _get_flags(self) -> tuple:
        """Return tuple: (EEPROM_Busy, Data_Ready, LOW_Alert) flags"""
        config = self._get_config_reg()
        # print(f"config_reg: {hex(config)}")
        return tuple([0 != (config & (0x01 << i)) for i in range(12, 16)])

    def is_data_ready(self) -> bool:
        """Флаг готовности данных. Этот флаг указывает, что преобразование завершено и регистр температуры
        может быть прочитан. Каждый раз, когда считывается регистр температуры или регистр конфигурации,
        этот бит сбрасывается!
        Data ready flag.
        This flag indicates that the conversion is complete and the
        temperature register can be read. Every time the temperature
        register or configuration register is read, this bit is cleared."""
        return self._get_flags()[1]

    @micropython.native
    def get_temperature(self) -> float:
        """return temperature most recent conversion"""
        reg_val = self._read_register(0x00, 2)
        return TMP117.__scale * self.unpack("h", reg_val)[0]

    def soft_reset(self):
        """программный сброс датчика.
        software reset of the sensor"""
        config = self._get_config_reg()
        self._set_config_reg(config | 0x01)

    def __next__(self):
        """Удобное чтение температуры с помощью итератора"""
        return self.get_temperature()
