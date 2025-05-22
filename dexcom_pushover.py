import json
import time
import subprocess
from datetime import datetime, timedelta

from gpiozero import Button
from pydexcom import Dexcom

import tm1637
from sound_test import play_alarm, setup_pwm

# Alert thresholds in mmol/L
LOW_THRESHOLD = 4.0
HIGH_THRESHOLD = 13.0
VERY_LOW_THRESHOLD = 2.5
HIGH_LEVEL_MUTE_TIME = 120
LOW_LEVEL_MUTE_TIME = 5
ALERT_REPEAT_TIME = timedelta(minutes=0.5)

SPEAKER_PIN = 16
TONE_HIGH = 220
TONE_LOW = 440
TONE_VERY_LOW = 880
DURATION = 0.6
REPEAT = 5
KEY_PIN = 14

sounds = [
    'sounds/707800__scottyd0es__aeroce-tri-tone-text-alert.wav',
    'sounds/216676__robinhood76__04864-notification-music-box.wav',
    'sounds/399190__spiceprogram__glockenspiel-brass-rolls.wav'
]

def play_sound(index):
    subprocess.run(['aplay', sounds[index]])

def load_config(filename):
    with open(filename, 'r') as file:
        return json.load(file)

# Display setup
ROTATION_FRAMES = [0x40, 0x20, 0x01, 0x02]
rotation_index = 0
currently_muted = False
current_glucose = -1


def display_float(display, number):
    global rotation_index, currently_muted
    if number < 0 or number > 50:
        return
    num_str = "{:.1f}".format(number).replace('.', '')
    digits = [int(d) for d in num_str]
    SEGMENTS = [0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07, 0x7F, 0x6F]
    decimal_point = 0x80
    rotating_char = ROTATION_FRAMES[rotation_index]
    if currently_muted:
        rotating_char |= 0x08
    rotation_index = (rotation_index + 1) % len(ROTATION_FRAMES)
    if number < 10:
        display_data = [0x00, SEGMENTS[digits[0]] | decimal_point, SEGMENTS[digits[1]], rotating_char]
    else:
        display_data = [SEGMENTS[digits[0]], SEGMENTS[digits[1]] | decimal_point, SEGMENTS[digits[2]], rotating_char]
    display.write(display_data)

def monitor_glucose_dexcom(dexcom_client, last_low_alert_time, last_high_alert_time, display):
    global current_glucose, currently_muted, pwm

    glucose_reading = dexcom_client.get_current_glucose_reading()
    current_glucose = glucose_reading.mmol_l
    print(f"Current glucose: {current_glucose} mmol/L")
    display_float(display, current_glucose)

    now = datetime.now()

    if current_glucose < VERY_LOW_THRESHOLD:
        play_alarm(pwm, TONE_VERY_LOW, DURATION, REPEAT)
        play_sound(0)
    elif current_glucose < LOW_THRESHOLD:
        if not last_low_alert_time or (now - last_low_alert_time) > ALERT_REPEAT_TIME:
            if not currently_muted:
                play_alarm(pwm, TONE_LOW, DURATION, REPEAT)
                play_sound(2)
            last_low_alert_time = now
    elif current_glucose > HIGH_THRESHOLD:
        if not last_high_alert_time or (now - last_high_alert_time) > ALERT_REPEAT_TIME:
            if not currently_muted:
                play_alarm(pwm, TONE_HIGH, DURATION, REPEAT)
                play_sound(1)
            last_high_alert_time = now
    else:
        print("Glucose is within normal range.")

    return last_low_alert_time, last_high_alert_time, current_glucose

def button_press():
    global currently_muted, current_glucose, mute_stop_time
    print("Button Pressed!")
    if current_glucose > HIGH_THRESHOLD:
        currently_muted = True
        mute_stop_time = datetime.now() + timedelta(minutes=HIGH_LEVEL_MUTE_TIME)
        print("High alert muted.")
    elif current_glucose < LOW_THRESHOLD:
        currently_muted = True
        mute_stop_time = datetime.now() + timedelta(minutes=LOW_LEVEL_MUTE_TIME)
        print("Low alert muted.")

if __name__ == "__main__":
    play_sound(0)
    config = load_config('config.json')

    CLK_PIN = 3
    DIO_PIN = 2
    display = tm1637.TM1637(clk=CLK_PIN, dio=DIO_PIN)
    display.brightness(0)
    display.write([0, 0, 0, 0])

    pwm = setup_pwm()
    mute_button = Button(KEY_PIN, pull_up=True)
    mute_button.when_pressed = button_press

    while True:
        try:
            dexcom = Dexcom(
                username=config['dexcom_username'],
                password=config['dexcom_password'],
                region="ous"  # or "us" depending on account
            )
            print("Connected to Dexcom Share.")
            last_low_alert_time = None
            last_high_alert_time = None

            while True:
                if currently_muted and datetime.now() > mute_stop_time:
                    currently_muted = False

                try:
                    last_low_alert_time, last_high_alert_time, current_glucose = monitor_glucose_dexcom(
                        dexcom,
                        last_low_alert_time,
                        last_high_alert_time,
                        display
                    )
                except Exception as e:
                    print(f"Monitoring error: {e}")
                    break

                for _ in range(10):
                    display_float(display, current_glucose)
                    time.sleep(1)

        except Exception as e:
            print(f"Authentication or connection error: {e}")
            time.sleep(60)
