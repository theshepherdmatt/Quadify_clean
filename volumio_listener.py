import requests
from socketIO_client_nexus import SocketIO, LoggingNamespace
import threading
from PIL import Image

class VolumioListener:
    def __init__(self, host='localhost', port=3000, on_state_change_callback=None, oled=None, clock=None, mode_manager=None):
        self.host = host
        self.port = port
        self.on_state_change_callback = on_state_change_callback
        self.oled = oled
        self.clock = clock
        self.mode_manager = mode_manager
        
        # Initialize callback placeholders
        self.on_playlists_received_callback = None
        self.on_webradio_received_callback = None
        
        # Data storage
        self.playlists = []
        self.webradio_stations = []

        # Initialize SocketIO connection and register event handlers
        self.socketIO = SocketIO(self.host, self.port, LoggingNamespace)
        print(f"[Debug] Connecting to Volumio WebSocket at {self.host}:{self.port}")
        self._register_socketio_events()

    def _register_socketio_events(self):
        """Sets up WebSocket event listeners for connection and data events."""
        self.socketIO.on('connect', lambda: print("[WebSocket] Connected to Volumio"))
        self.socketIO.on('disconnect', lambda: print("[WebSocket] Disconnected from Volumio"))
        self.socketIO.on('pushState', self.on_push_state)
        self.socketIO.on('pushQueue', self.on_push_queue)
        self.socketIO.on('pushBrowseLibrary', self.on_receive_browse_library)
        print("[Debug] Registered WebSocket events.")

    def get_volumio_state(self):
        """Fetches the current Volumio state."""
        try:
            response = requests.get(f"http://{self.host}:{self.port}/api/v1/getState")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching Volumio state: {e}")
            return None

    def fetch_playlists(self):
        """Requests playlists from Volumio."""
        print("Fetching playlists from Volumio...")
        self.socketIO.emit('browseLibrary', {'uri': 'playlists'})

    def fetch_webradio_stations(self, uri="mywebradio"):
        """Requests webradio stations from Volumio."""
        print(f"Fetching webradio stations from Volumio for URI: {uri}")
        self.socketIO.emit('browseLibrary', {'uri': uri})

    def register_playlists_callback(self, callback):
        """Registers a callback to be triggered when playlists are received."""
        self.on_playlists_received_callback = callback
        print("Registered playlists callback.")

    def register_webradio_callback(self, callback):
        """Registers a callback to be triggered when webradio stations are received."""
        self.on_webradio_received_callback = callback
        print("[VolumioListener] Registered webradio callback.")

    def on_receive_playlists(self, data):
        """Processes and stores received playlist data, then triggers the callback."""
        if 'navigation' in data and 'lists' in data['navigation']:
            playlists = data['navigation']['lists'][0].get('items', [])
            self.playlists = [{'title': item['title'], 'uri': item['uri']} for item in playlists if 'title' in item and 'uri' in item]
            print(f"[Debug] Playlists received: {[playlist['title'] for playlist in self.playlists]}")
            if self.on_playlists_received_callback:
                self.on_playlists_received_callback(self.playlists)
        else:
            print("[Error] No playlists found in the received data.")

    def on_receive_radio(self, data):
        """Processes and stores received webradio data, then triggers the callback."""
        if 'navigation' in data and 'lists' in data['navigation']:
            radio_items = data['navigation']['lists'][0].get('items', [])
            self.webradio_stations = [
                {
                    'title': item['title'],
                    'uri': item['uri'],
                    'albumart': item.get('albumart', ''),
                    'bitrate': item.get('bitrate', 0)
                }
                for item in radio_items if item['type'] == 'webradio'
            ]
            print(f"Radio stations received: {[station['title'] for station in self.webradio_stations]}")
            if self.on_webradio_received_callback:
                self.on_webradio_received_callback(self.webradio_stations)
        else:
            print("No radio stations found.")

    def on_receive_browse_library(self, data):
        if 'navigation' in data and 'lists' in data['navigation']:
            items = data['navigation']['lists'][0].get('items', [])
            playlists, webradio = [], []
            for item in items:
                item_type = item.get('type')
                if item_type == "playlist":
                    playlists.append({'title': item.get('title', ''), 'uri': item.get('uri', '')})
                elif item_type in ['webradio', 'mywebradio']:
                    webradio.append({
                        'title': item.get('title', ''),
                        'uri': item.get('uri', ''),
                        'albumart': item.get('albumart', ''),
                        'bitrate': item.get('bitrate', 0)
                    })

            # Assign and callback
            self.playlists = playlists if playlists else self.playlists
            self.webradio_stations = webradio if webradio else self.webradio_stations
            if self.on_playlists_received_callback and playlists:
                self.on_playlists_received_callback(self.playlists)
            if self.on_webradio_received_callback and webradio:
                self.on_webradio_received_callback(self.webradio_stations)
        else:
            print("[Error] Invalid browseLibrary data received.")

    def play_playlist(self, playlist_name):
        """Sends a request to Volumio to play a specific playlist."""
        print(f"Attempting to play playlist: {playlist_name}")
        self.socketIO.emit('playPlaylist', {'name': playlist_name})
        print(f"'playPlaylist' event emitted with playlist: {playlist_name}")

    def play_webradio_station(self, title, uri):
        """Attempts to play a specific webradio station based on title match."""
        normalized_title = title.strip().lower()
        for station in self.webradio_stations:
            if normalized_title in station.get('title', '').strip().lower():
                print(f"[Playing] Playing webradio station '{station.get('title')}' with URI: {station.get('uri')}")
                self.socketIO.emit('replaceAndPlay', {
                    "service": "webradio",
                    "type": "webradio",
                    "title": station.get('title'),
                    "uri": station.get('uri')
                })
                return
        print(f"[Failure] Webradio station '{title}' not found.")

    def connect(self):
        """Starts the Volumio listener in a separate thread."""
        def listener_thread():
            print("Starting Volumio listener...")
            self.socketIO.emit('getState', {}, self.on_push_state)
            self.socketIO.wait()
        threading.Thread(target=listener_thread, daemon=True).start()

    def on_push_state(self, data):
        if self.on_state_change_callback:
            self.on_state_change_callback(data)

    def on_push_queue(self, data):
        """Handles Volumio 'pushQueue' events (placeholder)."""
        print("Queue event received but not processed.")
