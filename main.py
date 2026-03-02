# Please read this before use!: https://www.ti.com/product/TMP117
import time
import tmp11Xtimod
from machine import I2C, Pin
from collections import namedtuple
from sensor_pack_2.bus_service import I2cAdapter

# Тип для возвращаемого результата
stats_result = namedtuple("stats_result", "count min max avg median range std_dev")

def calc_stats(samples: list[float]) -> stats_result | None:
    """
    Вычисляет базовую статистику по списку измерений температуры.

    Аргументы:
        samples (list[float]): Список измерений температуры в °C.

    Возвращает:
        stats_result: Именованный кортеж с полями:
            - count: количество измерений
            - min: минимальное значение
            - max: максимальное значение
            - avg: среднее арифметическое
            - median: медиана
            - range: размах (max - min)
            - std_dev: стандартное отклонение (выборочное)
        None: Если список пуст.
    """
    n = len(samples)
    if 0 == n:
        return None

    # Сортировка для медианы
    sorted_samples = sorted(samples)

    # Основные метрики
    min_val: float = sorted_samples[0]
    max_val: float = sorted_samples[-1]
    avg_val: float = sum(samples) / n
    range_val: float = max_val - min_val

    # Медиана
    if 0 == n % 2:
        median_val: float = (sorted_samples[n // 2 - 1] + sorted_samples[n // 2]) / 2
    else:
        median_val: float = sorted_samples[n // 2]

    # Стандартное отклонение (формула стандартного отклонения)
    variance: float = sum((x - avg_val) ** 2 for x in samples) / (n - 1)
    std_dev: float = variance ** 0.5

    return stats_result(
        count=n,
        min=min_val,
        max=max_val,
        avg=avg_val,
        median=median_val,
        range=range_val,
        std_dev=std_dev
    )


if __name__ == '__main__':
    # пожалуйста установите выводы scl и sda в конструкторе для вашей платы, иначе ничего не заработает!
    # please set scl and sda pins for your board, otherwise nothing will work!
    # https://docs.micropython.org/en/latest/library/machine.I2C.html#machine-i2c
    # i2c = I2C(0, scl=Pin(13), sda=Pin(12), freq=400_000) № для примера
    # bus =  I2C(scl=Pin(4), sda=Pin(5), freq=100000)   # на esp8266    !
    # i2c = I2C(id=1, freq=400_000)  # on Arduino Nano RP2040 Connect tested
    i2c = I2C(id=1, scl=Pin(7), sda=Pin(6), freq=400_000)  # on Raspberry Pi Pico
    adapter = I2cAdapter(i2c)
    # ts - temperature sensor
    ts = tmp11Xtimod.TMP11X(adapter)

    # если у вас посыпались исключения EIO, проверьте все соединения!
    # if you're getting EIO exceptions, check all connections!
    res = ts.get_id()
    print(f"chip_id: 0x{res.device_id:03X}")
    # UID
    uid = ts.get_uid()
    print(f"UID: 0x{uid.word_0:04X}-0x{uid.word_1:04X}-0x{uid.word_2:04X}")
    res = ts.get_config()
    print(f"config after __init__: {hex(res)}")
    ts.conversion_cycle_time = 7
    ts.average = 3
    ts.set_config()
    res = ts.get_config()
    print(f"new config: {hex(res)}")
    print(f"temperature offset: {ts.get_temperature_offset()}")
    ts.set_temperature_offset(3.0)
    print(f"temperature offset: {ts.get_temperature_offset()}")
    ts.set_temperature_offset(0.0)
    sleep_time = 0

    print(20*"*_")
    print("Continuous conversion mode!")
    ts.start_measurement(single_shot=False)
    for _ in range(5):
        val = ts.get_measurement_value()
        print(f"Temperature: {val} \u2103.\tSleep time: {sleep_time} [ms]")
        sleep_time = ts.get_conversion_cycle_time()
        time.sleep_ms(sleep_time)
        
    print(20*"*_")
    print("One-shot conversion mode!")
    ts.start_measurement(single_shot=True)
    sleep_time = ts.get_conversion_cycle_time()
    for _ in range(10):
        if ts.get_data_status():
            val = ts.get_measurement_value()
            print(f"Temperature: {val} \u2103.\tSleep time: {sleep_time} [ms]")
            ts.start_measurement(single_shot=True)  # re-launch conversion
        # Задержка 3 × sleep_time:
        # - sleep_time: датчик выполняет преобразование
        # - 2×sleep_time: датчик в idle, экономия энергии
        # Можно уменьшить до 1 × sleep_time для максимальной частоты опроса
        time.sleep_ms(3 * sleep_time)

    print(20*"*_")
    print("Reading using an iterator!")
    # Continuous conversion mode
    ts.start_measurement(single_shot=False)
    sleep_time = ts.get_conversion_cycle_time()

    _lim = 10
    _min_old = float("inf")
    _max_old = float("-inf")
    samples: list[float] = []
    for i, val in enumerate(ts):
        if i >= _lim:
            break
        if val is not None:
            samples.append(val)
        time.sleep_ms(sleep_time)
        _min = min(val, _min_old)
        _max = max(val, _max_old)
        print(f"Temperature: {val} \u2103.\tmin: {_min}\tmax: {_max}")
        _min_old = _min
        _max_old = _max

    # Расчёт статистики
    stats = calc_stats(samples)

    if stats is not None:
        print(f"\nСтатистика ({stats.count} измерений):")
        print(f"\tMin:\t{stats.min:.5f} °C")
        print(f"\tMax:\t{stats.max:.5f} °C")
        print(f"\tAvg:\t{stats.avg:.5f} °C")
        print(f"\tMedian:\t{stats.median:.5f} °C")
        print(f"\tRange:\t{stats.range:.5f} °C ({128 * stats.range:.1f} LSB)")
        print(f"\tStdDev:\t{stats.std_dev:.5f} °C")
    else:
        print("Нет данных для анализа!")

    # ================================================
    # ТЕСТ ТЕМПЕРАТУРНОГО КОМПАРАТОРА (ICompInterface)
    # ================================================
    print("\n" + 20 * "*_")
    print("\tПроверка работы компаратора (ICompInterface)")
    print(20 * "*_")

    # 1. Настройка компаратора
    print("\nНастройка компаратора...")

    comp_mode = 0  # 0=Therm, 1=Alert
    ts.set_comp_mode(mode=comp_mode, level=False)

    # ← result теперь доступен! Используем result.avg из статистики
    t_center = stats.avg if stats is not None else 26.0
    t_min_set = int(t_center - 0.5)
    t_max_set = int(t_center + 0.5)

    ts.set_thresholds(range(t_min_set, t_max_set))

    actual_range = ts.set_thresholds(None)
    current_mode = ts.set_comp_mode(mode=None)

    print(f"Режим: {'Therm (термостат)' if 0 == current_mode else 'Alert (прерывание)'}")
    print(f"Полярность: {'Активный высокий' if ts.POL else 'Активный низкий'}")
    print(f"Пороги: {actual_range[0]:.3f} °C — {actual_range[1]:.3f} °C")
    print(f"Текущая температура: {ts.get_measurement_value():.5f} °C")

    comp_samples_count = 10
    print("\nМониторинг компаратора ({comp_samples_count} измерений)...")
    print(f"   {'№':<3} | {'Температура':<12} | {'ALERT':<6} | {'Статус':<20}")
    print(50 * "-")

    ts.start_measurement(single_shot=False)
    sleep_time = ts.get_conversion_cycle_time()

    for i in range(comp_samples_count):
        temp = ts.get_measurement_value()
        is_alert = ts.is_over_threshold()

        if temp < actual_range[0]:
            status = "Ниже Tmin"
        elif temp > actual_range[1]:
            status = "Выше Tmax"
        else:
            status = "В диапазоне"

        print(f"   {i + 1:<3} | {temp:<12.5f} | {str(is_alert):<6} | {status:<20}")
        time.sleep_ms(sleep_time)

    # 3. Тест срабатывания (нагрев пальцем)
    print("\nПроверка срабатывания (нагрев датчика пальцем)")
    print(50 * "-")
    print("Прикоснитесь к корпусу датчика на 5 секунд...")

    alert_count = 0
    for i in range(2 * comp_samples_count):
        temp = ts.get_measurement_value()
        is_alert = ts.is_over_threshold()

        if is_alert:
            alert_count += 1
            print(f"Тревога! T={temp:.5f} °C (срабатываний: {alert_count})")

        time.sleep_ms(sleep_time)

    if alert_count > 0:
        print(f"\nКомпаратор сработал {alert_count} раз(а)!")
    else:
        print(f"\nТревог не было! Попробуйте нагреть сильнее или сузить пороги.")

    print("\nФлаги компаратора:")
    flags = ts.get_flags()
    print(f"   HIGH_Alert: {flags.high_alert}")
    print(f"   LOW_Alert:  {flags.low_alert}")
    print(f"   Data_Ready: {flags.data_ready}")
    print(f"   EEPROM_Busy: {flags.eeprom_busy}")

    print("\nПроверка компаратора завершена!")