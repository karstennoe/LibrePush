import RPi.GPIO as GPIO
import time

# Constants
PIN = 16  # GPIO pin where the piezo speaker is connected
TONE_HIGH = 220  # Frequency of the high tone in Hz
TONE_LOW = 800/4    # Frequency of the low tone in Hz
DURATION = 0.6    # Duration of each tone in seconds
REPEAT = 5       # Number of repetitions for the alarm sound

def setup_pwm():
    """Setup GPIO pin for PWM."""
    GPIO.setmode(GPIO.BCM)  # Use BCM pin numbering
    GPIO.setup(PIN, GPIO.OUT)
    pwm = GPIO.PWM(PIN, TONE_HIGH)  # Initialize PWM with an initial frequency
    pwm.start(0)  # Start PWM with 0% duty cycle (off)
    return pwm

def play_alarm(pwm, tone_high, duration, repeat):
    """
    Play a standard alarm clock sound.
    :param pwm: PWM object
    :param tone_high: Frequency of the high tone in Hz
    :param tone_low: Frequency of the low tone in Hz
    :param duration: Duration of each tone in seconds
    :param repeat: Number of repetitions for the alarm sound
    """
    for _ in range(repeat):
        pwm.ChangeFrequency(tone_high)  # Play high tone
        pwm.ChangeDutyCycle(5)        # 50% duty cycle for a clean tone
        time.sleep(duration)           # Wait for the tone duration

        pwm.ChangeDutyCycle(0)  # Turn off the sound
        time.sleep(duration)
    pwm.ChangeDutyCycle(0)  # Turn off the sound

if __name__ == "__main__":
    try:
        pwm = setup_pwm()
        print("Playing alarm sound...")
        play_alarm(pwm, TONE_HIGH, DURATION, REPEAT)
        print("Alarm finished!")
    except KeyboardInterrupt:
        print("Interrupted!")
    finally:
        pwm.stop()  # Stop PWM
        GPIO.cleanup()  # Clean up GPIO settings
