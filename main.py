# Please read this before use!: https://www.ti.com/product/TMP117
from machine import I2C, Pin
import tmp117timod
import time
from sensor_pack_2.bus_service import I2cAdapter

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
    ts = tmp117timod.TMP117(adapter)

    # если у вас посыпались исключения EIO, проверьте все соединения!
    # if you're getting EIO exceptions, check all connections!
    res = ts.get_id()
    print(f"chip_id: {res}")
    # Таинственное число :-)    mysterious number :-)
    print(f"NIST: {ts.get_nist()}")
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
        # тройное время сна. 1/3 времени датчик работает и 2/3 времени датчик находится в режиме сна!
        time.sleep_ms(3 * sleep_time)

    print(20*"*_")
    print("Reading using an iterator!")
    # Continuous conversion mode
    ts.start_measurement(single_shot=False)
    sleep_time = ts.get_conversion_cycle_time()
    _lim = 100
    _min_old = _lim
    _max_old = -1 * _lim
    for val in ts:
        time.sleep_ms(sleep_time)
        _min = min(val, _min_old)
        _max = max(val, _max_old)
        print(f"Temperature: {val} \u2103.\tmin: {_min}\tmax: {_max}")
        _min_old = _min
        _max_old = _max
