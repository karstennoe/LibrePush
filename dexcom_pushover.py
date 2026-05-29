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
LOW_LEVEL_MUTE_TIME = 60
LOW_FALLING_ALERT_DELTA = 0.5
LOW_RECOVERY_DELTA = 0.1
ALERT_REPEAT_TIME = timedelta(minutes=5)

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
muted_alert_type = None
mute_stop_time = None
low_mute_glucose = None
previous_glucose = None
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
    global current_glucose, currently_muted, previous_glucose, pwm

    glucose_reading = dexcom_client.get_current_glucose_reading()
    last_glucose = previous_glucose
    current_glucose = glucose_reading.mmol_l
    previous_glucose = current_glucose
    print(f"Current glucose: {current_glucose} mmol/L")
    display_float(display, current_glucose)

    now = datetime.now()

    if current_glucose < VERY_LOW_THRESHOLD:
        play_alarm(pwm, TONE_VERY_LOW, DURATION, REPEAT)
        play_sound(0)
        last_low_alert_time = now
    elif current_glucose < LOW_THRESHOLD:
        if currently_muted and muted_alert_type != "low":
            clear_mute()

        alert_due = not last_low_alert_time or (now - last_low_alert_time) > ALERT_REPEAT_TIME
        recovering = last_glucose is not None and current_glucose >= last_glucose - LOW_RECOVERY_DELTA
        mute_broken_by_fall = low_mute_should_break(current_glucose)

        if mute_broken_by_fall:
            print("Low glucose kept falling after mute; alarm re-enabled.")
            clear_mute()

        if alert_due or mute_broken_by_fall:
            if currently_muted and muted_alert_type == "low":
                print("Low glucose alert muted while values are not falling.")
            elif recovering and last_low_alert_time:
                print("Low glucose is flat or rising; repeat alarm suppressed.")
            else:
                play_alarm(pwm, TONE_LOW, DURATION, REPEAT)
                play_sound(2)
                last_low_alert_time = now
    elif current_glucose > HIGH_THRESHOLD:
        if currently_muted and muted_alert_type != "high":
            clear_mute()

        if not last_high_alert_time or (now - last_high_alert_time) > ALERT_REPEAT_TIME:
            if not currently_muted:
                play_alarm(pwm, TONE_HIGH, DURATION, REPEAT)
                play_sound(1)
            else:
                print("High glucose alert muted.")
            last_high_alert_time = now
    else:
        if currently_muted and muted_alert_type == "low":
            clear_mute()
        print("Glucose is within normal range.")

    return last_low_alert_time, last_high_alert_time, current_glucose

def clear_mute():
    global currently_muted, muted_alert_type, mute_stop_time, low_mute_glucose

    currently_muted = False
    muted_alert_type = None
    mute_stop_time = None
    low_mute_glucose = None

def low_mute_should_break(current_value):
    return (
        currently_muted
        and muted_alert_type == "low"
        and low_mute_glucose is not None
        and current_value <= low_mute_glucose - LOW_FALLING_ALERT_DELTA
    )

def button_press():
    global currently_muted, current_glucose, mute_stop_time, muted_alert_type, low_mute_glucose
    print("Button Pressed!")
    if current_glucose > HIGH_THRESHOLD:
        currently_muted = True
        muted_alert_type = "high"
        low_mute_glucose = None
        mute_stop_time = datetime.now() + timedelta(minutes=HIGH_LEVEL_MUTE_TIME)
        print("High alert muted.")
    elif current_glucose < LOW_THRESHOLD:
        currently_muted = True
        muted_alert_type = "low"
        low_mute_glucose = current_glucose
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
                    clear_mute()

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
