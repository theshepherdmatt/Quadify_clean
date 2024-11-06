from PIL import Image, ImageDraw, ImageFont

class PlaylistManager:
    def __init__(self, oled, volumio_listener, mode_manager):
        self.oled = oled
        self.font_path = "/home/volumio/Quadify/oled/OpenSans-Regular.ttf"
        try:
            self.font = ImageFont.truetype(self.font_path, 12)
        except IOError:
            print(f"Font file not found at {self.font_path}. Using default font.")
            self.font = ImageFont.load_default()

        self.playlists = []
        self.current_selection_index = 0
        self.is_active = False
        self.is_loading = False  # Track if loading is in progress
        self.volumio_listener = volumio_listener
        self.mode_manager = mode_manager
        self.mode_manager.add_on_mode_change_callback(self.handle_mode_change)
        self.volumio_listener.register_playlists_callback(self.update_playlists)

    def handle_mode_change(self, current_mode):
        if current_mode == "playlist":
            print("Entering playlist mode...")
            self.start_playlist_mode()
        else:
            if self.is_active:
                print("Exiting playlist mode...")
                self.stop_playlist_mode()

    def start_playlist_mode(self):
        self.is_active = True
        self.is_loading = True  # Set loading flag to true
        self.current_selection_index = 0
        self.playlists = []
        self.display_loading_screen()
        self.volumio_listener.fetch_playlists()

    def display_loading_screen(self):
        self.clear_display()  # Clear display first
        image = Image.new(self.oled.mode, (self.oled.width, self.oled.height), "black")
        draw = ImageDraw.Draw(image)
        loading_text = "Loading Playlists..."
        w, h = draw.textsize(loading_text, font=self.font)
        x = (self.oled.width - w) / 2
        y = (self.oled.height - h) / 2
        draw.text((x, y), loading_text, font=self.font, fill="white")
        self.oled.display(image)

    def stop_playlist_mode(self):
        self.is_active = False
        self.clear_display()

    def update_playlists(self, playlists):
        print(f"[Debug] update_playlists called with playlists: {playlists}")
        
        # Update playlists only if we're in playlist mode
        if self.is_active:
            self.is_loading = False  # Loading complete
            self.playlists = playlists or []  # Overwrite playlists
            
            # If playlists are empty, show a no playlists message
            if not self.playlists:
                self.display_no_playlists_message()
            else:
                self.display_playlists()

    def display_playlists(self):
        self.clear_display()  # Clear screen before displaying playlists
        
        if not self.playlists:
            self.display_no_playlists_message()
            return

        image = Image.new(self.oled.mode, (self.oled.width, self.oled.height), "black")
        draw = ImageDraw.Draw(image)
        y_offset = 1
        x_offset = 10

        for i, playlist in enumerate(self.playlists):
            title = playlist['title']
            if i == self.current_selection_index:
                draw.text((x_offset, y_offset), "->", font=self.font, fill="white")
                draw.text((x_offset + 20, y_offset), title, font=self.font, fill="white")
            else:
                draw.text((x_offset + 20, y_offset), title, font=self.font, fill="gray")
            y_offset += 15

        self.oled.display(image)

    def display_no_playlists_message(self):
        self.clear_display()  # Clear screen before displaying message
        image = Image.new(self.oled.mode, (self.oled.width, self.oled.height), "black")
        draw = ImageDraw.Draw(image)
        message = "No Playlists Found"
        w, h = draw.textsize(message, font=self.font)
        x = (self.oled.width - w) / 2
        y = (self.oled.height - h) / 2
        draw.text((x, y), message, font=self.font, fill="white")
        self.oled.display(image)

    def clear_display(self):
        """Clears the OLED display by setting it to black."""
        if self.oled:
            image = Image.new(self.oled.mode, (self.oled.width, self.oled.height), "black")
            self.oled.display(image)
