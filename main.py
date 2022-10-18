# micropython
# mail: goctaprog@gmail.com
# MIT license


# Please read this before use!: https://www.ti.com/product/TMP117
from machine import I2C
import tmp117ti
import time
from sensor_pack.bus_service import I2cAdapter

if __name__ == '__main__':
    # пожалуйста установите выводы scl и sda в конструкторе для вашей платы, иначе ничего не заработает!
    # please set scl and sda pins for your board, otherwise nothing will work!
    # https://docs.micropython.org/en/latest/library/machine.I2C.html#machine-i2c
    # i2c = I2C(0, scl=Pin(13), sda=Pin(12), freq=400_000) № для примера
    # bus =  I2C(scl=Pin(4), sda=Pin(5), freq=100000)   # на esp8266    !
    # Внимание!!!
    # Замените id=1 на id=0, если пользуетесь первым портом I2C !!!
    # Warning!!!
    # Replace id=1 with id=0 if you are using the first I2C port !!!
    i2c = I2C(id=1, freq=400_000)  # on Arduino Nano RP2040 Connect tested
    adapter = I2cAdapter(i2c)
    # ps - pressure sensor
    ts = tmp117ti.TMP117(adapter)

    # если у вас посыпались исключения EIO, проверьте все соединения!
    # if you're getting EIO exceptions, check all connections!
    res = ts.get_id()
    print(f"chip_id: {hex(res)}")
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
    for _ in range(5):
        val = ts.get_temperature()
        print(f"Temperature: {val} \u2103.\tSleep time: {sleep_time} [ms]")
        sleep_time = ts.get_conversion_cycle_time()
        time.sleep_ms(sleep_time)
        
    print(20*"*_")
    print("One-shot conversion mode!")
    ts.conversion_mode = 0x03
    ts.set_config()  # change mode
    for _ in range(10):
        if ts.is_data_ready():
            val = ts.get_temperature()
            print(f"Temperature: {val} \u2103.\tSleep time: {sleep_time} [ms]")
            ts.conversion_mode = 0x03
            ts.set_config()  # re-launch conversion
        sleep_time = ts.get_conversion_cycle_time()
        print(f"conversion time: {sleep_time} ms")
        # тройное время сна. 1/3 времени датчик работает и 2/3 времени датчик находится в режиме сна!
        time.sleep_ms(3 * sleep_time)

    print(20*"*_")
    print("Reading using an iterator!")
    ts.conversion_mode = 0x00   # Continuous conversion mode
    ts.set_config()  # change mode
    for val in ts:
        sleep_time = ts.get_conversion_cycle_time()
        print(f"Temperature: {val} \u2103.\tSleep time: {sleep_time} [ms]")
        time.sleep_ms(sleep_time)
