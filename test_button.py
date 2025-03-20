from gpiozero import Button
from signal import pause

# Define GPIO pins
KEY_PIN = 14  # Connected to KEY

def button_press():
    print("Button Pressed!")

key = Button(KEY_PIN, pull_up=True)

key.when_pressed = button_press

print("Rotary Encoder Test Initialized.")
print("Listening for input. Press CTRL+C to exit.")

# Keep the script running
pause()
