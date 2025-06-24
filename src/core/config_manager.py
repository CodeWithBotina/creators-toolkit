import json
import os
from pathlib import Path
from src.core.logger import get_application_logger # Correct reference to our logger

class ConfigManager:
    """
    Manages application configuration settings.
    Settings are loaded from and saved to a JSON file.
    """
    _instance = None
    _default_config = {
        "output_directories": {
            "default_video_output": str(Path.home() / "Videos" / "CreatorToolkit"),
            "default_audio_output": str(Path.home() / "Music" / "CreatorToolkit"),
            "default_image_output": str(Path.home() / "Pictures" / "CreatorToolkit")
        },
        "processing_parameters": {
            "video_conversion": {
                "delete_original_after_conversion": False
            },
            "audio_enhancement": { # NEW: Audio Enhancement parameters
                "noise_reduction_strength": 0.5,
                "normalization_level_dbfs": -3.0,
                "remove_silence": False,
                "min_silence_len_ms": 1000,
                "silence_thresh_db": -35,
                "sample_rate": 48000, # Added sample rate setting
                "delete_original_after_processing": False # Specific for audio
            },
            "image_background_removal": {
                "delete_original_after_processing": False,
                "image_quality_enhancement": True
            },
            "video_background_removal": {
                "output_fps": None, # Use original FPS by default
                "default_background_color": "#000000" # Black for transparency fallback
            },
            "video_enhancement": {
                "denoise_strength": 2.0,
                "sharpen_strength": 0.5,
                "contrast_enhance": 1.1,
                "saturation": 1.1,
                "gamma": 1.0,
                "brightness": 0.0,
                "shadow_highlight": 0.2
            }
        },
        "app_settings": {
            "theme": "dark-blue", # This must be "dark-blue"
            "appearance_mode": "System", # "System", "Dark", "Light"
            "logging_level": "INFO" # Corresponds to logging.INFO
        }
    }

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_dir="config", config_file_name="settings.json"):
        if self._initialized:
            return

        self.logger = get_application_logger()
        self.config_dir = Path(config_dir)
        self.config_file_path = self.config_dir / config_file_name
        self._config_data = {}
        self._initialized = True
        self._load_config()

    def _load_config(self):
        """
        Loads configuration from the JSON file. If the file doesn't exist,
        it creates one with default settings.
        """
        self.config_dir.mkdir(parents=True, exist_ok=True) # Ensure config directory exists

        if self.config_file_path.exists():
            try:
                with open(self.config_file_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                
                # Merge loaded config with default config to handle new settings in future versions
                # and ensure all keys are present. Existing keys from file override defaults.
                self._config_data = self._deep_merge_dicts(self._default_config, loaded_config)
                self.logger.info(f"Configuration loaded from {self.config_file_path}")
            except json.JSONDecodeError as e:
                self.logger.error(f"Error decoding config file {self.config_file_path}: {e}. Using default configuration.")
                self._config_data = self._default_config.copy()
                self._save_config() # Save defaults if corrupted
            except Exception as e:
                self.logger.error(f"An unexpected error occurred while loading config: {e}. Using default configuration.")
                self._config_data = self._default_config.copy()
                self._save_config() # Save defaults if an error occurred
        else:
            self.logger.info(f"Config file not found at {self.config_file_path}. Creating with default settings.")
            self._config_data = self._default_config.copy()
            self._save_config() # Save default configuration

    def _save_config(self):
        """
        Saves the current configuration to the JSON file.
        """
        self.config_dir.mkdir(parents=True, exist_ok=True) # Ensure directory exists before saving
        try:
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(self._config_data, f, indent=4)
            self.logger.info(f"Configuration saved to {self.config_file_path}")
        except Exception as e:
            self.logger.error(f"Error saving configuration to {self.config_file_path}: {e}")

    def _deep_merge_dicts(self, default_dict, custom_dict):
        """
        Recursively merges two dictionaries. Values from custom_dict override
        those in default_dict.
        """
        merged_dict = default_dict.copy()
        for key, value in custom_dict.items():
            if key in merged_dict and isinstance(merged_dict[key], dict) and isinstance(value, dict):
                merged_dict[key] = self._deep_merge_dicts(merged_dict[key], value)
            else:
                merged_dict[key] = value
        return merged_dict

    def get_setting(self, key_path: str, default=None):
        """
        Retrieves a setting value using a dot-separated key path (e.g., "output_directories.default_video_output").
        """
        keys = key_path.split('.')
        current_level = self._config_data
        for key in keys:
            if isinstance(current_level, dict) and key in current_level:
                current_level = current_level[key]
            else:
                self.logger.warning(f"Configuration key '{key_path}' not found. Returning default value: {default}")
                return default
        return current_level

    def set_setting(self, key_path: str, value):
        """
        Sets a setting value using a dot-separated key path.
        Automatically saves the configuration after setting.
        """
        keys = key_path.split('.')
        current_level = self._config_data
        for i, key in enumerate(keys):
            if i == len(keys) - 1: # Last key in the path
                current_level[key] = value
            else:
                if key not in current_level or not isinstance(current_level[key], dict):
                    current_level[key] = {} # Create sub-dictionary if it doesn't exist
                current_level = current_level[key]
        self.logger.info(f"Setting '{key_path}' updated to '{value}'.")
        self._save_config() # Save changes immediately

    def get_all_settings(self):
        """
        Returns a copy of all current configuration settings.
        """
        return self._config_data.copy()

# Global instance for easy access throughout the application
# Initialize with default config directory and file name
app_config_manager = ConfigManager(config_dir="config", config_file_name="settings.json")

def get_application_config():
    """
    Convenience function to get the global config manager instance.
    """
    return app_config_manager

if __name__ == "__main__":
    # Example Usage and Testing
    # Ensure logs directory exists for the logger
    os.makedirs("logs", exist_ok=True)
    # Re-initialize logger for standalone testing context
    from src.core.logger import AppLogger
    AppLogger(log_dir="logs", log_level=logging.DEBUG)


    config = get_application_config()
    logger = get_application_logger()

    logger.info("\n--- Testing ConfigManager ---")

    # Test getting default settings
    default_video_output = config.get_setting("output_directories.default_video_output")
    logger.info(f"Default Video Output: {default_video_output}")

    denoise_strength = config.get_setting("processing_parameters.video_enhancement.denoise_strength")
    logger.info(f"Default Denoise Strength: {denoise_strength}")

    app_theme = config.get_setting("app_settings.theme")
    logger.info(f"App Theme: {app_theme}")

    # Test setting a new value
    test_output_path = str(Path.home() / "Desktop" / "MyCustomOutput")
    config.set_setting("output_directories.default_video_output", test_output_path)
    logger.info(f"New Default Video Output: {config.get_setting('output_directories.default_video_output')}")

    # Test setting a non-existent key path (it should create it)
    config.set_setting("new_category.new_setting", "Hello World")
    logger.info(f"New setting 'new_category.new_setting': {config.get_setting('new_category.new_setting')}")

    # Test getting a non-existent key
    non_existent = config.get_setting("non_existent.key", "default_value_fallback")
    logger.info(f"Non-existent key (with fallback): {non_existent}")

    # Verify content of the config file
    logger.info(f"Config file content: {config.get_all_settings()}")

    # Clean up test entry
    config.set_setting("new_category", None) # Cannot delete, setting to None

    logger.info("\n--- ConfigManager Test Completed ---")

    # To truly clean up the new_category created for testing, you'd need to manually
    # delete it from the underlying dictionary or reload defaults.
    # For a real application, you'd have more robust UI for managing settings.
