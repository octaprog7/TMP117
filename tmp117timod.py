# micropython
# MIT license

import micropython
from collections import namedtuple
from sensor_pack_2 import bus_service
from sensor_pack_2.base_sensor import DeviceEx, IBaseSensorEx, IDentifier, Iterator, check_value

flags_tmp117 = namedtuple("flags_tmp117", "eeprom_busy data_ready low_alert high_alert")
id_tmp117 = namedtuple("id_tmp117", "revision_number device_id")
nist_tmp117 = namedtuple("nist_tmp117", "word_0 word_1")
data_status_tmp117 = namedtuple("data_status_tmp117", "temp_ready press_ready cmd_decoder_ready")

# Please read this before use!: https://www.ti.com/product/TMP117
# About NIST:   https://e2e.ti.com/support/sensors-group/sensors/f/sensors-forum/1000579/tmp117-tmp117-nist-byte-order-and-eeprom4-address

class TMP117(IBaseSensorEx, IDentifier, Iterator):
    __scale = 7.8125E-3

    def __init__(self, adapter: bus_service.BusAdapter, address: int = 0x48):
                 #conversion_mode: int = 2, conversion_cycle_time: int = 4,
                 #average: int = 1):
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
        self._connection = DeviceEx(adapter=adapter, address=address, big_byte_order=True)
        self._buf_2 = bytearray((0 for _ in range(2)))      # для _read_from_into
        self.conversion_mode = 2
        self.conversion_cycle_time = 4
        self.average = 1
        self.DR_Alert = self.POL = self.T_nA = False
        self.data_ready = self.low_alert = self.high_alert = False
        #
        self.set_config()

    @micropython.native
    def get_conversion_cycle_time(self) -> int:
        """Возвращает время преобразования температуры датчиком в миллисекундах(!) в зависимости от его настроек."""
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
        del self._buf_2     # возвращаю несколько байт управляющему памятью :-)

    def _get_config_reg(self) -> int:
        """read config from register (2 byte)"""
        buf = self._buf_2
        _conn = self._connection
        # читаю из памяти устройства в буфер два байта
        _conn.read_buf_from_mem(address=0x01, buf=buf, address_size=1)
        return _conn.unpack(fmt_char="H", source=buf)[0]

    def _set_config_reg(self, cfg: int) -> int:
        """write config to register (2 byte)"""
        return self._connection.write_reg(reg_addr=0x01, value=cfg, bytes_count=2)

    @micropython.native
    def get_config(self) -> int:
        """Читает настройки датчика из регистра. Cохраняет(!) их в полях экземпляра класса."""
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

    def start_measurement(self, single_shot: bool = False, conv_cycle_time: int = 4,
                          average_mode: int = 1, refresh_conf: bool = True):
        """Настраивает работу датчика в желаемом режиме.
        Если refresh_conf в Истина, то после вызова метода set_config, вызывается метод get_config,
        обновляющий значения текущих настроек в полях экземпляра класса."""
        self.conversion_cycle_time = check_value(conv_cycle_time, range(8),
                                                 f"Invalid conversion_cycle_time value: {conv_cycle_time}")
        self.average = check_value(average_mode, range(4), f"Invalid conversion_mode value: {average_mode}")
        self.conversion_mode = 2    # continuous mode
        if single_shot:
            self.conversion_mode = 3
        self.set_config()
        if refresh_conf:
            self.get_config()

    def set_temperature_offset(self, offset: float) -> int:
        """set temperature offset to sensor.
        Большая просьба к читателям: значение смещения не должно превышать разумного значения.
        Например +/- 10. Контролируйте это самостоятельно!
        A big request to readers: the offset value should not exceed a reasonable value.
        For example +/- 10.
        Control it yourself!
        """
        reg_val = int(offset // TMP117.__scale)
        return self._connection.write_reg(reg_addr=0x07, value=reg_val, bytes_count=2)

    def get_temperature_offset(self) -> float:
        """set temperature offset from sensor"""
        buf = self._buf_2
        _conn = self._connection
        # читаю из памяти устройства в буфер два байта
        _conn.read_buf_from_mem(address=0x07, buf=buf)
        return TMP117.__scale * _conn.unpack(fmt_char="h", source=buf)[0]

    def get_id(self) -> id_tmp117:
        """Возвращает идентификатор датчика. Returns the ID of the sensor."""
        buf = self._buf_2
        _conn = self._connection
        # читаю из памяти устройства в буфер два байта
        _conn.read_buf_from_mem(address=0x0F, buf=buf)
        _raw = _conn.unpack(fmt_char="H", source=buf)[0]
        return id_tmp117(revision_number=(0xF000 & _raw) >> 12, device_id=0xFFF & _raw)

    def soft_reset(self):
        """программный сброс датчика.
        software reset of the sensor"""
        config = self._get_config_reg()
        self._set_config_reg(config | 0x01)

    def get_flags(self) -> flags_tmp117:
        """Return tuple: (EEPROM_Busy, Data_Ready, LOW_Alert) flags"""
        config = self._get_config_reg()
        # print(f"config_reg: {hex(config)}")
        _gen = (0 != (config & (0x01 << i)) for i in range(12, 16))
        return flags_tmp117(eeprom_busy=next(_gen), data_ready=next(_gen), low_alert=next(_gen), high_alert=next(_gen))

    def get_data_status(self) -> bool:
        """Флаг готовности данных. Этот флаг указывает, что преобразование завершено и регистр температуры
        может быть прочитан. Каждый раз, когда считывается регистр температуры или регистр конфигурации,
        этот бит сбрасывается!
        Data ready flag.
        This flag indicates that the conversion is complete and the
        temperature register can be read. Every time the temperature
        register or configuration register is read, this bit is cleared."""
        return self.get_flags().data_ready

    @micropython.native
    def get_measurement_value(self, value_index: int = 0) -> float:
        """return temperature most recent conversion"""
        buf = self._buf_2
        _conn = self._connection
        # читаю из памяти устройства в буфер два байта
        _conn.read_buf_from_mem(address=0x00, buf=buf)
        return TMP117.__scale * _conn.unpack(fmt_char="h", source=buf)[0]

    def __next__(self):
        """Удобное чтение температуры с помощью итератора"""
        return self.get_measurement_value()

    def get_nist(self) -> nist_tmp117:
        """Читает NIST, число необходимое для идентификации датчика. TI не сообщает о способе вычисления NIST.
        Дискуссии на эту тему вы найдете на TI E2E форуме.
        Reads NIST, the number needed to identify the sensor.
        TI does not report how NIST calculates.
        You can find discussions on this topic on the TI E2E forum."""
        _conn = self._connection
        addresses = 0x05, 0x08
        _gen = (_conn.unpack(fmt_char="H", source=_conn.read_buf_from_mem(adr, self._buf_2))[0] for adr in addresses)
        return nist_tmp117(word_0=next(_gen), word_1=next(_gen))

    def is_single_shot_mode(self) -> bool:
        """Возвращает Истина, когда датчик находится в режиме однократных измерений,
        каждое из которых запускается методом start_measurement"""
        self.get_config()
        return 3 == self.conversion_mode

    def is_continuously_mode(self) -> bool:
        """Возвращает Истина, когда датчик находится в режиме многократных измерений,
        производимых автоматически. Процесс запускается методом start_measurement"""
        self.get_config()
        return 0 == self.conversion_mode or 2 == self.conversion_mode