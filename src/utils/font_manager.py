import logging
from pathlib import Path
import os
import shutil
from typing import List, Dict, Any, Optional

from src.core.logger import get_application_logger
from src.core.config_manager import get_application_config

class FontManager:
    """
    Manages application font resources.
    - Scans for fonts in a designated custom font directory.
    - Provides paths to fonts for use by other modules (e.g., MoviePy).
    - Includes a fallback for common system fonts.
    - Simulates downloading fonts if they are not found locally.
    """
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(FontManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, font_dir="assets/fonts", default_system_fonts=None):
        """
        Initializes the FontManager.
        
        Args:
            font_dir (str): Directory where custom/downloaded fonts will be stored.
            default_system_fonts (List[str], optional): A list of common font names
                                                        to assume are available on the system.
        """
        if self._initialized:
            return

        self.logger = get_application_logger()
        self.config_manager = get_application_config() # Access global config manager
        self.font_dir = Path(font_dir)
        self.font_dir.mkdir(parents=True, exist_ok=True) # Ensure the font directory exists
        self.logger.info(f"FontManager initialized. Custom/downloadable font directory: {self.font_dir}")

        self.available_fonts = set() # Set to store unique font names
        self.font_paths_cache = {} # Map font name (e.g., "Arial") to its Path object

        # List of universally common system fonts. For cross-platform compatibility,
        # we assume these are often available by name, or we provide a dummy.
        if default_system_fonts is None:
            self.default_system_fonts = [
                "Arial", "Verdana", "Helvetica", "Times New Roman", 
                "Courier New", "Georgia", "Trebuchet MS", "Impact", "Consolas",
                "Roboto", "Open Sans", "Lato", "Montserrat", "Oswald" # Common web fonts that might be installed
            ]
        else:
            self.default_system_fonts = default_system_fonts
        
        self.available_fonts.update(self.default_system_fonts)
        self._scan_custom_fonts_dir() # Scan for fonts already in our custom directory
        
        self._initialized = True
        self.logger.info(f"FontManager scan complete. Found {len(self.available_fonts)} font names.")

    def _scan_custom_fonts_dir(self):
        """
        Scans the custom font directory for .ttf and .otf files and adds them
        to the available fonts and cache.
        """
        self.logger.debug(f"Scanning custom font directory: {self.font_dir}")
        for font_file in self.font_dir.iterdir():
            if font_file.suffix.lower() in ['.ttf', '.otf']:
                # Extract font name from filename. This is a simplification;
                # for true font names, parsing the font file metadata is needed.
                # For example: 'arial.ttf' -> 'Arial'
                # 'open-sans-bold.ttf' -> 'Open Sans Bold'
                font_name = font_file.stem.replace('-', ' ').replace('_', ' ').title()
                if font_name not in self.available_fonts:
                    self.available_fonts.add(font_name)
                    self.font_paths_cache[font_name] = font_file
                    self.logger.debug(f"Found custom font: '{font_name}' at '{font_file}'")
                elif font_name in self.available_fonts and font_name not in self.font_paths_cache:
                    # If it's a default system font but we found a local file, prioritize local
                    self.font_paths_cache[font_name] = font_file
                    self.logger.debug(f"Prioritizing local file for '{font_name}': '{font_file}'")


    def get_available_font_names(self) -> List[str]:
        """
        Returns a sorted list of all unique font names that are either recognized system fonts
        or available in the custom font directory.
        """
        return sorted(list(self.available_fonts))

    def get_font_path(self, font_name: str) -> Optional[Path]:
        """
        Returns the Path object for a given font name.
        
        Args:
            font_name (str): The name of the font (e.g., "Arial", "Open Sans").
            
        Returns:
            Optional[Path]: The path to the font file if found or "downloaded", else None.
        """
        # 1. Check if already in cache
        if font_name in self.font_paths_cache:
            self.logger.debug(f"Font '{font_name}' found in cache: {self.font_paths_cache[font_name]}")
            return self.font_paths_cache[font_name]
        
        # 2. Check if it's a known default system font (MoviePy might find it by name)
        # For actual file paths for system fonts, platform-specific methods are needed.
        # As a simplified approach for Windows, we can try common font directories.
        # For other OSes, this would need expansion.
        if font_name in self.default_system_fonts:
            # Attempt to find a common system font path (Windows specific for example)
            # This is a very basic attempt. A robust solution needs platform-specific logic.
            if os.name == 'nt': # Windows
                for font_ext in ['.ttf', '.otf']:
                    potential_path = Path(os.environ['WINDIR']) / "Fonts" / f"{font_name}{font_ext}"
                    if potential_path.exists():
                        self.font_paths_cache[font_name] = potential_path
                        self.logger.info(f"Found system font '{font_name}' at: {potential_path}")
                        return potential_path
                    # Also try common variations like "Arial Bold.ttf" etc.
                    potential_path_lower = Path(os.environ['WINDIR']) / "Fonts" / f"{font_name.lower().replace(' ', '')}{font_ext}"
                    if potential_path_lower.exists():
                        self.font_paths_cache[font_name] = potential_path_lower
                        self.logger.info(f"Found system font '{font_name}' at: {potential_path_lower}")
                        return potential_path_lower
            # Linux: /usr/share/fonts, ~/.local/share/fonts
            # macOS: /Library/Fonts, /System/Library/Fonts, ~/Library/Fonts
            # For now, if not found explicitly, proceed to simulate download for consistency.


        # 3. If not found, simulate downloading and saving the font to our custom directory.
        # In a real application, this would involve:
        #   a) Querying a font API (e.g., Google Fonts API) to get a download URL.
        #   b) Using 'requests' to download the font file.
        #   c) Saving the file to self.font_dir.
        
        self.logger.warning(f"Font '{font_name}' not found locally or in common system paths. Simulating download.")
        # Create a dummy font file for simulation
        safe_font_filename = f"{font_name.lower().replace(' ', '_')}.ttf"
        dummy_font_file_path = self.font_dir / safe_font_filename
        
        try:
            # Create a placeholder dummy font file content
            # (This is NOT a real TTF/OTF file, just a byte placeholder)
            dummy_content = b'This is a dummy font file content. Replace with real font data.'
            with open(dummy_font_file_path, 'wb') as f:
                f.write(dummy_content)
            
            self.logger.info(f"Simulated download and saved dummy font '{font_name}' to '{dummy_font_file_path}'")
            self.font_paths_cache[font_name] = dummy_font_file_path
            self.available_fonts.add(font_name) # Add to available fonts if newly "downloaded"
            return dummy_font_file_path
        except Exception as e:
            self.logger.error(f"Failed to simulate font download for '{font_name}': {e}", exc_info=True)
            return None # Cannot provide a path

    def get_default_font_path(self) -> Path:
        """
        Returns a path to a universally available fallback font.
        This is used when a selected font cannot be found or downloaded.
        Prioritizes 'Arial' from our custom dir or system, then a basic dummy.
        """
        # Try to get Arial, which is a very common font
        arial_path = self.get_font_path("Arial")
        if arial_path and arial_path.exists():
            return arial_path
        
        self.logger.warning("Could not find 'Arial'. Falling back to a generic dummy font.")
        # If Arial isn't available, create/use a generic dummy font in our assets
        generic_dummy_path = self.font_dir / "generic_fallback_font.ttf"
        if not generic_dummy_path.exists():
            try:
                with open(generic_dummy_path, 'wb') as f:
                    f.write(b'Generic Fallback Font Content') # Placeholder
                self.logger.info(f"Created generic fallback font at {generic_dummy_path}")
            except Exception as e:
                self.logger.error(f"Failed to create generic fallback font: {e}", exc_info=True)
                # If all else fails, return a non-existent path, which MoviePy will then likely error on.
                # This should ideally not happen in a well-configured environment.
                return Path("non_existent_fallback_font.ttf") 
        return generic_dummy_path


# Global instance for easy access throughout the application
_app_font_manager_instance = None

def get_application_font_manager():
    """
    Convenience function to get the global FontManager instance.
    Ensures it's initialized only once.
    """
    global _app_font_manager_instance
    if _app_font_manager_instance is None:
        _app_font_manager_instance = FontManager()
    return _app_font_manager_instance