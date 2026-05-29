import json
import time
#from pushover_complete import PushoverAPI
from pylibrelinkup import PyLibreLinkUp, APIUrl
from datetime import datetime, timedelta
import requests
from requests.exceptions import HTTPError
from sound_test import play_alarm, setup_pwm

import tm1637
import time
#from RPi import GPIO  # For controlling GPIO pins on the Raspberry Pi
#import tm1637

import subprocess

from gpiozero import Button

sounds = ['sounds/707800__scottyd0es__aeroce-tri-tone-text-alert.wav', 'sounds/216676__robinhood76__04864-notification-music-box.wav' , 'sounds/399190__spiceprogram__glockenspiel-brass-rolls.wav']

def play_sound(index):
    subprocess.run(['aplay', sounds[index]])

# Glucose level thresholds (modify as needed)
LOW_THRESHOLD = 4.0  # mmol/L
HIGH_THRESHOLD = 13.0  # mmol/L
VERY_LOW_THRESHOLD = 2.5  # mmol/L - non mutable


pwm = setup_pwm()

# Constants
SPEAKER_PIN = 16  # GPIO pin where the piezo speaker is connected
TONE_HIGH = 220  # Frequency of the high blood sugar alert tone in Hz
TONE_LOW = 440    # Frequency of the low blood sugar alert tone in Hz
TONE_VERY_LOW = 880    # Frequency of the low blood sugar alert tone in Hz
DURATION = 0.6    # Duration of each tone in seconds
REPEAT = 5    
ALERT_REPEAT_TIME = timedelta(minutes=0.5)

currently_muted = False
muted_alert_type = None
mute_stop_time = None
low_mute_glucose = None
previous_glucose = None

current_glucose = -1

# Define GPIO pins
KEY_PIN = 14  # Connected to KEY

HIGH_LEVEL_MUTE_TIME = 120
LOW_LEVEL_MUTE_TIME = 60
LOW_FALLING_ALERT_DELTA = 0.2
LOW_RECOVERY_DELTA = 0.1

# Test overwrites
#HIGH_LEVEL_MUTE_TIME = 1
#LOW_LEVEL_MUTE_TIME = 1
#LOW_THRESHOLD = 7.0  # mmol/L
#HIGH_THRESHOLD = 13.0  # mmol/L
#VERY_LOW_THRESHOLD = 2.5  # mmol/L - non mutable


def button_press():
    global currently_muted
    global current_glucose
    global mute_stop_time
    global muted_alert_type
    global low_mute_glucose
    print("Button Pressed!")
    if current_glucose > HIGH_THRESHOLD:
        print(f"Muting for {HIGH_LEVEL_MUTE_TIME} minutes!")
        currently_muted = True
        muted_alert_type = "high"
        low_mute_glucose = None
        mute_stop_time = datetime.now() + timedelta(minutes=HIGH_LEVEL_MUTE_TIME)
    if current_glucose < LOW_THRESHOLD:
        print(f"Muting for {LOW_LEVEL_MUTE_TIME} minutes!")
        currently_muted = True
        muted_alert_type = "low"
        low_mute_glucose = current_glucose
        mute_stop_time = datetime.now() + timedelta(minutes=LOW_LEVEL_MUTE_TIME)


def clear_mute():
    global currently_muted
    global muted_alert_type
    global mute_stop_time
    global low_mute_glucose

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



# Load configuration from the JSON file
def load_config(filename):
    with open(filename, 'r') as file:
        return json.load(file)

def send_pushover_notification(message, user_key, api_token, priority=0, sound='default'):
    """Send a Pushover notification using pushover_complete with priority level and custom sound."""
    pushover = PushoverAPI(api_token)
    
    if priority == 2:
        pushover.send_message(
            user=user_key,
            message=message,
            title="LibrePush",
            priority=priority,  # Set the priority level
            sound=sound,        # Set the custom sound
            retry=30,
            expire=3600
        )
    else:
        pushover.send_message(
            user=user_key,
            message=message,
            title="LibrePush",
            priority=priority,  # Set the priority level
            sound=sound        # Set the custom sound
        )


# Define rotation states
ROTATION_FRAMES = [0x40, 0x20, 0x01, 0x02]  # Corresponding to '-', '\', '|', '/'

# Global rotation index
rotation_index = 0

def display_float(display, number):
    """
    Displays a float (0 to 30) with one decimal place on a 4-digit TM1637 display.
    The number is right-justified. The first digit cycles through an animation for effect.
    
    :param display: TM1637 display object
    :param number: Float number between 0 and 30
    """
    global rotation_index  # Use global counter to track animation state

    global currently_muted # Make a "mark" under "progress bar" if muted

    # Ensure the number is within range
    if number < 0 or number > 50:
        return

    # Format number with one decimal place
    num_str = "{:.1f}".format(number).replace('.', '')  # Remove decimal for processing
    digits = [int(d) for d in num_str]

    # Create segment mappings
    SEGMENTS = [0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07, 0x7F, 0x6F]  # 0-9
    decimal_point = 0x80  # Bit for DP

    # Select current rotation character
    rotating_char = ROTATION_FRAMES[rotation_index]

    SEGMENT_D_MASK = 0x08  # Bit 3 controls the lowest LED (segment D)
    if currently_muted:
       rotating_char = rotating_char | SEGMENT_D_MASK  # Turn segment D ON

    # Update rotation index for next call
    rotation_index = (rotation_index + 1) % len(ROTATION_FRAMES)

    # Create segment data
    if number < 10:
        # Right-align a single-digit float (e.g., "4.5" → " 4.5")
        display_data = [0x00, SEGMENTS[digits[0]] | decimal_point, SEGMENTS[digits[1]], rotating_char]
    else:
        # Right-align a two-digit float (e.g., "12.3" → "12.3")
        display_data = [SEGMENTS[digits[0]], SEGMENTS[digits[1]] | decimal_point, SEGMENTS[digits[2]], rotating_char]

    # Write data to display
    display.write(display_data)


def monitor_glucose(lib_client, user_key, api_token, last_low_alert_time, last_high_alert_time, display):
    """Check glucose values from the LibreLinkUp client and send notifications if necessary."""
    global current_glucose
    global currently_muted
    global previous_glucose
    global pwm
    patients = lib_client.get_patients()
    if not patients:
        print("No patients found.")
        return last_low_alert_time, last_high_alert_time

    patient = patients[0]  # Assuming we're interested in the first patient
    glucose_data = lib_client.read(patient_identifier=patient.patient_id)
    last_glucose = previous_glucose
    current_glucose = glucose_data.current.value
    previous_glucose = current_glucose
    
    # Example: Display a number (4 digits)
    print(f"{current_glucose}".replace(".",""))

    # Example: Display a number (4 digits)
    #display.show(f"{current_glucose}".replace(".",""))
    #display.numbers(int(current_glucose), int((current_glucose-int(current_glucose))*100))
    display_float(display, current_glucose)


    # Current time
    current_time = datetime.now()

    if current_glucose < VERY_LOW_THRESHOLD:
        play_alarm(pwm, TONE_VERY_LOW, DURATION, REPEAT)
        play_sound(0)
        print("Very low level alarm tone played")
        last_low_alert_time = current_time
    elif current_glucose < LOW_THRESHOLD:
        if currently_muted and muted_alert_type != "low":
            clear_mute()

        alert_due = not last_low_alert_time or (current_time - last_low_alert_time) > ALERT_REPEAT_TIME
        recovering = last_glucose is not None and current_glucose >= last_glucose - LOW_RECOVERY_DELTA
        mute_broken_by_fall = low_mute_should_break(current_glucose)

        if mute_broken_by_fall:
            print("Low glucose kept falling after mute; alarm re-enabled.")
            clear_mute()

        if alert_due or mute_broken_by_fall:
            #send_pushover_notification(f"Low glucose alert! Current level: {current_glucose} mmol/L.", user_key, api_token, 2, "falling")
            if currently_muted and muted_alert_type == "low":
                print("Low glucose alert muted while values are not falling.")
            elif recovering and last_low_alert_time:
                print("Low glucose is flat or rising; repeat alarm suppressed.")
            else:
                play_alarm(pwm, TONE_LOW, DURATION, REPEAT)
                play_sound(2)
                print("Low level alarm tone played")
                last_low_alert_time = current_time
        else:
            print("Low glucose alert suppressed to avoid repetition.")
    elif current_glucose > HIGH_THRESHOLD:
        if currently_muted and muted_alert_type != "high":
            clear_mute()

        if not last_high_alert_time or (current_time - last_high_alert_time) > ALERT_REPEAT_TIME:
            if not currently_muted:
                play_alarm(pwm, TONE_HIGH, DURATION, REPEAT)
                play_sound(1)
                print("High level alarm tone played")
            else:
                print("High glucose alert muted.")
            #send_pushover_notification(f"High glucose alert! Current level: {current_glucose} mmol/L.", user_key, api_token)
            last_high_alert_time = current_time
        else:
            print("High glucose alert suppressed to avoid repetition.")
    else:
        if currently_muted and muted_alert_type == "low":
            clear_mute()
        print(f"Glucose levels are normal: {current_glucose} mmol/L.")

    return last_low_alert_time, last_high_alert_time, current_glucose

def authenticate_with_retries(email, password, max_retries=5):
    """Authenticate with LibreLinkUp with retry logic."""
    retry_attempts = 1
    backoff_time = 2  # Initial backoff time in seconds

    while retry_attempts < max_retries:
        try:
            lib_client = PyLibreLinkUp(email=email, password=password, api_url=APIUrl.EU)
            lib_client.authenticate()
            print("Successfully authenticated to LibreLinkUp.")
            return lib_client
        except HTTPError as http_err:
            if http_err.response.status_code == 429:
                print(f"Rate limit exceeded. Retrying in {backoff_time} seconds...")
                time.sleep(backoff_time)
                retry_attempts += 1
                backoff_time *= 1.5  # Exponential backoff
            else:
                print(f"An http error occurred: {http_err}")
                print(f"Retrying in {backoff_time} seconds...")
                time.sleep(backoff_time)
                retry_attempts += 1
                backoff_time *= 1.5  # Exponential backoff
                raise http_err
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            raise e

    raise RuntimeError("Maximum retry attempts exceeded for authentication.")
    
if __name__ == "__main__":
    play_sound(0)

    # Load configuration
    config = load_config('config.json')

    #send_pushover_notification("LibrePush process started", config['pushover_user_key'], config['pushover_api_token'], 1, "falling")

    # Set up the CLK (Clock) and DIO (Data) pins
    CLK_PIN = 3  # Replace with your CLK pin (GPIO number)
    DIO_PIN = 2  # Replace with your DIO pin (GPIO number)

    # Create an instance of the TM1637 class
    display = tm1637.TM1637(clk=CLK_PIN, dio=DIO_PIN)

    # Display brightness (optional, 0 to 7)
    display.brightness(0)

    display.write([0,0,0,0])

    mute_button = Button(KEY_PIN, pull_up=True)

    mute_button.when_pressed = button_press

    while True:
        try:
            # Connect to LibreLinkUp with retries
            lib_client = authenticate_with_retries(config['libre_email'], config['libre_password'])

            # Track the last alert times
            last_low_alert_time = None
            last_high_alert_time = None

            # Continuous monitoring loop
            while True:
                if currently_muted:
                    if datetime.now() > mute_stop_time:
                        clear_mute()

                try:
                    last_low_alert_time, last_high_alert_time, current_glucose = monitor_glucose(
                        lib_client,
                        config['pushover_user_key'],
                        config['pushover_api_token'],
                        last_low_alert_time,
                        last_high_alert_time,
                        display
                    )
                except HTTPError as http_err:
                    if http_err.response.status_code == 429:
                        print("Rate limit hit during glucose monitoring. Pausing for backoff.")
                        time.sleep(60)  # Wait before retrying
                    else:
                        print(f"HTTP error occurred: {http_err}. Reconnecting...")
                        break  # Exit the inner loop to reconnect
                except Exception as e:
                    print(f"An unexpected error occurred during monitoring: {e}. Reconnecting...")
                    break  # Exit the inner loop to reconnect

                time.sleep(1)  # Wait before checking again
                for x in range(10):
                    display_float(display, current_glucose)
                    time.sleep(1)  # Wait before checking again

        except Exception as e:
            print(f"An error occurred while trying to authenticate or monitor: {e}. Retrying...")
            time.sleep(60)  # Wait before trying to reconnect
