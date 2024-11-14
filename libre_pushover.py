import json
import time
from pushover_complete import PushoverAPI
from pylibrelinkup import PyLibreLinkUp
from datetime import datetime, timedelta
import requests
from requests.exceptions import HTTPError

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

def monitor_glucose(lib_client, user_key, api_token, last_low_alert_time, last_high_alert_time):
    """Check glucose values from the LibreLinkUp client and send notifications if necessary."""
    patients = lib_client.get_patients()
    if not patients:
        print("No patients found.")
        return last_low_alert_time, last_high_alert_time

    patient = patients[0]  # Assuming we're interested in the first patient
    glucose_data = lib_client.read(patient_identifier=patient.patient_id)
    current_glucose = glucose_data.current.value

    # Glucose level thresholds (modify as needed)
    LOW_THRESHOLD = 4.0  # mmol/L
    HIGH_THRESHOLD = 12.0  # mmol/L

    # Current time
    current_time = datetime.now()
    ten_minutes = timedelta(minutes=10)

    if current_glucose < LOW_THRESHOLD:
        if not last_low_alert_time or (current_time - last_low_alert_time) > ten_minutes:
            send_pushover_notification(f"Low glucose alert! Current level: {current_glucose} mmol/L.", user_key, api_token, 2, "falling")
            last_low_alert_time = current_time
        else:
            print("Low glucose alert suppressed to avoid repetition.")
    elif current_glucose > HIGH_THRESHOLD:
        if not last_high_alert_time or (current_time - last_high_alert_time) > ten_minutes:
            send_pushover_notification(f"High glucose alert! Current level: {current_glucose} mmol/L.", user_key, api_token)
            last_high_alert_time = current_time
        else:
            print("High glucose alert suppressed to avoid repetition.")
    else:
        print(f"Glucose levels are normal: {current_glucose} mmol/L.")

    return last_low_alert_time, last_high_alert_time

def authenticate_with_retries(email, password, max_retries=5):
    """Authenticate with LibreLinkUp with retry logic."""
    retry_attempts = 0
    backoff_time = 5  # Initial backoff time in seconds

    while retry_attempts < max_retries:
        try:
            lib_client = PyLibreLinkUp(email=email, password=password)
            lib_client.authenticate()
            print("Successfully authenticated to LibreLinkUp.")
            return lib_client
        except HTTPError as http_err:
            if http_err.response.status_code == 429:
                print(f"Rate limit exceeded. Retrying in {backoff_time} seconds...")
                time.sleep(backoff_time)
                retry_attempts += 1
                backoff_time *= 2  # Exponential backoff
            else:
                raise http_err
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            raise e

    raise RuntimeError("Maximum retry attempts exceeded for authentication.")
    
if __name__ == "__main__":
    # Load configuration
    config = load_config('config.json')

    send_pushover_notification("LibrePush process started", config['pushover_user_key'], config['pushover_api_token'], 1, "falling")

    while True:
        try:
            # Connect to LibreLinkUp with retries
            lib_client = authenticate_with_retries(config['libre_email'], config['libre_password'])

            # Track the last alert times
            last_low_alert_time = None
            last_high_alert_time = None

            # Continuous monitoring loop
            while True:
                try:
                    last_low_alert_time, last_high_alert_time = monitor_glucose(
                        lib_client,
                        config['pushover_user_key'],
                        config['pushover_api_token'],
                        last_low_alert_time,
                        last_high_alert_time
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

                time.sleep(60)  # Wait before checking again

        except Exception as e:
            print(f"An error occurred while trying to authenticate or monitor: {e}. Retrying...")
            time.sleep(60)  # Wait before trying to reconnect
