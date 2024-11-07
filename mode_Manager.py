import time
import threading
import RPi.GPIO as GPIO
from PIL import Image
from playback import Playback
from menus import PlaylistManager, RadioManager

last_button_press_time = 0  # Initialize button press debounce timer

class ModeManager:
    def __init__(self, oled, clock, menu_manager=None, playlist_manager=None, radio_manager=None, volumio_listener=None, rotary_control=None):
        self.current_mode = "clock"
        self.home_mode = "clock"
        self.is_playing = False
        self.on_mode_change_callbacks = []
        self.oled = oled
        self.clock = clock
        self.menu_manager = menu_manager
        self.playlist_manager = playlist_manager
        self.radio_manager = radio_manager
        self.playback = None
        self.volumio_listener = volumio_listener
        self.mode_lock = threading.Lock()
        self._blank_image = Image.new(oled.mode, (oled.width, oled.height), "black") if oled else None
        self.last_button_press_time = 0
        self.rotary_control = rotary_control

    def set_mode(self, new_mode, playback_state=None):
        with self.mode_lock:
            if self.current_mode == new_mode:
                if new_mode == "clock" and not self.clock.running:
                    self.clock.start()
                    print("Clock mode re-started because it was inactive.")
                print(f"Already in {new_mode} mode. Skipping re-entry.")
                return

            # Clear screen only if switching modes
            if self.current_mode != new_mode:
                print(f"Transitioning from '{self.current_mode}' to '{new_mode}'. Clearing screen.")
                self.clear_screen()

            # Exit and switch mode
            self._exit_current_mode()
            self.current_mode = new_mode
            self._enter_new_mode(new_mode, playback_state)
            self.notify_mode_change()

    def get_mode(self):
        return self.current_mode

    def clear_screen(self):
        if self.oled and self._blank_image:
            self.oled.display(self._blank_image)
            print("OLED display cleared.")

    def process_state_change(self, state):
        """Handles playback state changes and updates mode accordingly."""
        status = state.get("status", "")
        self.is_playing = status == "play"

        if self.is_playing:
            # Enter playback mode if there's active playback
            self.set_mode("playback", playback_state=state)
        else:
            # Stop playback and revert to clock mode if playback stops or pauses
            print(f"Playback stopped or paused. Switching to clock mode.")
            self.set_mode("clock")

    def handle_rotation(self, direction):
        current_mode = self.get_mode()
        print(f"Rotary turned {direction}. Current mode: {current_mode}")

        if current_mode == "menu" and self.menu_manager:
            self.menu_manager.scroll_selection(direction)
        elif current_mode == "webradio" and self.radio_manager:
            self.radio_manager.scroll_selection(direction)
        elif current_mode == "playlist" and self.playlist_manager:
            self.playlist_manager.scroll_selection(direction)
        elif current_mode == "playback":
            volume_change = 5 * direction  # 5 for clockwise, -5 for counterclockwise
            self.adjust_volume(volume_change)
        else:
            print(f"Unhandled mode '{current_mode}' in handle_rotation")

    def handle_button_press(self):
        global last_button_press_time
        current_time = time.time()

        # Debounce logic to avoid multiple triggers in a short span
        if current_time - last_button_press_time < 0.3:  # Adjust debounce time if needed
            print("Button press ignored due to debounce.")
            return

        last_button_press_time = current_time
        button_pressed_time = time.time()

        # Detect if the button is held down
        while GPIO.input(self.rotary_control.SW_PIN) == GPIO.LOW:
            time.sleep(0.1)
            if time.time() - button_pressed_time > 1.5:  # Long press detected after 1.5 seconds
                print("Long button press detected: Switching to clock mode.")
                if self.current_mode != "clock":
                    self.set_mode("clock")  # Enter clock mode immediately

                # Keep checking the button state until it’s released
                while GPIO.input(self.rotary_control.SW_PIN) == GPIO.LOW:
                    time.sleep(0.1)  # Continue to hold clock mode while button is pressed

                print("Button released; remaining in clock mode.")
                return  # Exit function upon button release

        # Regular short press actions
        current_mode = self.get_mode()
        print(f"Button short-pressed in mode: {current_mode}")
        if current_mode == "menu":
            self.menu_manager.select_item()
        elif current_mode == "webradio":
            self.radio_manager.select_item()
        elif current_mode == "playlist":
            self.playlist_manager.select_playlist()
        elif current_mode == "clock":
            self.set_mode("menu")
        elif current_mode == "playback":
            if self.playback:
                self.playback.toggle_play_pause()
        else:
            print("Button short-press in unrecognized mode.")


    def _exit_current_mode(self):
        if self.current_mode == "clock" and self.clock.running:
            self.clock.stop()
            print("Clock mode stopped.")
        elif self.current_mode == "playback":
            self.stop_playback()
        elif self.current_mode == "menu" and self.menu_manager:
            self.menu_manager.stop_menu_mode()
            print("Stopping menu mode.")
        elif self.current_mode == "webradio" and self.radio_manager:
            self.radio_manager.stop_mode()
            print("Stopping radio mode.")
        elif self.current_mode == "playlist" and self.playlist_manager:
            self.playlist_manager.stop_playlist_mode()
            print("Stopping playlist mode.")

    def _enter_new_mode(self, new_mode, playback_state):
        if new_mode == "clock":
            self.clock.start()
            print("Clock mode started and displayed.")
        elif new_mode == "playback" and playback_state:
            self.start_playback(playback_state)
        elif new_mode == "menu" and self.menu_manager:
            self.menu_manager.start_menu_mode()
        elif new_mode == "webradio" and self.radio_manager:
            self.radio_manager.start_radio_mode()
        elif new_mode == "playlist" and self.playlist_manager:
            self.playlist_manager.start_playlist_mode()

    def start_playback(self, playback_state):
        if not self.playback:
            self.playback = Playback(self.oled, playback_state, self)
        if not self.playback.running:
            self.playback.start()
            print("Playback mode started.")
        self.is_playing = True

    def stop_playback(self):
        if self.playback and self.playback.running:
            self.playback.stop()
            self.playback = None
            self.is_playing = False
            print("Playback mode stopped.")

    def notify_mode_change(self):
        print(f"Mode changed to: {self.current_mode}")
        for callback in self.on_mode_change_callbacks:
            try:
                callback(self.current_mode)
            except Exception as e:
                print(f"Error in callback execution: {e}")

    def add_on_mode_change_callback(self, callback):
        if callable(callback):
            self.on_mode_change_callbacks.append(callback)
            print(f"Added mode change callback: {callback}")
