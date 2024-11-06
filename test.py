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

# Initialize I2C bus and set up MCP23017
bus = smbus.SMBus(1)

# SocketIO setup for Volumio
VOLUMIO_URL = "http://localhost:3000/api/v1/commands/?cmd="
volumioIO = SocketIO('localhost', 3000)

# Button and LED mappings
button_map = [[2, 1], [4, 3], [6, 5], [8, 7]]
prev_button_state = [[1, 1], [1, 1], [1, 1], [1, 1]]
led_state = 0

def initialize_mcp23017():
    print("Configuring MCP23017 I/O expander.")
    bus.write_byte_data(MCP23017_ADDRESS, MCP23017_IODIRB, 0x3C)
    bus.write_byte_data(MCP23017_ADDRESS, MCP23017_GPPUB, 0x3C)
    bus.write_byte_data(MCP23017_ADDRESS, MCP23017_IODIRA, 0x00)
    bus.write_byte_data(MCP23017_ADDRESS, MCP23017_GPIOA, 0x00)  # Turn off all LEDs initially

def control_leds(state):
    print(f"Setting LED state to: {bin(state)}")
    bus.write_byte_data(MCP23017_ADDRESS, MCP23017_GPIOA, state)
    time.sleep(0.1)
    read_back = bus.read_byte_data(MCP23017_ADDRESS, MCP23017_GPIOA)
    if read_back != state:
        print("LED state did not match; retrying...")
        bus.write_byte_data(MCP23017_ADDRESS, MCP23017_GPIOA, state)

def read_button_matrix():
    button_matrix_state = [[0, 0], [0, 0], [0, 0], [0, 0]]
    for column in range(2):
        bus.write_byte_data(MCP23017_ADDRESS, MCP23017_GPIOB, ~(1 << column) & 0x03)
        row_state = bus.read_byte_data(MCP23017_ADDRESS, MCP23017_GPIOB) & 0x3C
        for row in range(4):
            button_matrix_state[row][column] = (row_state >> (row + 2)) & 1
    return button_matrix_state

def execute_volumio_command(command):
    try:
        print(f"Executing Volumio command: {command}")
        volumioIO.emit(command)
    except Exception as e:
        print(f"Error sending command '{command}' to Volumio: {e}")

def restart_oled_service():
    print("Restarting OLED service...")
    call("sudo systemctl restart oled.service", shell=True)

def handle_button_press(button_id):
    global led_state
    if button_id == 7:
        add_to_favourites()
    elif button_id == 8:
        restart_oled_service()
    else:
        command = get_volumio_command(button_id)
        if command:
            execute_volumio_command(command)

    # Update LEDs for the current button
    led_state = 1 << (8 - button_id)
    control_leds(led_state)

def get_volumio_command(button_id):
    commands = {
        1: "play",
        2: "pause",
        3: "previous",
        4: "next",
        5: "setRepeat",
        6: "setRandom",
    }
    return commands.get(button_id, "")

def add_to_favourites():
    print("Adding current track to favourites.")
    volumioIO.emit('getState')

    @volumioIO.on('pushState')
    def on_state(state):
        track_uri = state.get("uri")
        if track_uri:
            volumioIO.emit('addToFavourites', {'service': 'mpd', 'uri': track_uri})
            print(f"Track added to favourites: {track_uri}")
        else:
            print("No track currently playing.")

def check_buttons_and_update_leds():
    global prev_button_state
    button_matrix = read_button_matrix()

    for row in range(4):
        for col in range(2):
            button_id = button_map[row][col]
            current_button_state = button_matrix[row][col]
            if current_button_state == 0 and prev_button_state[row][col] != current_button_state:
                print(f"Button {button_id} pressed")
                handle_button_press(button_id)
            prev_button_state[row][col] = current_button_state

    time.sleep(0.1)
    check_buttons_and_update_leds()

def update_play_pause_leds():
    try:
        response = requests.get("http://localhost:3000/api/v1/getState")
        state = response.json().get("status")
        if state == "play":
            led_state = 1
        elif state == "pause":
            led_state = 2
        control_leds(led_state)
    except Exception as e:
        print(f"Error updating play/pause LEDs: {e}")

def start_status_update_loop():
    while True:
        update_play_pause_leds()
        time.sleep(5)

initialize_mcp23017()
check_buttons_and_update_leds()
start_status_update_loop()
