# TMP11X
Micropython module for TMP117, TMP119 Texas Instruments temperature sensors.

Just connect your TMP117, TMP119 board to Arduino, ESP or any other board with MicroPython firmware.

Supply voltage TMP117, TMP119 3.3 or 5.0 volts! Use four wires to connect (I2C).
1. +VCC (Supply voltage)
2. GND
3. SDA
4. SCL

Upload micropython firmware to the NANO(ESP, etc) board, and then files: main.py, tmp11Xtimod.py and sensor_pack_2 folder. 
Then open main.py in your IDE and run it.

# Pictures
## IDE
![alt text](https://github.com/octaprog7/TMP117/blob/master/ide117.png)
## Breadboard
![alt text](https://github.com/octaprog7/TMP117/blob/master/tmp117board.jpg)

# Troubleshooting
| Problem | Possible Cause | Solution |
|---------|----------------|----------|
| ALERT=True always | Therm Mode + hysteresis | Cool below Tmin or switch to Alert Mode |
| No I2C communication | Wrong address/pull-ups | Check ADD0, 4.7kΩ pull-up on SDA/SCL |
| Inaccurate readings | Self-heating/mounting | Use `set_temperature_offset()` |
| EEPROM not writing | Locked/busy | Check `EEPROM_Busy`, perform unlock sequence |

## Notes
Note: This driver is tested on real hardware with TMP117.

## Support the project
If you found this driver helpful, please rate it!
This helps us develop the project and add support for new sensors.
If you liked my software, please be generous and give it a star!