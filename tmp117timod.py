# micropython
# MIT license

import micropython
from micropython import const
from collections import namedtuple
from sensor_pack_2 import bus_service
from sensor_pack_2.base_sensor import DeviceEx, IBaseSensorEx, IDentifier, Iterator, check_value

flags_tmp117 = namedtuple("flags_tmp117", "eeprom_busy data_ready low_alert high_alert")
id_tmp117 = namedtuple("id_tmp117", "revision_number device_id")
uid_tmp117 = namedtuple("uid_tmp117", "word_0 word_1 word_2")

# Please read this before use!: https://www.ti.com/product/TMP117
# About NIST:   https://e2e.ti.com/support/sensors-group/sensors/f/sensors-forum/1000579/tmp117-tmp117-nist-byte-order-and-eeprom4-address

# Базовое время цикла преобразования для CONV[2:0] при AVG=00 (в мс)
# Индексы: 0 1 2 3 4 5 6 7
_CONV_BASE_TIME_MS: tuple[int, ...] = const((16, 125, 250, 500, 1000, 4000, 8000, 16000))
# Минимальное время цикла, требуемое режимом усреднения AVG[1:0] (в мс)
# Если время усреднения больше базового CONV, цикл удлиняется (standby = 0)
# Индексы: b00 b01 b10 b11
_AVG_MIN_CYCLE_MS: tuple[int, ...] = const((0, 125, 500, 1000))
# коэффициент для расчета температуры
_scale = const(7.8125E-3)
# Адреса регистров EEPROM (3 регистра по 16 бит). Полный уникальный ID датчика.
_UID_EEPROM_ADDR: tuple[int, ...] = const((0x05, 0x06, 0x08))

class TMP117(IBaseSensorEx, IDentifier, Iterator):

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
        self._buf_2 = bytearray(2)      # для _read_from_into
        self.conversion_mode = 2
        self.conversion_cycle_time = 4
        self.average = 1
        self.DR_Alert = self.POL = self.T_nA = False
        self.data_ready = self.low_alert = self.high_alert = False
        #
        self.set_config()

    def get_reg_value(self, addr: int, format_value: str) -> int:
        """
        Возвращает значение регистра.
        Returns: значение регистра.
        addr - адрес регистра.
        format_value - формат значения для unpack
        """
        buf = self._buf_2
        _conn = self._connection
        # читаю из Register устройства в буфер два байта
        _conn.read_buf_from_mem(address=addr, buf=buf, address_size=1)
        return _conn.unpack(fmt_char=format_value, source=buf)[0]

    @micropython.native
    def get_unlock_reg(self) -> int:
        """Возвращает значение EEPROM Unlock Register"""
        return self.get_reg_value(addr=0x04, format_value="H")

    @micropython.native
    def is_eeprom_busy(self) -> bool:
        """Проверяет флаг занятости EEPROM.

        Returns:
            bool: True если EEPROM занята (программирование или загрузка при старте),
                False если EEPROM готова к операциям.

        Note:
            Флаг EEPROM_Busy устанавливается в двух случаях:
            - Во время программирования EEPROM (запись занимает ~7 мс)
            - Во время загрузки настроек из EEPROM при включении питания (~1.5 мс)

        Согласно разделу 7.5.1.2 дата шита, перед записью в EEPROM
        необходимо убедиться, что этот флаг сброшен.

        See Also:
            - Раздел 7.6.6 дата шита: EEPROM Unlock Register (адрес 0x04)
            - Раздел 7.5.1.2 дата шита: Programming the EEPROM"""
        unlock_reg = self.get_unlock_reg()
        return bool(unlock_reg & 0x4000)  # Бит 14

    @micropython.native
    def get_conversion_cycle_time(self) -> int:
        """Возвращает время преобразования температуры датчиком в миллисекундах(!) в зависимости от его настроек."""
        conv = check_value(self.conversion_cycle_time, range(8),
                        f"Invalid conversion cycle time value: {self.conversion_cycle_time}")
        avg = check_value(self.average, range(4),
                        f"Invalid conversion averaging mode value: {self.average}")
        # запланированное время цикла из настроек CONV
        base_time = _CONV_BASE_TIME_MS[conv]
        # минимально необходимое время для выбранного усреднения AVG
        min_required_time = _AVG_MIN_CYCLE_MS[avg]
        # Реальное время = максимум из двух (общее время цикла не может быть меньше времени,
        # которое физически требуется датчику на выполнение всех измерений для усреднения.)
        return base_time if base_time > min_required_time else min_required_time

    def __del__(self):
        self.conversion_mode = 0x01     # Shutdown (SD)
        self.set_config()
        del self._buf_2     # возвращаю несколько байт управляющему памятью:-)

    def _get_config_reg(self) -> int:
        """read config from register (2 byte)"""
        return self.get_reg_value(addr=0x01, format_value="H")

    def _set_config_reg(self, cfg: int) -> int:
        """write config to register (2 byte)"""
        return self._connection.write_reg(reg_addr=0x01, value=cfg, bytes_count=2)

    @micropython.native
    def get_config(self) -> int:
        """Читает настройки датчика из регистра. Сохраняет(!) их в полях экземпляра класса."""
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
        Если refresh_conf Истина, то после вызова метода set_config, вызывается метод get_config,
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
        reg_val = int(offset // _scale)
        return self._connection.write_reg(reg_addr=0x07, value=reg_val, bytes_count=2)

    def get_temperature_offset(self) -> float:
        """get temperature offset from sensor"""
        raw_offset = self.get_reg_value(addr=0x07, format_value="h")
        return _scale * raw_offset

    def get_id(self) -> id_tmp117:
        """Возвращает идентификатор устройства TMP117.

        Читает регистр Device_ID (адрес 0x0F), содержащий:
        - Revision number (биты 15:12) — версия ревизии чипа
        - Device ID (биты 11:0) — должен быть 0x117 для TMP117

        Returns:
            id_tmp117: Именованный кортеж с полями:
                - revision_number: 4-битная версия ревизии (0–15)
                - device_id: 12-битный идентификатор устройства (должен быть 0x117)

        Note:
        - Device ID = 0x117 подтверждает, что подключён TMP117
        - Проверка device_id полезна для верификации подключения датчика"""
        _raw = self.get_reg_value(addr=0x0F, format_value="H")
        return id_tmp117(revision_number=(0xF000 & _raw) >> 12, device_id=0xFFF & _raw)

    def soft_reset(self):
        """программный сброс датчика.
        software reset of the sensor"""
        config = self._get_config_reg()
        self._set_config_reg(config | 0x02)

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
    def get_measurement_value(self, value_index: int = 0) -> float | None:
        """Возвращает последнее измеренное значение температуры в °C.

        Returns:
            float: Температура в градусах Цельсия.
            None: Если преобразование ещё не завершено (значение 0x8000/-32768).

        Note:
            Согласно разделу 7.3.1 дата шита, до первого преобразования
            регистр температуры содержит -256 °C (код 0x8000).
        """
        raw_val = self.get_reg_value(addr=0x00, format_value="h")
        if -32768 == raw_val:
            return None
        return _scale * raw_val

    def __next__(self):
        """Удобное чтение температуры с помощью итератора"""
        return self.get_measurement_value()

    def get_uid(self) -> uid_tmp117:
        """Возвращает уникальный 48-битный ID датчика TMP117.

        Читает три регистра EEPROM (0x05, 0x06, 0x08), содержащие уникальный
        идентификатор, запрограммированный на заводе TI.

        Returns:
            uid_tmp117: Именованный кортеж с тремя 16-битными словами:
                - word_0: EEPROM1 (адрес 0x05) — критичен для NIST-трассируемости
                - word_1: EEPROM2 (адрес 0x06) — пользовательские данные
                - word_2: EEPROM3 (адрес 0x08) — пользовательские данные

        Warning:
            Не перезаписывайте EEPROM1 (word_0, адрес 0x05)!
            Это нарушит NIST-трассируемость калибровки датчика.
            Согласно разделу 7.6.7 дата шита:

        Note:
            - Уникальный ID используется для трассировки калибровки к стандартам NIST
            - TMP117 тестируется на производстве с NIST-трассируемым оборудованием
            - Верифицировано по стандартам ISO/IEC 17025 (раздел 7.5.1.1 дата шита)
            - Общий объём EEPROM для ID: 48 бит (3 регистра × 16 бит)"""
        _gen = (self.get_reg_value(addr=adr, format_value="H") for adr in _UID_EEPROM_ADDR)
        return uid_tmp117(word_0=next(_gen), word_1=next(_gen), word_2=next(_gen))

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