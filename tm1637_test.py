import tm1637
import time
from RPi import GPIO  # For controlling GPIO pins on the Raspberry Pi

# Set up the CLK (Clock) and DIO (Data) pins
CLK_PIN = 3  # Replace with your CLK pin (GPIO number)
DIO_PIN = 2  # Replace with your DIO pin (GPIO number)

# Create an instance of the TM1637 class
display = tm1637.TM1637(clk=CLK_PIN, dio=DIO_PIN)

# Display brightness (optional, 0 to 7)
display.brightness(0)

# Example: Display a number (4 digits)
display.show('1234')

# Clear the display
time.sleep(2)
#display.clear()

# Example: Display individual segments (can handle more custom displays)
#display.show([1, 2, 3, 4])  # This will show segments for digits 1, 2, 3, 4
