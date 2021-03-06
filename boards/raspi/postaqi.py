#!/usr/bin/python3
# TODO maybe recheck sensor connectedness at boot
"""Periodically send bme280 data via POST request using the information stored in the file 'config'"""

import sys
import time
import json
import math
import board
import requests
from busio import I2C
import adafruit_bme280
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import pigpio
sys.path.append("tests/")
import read_pwm

# constants
# resistance -> ppm constants (in zero air)
OXIDATION_R0 = 48. # kΩ
NH3_R0 = 29. # kΩ
REDUCTION_R0 = 160. # kΩ

PWM_GPIO = 4 # physical port 7

try:
    # initalize sensors, host, name from config file
    with open("config.json", "r") as f:
        CONFIG = json.loads(f)
        USERNAME = CONFIG["username"]
        PASSWORD = CONFIG["password"]
        HOST = CONFIG["host"]
        SENSOR_NAME = CONFIG["sensorname"]
        BME = int(CONFIG["BME"])
        CJMCU = int(CONFIG["CJMCU"])
        MHZ19B = int(CONFIG["MHZ19B"])
except IOError as error: # config file probably not created if this fails
    print("config file has likley not been created! Please run \"sudo ./setup.sh\"")
    print("error trace below:")
    print(error)

if BME:
    try:
        i2c = I2C(board.SCL, board.SDA)
        bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c)
        bme280.sea_level_pressure = 1013.25

    except OSError:
        print(1)
    except ValueError:
        try:
            i2c = I2C(board.SCL, board.SDA)
            bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x76)
            bme280.sea_level_pressure = 1013.25
        except ValueError:
            print(1)
        except Exception as e:
            print(e)

if CJMCU:
    try:
        # Create the I2C bus
        i2c = busio.I2C(board.SCL, board.SDA)

        # Create the ADC object using the I2C bus
        ads = ADS.ADS1115(i2c) # default addr; 48

        # Create single-ended input on channels 0-2
        chan0 = AnalogIn(ads, ADS.P0)
        chan1 = AnalogIn(ads, ADS.P1)
        chan2 = AnalogIn(ads, ADS.P2)
    except ValueError:
        print(1)
    except OSError:
        print(1)
    except Exception as e:
        print(e)

# no setup required for mhz19b

def update():

    """gather data for connected sensors and return dictionary with it for POSTing"""
    res = {}
    if BME:
        res["temp"] = bme280.temperature
        res["humidity"] = bme280.humidity
        res["pressure"] = bme280.pressure
        res["altitude"] = bme280.altitude

    if CJMCU:
        ch0_oxy_r =  69./((5.0/chan0.voltage)-1.)
        ch1_nh3_r =  220./((5.0/chan1.voltage)-1.)
        ch2_red_r =  220./((5.0/chan2.voltage)-1.)

        ch0_oxy_rratio = ch0_oxy_r/OXIDATION_R0
        ch1_nh3_rratio = ch1_nh3_r/NH3_R0
        ch2_red_rratio = ch2_red_r/REDUCTION_R0

        res["NO2"] = 0.1516*math.pow(ch0_oxy_rratio, 0.9979)
        res["NH3"] = 0.6151*math.pow(ch1_nh3_rratio, -1.903)
        res["CO"] = 4.4638*math.pow(ch2_red_rratio, -1.177)

    if MHZ19B:
        raspi = pigpio.pi()
        pulse = read_pwm.PwmReader(raspi, PWM_GPIO)
        time.sleep(5)
        pulse_period = pulse.pulse_period()
        pulse_width = pulse.pulse_width()
        res["CO2"] = (5000.0)*(pulse_width-2.0)/(pulse_period-4.0)
    res["username"] = USERNAME
    res["password"] = PASSWORD
    res["sensorname"] = SENSOR_NAME
    return res

if len(sys.argv) == 2:
    try:
        print(requests.post(HOST + "/api/in", data=update()))
    except Exception as e:
        print(e)
else:
    while True:
        try:
            print(requests.post(HOST + "/api/in", data=update()))
        except Exception as e:
            print(e)
        time.sleep(55)
