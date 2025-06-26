import json
from pathlib import Path
import logging
from typing import List, Dict, Any, Optional

from src.core.logger import get_application_logger
from src.core.config_manager import get_application_config

# Placeholder for actual font download (would use requests in a real application)
def _download_file(url: str, destination_path: Path) -> bool:
    """
    Simulates file download. In a real application, this would use a library
    like 'requests' to fetch the font from the given URL.
    """
    try:
        # Simulate successful download by creating a dummy file
        with open(destination_path, 'wb') as f:
            f.write(b'dummy font data for ' + url.encode('utf-8')) # Placeholder content
        get_application_logger().info(f"Simulated download success for {url} to {destination_path}")
        return True
    except Exception as e:
        get_application_logger().error(f"Simulated download failed for {url}: {e}", exc_info=True)
        return False

class SocialMediaFontManager:
    """
    Manages popular fonts specifically for social media post processing.
    Loads font metadata from a config file and can simulate downloading them.
    """
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(SocialMediaFontManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, font_dir: str = "assets/fonts", config_file_name: str = "fonts_config.json"):
        """
        Initializes the SocialMediaFontManager.

        Args:
            font_dir (str): Directory where custom/downloaded fonts will be stored.
            config_file_name (str): Name of the JSON file containing popular font metadata.
        """
        if self._initialized:
            return

        self.logger = get_application_logger()
        self.config_manager = get_application_config()
        
        # Ensure the font directory exists
        self.font_dir = Path(font_dir)
        self.font_dir.mkdir(parents=True, exist_ok=True)

        # Determine the path for the popular fonts configuration file
        # It's assumed to be within the assets directory
        assets_dir_path = Path(self.config_manager.get_setting("app_settings.assets_dir", "assets"))
        self.config_file_path = assets_dir_path / config_file_name
        
        self.popular_fonts_data: List[Dict[str, Any]] = []
        self._load_popular_fonts_metadata()
        
        self._initialized = True
        self.logger.info("SocialMediaFontManager initialized.")

    def _load_popular_fonts_metadata(self):
        """
        Loads metadata about popular fonts from the JSON configuration file.
        Includes error handling for missing files and incorrect formats.
        """
        if not self.config_file_path.exists():
            self.logger.warning(f"Popular fonts config file not found: {self.config_file_path}. Creating a dummy one.")
            # Create a dummy config if the file doesn't exist
            dummy_data = [
                {"name": "Roboto", "filename": "Roboto-Regular.ttf", "download_url": "https://fonts.google.com/specimen/Roboto/download"},
                {"name": "Open Sans", "filename": "OpenSans-Regular.ttf", "download_url": "https://fonts.google.com/specimen/Open+Sans/download"},
                {"name": "Lato", "filename": "Lato-Regular.ttf", "download_url": "https://fonts.google.com/specimen/Lato/download"}
            ]
            try:
                with open(self.config_file_path, 'w', encoding='utf-8') as f:
                    json.dump(dummy_data, f, indent=4)
                self.logger.info(f"Dummy popular fonts config created at: {self.config_file_path}")
                self.popular_fonts_data = dummy_data
                return
            except Exception as e:
                self.logger.error(f"Failed to create dummy popular fonts config: {e}", exc_info=True)
                self.popular_fonts_data = [] # Ensure it's an empty list on failure
                return # Exit early

        try:
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
                # Validate that the loaded data is a list of dictionaries, each with a 'name' key
                if isinstance(loaded_data, list) and all(isinstance(item, dict) and "name" in item for item in loaded_data):
                    self.popular_fonts_data = loaded_data
                    self.logger.info(f"Popular font metadata loaded from: {self.config_file_path}. {len(self.popular_fonts_data)} fonts found.")
                else:
                    self.logger.error(
                        f"Invalid format in popular fonts config file: {self.config_file_path}. "
                        "Expected a list of dictionaries, each containing a 'name' key."
                    )
                    self.popular_fonts_data = [] # Reset to empty list if format is incorrect
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decoding popular fonts config JSON from {self.config_file_path}: {e}", exc_info=True)
            self.popular_fonts_data = []
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while loading popular fonts metadata from {self.config_file_path}: {e}", exc_info=True)
            self.popular_fonts_data = []

    def get_popular_font_names(self) -> List[str]:
        """
        Returns a list of names of popular fonts available in the metadata.
        """
        return [font["name"] for font in self.popular_fonts_data]

    def get_font_info(self, font_name: str) -> Optional[Dict[str, Any]]:
        """
        Returns the metadata dictionary for a specific popular font by its name.
        """
        for font in self.popular_fonts_data:
            if font["name"] == font_name:
                return font
        return None

    def download_font(self, font_name: str) -> Optional[Path]:
        """
        Simulates downloading a popular font to the font directory.
        In a real application, this would use a library like `requests`.
        """
        font_info = self.get_font_info(font_name)
        if not font_info or not font_info.get("download_url") or not font_info.get("filename"):
            self.logger.warning(f"No download URL or filename found for font: {font_name}")
            return None

        download_url = font_info["download_url"]
        filename = font_info["filename"]
        destination_path = self.font_dir / filename

        if destination_path.exists():
            self.logger.info(f"Font '{font_name}' already exists at {destination_path}. Skipping download.")
            return destination_path

        self.logger.info(f"Attempting to download font '{font_name}' from {download_url} to {destination_path}")
        
        # Use the internal helper for simulated download
        success = _download_file(download_url, destination_path)
        
        if success:
            self.logger.info(f"Successfully downloaded font: {destination_path}")
            return destination_path
        else:
            self.logger.error(f"Failed to download font '{font_name}'.")
            return None

# Global instance for easy access throughout the application
_app_social_media_font_manager_instance = None

def get_social_media_font_manager():
    """
    Convenience function to get the global SocialMediaFontManager instance.
    Ensures it's initialized only once (singleton pattern).
    """
    global _app_social_media_font_manager_instance
    if _app_social_media_font_manager_instance is None:
        _app_social_media_font_manager_instance = SocialMediaFontManager()
    return _app_social_media_font_manager_instance

