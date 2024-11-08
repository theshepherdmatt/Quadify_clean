import time
import threading
import requests
from PIL import Image, ImageDraw, ImageFont
from luma.core.interface.serial import spi
from luma.oled.device import ssd1322
from socketIO_client_nexus import SocketIO, LoggingNamespace
from io import BytesIO
import os

class Playback:
    def __init__(self, device, state, mode_manager, host='localhost', port=3000):
        self.device = device
        self.state = state
        self.mode_manager = mode_manager
        self.host = host
        self.port = port
        self.running = False
        self.VOL_API_URL = "http://localhost:3000/api/v1/getState"
        self.previous_service = None

        # Connect to Volumio via SocketIO
        self.socketIO = SocketIO(self.host, self.port, LoggingNamespace)
        self.socketIO.on('pushState', self.on_push_state)
        self.socketIO_thread = threading.Thread(target=self.socketIO.wait, daemon=True)

        # Load fonts
        font_path = "/home/volumio/Quadify/DSEG7Classic-Light.ttf"
        alt_font_path = "/home/volumio/Quadify/OpenSans-Regular.ttf"
        try:
            self.large_font = ImageFont.truetype(font_path, 48)
            self.alt_font_medium = ImageFont.truetype(alt_font_path, 18)
            self.alt_font = ImageFont.truetype(alt_font_path, 12)
        except IOError:
            print("Font file not found. Please check the font paths.")
            exit()

        # Load icons
        self.icons = {}
        services = ["favourites", "nas", "playlists", "qobuz", "tidal", "default"]
        icon_dir = "/home/volumio/Quadify/icons"
        for service in services:
            try:
                icon_path = os.path.join(icon_dir, f"{service}.bmp")
                self.icons[service] = Image.open(icon_path).convert("RGB").resize((45, 45))
            except IOError:
                print(f"Icon for {service} not found. Please check the path.")

    def on_push_state(self, state):
        """Handles 'pushState' events from Volumio."""
        print(f"Received new state from Volumio: {state}")
        self.state = state
        if state.get("status") == "play":
            if not self.running:
                self.start_display()
        elif state.get("status") in ["pause", "stop"]:
            self.stop_display()

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

    def get_text_dimensions(self, text, font):
        bbox = font.getbbox(text)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        return width, height

    def start_display(self):
        """Start the display update thread."""
        print("Starting display thread.")
        self.running = True
        self.update_thread = threading.Thread(target=self.update_display, daemon=True)
        self.update_thread.start()

    def stop_display(self):
        """Stop the display update thread and clear the display."""
        print("Stopping display thread.")
        self.running = False
        if hasattr(self, 'update_thread'):
            self.update_thread.join()
        self.clear_screen()

    def draw_display(self, data):
        current_service = data.get("service", "default").lower()
        
        # Clear display on service change
        if current_service != self.previous_service:
            self.device.clear()
            self.previous_service = current_service

        # Create a blank image to draw on
        image = Image.new("RGB", (self.device.width, self.device.height), "black")
        draw = ImageDraw.Draw(image)

        # Volume Indicator
        volume = int(data.get("volume", 0))
        print(f"Drawing volume bars for volume level: {volume}")
        self.draw_volume_bars(draw, volume)

        # Display handling based on service
        if current_service == "webradio":
            # Display Webradio with album art and title
            draw.text((self.device.width // 2, 25), "Webradio", font=self.alt_font_medium, fill="white", anchor="mm")
            title = data.get("title", "No Title")
            draw.text((self.device.width // 2, 45), title, font=self.alt_font, fill="white", anchor="mm")

            # Display album art (if available) at the specified location
            album_art_url = data.get("albumart")
            if album_art_url:
                try:
                    response = requests.get(album_art_url)
                    album_art = Image.open(BytesIO(response.content)).resize((60, 60))
                    image.paste(album_art, (120, 10))  # Position album art
                except requests.RequestException:
                    print("Could not load album art")

        else:
            # Display sample rate and bit depth for other services
            sample_rate = data.get("samplerate", "0 KHz")
            sample_rate_value, sample_rate_unit = sample_rate.split() if ' ' in sample_rate else (sample_rate, "")

            try:
                sample_rate_value = str(int(float(sample_rate_value)))
            except ValueError:
                sample_rate_value = "0"

            sample_rate_width, _ = self.get_text_dimensions(sample_rate_value, self.large_font)
            sample_rate_x = self.device.width / 2 - sample_rate_width / 2
            sample_rate_y = 30
            unit_x = sample_rate_x + sample_rate_width - 25
            unit_y = sample_rate_y + 15

            draw.text((sample_rate_x, sample_rate_y), sample_rate_value, font=self.large_font, fill="white", anchor="mm")
            draw.text((unit_x, unit_y), sample_rate_unit, font=self.alt_font, fill="white", anchor="lm")

            # Display audio format and bit depth
            audio_format = data.get("trackType", "Unknown")
            bitdepth = data.get("bitdepth") or "N/A"
            format_bitdepth_text = f"{audio_format}/{bitdepth}"
            draw.text((210, 45), format_bitdepth_text, font=self.alt_font, fill="white", anchor="mm")

            # Display the service icon
            icon = self.icons.get(current_service, self.icons["default"])
            image.paste(icon, (185, -4))

        # Display the image on the OLED screen
        self.device.display(image)

    def draw_volume_bars(self, draw, volume):
        """Draws volume bars on the left side of the display."""
        volume = max(0, min(int(volume), 100))
        filled_squares = round((volume / 100) * 6)
        square_size = 4
        row_spacing = 4
        padding_bottom = 16
        columns = [8, 28]

        for x in columns:
            for row in range(6):
                y = self.device.height - padding_bottom - ((row + 1) * (square_size + row_spacing))
                if row < filled_squares:
                    draw.rectangle([x, y, x + square_size, y + square_size], fill="white")
                else:
                    draw.rectangle([x, y, x + square_size, y + square_size], outline="white")

    def update_display(self):
        while self.running:
            data = self.get_volumio_data()
            if data:
                self.draw_display(data)
            else:
                print("No data received from Volumio.")
            time.sleep(0.05)

    def clear_screen(self):
        """Clears the OLED display."""
        blank_image = Image.new(self.device.mode, (self.device.width, self.device.height), "black")
        self.device.display(blank_image)

    def start(self):
        if not self.running:
            print("Starting Playback mode.")
            self.running = True
            self.socketIO_thread.start()
            self.start_display()
            print("Playback mode started.")

    def stop(self):
        if self.running:
            print("Stopping Playback mode.")
            self.running = False
            if self.update_thread:
                self.update_thread.join()
            self.socketIO.disconnect()
            self.clear_screen()
            print("Playback mode stopped and screen cleared.")

    def set_volume(self, volume):
        """Sets the volume on Volumio."""
        print(f"Setting volume to: {volume}")
        self.socketIO.emit('volume', volume)

# Main Execution
if __name__ == "__main__":
    try:
        serial = spi(device=0, port=0)
        device = ssd1322(serial, rotate=2)
        playback = Playback(device, state={}, mode_manager=None)
        playback.start()
        print("Press Ctrl+C to exit.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        playback.stop()
    except Exception as e:
        print(f"An error occurred: {e}")
        playback.stop()
