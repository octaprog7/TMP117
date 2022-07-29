# micropython
# mail: goctaprog@gmail.com
# MIT license


# Please read this before use!: https://www.ti.com/product/TMP117
from machine import I2C, Pin
import tmp117ti
import time
from sensor_pack.bus_service import I2cAdapter

if __name__ == '__main__':
    # пожалуйста установите выводы scl и sda в конструкторе для вашей платы, иначе ничего не заработает!
    # please set scl and sda pins for your board, otherwise nothing will work!
    # https://docs.micropython.org/en/latest/library/machine.I2C.html#machine-i2c
    # i2c = I2C(0, scl=Pin(13), sda=Pin(12), freq=400_000) № для примера
    # bus =  I2C(scl=Pin(4), sda=Pin(5), freq=100000)   # на esp8266    !
    i2c = I2C(0, freq=400_000)  # on Arduino Nano RP2040 Connect tested
    adapter = I2cAdapter(i2c)
    # ps - pressure sensor
    ts = tmp117ti.TMP117(adapter)

    # если у вас посыпались исключения, чего у меня на макетной плате с али и проводами МГТВ не наблюдается,
    # то проверьте все соединения.
    # Радиотехника - наука о контактах! РТФ-Чемпион!
    res = ts.get_id()
    print(f"chip_id: {hex(res)}")
    res = ts._get_config()
    print(f"config after __init__: {hex(res)}")
    ts.conversion_cycle_time = 7
    ts.average = 3
    ts.set_config()
    res = ts._get_config()
    print(f"new config: {hex(res)}")
    print(f"temperature offset: {ts.get_temperature_offset()}")
    ts.set_temperature_offset(3.0)
    print(f"temperature offset: {ts.get_temperature_offset()}")
    ts.set_temperature_offset(0.0)

    for _ in range(10):
        val = ts.get_temperature()
        print(f"Temperature: {val}")
        time.sleep_ms(16_000)
    
    

