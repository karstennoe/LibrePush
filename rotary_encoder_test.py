from gpiozero import Button
from signal import pause

# Define GPIO pins
S1_PIN = 18  # Connected to S1
S2_PIN = 15  # Connected to S2
KEY_PIN = 14  # Connected to KEY

# Variables to track the encoder state
counter = 0

# Define functions for handling rotary encoder
def rotary_turn():
    global counter
    if s1.is_pressed == s2.is_pressed:
        counter += 1
    else:
        counter -= 1
    print(f"Counter: {counter}")

def button_press():
    print("Button Pressed!")

# Setup gpiozero buttons
s1 = Button(S1_PIN, pull_up=True)
s2 = Button(S2_PIN, pull_up=True)
key = Button(KEY_PIN, pull_up=True)

# Add event handlers
s1.when_pressed = rotary_turn
key.when_pressed = button_press

print("Rotary Encoder Test Initialized.")
print("Listening for input. Press CTRL+C to exit.")

# Keep the script running
pause()
