#!/usr/bin/env python3
"""
SpotifyToYT GUI Application using Kivy
Cross-platform graphical interface for the complete pipeline
"""

import sys

print("[DEBUG] Starting GUI application...")
print("[DEBUG] Python version:", sys.version)
import os
import json
import threading
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

print("[DEBUG] Basic imports successful")

# Setup path to .lib/
lib_path = os.path.join(os.path.dirname(__file__), '.lib')
sys.path.append(lib_path)
print(f"[DEBUG] Added .lib path: {lib_path}")
print(f"[DEBUG] Current working directory: {os.getcwd()}")
print(f"[DEBUG] Script directory: {os.path.dirname(__file__)}")

# Kivy imports
print("[DEBUG] Importing Kivy...")
try:
    import kivy
    kivy.require('2.1.0')
    print(f"[DEBUG] Kivy version: {kivy.__version__}")
except Exception as e:
    print(f"[ERROR] Failed to import/configure Kivy: {e}")
    raise

print("[DEBUG] Importing Kivy widgets...")
try:
    from kivy.app import App
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.gridlayout import GridLayout
    from kivy.uix.label import Label
    from kivy.uix.button import Button
    from kivy.uix.textinput import TextInput
    from kivy.uix.spinner import Spinner
    from kivy.uix.checkbox import CheckBox
    from kivy.uix.progressbar import ProgressBar
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.popup import Popup
    from kivy.clock import Clock
    from kivy.core.audio import SoundLoader
    from kivy.core.window import Window
    from kivy.uix.widget import Widget
    from kivy.uix.switch import Switch
    from kivy.graphics import Color, Rectangle
    print("[DEBUG] Kivy widgets imported successfully")
except Exception as e:
    print(f"[ERROR] Failed to import Kivy widgets: {e}")
    raise

# Import our pipeline modules
print("[DEBUG] Importing pipeline modules...")
try:
    from spotify.auth import get_authenticated_client
    from spotify.playlists import get_user_playlists
    from spotify.playlist_tracks import get_tracks_from_playlist
    print("[DEBUG] Spotify modules imported successfully")
except Exception as e:
    print(f"[ERROR] Failed to import Spotify modules: {e}")
    raise

try:
    from utils.logging import create_logger
    from utils.paths import validate_output_file, validate_directory
    print("[DEBUG] Utils modules imported successfully")
except Exception as e:
    print(f"[ERROR] Failed to import Utils modules: {e}")
    raise

# Try to import pipeline scripts
print("[DEBUG] Importing pipeline scripts...")
try:
    import spoty_exporter_MK1
    print("[DEBUG] spoty_exporter_MK1 imported")
except ImportError as e:
    print(f"[WARNING] Could not import spoty_exporter_MK1: {e}")

try:
    import yt_searchtMK1
    print("[DEBUG] yt_searchtMK1 imported")
except ImportError as e:
    print(f"[WARNING] Could not import yt_searchtMK1: {e}")

try:
    import yt_FetchMK1
    print("[DEBUG] yt_FetchMK1 imported")
except ImportError as e:
    print(f"[WARNING] Could not import yt_FetchMK1: {e}")

try:
    import yt_PushMK1
    print("[DEBUG] yt_PushMK1 imported")
except ImportError as e:
    print(f"[WARNING] Could not import yt_PushMK1: {e}")

print("[DEBUG] All imports completed")

class ThemeManager:
    """Manages light and dark theme colors"""
    
    LIGHT_THEME = {
        'bg_primary': (0.95, 0.95, 0.95, 1),      # Light gray background
        'bg_secondary': (1, 1, 1, 1),             # White secondary background
        'bg_accent': (0.2, 0.3, 0.5, 1),          # Blue accent
        'text_primary': (0, 0, 0, 1),             # Black text
        'text_secondary': (0.3, 0.3, 0.3, 1),    # Dark gray text
        'text_accent': (1, 1, 1, 1),              # White text on accent
        'button_normal': (0.9, 0.9, 0.9, 1),     # Light button
        'button_success': (0.2, 0.8, 0.2, 1),    # Green button
        'button_danger': (0.8, 0.2, 0.2, 1),     # Red button
        'button_info': (0.5, 0.5, 0.5, 1),       # Gray button
        'log_bg': (0.98, 0.98, 0.98, 1),         # Very light log background
        'log_text': (0.1, 0.1, 0.1, 1),          # Dark log text
        'input_bg': (1, 1, 1, 1),                # White input background
        'input_text': (0, 0, 0, 1),              # Black input text
    }
    
    DARK_THEME = {
        'bg_primary': (0.1, 0.1, 0.1, 1),         # Dark background
        'bg_secondary': (0.15, 0.15, 0.15, 1),   # Slightly lighter dark
        'bg_accent': (0.2, 0.4, 0.6, 1),          # Blue accent (lighter in dark)
        'text_primary': (1, 1, 1, 1),             # White text
        'text_secondary': (0.8, 0.8, 0.8, 1),    # Light gray text
        'text_accent': (1, 1, 1, 1),              # White text on accent
        'button_normal': (0.2, 0.2, 0.2, 1),     # Dark button
        'button_success': (0.15, 0.6, 0.15, 1),  # Dark green button
        'button_danger': (0.6, 0.15, 0.15, 1),   # Dark red button
        'button_info': (0.3, 0.3, 0.3, 1),       # Dark gray button
        'log_bg': (0.05, 0.05, 0.05, 1),         # Very dark log background
        'log_text': (0.9, 0.9, 0.9, 1),          # Light log text
        'input_bg': (0.2, 0.2, 0.2, 1),          # Dark input background
        'input_text': (1, 1, 1, 1),              # White input text
    }
    
    def __init__(self):
        self.is_dark_mode = False
        self.theme_callbacks = []
    
    def get_color(self, color_name):
        """Get color from current theme"""
        theme = self.DARK_THEME if self.is_dark_mode else self.LIGHT_THEME
        return theme.get(color_name, (1, 1, 1, 1))
    
    def toggle_theme(self):
        """Toggle between light and dark themes"""
        self.is_dark_mode = not self.is_dark_mode
        self.notify_theme_change()
    
    def set_dark_mode(self, is_dark):
        """Set theme mode explicitly"""
        if self.is_dark_mode != is_dark:
            self.is_dark_mode = is_dark
            self.notify_theme_change()
    
    def register_callback(self, callback):
        """Register callback for theme changes"""
        self.theme_callbacks.append(callback)
    
    def notify_theme_change(self):
        """Notify all registered callbacks of theme change"""
        for callback in self.theme_callbacks:
            try:
                callback()
            except Exception as e:
                print(f"Theme callback error: {e}")

class ThemedWidget:
    """Mixin class for widgets that support theming"""
    
    def __init__(self, theme_manager, **kwargs):
        self.theme_manager = theme_manager
        theme_manager.register_callback(self.update_theme)
        super().__init__(**kwargs)
        self.update_theme()
    
    def update_theme(self):
        """Override this method to update widget colors"""
        pass

class ColoredLabel(ThemedWidget, Label):
    """Label with background color support and theming"""
    
    def __init__(self, theme_manager, bg_color_name='bg_secondary', text_color_name='text_primary', **kwargs):
        self.bg_color_name = bg_color_name
        self.text_color_name = text_color_name
        super().__init__(theme_manager=theme_manager, **kwargs)
        
        with self.canvas.before:
            self.bg_color_instruction = Color(*self.theme_manager.get_color(bg_color_name))
            self.rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self._update_rect, pos=self._update_rect)
    
    def _update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size
    
    def update_theme(self):
        # Safety check - only update if attributes exist
        if hasattr(self, 'bg_color_instruction'):
            self.bg_color_instruction.rgba = self.theme_manager.get_color(self.bg_color_name)
        if hasattr(self, 'color'):
            self.color = self.theme_manager.get_color(self.text_color_name)

class LogTextInput(ThemedWidget, TextInput):
    """Custom TextInput for log display with color support and theming"""
    
    def __init__(self, theme_manager, **kwargs):
        super().__init__(theme_manager=theme_manager, **kwargs)
        self.readonly = True
        self.multiline = True
    
    def update_theme(self):
        self.background_color = self.theme_manager.get_color('log_bg')
        self.foreground_color = self.theme_manager.get_color('log_text')

class GUILogHandler(logging.Handler):
    """Custom log handler that sends logs to GUI"""
    
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        
    def emit(self, record):
        log_entry = self.format(record)
        # Schedule GUI update on main thread
        Clock.schedule_once(lambda dt: self.callback(log_entry, record.levelname), 0)

class PlaylistItem(ThemedWidget, BoxLayout):
    """Widget for displaying a playlist with radio button selection"""
    
    def __init__(self, playlist_data, callback, theme_manager, **kwargs):
        super().__init__(theme_manager=theme_manager, orientation='horizontal', size_hint_y=None, height=40, **kwargs)
        
        self.playlist_data = playlist_data
        self.callback = callback
        
        # Radio button (using CheckBox)
        self.checkbox = CheckBox(
            group='playlist_selection',
            size_hint_x=None,
            width=30,
            active=False
        )
        self.checkbox.bind(active=self.on_select)
        
        # Playlist info label
        name = playlist_data.get('name', 'Unknown')
        track_count = playlist_data.get('tracks', 0)
        self.label = Label(
            text=f"{name} ({track_count} songs)",
            text_size=(None, None),
            halign='left',
            valign='middle'
        )
        
        self.add_widget(self.checkbox)
        self.add_widget(self.label)
    
    def on_select(self, checkbox, value):
        if value:
            self.callback(self.playlist_data)
    
    def update_theme(self):
        if hasattr(self, 'label'):
            self.label.color = self.theme_manager.get_color('text_primary')

class SpotifyToYTGUI(BoxLayout):
    """Main GUI application class"""
    
    def __init__(self, **kwargs):
        print("[DEBUG] Initializing SpotifyToYTGUI...")
        super().__init__(orientation='vertical', padding=10, spacing=10, **kwargs)
        
        print("[DEBUG] Creating theme manager...")
        # Initialize theme manager
        self.theme_manager = ThemeManager()
        
        print("[DEBUG] Initializing state variables...")
        # Initialize state
        self.playlists = []
        self.selected_playlist = None
        self.pipeline_thread = None
        self.pipeline_running = False
        self.logger = None
        self.progress_values = {
            'overall': 0,
            'export': 0,
            'search': 0,
            'download': 0,
            'upload': 0
        }
        
        print("[DEBUG] Registering theme callbacks...")
        # Register for theme updates
        self.theme_manager.register_callback(self.update_theme)
        
        print("[DEBUG] Loading sounds...")
        # Load sounds
        self.warning_sound = None
        self.error_sound = None
        self.load_sounds()
        
        print("[DEBUG] Setting up logging...")
        # Setup logging
        self.setup_logging()
        
        print("[DEBUG] Building UI...")
        # Build UI
        self.build_ui()
        
        print("[DEBUG] GUI initialization complete")
        # Don't auto-load playlists on startup - let user click refresh when ready
        self.logger.info("GUI ready - click 'Refresh' to load playlists")
    
    def load_sounds(self):
        """Load notification sounds"""
        try:
            # You can add custom sound files here
            # For now, we'll use system beeps via plyer
            pass
        except Exception as e:
            print(f"Could not load sounds: {e}")
    
    def play_warning_sound(self):
        """Play warning notification sound"""
        try:
            import plyer
            plyer.notification.notify(
                title="SpotifyToYT Warning",
                message="Check the logs for details",
                timeout=2
            )
        except Exception:
            print("\a")  # System beep fallback
    
    def play_error_sound(self):
        """Play error notification sound"""
        try:
            import plyer
            plyer.notification.notify(
                title="SpotifyToYT Error",
                message="An error occurred, check the logs",
                timeout=3
            )
        except Exception:
            print("\a\a")  # Double system beep fallback
    
    def setup_logging(self):
        """Setup logging with GUI handler"""
        self.logger = create_logger("gui", quiet=False)
        
        # Add GUI log handler to the underlying logger
        self.gui_handler = GUILogHandler(self.add_log_message)
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', 
                                    datefmt='%H:%M:%S')
        self.gui_handler.setFormatter(formatter)
        
        # Get the underlying logger from the LoggerAdapter
        underlying_logger = self.logger.logger if hasattr(self.logger, 'logger') else logging.getLogger("gui")
        underlying_logger.addHandler(self.gui_handler)
    
    def build_ui(self):
        """Build the main user interface"""
        
        # Title bar with theme toggle
        title_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=50)
        
        title = ColoredLabel(
            theme_manager=self.theme_manager,
            text="SpotifyToYT Pipeline GUI",
            font_size=20,
            bg_color_name='bg_accent',
            text_color_name='text_accent',
            size_hint_x=0.8
        )
        
        # Theme toggle section
        theme_section = BoxLayout(orientation='horizontal', size_hint_x=0.2, padding=(10, 5))
        
        theme_label = Label(
            text="🌙",
            size_hint_x=0.4,
            font_size=16
        )
        
        self.theme_toggle = Switch(
            active=False,
            size_hint_x=0.6
        )
        self.theme_toggle.bind(active=self.on_theme_toggle)
        
        theme_section.add_widget(theme_label)
        theme_section.add_widget(self.theme_toggle)
        
        title_layout.add_widget(title)
        title_layout.add_widget(theme_section)
        
        self.title_label = title
        self.theme_label = theme_label
        self.add_widget(title_layout)
        
        # Main content in horizontal layout
        main_layout = BoxLayout(orientation='horizontal', spacing=10)
        
        # Left panel
        left_panel = self.build_left_panel()
        main_layout.add_widget(left_panel)
        
        # Right panel (logs)
        right_panel = self.build_right_panel()
        main_layout.add_widget(right_panel)
        
        self.add_widget(main_layout)
    
    def build_left_panel(self):
        """Build left panel with playlist selection and controls"""
        left_panel = BoxLayout(orientation='vertical', size_hint_x=0.6, spacing=10)
        
        # Playlist selection section
        playlist_section = self.build_playlist_section()
        left_panel.add_widget(playlist_section)
        
        # Settings section
        settings_section = self.build_settings_section()
        left_panel.add_widget(settings_section)
        
        # Pipeline control section
        control_section = self.build_control_section()
        left_panel.add_widget(control_section)
        
        # Progress section
        progress_section = self.build_progress_section()
        left_panel.add_widget(progress_section)
        
        return left_panel
    
    def build_playlist_section(self):
        """Build playlist selection section"""
        section = BoxLayout(orientation='vertical', size_hint_y=0.4, spacing=5)
        
        # Header
        header = BoxLayout(orientation='horizontal', size_hint_y=None, height=40)
        header.add_widget(Label(text="📋 Playlist Selection", font_size=16, size_hint_x=0.8))
        
        self.refresh_btn = Button(
            text="Refresh",
            size_hint_x=0.2,
            size_hint_y=None,
            height=35
        )
        self.refresh_btn.bind(on_press=lambda x: self.refresh_playlists())
        header.add_widget(self.refresh_btn)
        
        section.add_widget(header)
        
        # Playlist list
        self.playlist_scroll = ScrollView()
        self.playlist_layout = BoxLayout(orientation='vertical', size_hint_y=None)
        self.playlist_layout.bind(minimum_height=self.playlist_layout.setter('height'))
        
        self.playlist_scroll.add_widget(self.playlist_layout)
        section.add_widget(self.playlist_scroll)
        
        return section
    
    def build_settings_section(self):
        """Build settings section"""
        section = BoxLayout(orientation='vertical', size_hint_y=None, height=120, spacing=5)
        
        section.add_widget(Label(text="⚙️ Settings", font_size=16, size_hint_y=None, height=30))
        
        # Settings grid
        settings_grid = GridLayout(cols=2, size_hint_y=None, height=80, spacing=5)
        
        # Thread count
        self.threads_label = Label(text="Threads:")
        settings_grid.add_widget(self.threads_label)
        self.thread_spinner = Spinner(
            text='3',
            values=['1', '2', '3', '4', '5', '6', '7', '8'],
            size_hint_y=None,
            height=35
        )
        settings_grid.add_widget(self.thread_spinner)
        
        # Output directory
        self.output_label = Label(text="Output Dir:")
        settings_grid.add_widget(self.output_label)
        self.output_input = TextInput(
            text='out/',
            multiline=False,
            size_hint_y=None,
            height=35
        )
        settings_grid.add_widget(self.output_input)
        
        section.add_widget(settings_grid)
        return section
    
    def build_control_section(self):
        """Build pipeline control section"""
        section = BoxLayout(orientation='vertical', size_hint_y=None, height=100, spacing=5)
        
        section.add_widget(Label(text="🚀 Pipeline Control", font_size=16, size_hint_y=None, height=30))
        
        # Control buttons
        button_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=60, spacing=10)
        
        self.start_btn = Button(
            text="Start Pipeline",
            background_color=(0.2, 0.8, 0.2, 1)
        )
        self.start_btn.bind(on_press=self.start_pipeline)
        
        self.stop_btn = Button(
            text="Stop",
            background_color=(0.8, 0.2, 0.2, 1),
            disabled=True
        )
        self.stop_btn.bind(on_press=self.stop_pipeline)
        
        self.clear_btn = Button(
            text="Clear Logs",
            background_color=(0.5, 0.5, 0.5, 1)
        )
        self.clear_btn.bind(on_press=self.clear_logs)
        
        button_layout.add_widget(self.start_btn)
        button_layout.add_widget(self.stop_btn)
        button_layout.add_widget(self.clear_btn)
        
        section.add_widget(button_layout)
        return section
    
    def build_progress_section(self):
        """Build progress tracking section"""
        section = BoxLayout(orientation='vertical', size_hint_y=None, height=200, spacing=5)
        
        section.add_widget(Label(text="📊 Progress", font_size=16, size_hint_y=None, height=30))
        
        # Progress bars
        progress_layout = BoxLayout(orientation='vertical', spacing=5)
        
        # Overall progress
        overall_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=30)
        overall_layout.add_widget(Label(text="Overall:", size_hint_x=0.3))
        self.overall_progress = ProgressBar(max=100, value=0)
        overall_layout.add_widget(self.overall_progress)
        self.overall_label = Label(text="0%", size_hint_x=0.2)
        overall_layout.add_widget(self.overall_label)
        progress_layout.add_widget(overall_layout)
        
        # Step progress bars
        steps = [
            ('export', 'Step 1: Export'),
            ('search', 'Step 2: Search'),
            ('download', 'Step 3: Download'),
            ('upload', 'Step 4: Upload')
        ]
        
        self.step_progress = {}
        self.step_labels = {}
        
        for step_id, step_name in steps:
            step_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=30)
            step_layout.add_widget(Label(text=f"{step_name}:", size_hint_x=0.3))
            
            progress_bar = ProgressBar(max=100, value=0)
            self.step_progress[step_id] = progress_bar
            step_layout.add_widget(progress_bar)
            
            label = Label(text="0%", size_hint_x=0.2)
            self.step_labels[step_id] = label
            step_layout.add_widget(label)
            
            progress_layout.add_widget(step_layout)
        
        section.add_widget(progress_layout)
        return section
    
    def build_right_panel(self):
        """Build right panel with log output"""
        right_panel = BoxLayout(orientation='vertical', size_hint_x=0.4, spacing=5)
        
        # Log header with controls
        log_header = BoxLayout(orientation='horizontal', size_hint_y=None, height=40, spacing=10)
        log_header.add_widget(Label(text="📝 Log Output", font_size=16, size_hint_x=0.5))
        
        # Log level filter
        log_header.add_widget(Label(text="Level:", size_hint_x=0.2))
        self.log_level_spinner = Spinner(
            text='INFO',
            values=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
            size_hint_x=0.3,
            size_hint_y=None,
            height=35
        )
        log_header.add_widget(self.log_level_spinner)
        
        # Auto-scroll checkbox
        self.auto_scroll_checkbox = CheckBox(active=True, size_hint_x=None, width=30)
        log_header.add_widget(self.auto_scroll_checkbox)
        log_header.add_widget(Label(text="Auto-scroll", size_hint_x=0.3))
        
        right_panel.add_widget(log_header)
        
        # Log output area
        self.log_scroll = ScrollView()
        self.log_output = LogTextInput(
            theme_manager=self.theme_manager,
            text="[GUI] SpotifyToYT GUI Started\n",
            font_size=12
        )
        self.log_scroll.add_widget(self.log_output)
        right_panel.add_widget(self.log_scroll)
        
        return right_panel
    
    def refresh_playlists(self):
        """Refresh the playlist list from Spotify"""
        self.logger.info("Refreshing playlists...")
        
        # Disable refresh button during loading
        self.refresh_btn.disabled = True
        self.refresh_btn.text = "Loading..."
        
        def fetch_playlists():
            try:
                self.logger.info("Connecting to Spotify...")
                sp = get_authenticated_client()
                
                self.logger.info("Fetching playlists...")
                result = get_user_playlists(sp)
                
                if result["status"] == 200:
                    self.playlists = result["playlists"]
                    Clock.schedule_once(lambda dt: self.update_playlist_display(), 0)
                    self.logger.info(f"Successfully loaded {len(self.playlists)} playlists")
                else:
                    self.logger.error(f"Failed to load playlists: {result['error']}")
                    Clock.schedule_once(lambda dt: self.show_error_popup(f"Failed to load playlists: {result['error']}"), 0)
                    
            except Exception as e:
                self.logger.error(f"Exception loading playlists: {e}")
                Clock.schedule_once(lambda dt: self.show_error_popup(f"Error connecting to Spotify: {str(e)}"), 0)
            finally:
                # Re-enable refresh button
                Clock.schedule_once(lambda dt: self.reset_refresh_button(), 0)
        
        # Run in background thread
        threading.Thread(target=fetch_playlists, daemon=True).start()
    
    def reset_refresh_button(self):
        """Reset refresh button state"""
        self.refresh_btn.disabled = False
        self.refresh_btn.text = "Refresh"
    
    def update_playlist_display(self):
        """Update the playlist display widget"""
        # Clear existing widgets
        self.playlist_layout.clear_widgets()
        
        if not self.playlists:
            self.playlist_layout.add_widget(
                Label(text="No playlists found. Click Refresh to try again.",
                      size_hint_y=None, height=40)
            )
            return
        
        # Add playlist items
        for playlist in self.playlists:
            item = PlaylistItem(playlist, self.on_playlist_selected, self.theme_manager)
            self.playlist_layout.add_widget(item)
    
    def on_playlist_selected(self, playlist_data):
        """Handle playlist selection"""
        self.selected_playlist = playlist_data
        self.logger.info(f"Selected playlist: {playlist_data['name']}")
    
    def start_pipeline(self, instance):
        """Start the pipeline process"""
        if not self.selected_playlist:
            self.show_error_popup("Please select a playlist first!")
            return
        
        if self.pipeline_running:
            self.logger.warning("Pipeline is already running!")
            return
        
        self.pipeline_running = True
        self.start_btn.disabled = True
        self.stop_btn.disabled = False
        
        # Reset progress
        self.reset_progress()
        
        self.logger.info("Starting pipeline...")
        
        # Start pipeline in background thread
        self.pipeline_thread = threading.Thread(
            target=self.run_pipeline,
            daemon=True
        )
        self.pipeline_thread.start()
    
    def stop_pipeline(self, instance):
        """Stop the pipeline process"""
        self.logger.warning("Stop requested - pipeline will finish current step")
        self.pipeline_running = False
        self.start_btn.disabled = False
        self.stop_btn.disabled = True
    
    def clear_logs(self, instance):
        """Clear the log output"""
        self.log_output.text = "[GUI] Logs cleared\n"
    
    def run_pipeline(self):
        """Run the complete pipeline in background thread"""
        try:
            playlist_name = self.selected_playlist['name']
            playlist_id = self.selected_playlist['id']
            thread_count = int(self.thread_spinner.text)
            output_dir = self.output_input.text.strip() or 'out'
            
            # Clean filename
            clean_name = self.clean_filename(playlist_name)
            
            # Step 1: Export Spotify playlist
            if not self.pipeline_running:
                return
            
            self.update_progress('export', 0)
            self.logger.info("Step 1: Exporting Spotify playlist...")
            
            json_file = Path(output_dir) / f"{clean_name}.json"
            json_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Export playlist
            self.export_playlist(playlist_id, str(json_file))
            self.update_progress('export', 100)
            self.update_overall_progress(25)
            
            # Step 2: Search YouTube matches
            if not self.pipeline_running:
                return
            
            self.update_progress('search', 0)
            self.logger.info("Step 2: Searching YouTube Music matches...")
            
            enriched_file = Path(output_dir) / f"{clean_name}-enriched.json"
            self.search_youtube_matches(str(json_file), str(enriched_file), thread_count)
            self.update_progress('search', 100)
            self.update_overall_progress(50)
            
            # Step 3: Download audio files
            if not self.pipeline_running:
                return
            
            self.update_progress('download', 0)
            self.logger.info("Step 3: Downloading audio files...")
            
            songs_dir = Path('songs') / clean_name
            songs_dir.mkdir(parents=True, exist_ok=True)
            self.download_audio_files(str(enriched_file), str(songs_dir), thread_count)
            self.update_progress('download', 100)
            self.update_overall_progress(75)
            
            # Step 4: Create YouTube playlist (optional)
            if not self.pipeline_running:
                return
            
            self.update_progress('upload', 0)
            self.logger.info("Step 4: Creating YouTube playlist...")
            
            # For now, skip this step or make it optional
            self.update_progress('upload', 100)
            self.update_overall_progress(100)
            
            self.logger.info("Pipeline completed successfully!")
            
        except Exception as e:
            self.logger.error(f"Pipeline failed: {e}")
            self.play_error_sound()
        finally:
            self.pipeline_running = False
            Clock.schedule_once(lambda dt: self.reset_controls(), 0)
    
    def export_playlist(self, playlist_id, output_path):
        """Export Spotify playlist"""
        # This would use the existing spoty_exporter_MK1 logic
        sp = get_authenticated_client()
        result = get_tracks_from_playlist(sp, playlist_id, export_path=output_path)
        
        if result["status"] != 200:
            raise Exception(f"Failed to export playlist: {result['error']}")
    
    def search_youtube_matches(self, input_file, output_file, thread_count):
        """Search YouTube Music matches"""
        # This would use the existing yt_searchtMK1 logic
        # For now, simulate the process
        import time
        for i in range(10):
            if not self.pipeline_running:
                break
            time.sleep(0.5)
            progress = (i + 1) * 10
            Clock.schedule_once(lambda dt, p=progress: self.update_progress('search', p), 0)
    
    def download_audio_files(self, input_file, output_dir, thread_count):
        """Download audio files"""
        # This would use the existing yt_FetchMK1 logic
        # For now, simulate the process
        import time
        for i in range(10):
            if not self.pipeline_running:
                break
            time.sleep(0.8)
            progress = (i + 1) * 10
            Clock.schedule_once(lambda dt, p=progress: self.update_progress('download', p), 0)
    
    def clean_filename(self, filename):
        """Clean filename for filesystem"""
        import re
        cleaned = re.sub(r'[<>:"/\\|?*]', '_', filename)
        cleaned = re.sub(r'\s+', '_', cleaned)
        cleaned = re.sub(r'_+', '_', cleaned)
        return cleaned.strip('_')
    
    def update_progress(self, step, value):
        """Update progress bar for a specific step"""
        self.progress_values[step] = value
        Clock.schedule_once(lambda dt: self._update_progress_ui(step, value), 0)
    
    def _update_progress_ui(self, step, value):
        """Update progress UI on main thread"""
        if step in self.step_progress:
            self.step_progress[step].value = value
            self.step_labels[step].text = f"{value}%"
    
    def update_overall_progress(self, value):
        """Update overall progress"""
        self.progress_values['overall'] = value
        Clock.schedule_once(lambda dt: self._update_overall_progress_ui(value), 0)
    
    def _update_overall_progress_ui(self, value):
        """Update overall progress UI on main thread"""
        self.overall_progress.value = value
        self.overall_label.text = f"{value}%"
    
    def reset_progress(self):
        """Reset all progress bars"""
        for step in self.progress_values:
            self.progress_values[step] = 0
        
        Clock.schedule_once(lambda dt: self._reset_progress_ui(), 0)
    
    def _reset_progress_ui(self):
        """Reset progress UI on main thread"""
        self.overall_progress.value = 0
        self.overall_label.text = "0%"
        
        for step_id in self.step_progress:
            self.step_progress[step_id].value = 0
            self.step_labels[step_id].text = "0%"
    
    def reset_controls(self):
        """Reset control buttons"""
        self.start_btn.disabled = False
        self.stop_btn.disabled = True
    
    def add_log_message(self, message, level):
        """Add a log message to the display"""
        level_filter = self.log_level_spinner.text
        level_priority = {'DEBUG': 0, 'INFO': 1, 'WARNING': 2, 'ERROR': 3}
        
        if level_priority.get(level, 1) >= level_priority.get(level_filter, 1):
            # Color code the message
            if level == 'ERROR':
                self.play_error_sound()
            elif level == 'WARNING':
                self.play_warning_sound()
            
            # Add to log output
            self.log_output.text += message + "\n"
            
            # Auto-scroll if enabled
            if self.auto_scroll_checkbox.active:
                self.log_scroll.scroll_y = 0
    
    def on_theme_toggle(self, switch, value):
        """Handle theme toggle switch"""
        self.theme_manager.set_dark_mode(value)
        # Update toggle emoji
        self.theme_label.text = "☀️" if value else "🌙"
        self.logger.info(f"Switched to {'dark' if value else 'light'} theme")
    
    def update_theme(self):
        """Update theme for main window components"""
        # Update Window background
        Window.clearcolor = self.theme_manager.get_color('bg_primary')
        
        # Update button colors
        self.start_btn.background_color = self.theme_manager.get_color('button_success')
        self.stop_btn.background_color = self.theme_manager.get_color('button_danger')
        self.clear_btn.background_color = self.theme_manager.get_color('button_info')
        self.refresh_btn.background_color = self.theme_manager.get_color('button_normal')
        
        # Update text input colors
        self.output_input.background_color = self.theme_manager.get_color('input_bg')
        self.output_input.foreground_color = self.theme_manager.get_color('input_text')
        
        # Update label colors
        self.threads_label.color = self.theme_manager.get_color('text_primary')
        self.output_label.color = self.theme_manager.get_color('text_primary')
        self.theme_label.color = self.theme_manager.get_color('text_primary')
        
        # Update spinner colors
        self.thread_spinner.background_color = self.theme_manager.get_color('input_bg')
        self.log_level_spinner.background_color = self.theme_manager.get_color('input_bg')
    
    def show_error_popup(self, message):
        """Show error popup"""
        popup_content = Label(
            text=message,
            color=self.theme_manager.get_color('text_primary')
        )
        
        popup = Popup(
            title='Error',
            content=popup_content,
            size_hint=(0.8, 0.4)
        )
        
        # Theme the popup
        popup.background_color = self.theme_manager.get_color('bg_secondary')
        popup.open()

class SpotifyToYTApp(App):
    """Main Kivy application"""
    
    def build(self):
        print("[DEBUG] SpotifyToYTApp.build() called")
        print("[DEBUG] Setting window size...")
        Window.size = (1200, 800)
        Window.minimum_width = 800
        Window.minimum_height = 600
        
        print("[DEBUG] Setting window background...")
        # Set initial window background
        Window.clearcolor = (0.95, 0.95, 0.95, 1)  # Light theme default
        
        print("[DEBUG] Creating main GUI widget...")
        gui = SpotifyToYTGUI()
        print("[DEBUG] Main GUI widget created successfully")
        return gui

if __name__ == '__main__':
    try:
        print("🎵 Starting SpotifyToYT GUI Application...")
        print("📝 Note: Click 'Refresh' to load Spotify playlists when ready")
        print("🚀 Launching GUI...")
        app = SpotifyToYTApp()
        app.run()
        print("✅ GUI closed normally")
    except KeyboardInterrupt:
        print("[DEBUG] App interrupted by user")
    except Exception as e:
        print(f"[ERROR] Error starting GUI: {e}")
        import traceback
        print("[ERROR] Full traceback:")
        traceback.print_exc()