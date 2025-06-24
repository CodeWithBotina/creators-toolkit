import os
import json
import logging
from pathlib import Path
import requests # For downloading fonts
from typing import Dict, List, Optional

from src.core.logger import get_application_logger
from src.core.config_manager import get_application_config

class FontManagerError(Exception):
    """Custom exception for font manager errors."""
    pass

class FontManager:
    """
    Manages downloading and providing paths to fonts for the application.
    Fonts are configured via a JSON file and downloaded on demand.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(FontManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, assets_dir: str = "assets", fonts_config_file: str = "fonts_config.json", fonts_subdir: str = "fonts"):
        if self._initialized:
            return

        self.logger = get_application_logger()
        self.config_manager = get_application_config()

        self.assets_dir = Path(assets_dir)
        self.fonts_config_path = self.assets_dir / fonts_config_file
        self.fonts_download_dir = self.assets_dir / fonts_subdir
        self.fonts_download_dir.mkdir(parents=True, exist_ok=True) # Ensure fonts directory exists

        self._fonts_data = {} # Stores data from fonts_config.json
        self._load_fonts_config()

        self._initialized = True
        self.logger.info("FontManager initialized.")

    def _load_fonts_config(self):
        """
        Loads the font configuration from the JSON file.
        """
        if self.fonts_config_path.exists():
            try:
                with open(self.fonts_config_path, 'r', encoding='utf-8') as f:
                    self._fonts_data = json.load(f)
                self.logger.info(f"Font configuration loaded from {self.fonts_config_path}")
            except json.JSONDecodeError as e:
                self.logger.error(f"Error decoding font config file {self.fonts_config_path}: {e}. Fonts will not be available.", exc_info=True)
                self._fonts_data = {}
            except Exception as e:
                self.logger.error(f"An unexpected error occurred while loading font config: {e}. Fonts will not be available.", exc_info=True)
                self._fonts_data = {}
        else:
            self.logger.warning(f"Font configuration file not found at {self.fonts_config_path}. No custom fonts will be available.")
            self.create_default_fonts_config() # Create a default one if not found

    def create_default_fonts_config(self):
        """
        Creates a default fonts_config.json if it doesn't exist.
        """
        default_config = {
            "default_font_name": "Arial", # A common system font that should always be available
            "available_fonts": [
                {
                    "name": "Montserrat",
                    "style": "Regular",
                    "file_name": "Montserrat-Regular.ttf",
                    "download_url": "https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat-Regular.ttf"
                },
                {
                    "name": "Open Sans",
                    "style": "Regular",
                    "file_name": "OpenSans-Regular.ttf",
                    "download_url": "https://github.com/google/fonts/raw/main/ofl/opensans/OpenSans-Regular.ttf"
                },
                {
                    "name": "Roboto",
                    "style": "Regular",
                    "file_name": "Roboto-Regular.ttf",
                    "download_url": "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Regular.ttf"
                },
                {
                    "name": "Lato",
                    "style": "Regular",
                    "file_name": "Lato-Regular.ttf",
                    "download_url": "https://github.com/google/fonts/raw/main/ofl/lato/Lato-Regular.ttf"
                },
                {
                    "name": "Oswald",
                    "style": "Regular",
                    "file_name": "Oswald-Regular.ttf",
                    "download_url": "https://github.com/google/fonts/raw/main/ofl/oswald/Oswald-Regular.ttf"
                }
            ]
        }
        try:
            with open(self.fonts_config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4)
            self.logger.info(f"Default font configuration created at {self.fonts_config_path}")
            self._fonts_data = default_config # Load the newly created default config
        except Exception as e:
            self.logger.error(f"Failed to create default font config file at {self.fonts_config_path}: {e}", exc_info=True)

    def get_font_path(self, font_name: str, style: str = "Regular") -> Optional[Path]:
        """
        Returns the path to the font file. If the font is not downloaded,
        it attempts to download it.
        Returns None if font is not found or download fails.
        """
        # First, check if it's a system font (e.g., Arial, Times New Roman)
        # For simplicity, we assume if it's not in our config, it might be a system font.
        # This is a basic check; a more robust solution would query system font directories.
        if font_name not in [f["name"] for f in self._fonts_data.get("available_fonts", [])]:
            self.logger.debug(f"Font '{font_name}' not found in custom config. Assuming it's a system font.")
            return Path(font_name) # Return font name directly, MoviePy/PIL might resolve it

        for font_info in self._fonts_data.get("available_fonts", []):
            if font_info["name"].lower() == font_name.lower() and font_info.get("style", "Regular").lower() == style.lower():
                font_file = self.fonts_download_dir / font_info["file_name"]
                if font_file.exists():
                    self.logger.debug(f"Font '{font_name}' already downloaded: {font_file}")
                    return font_file
                else:
                    self.logger.info(f"Attempting to download font '{font_name}' from: {font_info.get('download_url')}")
                    if self._download_font(font_info["download_url"], font_file):
                        return font_file
                    else:
                        self.logger.error(f"Failed to download font: {font_name}")
                        return None
        self.logger.warning(f"Font '{font_name}' with style '{style}' not found in configuration or could not be downloaded.")
        return None

    def _download_font(self, url: str, destination_path: Path) -> bool:
        """
        Downloads a font file from the given URL to the destination path.
        """
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
            with open(destination_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            self.logger.info(f"Successfully downloaded font to: {destination_path}")
            return True
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error downloading font from {url}: {e}", exc_info=True)
            return False
        except Exception as e:
            self.logger.error(f"Error saving downloaded font to {destination_path}: {e}", exc_info=True)
            return False

    def get_available_font_names(self) -> List[str]:
        """
        Returns a list of names of all fonts listed in the configuration.
        """
        return [font_info["name"] for font_info in self._fonts_data.get("available_fonts", [])]

    def get_default_font_path(self) -> Path:
        """
        Returns the path for the default font. Attempts to download if it's a custom font.
        Falls back to a very common system font if the configured default is unavailable.
        """
        default_font_name = self._fonts_data.get("default_font_name", "Arial")
        default_font_path = self.get_font_path(default_font_name)
        if default_font_path:
            return default_font_path
        else:
            self.logger.warning(f"Default font '{default_font_name}' not found or could not be downloaded. Falling back to 'Arial'.")
            # If default_font_name is not found in custom list, and is not downloadable, return "Arial"
            # MoviePy/PIL usually can find "Arial" on most systems
            return Path("Arial") # Rely on system's ability to find common fonts


# Global instance for easy access
app_font_manager = FontManager()

def get_application_font_manager() -> FontManager:
    """
    Convenience function to get the global font manager instance.
    """
    return app_font_manager

if __name__ == "__main__":
    # --- Isolated Test for FontManager ---
    # Setup logger for standalone testing
    current_dir = Path(__file__).parent
    logs_dir = current_dir.parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True) # Ensure logs directory exists
    from src.core.logger import AppLogger
    AppLogger(log_dir=str(logs_dir), log_level=logging.DEBUG)
    test_logger = get_application_logger()
    test_logger.info("--- Starting FontManager module test ---")

    assets_test_dir = current_dir.parent.parent / "test_assets"
    shutil.rmtree(assets_test_dir, ignore_errors=True) # Clean up previous test assets
    assets_test_dir.mkdir(exist_ok=True)

    # Re-initialize ConfigManager for this test context, assuming it's in parent.parent/config
    config_dir_path = current_dir.parent.parent / "config"
    config_dir_path.mkdir(exist_ok=True)
    from src.core.config_manager import ConfigManager
    ConfigManager(config_dir=str(config_dir_path))


    # Create a temporary FontManager instance for testing
    font_manager = FontManager(assets_dir=str(assets_test_dir))

    # Test 1: Get default font path (should create config file if not exists)
    test_logger.info("\n--- Test 1: Getting default font path ---")
    default_font = font_manager.get_default_font_path()
    test_logger.info(f"Default font path: {default_font}")
    assert default_font is not None
    assert font_manager.fonts_config_path.exists()

    # Test 2: List available fonts
    test_logger.info("\n--- Test 2: Listing available fonts ---")
    available_fonts = font_manager.get_available_font_names()
    test_logger.info(f"Available fonts: {available_fonts}")
    assert len(available_fonts) > 0
    assert "Montserrat" in available_fonts

    # Test 3: Download a specific font
    test_logger.info("\n--- Test 3: Downloading 'Montserrat' font ---")
    montserrat_path = font_manager.get_font_path("Montserrat")
    test_logger.info(f"Montserrat font path: {montserrat_path}")
    assert montserrat_path is not None
    assert montserrat_path.exists()
    assert montserrat_path.name == "Montserrat-Regular.ttf"

    # Test 4: Attempt to get a non-existent font (should return None or system font name)
    test_logger.info("\n--- Test 4: Getting non-existent font ---")
    non_existent_font = font_manager.get_font_path("NonExistentFont")
    test_logger.info(f"Non-existent font path: {non_existent_font}")
    # This behavior might depend on the system/PIL, but for this test, we expect a path-like object or None
    assert non_existent_font is not None # It should fall back to trying to find it as system font, or return Path("NonExistentFont")

    # Test 5: Try to get a font that's already downloaded
    test_logger.info("\n--- Test 5: Getting already downloaded font ---")
    montserrat_path_again = font_manager.get_font_path("Montserrat")
    test_logger.info(f"Montserrat font path (again): {montserrat_path_again}")
    assert montserrat_path_again == montserrat_path

    test_logger.info("\n--- FontManager module test completed ---")

    # Clean up test assets
    shutil.rmtree(assets_test_dir, ignore_errors=True)
    test_logger.info(f"Cleaned up test assets directory: {assets_test_dir}")