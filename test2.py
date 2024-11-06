import smbus
import time
import json
import requests
from socketIO_client_nexus import SocketIO
from subprocess import call

# MCP23017 Register Definitions
MCP23017_ADDRESS = 0x20
MCP23017_IODIRA = 0x00
MCP23017_IODIRB = 0x01
MCP23017_GPIOA = 0x12
MCP23017_GPIOB = 0x13
MCP23017_GPPUA = 0x0C
MCP23017_GPPUB = 0x0D

class ButtonsLEDController:
    def __init__(self, debounce_delay=0.1):
        self.bus = smbus.SMBus(1)  # Initialize I2C bus
        self.debounce_delay = debounce_delay
        self.prev_button_state = [[1, 1], [1, 1], [1, 1], [1, 1]]  # Default to 'not pressed' state
        self.led_state = 0
        self.button_map = [[2, 1], [4, 3], [6, 5], [8, 7]]  # Button matrix layout
        self.volumioIO = SocketIO('localhost', 3000)  # Volumio SocketIO connection
        
        # Initialize MCP23017 I/O expander
        self._initialize_mcp23017()

    def _initialize_mcp23017(self):
        """Configure MCP23017 I/O expander for buttons and LEDs."""
        print("Configuring MCP23017 I/O expander.")
        self.bus.write_byte_data(MCP23017_ADDRESS, MCP23017_IODIRB, 0x3C)  # Set inputs/outputs for Port B
        self.bus.write_byte_data(MCP23017_ADDRESS, MCP23017_GPPUB, 0x3C)   # Enable pull-ups for PB2-PB5
        self.bus.write_byte_data(MCP23017_ADDRESS, MCP23017_IODIRA, 0x00)  # Set Port A as outputs for LEDs
        self.bus.write_byte_data(MCP23017_ADDRESS, MCP23017_GPIOA, 0x00)   # Turn off all LEDs initially

    def read_button_matrix(self):
        """Reads button matrix and returns current state."""
        button_matrix_state = [[0, 0], [0, 0], [0, 0], [0, 0]]
        for column in range(2):
            self.bus.write_byte_data(MCP23017_ADDRESS, MCP23017_GPIOB, ~(1 << column) & 0x03)
            row_state = self.bus.read_byte_data(MCP23017_ADDRESS, MCP23017_GPIOB) & 0x3C
            for row in range(4):
                button_matrix_state[row][column] = (row_state >> (row + 2)) & 1
        print(f"Button matrix state: {button_matrix_state}")  # Debugging print
        return button_matrix_state

    def control_leds(self, state):
        """Sets the LED state on Port A."""
        print(f"Setting LED state to: {bin(state)}")
        self.bus.write_byte_data(MCP23017_ADDRESS, MCP23017_GPIOA, state)
        time.sleep(0.1)
        # Verify LED state
        read_back = self.bus.read_byte_data(MCP23017_ADDRESS, MCP23017_GPIOA)
        if read_back != state:
            print("LED state did not match; retrying...")
            self.bus.write_byte_data(MCP23017_ADDRESS, MCP23017_GPIOA, state)

    def handle_button_press(self, button_id):
        """Handles button actions based on button_id."""
        print(f"Handling button {button_id} press")  # Debugging print
        command = self.get_volumio_command(button_id)
        if command:
            self.execute_volumio_command(command)
        # Update LEDs for the current button
        self.led_state = 1 << (8 - button_id)
        self.control_leds(self.led_state)

    def get_volumio_command(self, button_id):
        """Maps button IDs to Volumio commands."""
        commands = {
            1: "play",
            2: "pause",
            3: "previous",
            4: "next",
            5: "setRepeat",
            6: "setRandom",
        }
        return commands.get(button_id, "")

    def execute_volumio_command(self, command):
        """Sends a command to Volumio via SocketIO."""
        try:
            print(f"Executing Volumio command: {command}")
            self.volumioIO.emit(command)
        except Exception as e:
            print(f"Error sending command '{command}' to Volumio: {e}")

    def check_buttons_and_update_leds(self):
        """Main loop to check button states and update LEDs."""
        button_matrix = self.read_button_matrix()
        
        for row in range(4):
            for col in range(2):
                button_id = self.button_map[row][col]
                current_button_state = button_matrix[row][col]

                # Check if button has just been pressed
                if current_button_state == 0 and self.prev_button_state[row][col] != current_button_state:
                    print(f"Button {button_id} pressed")  # Debugging print
                    self.handle_button_press(button_id)

                # Update previous button state
                self.prev_button_state[row][col] = current_button_state

        time.sleep(self.debounce_delay)

def main():
    controller = ButtonsLEDController()
    print("Starting button and LED test loop. Press Ctrl+C to stop.")
    try:
        while True:
            controller.check_buttons_and_update_leds()
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Test stopped by user.")

if __name__ == "__main__":
    main()
