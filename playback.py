import time
import threading
import requests
from luma.core.interface.serial import spi
from luma.oled.device import ssd1322
from PIL import Image, ImageDraw, ImageFont
from socketIO_client_nexus import SocketIO, LoggingNamespace


class Playback:
    def __init__(self, device, state, mode_manager, host='localhost', port=3000):
        # Store the device reference
        self.device = device
        self.state = state
        self.mode_manager = mode_manager
        self.host = host
        self.port = port
        
        self.socketIO = SocketIO(self.host, self.port, LoggingNamespace)

        # Load fonts
        font_path = "/home/volumio/Quadify/DSEG7Classic-Light.ttf"
        alt_font_path = "/home/volumio/Quadify/OpenSans-Regular.ttf"
        try:
            self.large_font = ImageFont.truetype(font_path, 45)
            self.small_font = ImageFont.truetype(font_path, 8)
            self.alt_font = ImageFont.truetype(alt_font_path, 12)
            self.alt_font_small = ImageFont.truetype(alt_font_path, 12)
            self.alt_font_smaller = ImageFont.truetype(alt_font_path, 8)
        except IOError:
            print("Font file not found. Please check the font paths.")
            exit()

        # Load the Tidal logo
        try:
            self.tidal_logo = Image.open("/home/volumio/Quadify/tidal.bmp").convert("1").resize((12, 12))
        except IOError:
            print("Logo file not found. Please check the path to the logo image.")
            exit()

        self.running = False
        self.update_thread = None
        self.VOL_API_URL = "http://localhost:3000/api/v1/getState"

    def get_volumio_data(self):
        try:
            response = requests.get(self.VOL_API_URL)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to connect to Volumio. Status code: {response.status_code}")
        except requests.RequestException as e:
            print(f"Error fetching data from Volumio: {e}")
        return None

    def draw_display(self, data):
        # Create a blank image to draw on
        image = Image.new("RGB", (self.device.width, self.device.height), "black")
        draw = ImageDraw.Draw(image)

        # Extract the relevant data from Volumio
        volume = data.get("volume", 0)  # Get the volume, default to 0 if not available
        try:
            volume = int(volume)
        except (ValueError, TypeError):
            volume = 0  # Fallback to 0 if conversion fails

        # Clamp volume between 0 and 100
        volume = max(0, min(volume, 100))

        # Extract other relevant data from Volumio
        sample_rate = data.get("samplerate", "0 kHz") or "0 kHz"
        if ' ' in sample_rate:
            sample_rate_value, sample_rate_unit = sample_rate.split()
        else:
            sample_rate_value, sample_rate_unit = (sample_rate, '')

        sample_rate_value = sample_rate_value.rjust(4)  # Right-justify the value to ensure alignment
        sample_rate_unit = sample_rate_unit.lower()

        audio_format = data.get("trackType", "Unknown") or "Unknown"
        bitrate = data.get("bitrate", "Unknown") or "Unknown"
        if bitrate == "Unknown":
            # Use bitdepth if bitrate is not provided
            bitdepth = data.get("bitdepth", "")
            bitrate = f"{bitdepth}" if bitdepth else "Unknown"

        # Determine the service being used and add the Tidal logo if it's Tidal
        service = data.get("service", "unknown").lower()
        if "tidal" in service:
            image.paste(self.tidal_logo, (200, 10))  # Position the Tidal logo above the bitrate (adjust coordinates as needed)

        # Draw sample rate with unit in the center
        draw.text((self.device.width / 2 + -10, self.device.height / 2 - 4), sample_rate_value, font=self.large_font, fill="white", anchor="mm")
        draw.text((self.device.width / 2 + 45, self.device.height / 1.5 + 2), sample_rate_unit, font=self.alt_font_small, fill="white", anchor="lm")

        # Draw audio format to the right of the sample rate
        draw.text((self.device.width * 0.9, self.device.height * 0.2), audio_format, font=self.alt_font, fill="white", anchor="mm")

        # Draw bitrate below the audio format
        draw.text((self.device.width * 0.9, self.device.height * 0.4), bitrate, font=self.alt_font, fill="white", anchor="mm")

        # Calculate number of squares to fill based on volume (0-100 mapped to 6 squares)
        filled_squares = round((volume / 100) * 6)

        # Draw the two vertical columns of 6 smaller squares filling from bottom up
        square_size = 4      # Size of each square
        row_spacing = 4      # Spacing between squares vertically
        padding_bottom = 12  # Padding from the bottom of the display
        columns = [8, 28]   # Original x positions for the two columns

        for x in columns:
            for row in range(6):
                # Calculate y starting from the bottom
                y = self.device.height - padding_bottom - ((row + 1) * (square_size + row_spacing))

                # Draw the word 'Volume' below the squares after drawing the last row
                if row == 5 and x == columns[1]:
                    draw.text((columns[0], self.device.height - padding_bottom + 4), 'Volume', font=self.alt_font_smaller, fill="white", anchor="lm")

                if row < filled_squares:
                    # Filled square
                    draw.rectangle([x, y, x + square_size, y + square_size], fill="white")
                else:
                    # Empty square (only outline)
                    draw.rectangle([x, y, x + square_size, y + square_size], outline="white")

        # Display the image on the device
        self.device.display(image)

    def start(self):
        if not self.running:
            self.running = True
            self.update_thread = threading.Thread(target=self.update_display)
            self.update_thread.start()
            print("Playback mode started.")

    def stop(self):
        if self.running:
            self.running = False
            if self.update_thread:
                self.update_thread.join()
            self.mode_manager.clear_screen()  # Clear the screen before stopping
            print("Playback mode stopped and screen cleared.")

    def update_display(self):
        while self.running:
            data = self.get_volumio_data()
            if data:
                self.draw_display(data)
            else:
                print("No data received from Volumio.")
            time.sleep(2)  # Update every 2 seconds

    def toggle_play_pause(self):
        # Emit the play/pause command to Volumio
        print("Toggling play/pause")
        self.socketIO.emit('toggle')
        

# Example usage
if __name__ == "__main__":
    # Assuming you have a device object to pass
    serial = spi(device=0, port=0)
    device = ssd1322(serial, rotate=2)

    # Pass a dummy mode_manager or None (if it's just for testing without ModeManager implementation)
    playback = Playback(device, state={}, mode_manager=None)  # Updated this line
    try:
        playback.start()
        time.sleep(10)
    finally:
        playback.stop()
