import time
import threading
from PIL import Image
from playback import Playback
from menus import PlaylistManager, RadioManager

class ModeManager:
    def __init__(self, oled, clock, menu_manager=None, playlist_manager=None, radio_manager=None, volumio_listener=None):
        self.current_mode = "clock"
        self.home_mode = "clock"
        self.is_playing = False
        self.on_mode_change_callbacks = []
        self.timer_thread = None
        self.timer_running = False
        self.oled = oled
        self.clock = clock
        self.menu_manager = menu_manager
        self.playlist_manager = playlist_manager
        self.radio_manager = radio_manager
        self.playback = None
        self.volumio_listener = volumio_listener
        self.mode_lock = threading.Lock()
        self._blank_image = Image.new(oled.mode, (oled.width, oled.height), "black") if oled else None

    def set_mode(self, new_mode, playback_state=None):
        with self.mode_lock:
            if self.current_mode == new_mode:
                print(f"Already in {new_mode} mode. Skipping re-entry.")
                return
            
            # Clear the screen when switching from clock to another mode
            if self.current_mode == "clock" and new_mode != "clock":
                self.clear_screen()
                print("Screen cleared for mode transition from clock to another mode.")

            print(f"Changing mode from '{self.current_mode}' to '{new_mode}'.")
            self._exit_current_mode()
            self.current_mode = new_mode
            self._enter_new_mode(new_mode, playback_state)

            # Notify callbacks of mode change
            self.notify_mode_change()

            # Start a timeout to revert to clock after inactivity if not in play mode
            if new_mode != self.home_mode and not self.is_playing:
                self.start_timer(timeout=10)

    def clear_screen(self):
        """Clears the OLED display."""
        if self.oled and self._blank_image:
            self.oled.display(self._blank_image)
            print("OLED display cleared by ModeManager.")


    def process_state_change(self, state):
        """Handles playback state changes and updates mode accordingly."""
        status = state.get("status", "")
        self.is_playing = status == "play"
        if self.is_playing:
            self.set_mode("playback", playback_state=state)
        else:
            self._start_clock_timer(timeout=5)
    
    def get_mode(self):
        """Returns the current mode."""
        return self.current_mode

    def set_mode(self, new_mode, playback_state=None):
        with self.mode_lock:
            if self.current_mode == new_mode and new_mode == "clock":
                # Even if in clock mode, ensure the clock is running
                if not self.clock.running:
                    self.clock.start()
                    print("Clock mode re-started as it was not running.")
                print("Already in clock mode. Skipping re-entry.")
                return
            elif self.current_mode == new_mode:
                print(f"Already in {new_mode} mode. Skipping re-entry.")
                return

            # Clear the screen before switching modes
            print("Clearing screen before changing modes.")
            self.clear_screen()

            print(f"Changing mode from '{self.current_mode}' to '{new_mode}'.")
            self._exit_current_mode()
            self.current_mode = new_mode
            self._enter_new_mode(new_mode, playback_state)

            # Notify callbacks of mode change
            self.notify_mode_change()

            # Start a timeout to revert to clock after inactivity if not in play mode
            if new_mode != self.home_mode and not self.is_playing:
                self.start_timer(timeout=15)


    def _exit_current_mode(self):
        """Exits the current mode by stopping relevant components."""
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
        """Starts components related to the new mode."""
        if new_mode == "clock":
            self.clock.start()
            print("Clock mode started.")
        elif new_mode == "playback" and playback_state:
            self.start_playback(playback_state)
        elif new_mode == "menu" and self.menu_manager:
            self.menu_manager.start_menu_mode()
        elif new_mode == "webradio":
            if not self.radio_manager:
                self.radio_manager = RadioManager(self.oled, self.volumio_listener, self)
                print("[ModeManager] Initialized RadioManager.")
            self.radio_manager.start_radio_mode()
        elif new_mode == "playlist" and self.playlist_manager:
            self.playlist_manager.start_playlist_mode()

    def start_playback(self, playback_state):
        """Starts playback mode."""
        if not self.playback:
            self.playback = Playback(self.oled, playback_state, self)
        if not self.playback.running:
            self.playback.start()
            print("Playback mode started.")
        self.is_playing = True

    def stop_playback(self):
        """Stops playback if active."""
        if self.playback and self.playback.running:
            self.playback.stop()
            self.playback = None
            self.is_playing = False
            print("Playback mode stopped.")

    def start_timer(self, timeout=15):
        """Starts or resets a timer to revert to clock mode."""
        self.stop_timer()
        def timer_function():
            print(f"Timer started for {timeout} seconds.")
            time.sleep(timeout)
            if not self.is_playing:
                self.set_mode(self.home_mode)
        self.timer_thread = threading.Thread(target=timer_function, daemon=True)
        self.timer_thread.start()

    def _start_clock_timer(self, timeout=5):
        """Starts a delayed switch to clock if playback is not active."""
        self.start_timer(timeout=timeout)

    def stop_timer(self):
        """Stops the timer."""
        self.timer_running = False
        if self.timer_thread and self.timer_thread.is_alive():
            print("Stopping timer thread.")
        self.timer_thread = None

    def clear_screen(self):
        """Clears the OLED display."""
        if self.oled and self._blank_image:
            self.oled.display(self._blank_image)
            print("OLED display cleared.")

    def notify_mode_change(self):
        """Notifies registered components of a mode change."""
        print(f"Mode changed to: {self.current_mode}")
        for callback in self.on_mode_change_callbacks:
            try:
                callback(self.current_mode)
            except Exception as e:
                print(f"Error in callback execution: {e}")

    def add_on_mode_change_callback(self, callback):
        """Adds a callback to be triggered on mode change."""
        if callable(callback):
            self.on_mode_change_callbacks.append(callback)
            print(f"Added mode change callback: {callback}")
