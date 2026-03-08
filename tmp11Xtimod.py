# micropython
# MIT license

import micropython
from micropython import const
from collections import namedtuple
from sensor_pack_2 import bus_service
from sensor_pack_2.base_sensor import DeviceEx, IBaseSensorEx, IDentifier, Iterator, check_value_ex, check_value
from sensor_pack_2.comp_interface import ICompInterface

flags_tmp11X = namedtuple("flags_tmp11X", "eeprom_busy data_ready low_alert high_alert")
id_tmp11X = namedtuple("id_tmp11X", "revision_number device_id")
uid_tmp11X = namedtuple("uid_tmp11X", "word_0 word_1 word_2")

# Please read this before use!: https://www.ti.com/product/TMP117
# About NIST:   https://e2e.ti.com/support/sensors-group/sensors/f/sensors-forum/1000579/tmp117-tmp117-nist-byte-order-and-eeprom4-address

# ========================================================================
# Register Addresses (TMP117/TMP119)
# ========================================================================

# Основной регистр температуры
_REG_TEMP: int = const(0x00)
# Регистр конфигурации
_REG_CONFIG: int = const(0x01)
# Регистры порогов температуры (компаратор)
_REG_THIGH: int = const(0x02)      # Верхний порог (T_max)
_REG_TLOW: int = const(0x03)       # Нижний порог (Tmin)
# Регистр разблокировки EEPROM
_REG_EEPROM_UL: int = const(0x04)
# Регистры EEPROM (уникальный ID)
_REG_EEPROM1: int = const(0x05)
_REG_EEPROM2: int = const(0x06)
_REG_EEPROM3: int = const(0x08)
# Регистр температурного смещения (offset)
_REG_OFFSET: int = const(0x07)
# Регистр идентификатора устройства
_REG_DEVICE_ID: int = const(0x0F)

# Базовое время цикла преобразования для CONV[2:0] при AVG=00 (в мс)
# Индексы: 0 1 2 3 4 5 6 7
_CONV_BASE_TIME_MS: tuple[int, ...] = const((16, 125, 250, 500, 1000, 4000, 8000, 16000))
# Минимальное время цикла, требуемое режимом усреднения AVG[1:0] (в мс)
# Если время усреднения больше базового CONV, цикл удлиняется (standby = 0)
# Индексы: b00 b01 b10 b11
_AVG_MIN_CYCLE_MS: tuple[int, ...] = const((0, 125, 500, 1000))
# коэффициент для расчета температуры
_scale = const(7.8125E-3)
_scale_inv = const(128)
# Адреса регистров EEPROM (3 регистра по 16 бит). Полный уникальный ID датчика.
_UID_EEPROM_ADDR: tuple[int, ...] = const((_REG_EEPROM1, _REG_EEPROM2, _REG_EEPROM3))
# рабочий диапазон порогов температуры для датчиков из полупроводников на основе кремния
_THRESHOLD_TEMP_MIN: int = const(-40)   # для Industrial/Extended/Automotive исполнений датчиков
_THRESHOLD_TEMP_MAX: int = const(125)   # для Extended/Automotive исполнений датчиков
_hex_FFFF = const(0xFFFF)

@micropython.native
def _celsius_to_raw(temp_celsius: float) -> int:
    """Преобразует °C в raw-значение регистра."""
    return int(_scale_inv * temp_celsius) & _hex_FFFF

@micropython.native
def _raw_to_celsius(value: int) -> float:
    """Преобразует raw-значение в °C."""
    # Масштабирование: temp = raw / 128
    return _scale * value

class TMP11X(IBaseSensorEx, IDentifier, Iterator, ICompInterface):
    """
    Драйвер для семейства температурных датчиков TI TMP11X.

    Поддерживаемые устройства:
        - TMP117: Высокая точность (±0.1°C). Год начала производства: 2021
        - TMP119: Улучшенная точность (±0.08°C). Год начала производства: 2024, Strain Tolerance

    Оба устройства имеют идентичную карту регистров и полностью совместимы.
    """

    def __init__(self, adapter: bus_service.BusAdapter, address: int = 0x48):
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

    def get_set_reg(self, addr: int, format_value: str | None, value: int | None = None) -> int:
        """Возвращает (при value is None)/устанавливает (при not value is None) содержимое регистра с адресом addr.
        разрядность регистра 16 бит!"""
        buf = self._buf_2
        _conn = self._connection
        if value is None:
            # читаю из Register устройства в буфер два байта
            if format_value is None:
                raise ValueError("При чтении из регистра не задан формат его значения!")
            _conn.read_buf_from_mem(address=addr, buf=buf, address_size=1)
            return _conn.unpack(fmt_char=format_value, source=buf)[0]
        #
        return self._connection.write_reg(reg_addr=addr, value=value, bytes_count=len(buf))

    @micropython.native
    def get_unlock_reg(self) -> int:
        """Возвращает значение EEPROM Unlock Register"""
        return self.get_set_reg(addr=_REG_EEPROM_UL, format_value="H")

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
            - Раздел 7.6.6 дата шита: EEPROM Unlock Register (адрес _REG_EEPROM_UL)
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
        # В One-Shot режиме CONV игнорируется (раздел 7.4.3)
        if 3 == self.conversion_mode:  # One-shot
            return _AVG_MIN_CYCLE_MS[avg]
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
        # del self._buf_2 # возвращаю несколько байт управляющему памятью:-)

    def _get_config_reg(self) -> int:
        """read config from register (2 byte)"""
        return self.get_set_reg(addr=_REG_CONFIG, format_value="H")

    def _set_config_reg(self, cfg: int) -> int:
        """write config to register (2 byte)"""
        return self.get_set_reg(addr=_REG_CONFIG, format_value=None, value=cfg)

    @micropython.native
    def get_config(self) -> int:
        """Читает настройки датчика из регистра. Сохраняет(!) их в полях экземпляра класса."""
        raw_cfg = self._get_config_reg()
        self.DR_Alert = bool(raw_cfg & (0x01 << 2))
        self.POL = bool(raw_cfg & (0x01 << 3))
        self.T_nA = bool(raw_cfg & (0x01 << 4))
        self.average = (raw_cfg & (0b11 << 5)) >> 5
        self.conversion_cycle_time = (raw_cfg & (0b111 << 7)) >> 7
        self.conversion_mode = (raw_cfg & (0b11 << 10)) >> 10
        self.data_ready = bool(raw_cfg & (0x01 << 13))
        self.low_alert = bool(raw_cfg & (0x01 << 14))
        self.high_alert = bool(raw_cfg & (0x01 << 15))
        #
        return raw_cfg

    @micropython.native
    def set_config(self):
        """write current settings to sensor"""
        raw_cfg = 0
        raw_cfg |= int(self.DR_Alert) << 2
        raw_cfg |= int(self.POL) << 3
        raw_cfg |= int(self.T_nA) << 4
        raw_cfg |= int(self.average) << 5
        raw_cfg |= int(self.conversion_cycle_time) << 7
        raw_cfg |= int(self.conversion_mode) << 10
        #
        self._set_config_reg(raw_cfg)

    def start_measurement(self, single_shot: bool = False, conv_cycle_time: int = 4,
                          average_mode: int = 1):
        """Настраивает работу датчика в желаемом режиме.
        Вызывайте метод get_config для обновления конфигурации самостоятельно!"""
        self.conversion_cycle_time = check_value(conv_cycle_time, range(8),
                                                 f"Неверное значение параметра conversion_cycle_time: {conv_cycle_time}")
        self.average = check_value(average_mode, range(4), f"Неверное значение параметра average_mode: {average_mode}")
        self.conversion_mode = 2    # continuous mode
        if single_shot:
            self.conversion_mode = 3
        self.set_config()

    def set_temperature_offset(self, offset: float) -> int:
        """set temperature offset to sensor.
        Большая просьба к читателям: значение смещения не должно превышать разумного значения.
        Например +/- 10. Контролируйте это самостоятельно!
        A big request to readers: the offset value should not exceed a reasonable value.
        For example +/- 10.
        Control it yourself!
        """
        reg_val = _celsius_to_raw(offset)
        return self.get_set_reg(addr=_REG_OFFSET, format_value=None, value=reg_val)

    def get_temperature_offset(self) -> float:
        """get temperature offset from sensor"""
        raw_offset = self.get_set_reg(addr=_REG_OFFSET, format_value="h")
        return _raw_to_celsius(raw_offset)

    def get_id(self) -> id_tmp11X:
        """Возвращает идентификатор устройства TMP117, TMP119.

        Читает регистр Device_ID (адрес _REG_DEVICE_ID), содержащий:
        - Revision number (биты 15:12) — номер версии кристалла. Равен нулю для 117, а для 119 равен двум (во всяком случае в марте 2026)!
        - Device ID (биты 11:0) — должен быть 0x117 для TMP117 и для TMP119!

        Returns:
            id_tmp11X: Именованный кортеж с полями:
                - revision_number: 4-битная версия кристалла (0–15)
                - device_id: 12-битный идентификатор устройства (должен быть 0x117 для TMP117)

        Note:
        - Device ID = 0x117 подтверждает, что подключён TMP117 для TMP119 будет что-то другое
        - Проверка device_id полезна для проверки подключения датчика"""
        _raw = self.get_set_reg(addr=_REG_DEVICE_ID, format_value="H")
        return id_tmp11X(revision_number=(0xF000 & _raw) >> 12, device_id=0xFFF & _raw)

    def soft_reset(self):
        """Выполняет программный сброс датчика TMP117, TMP119.
    
        Устанавливает бит Soft_Reset (бит 1) в регистре конфигурации (_REG_CONFIG), что запускает последовательность сброса устройства.
        ВНИМАНИЕ: ТРЕБУЮТСЯ ДЕЙСТВИЯ ПОСЛЕ ВЫЗОВА!!!
        После вызова этого метода необходимо:
        1. Выждать минимум 2 мс перед любыми операциями с датчиком: time.sleep_ms(2)
        2. Обновить кэш конфигурации: sensor.get_config()
        Если после вызова soft_reset есть свой код, требующий времени выполнения от 2 мс,
        то вызывать sleep_ms(2) не нужно. Этот код не должен работать с датчиком!
        sensor.get_config() вызвать все таки желательно!
        """
        config = self._get_config_reg()
        self._set_config_reg(config | 0x02)

    def get_flags(self) -> flags_tmp11X:
        """Return tuple: (EEPROM_Busy, Data_Ready, LOW_Alert) flags"""
        config = self._get_config_reg()
        # print(f"config_reg: {hex(config)}")
        _gen = (0 != (config & (0x01 << i)) for i in range(12, 16))
        return flags_tmp11X(eeprom_busy=next(_gen), data_ready=next(_gen), low_alert=next(_gen), high_alert=next(_gen))

    def get_data_status(self, raw: bool = False) -> bool | int:
        """Флаг готовности данных. Этот флаг указывает, что преобразование завершено и регистр температуры
        может быть прочитан. Каждый раз, когда считывается регистр температуры или регистр конфигурации,
        этот бит сбрасывается!"""
        if raw:
            return self._get_config_reg()
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
        raw_val = self.get_set_reg(addr=_REG_TEMP, format_value="h")
        if -32768 == raw_val:
            return None
        return _raw_to_celsius(raw_val)

    def __next__(self):
        """Удобное чтение температуры с помощью итератора"""
        return self.get_measurement_value()

    def get_uid(self) -> uid_tmp11X:
        """Возвращает уникальный 48-битный ID датчика TMP117.

        Читает три регистра EEPROM (0x05, 0x06, 0x08), содержащие уникальный
        идентификатор, запрограммированный на заводе TI.

        Returns:
            uid_tmp11X: Именованный кортеж с тремя 16-битными словами:
                - word_0: EEPROM1 (адрес 0x05) — критичен для NIST прослеживаемости
                - word_1: EEPROM2 (адрес 0x06) — пользовательские данные
                - word_2: EEPROM3 (адрес 0x08) — пользовательские данные

        Warning:
            Не перезаписывайте EEPROM1 (word_0, адрес 0x05)!
            Это нарушит NIST-прослеживаемость калибровки датчика.
            Согласно разделу 7.6.7 дата шита: «To support NIST traceability do not delete or reprogram the EEPROM[1] register.»

        Note:
            - Уникальный ID используется для отслеживаемости калибровки к стандартам NIST
            - TMP117, TMP119 тестируется на производстве с NIST оборудованием
            - по стандартам ISO/IEC 17025 (раздел 7.5.1.1 дата шита)
            - Общий объём EEPROM для ID: 48 бит (3 регистра × 16 бит)"""
        # Проверка: не занята ли EEPROM
        if self.is_eeprom_busy():
            raise RuntimeError("EEPROM занята, результат будет неверен!")
        # можно читать!
        _gen = (self.get_set_reg(addr=adr, format_value="H") for adr in _UID_EEPROM_ADDR)
        return uid_tmp11X(word_0=next(_gen), word_1=next(_gen), word_2=next(_gen))

    def is_single_shot_mode(self) -> bool:
        """Возвращает Истина, когда датчик находится в режиме однократных измерений,
        каждое из которых запускается методом start_measurement"""
        self.get_config()
        return 3 == self.conversion_mode

    def is_continuously_mode(self) -> bool:
        """Возвращает Истина, когда датчик находится в режиме многократных измерений,
        производимых автоматически. Процесс запускается методом start_measurement"""
        self.get_config()
        return self.conversion_mode in (0, 2)

    # ========================================================================
    # ICompInterface Implementation (Температурный компаратор)               #
    # ========================================================================

    @micropython.native
    def set_comp_mode(self, mode: int | None = None, active_alarm_level: bool = False) -> int:
        """Установить режим работы встроенного температурного компаратора. Смотри в comp_interface.py"""
        if mode is not None:
            mode = check_value(mode, range(2), f"Invalid comparator mode: {mode}")
            # T/nA бит (бит 4): 1=Therm (режим 0), 0=Alert (режим 1)
            self.T_nA = (0 == mode)
            self.POL = active_alarm_level
            self.set_config()

        self.get_config()
        # Возвращаем текущий режим
        return 0 if self.T_nA else 1

    @micropython.native
    def set_thresholds(self, thresholds: tuple[float, float] | None = None) -> tuple[float, float]:
        """
        Устанавливает нижний и верхний пороги температуры (Tmin, T_max).

        Аргументы:
            thresholds (tuple[float, float] | None): пороги температуры в градусах Цельсия.
                Формат: (Tmin, T_max) где Tmin < T_max обязательно!
                Диапазон: {_THRESHOLD_TEMP_MIN} °C до {_THRESHOLD_TEMP_MAX} °C
                Разрешение: 0.0078125 °C (1 LSB) — полная точность датчика
                Если thresholds=None, возвращает текущие пороги без изменений.

        Возвращает:
            tuple[float, float]: Текущие пороги температуры (Tmin, T_max) в градусах Цельсия.

        Warning:
            - В режиме компаратора (mode=0): Tmin работает как гистерезис для сброса
            - В режиме прерывания (mode=1): оба порога работают независимо
        """
        def get_err_str(value: int | float, r: range | tuple) -> str:
            """Возвращает строковое описание ошибки"""
            return f"Температура {value} вне диапазона: {r}"

        if thresholds is not None:
            valid_range = _THRESHOLD_TEMP_MIN, _THRESHOLD_TEMP_MAX
            t_min = check_value_ex(thresholds[0], valid_range, get_err_str(thresholds[0], valid_range))
            t_max = check_value_ex(thresholds[1], valid_range, get_err_str(thresholds[1], valid_range))

            if t_min >= t_max:
                raise ValueError(f"Tmin ({t_min}) должна быть строго меньше T_max ({t_max})!")

            t_min_raw = _celsius_to_raw(t_min)
            t_max_raw = _celsius_to_raw(t_max)

            self.get_set_reg(addr=_REG_TLOW, format_value=None, value=t_min_raw)  # T_LOW
            self.get_set_reg(addr=_REG_THIGH, format_value=None, value=t_max_raw)  # T_HIGH

        # Чтение текущих порогов
        t_low_raw = self.get_set_reg(addr=_REG_TLOW, format_value="h")  # signed
        t_high_raw = self.get_set_reg(addr=_REG_THIGH, format_value="h")  # signed

        # Конвертация обратно в градусы Цельсия
        t_min = _raw_to_celsius(t_low_raw)
        t_max = _raw_to_celsius(t_high_raw)

        return t_min, t_max

    @micropython.native
    def is_over_threshold(self) -> bool:
        """
        Проверить, превышен ли верхний порог температуры (T > T_max).

        Возвращает:
            bool: True, если температура превысила T_max (тревога), False — иначе.

        Note:
            - В режиме прерывания (mode=1) вызов этого метода может подтвердить тревогу
              и вернуть вывод в состояние нормы (чтение регистра сбрасывает флаг)
            - В режиме компаратора (mode=0) состояние сбрасывается автоматически при T < Tmin
            - Метод читает регистр конфигурации (бит 15 = HIGH_Alert)

            - В режиме Therm (mode=0): флаг сбрасывается только при T < Tmin (гистерезис)
            - В режиме Alert (mode=1): флаг сбрасывается чтением регистра конфигурации
            - Метод читает регистр конфигурации напрямую (без обновления кэша)

        Warning:
            В режиме прерывания повторный вызов сразу после срабатывания
            может вернуть False (флаг уже сброшен чтением)!
        """
        self.get_config()
        return self.high_alert