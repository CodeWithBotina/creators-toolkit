import json
from pathlib import Path
import logging
from typing import Any, Dict, Optional

# Get the application logger instance
from src.core.logger import get_application_logger

class ConfigManagerError(Exception):
    """Custom exception for configuration management errors."""
    pass

class ConfigManager:
    """
    Manages application-wide configuration settings.
    Implements a singleton pattern to ensure a single source of truth for settings.
    Settings are stored and loaded from a JSON file.
    """
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        """Ensures that only one instance of ConfigManager exists (Singleton pattern)."""
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, config_dir: str = "config", config_file_name: str = "settings.json"):
        """
        Initializes the ConfigManager.
        
        Args:
            config_dir (str): The absolute path to the directory where the configuration
                              file should be stored or is located. This should be derived
                              from the application's root directory during startup.
            config_file_name (str): The name of the configuration JSON file.
        """
        if self._initialized:
            return

        self.logger = get_application_logger()
        self.config_dir = Path(config_dir)
        self.config_file_path = self.config_dir / config_file_name
        self.settings: Dict[str, Any] = {}

        self._load_config()
        self._initialized = True
        self.logger.info(f"ConfigManager initialized. Configuration file: {self.config_file_path}")

    def _load_config(self):
        """
        Loads configuration settings from the JSON file.
        If the file does not exist, it initializes with default settings.
        """
        self.config_dir.mkdir(parents=True, exist_ok=True) # Ensure config directory exists

        if self.config_file_path.exists():
            try:
                with open(self.config_file_path, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
                self.logger.info(f"Configuration loaded from {self.config_file_path}")
            except json.JSONDecodeError as e:
                self.logger.error(f"Error decoding JSON from config file {self.config_file_path}: {e}", exc_info=True)
                self.settings = self._get_default_settings() # Fallback to defaults on error
                self.logger.warning("Falling back to default settings due to JSON decode error.")
                self._save_config() # Attempt to save valid defaults
            except Exception as e:
                self.logger.error(f"An unexpected error occurred while loading config from {self.config_file_path}: {e}", exc_info=True)
                self.settings = self._get_default_settings() # Fallback to defaults on error
                self.logger.warning("Falling back to default settings due to unexpected error during load.")
                self._save_config() # Attempt to save valid defaults
        else:
            self.logger.warning(f"Configuration file not found: {self.config_file_path}. Initializing with default settings.")
            self.settings = self._get_default_settings()
            self._save_config() # Save default settings to file

    def _save_config(self):
        """Saves the current configuration settings to the JSON file."""
        try:
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4)
            self.logger.info(f"Configuration saved to {self.config_file_path}")
        except Exception as e:
            self.logger.error(f"Failed to save configuration to {self.config_file_path}: {e}", exc_info=True)
            raise ConfigManagerError(f"Could not save configuration: {e}")

    def _get_default_settings(self) -> Dict[str, Any]:
        """
        Returns a dictionary of default application settings.
        This includes default paths and processing parameters.
        """
        # IMPORTANT: These paths are *relative placeholders* if config_dir is not explicitly set
        # by main.py during initial setup. Once main.py sets absolute paths, these defaults
        # will be overridden by the values from app_settings.
        return {
            "app_settings": {
                "appearance_mode": "System", # "Light", "Dark", "System"
                "theme": "dark-blue",        # "blue", "dark-blue", "green"
                "app_root": "",              # Will be set by main.py
                "log_dir": "",               # Will be set by main.py
                "config_dir": "",            # Will be set by main.py
                "assets_dir": "",            # Will be set by main.py
                "binaries_dir": "",          # Will be set by main.py
                "models_dir": ""             # Will be set by main.py
            },
            "output_directories": {
                # These will ideally be subdirectories within the user's Documents/Videos/Pictures
                # or a custom output folder. For now, they'll default relative to APP_ROOT
                # until a proper installer-time/first-run setup allows user choice.
                "default_video_output": str(Path("output") / "videos"),
                "default_audio_output": str(Path("output") / "audio"),
                "default_image_output": str(Path("output") / "images"),
                "default_social_media_output": str(Path("output") / "social_media")
            },
            "processing_parameters": {
                "video_conversion": {
                    "delete_original_after_processing": False
                },
                "audio_enhancement": {
                    "noise_reduction_strength": 0.5,
                    "normalization_level_dbfs": -3.0,
                    "remove_silence": False,
                    "min_silence_len_ms": 1000,
                    "silence_thresh_db": -35,
                    "sample_rate": 48000, # Added for consistency, typical for professional audio
                    "delete_original_after_processing": False
                },
                "image_background_removal": {
                    "image_quality_enhancement": True,
                    "delete_original_after_processing": False
                },
                "video_enhancement": {
                    "denoise_strength": 2.0,
                    "sharpen_strength": 0.5,
                    "contrast_enhance": 1.0,
                    "saturation": 1.0,
                    "gamma": 1.0,
                    "brightness": 0.0,
                    "shadow_highlight": 0.0,
                    "delete_original_after_processing": False
                },
                "video_background_removal": {
                    "delete_original_after_processing": False
                },
                "social_media_post_processing": {
                    "auto_crop": True,
                    "generate_subtitles": True,
                    "subtitle_font_size": 40,
                    "default_subtitle_font_name": "Arial",
                    "subtitle_color": "#FFFFFF",
                    "subtitle_stroke_width": 2,
                    "subtitle_stroke_color": "#000000",
                    "subtitle_font_position_y": 0.85,
                    "subtitle_words_per_line": 3,
                    "auto_remove_silent_segments": True, # Renamed for consistency with backend
                    "min_silence_duration_ms": 1000,     # Renamed for consistency with backend
                    "silence_threshold_db": -40,         # Renamed for consistency with backend
                    "apply_auto_video_enhancement": True,
                    "apply_auto_audio_enhancement": True,
                    "delete_original_after_processing": False,
                    "target_social_media_resolution": "1080x1920",
                    "overlays": [] # List to store overlay configurations
                }
            }
        }

    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Retrieves a configuration setting using a dot-separated key (e.g., "app_settings.theme").

        Args:
            key (str): The dot-separated key for the setting.
            default (Any, optional): The default value to return if the key is not found.
                                     Defaults to None.

        Returns:
            Any: The value of the setting, or the default value if not found.
        """
        parts = key.split('.')
        current_level = self.settings
        for part in parts:
            if isinstance(current_level, dict) and part in current_level:
                current_level = current_level[part]
            else:
                self.logger.warning(f"Configuration key '{key}' not found. Returning default value: {default}")
                return default
        return current_level

    def set_setting(self, key: str, value: Any):
        """
        Sets a configuration setting using a dot-separated key (e.g., "app_settings.theme").
        Automatically saves the updated configuration to the file.

        Args:
            key (str): The dot-separated key for the setting.
            value (Any): The value to set.
        """
        parts = key.split('.')
        current_level = self.settings
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                if isinstance(current_level, dict):
                    current_level[part] = value
                    self.logger.info(f"Setting '{key}' updated to '{value}'.")
                    self._save_config()
                    return
                else:
                    self.logger.error(f"Cannot set setting '{key}'. Parent key '{'.'.join(parts[:i])}' is not a dictionary.")
                    raise ConfigManagerError(f"Cannot set setting '{key}'. Parent is not a dictionary.")
            else:
                if isinstance(current_level, dict) and part not in current_level:
                    current_level[part] = {} # Create sub-dictionary if it doesn't exist
                elif not isinstance(current_level.get(part), dict):
                    self.logger.error(f"Cannot set setting '{key}'. Intermediate key '{part}' is not a dictionary.")
                    raise ConfigManagerError(f"Cannot set setting '{key}'. Intermediate key '{part}' is not a dictionary.")
                current_level = current_level[part]
        
        self.logger.error(f"Failed to set setting '{key}' with value '{value}'. Path resolution error.")
        raise ConfigManagerError(f"Failed to set setting '{key}'. Path resolution error.")

# Global instance for easy access throughout the application
_app_config_manager_instance: Optional[ConfigManager] = None

def get_application_config(config_dir: str = "config") -> ConfigManager:
    """
    Convenience function to get the global ConfigManager instance.
    Ensures it's initialized only once with the specified config directory.
    """
    global _app_config_manager_instance
    if _app_config_manager_instance is None:
        _app_config_manager_instance = ConfigManager(config_dir=config_dir)
    return _app_config_manager_instance

