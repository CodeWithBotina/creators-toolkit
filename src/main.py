import customtkinter
import logging
import sys
from pathlib import Path
import subprocess # For running external commands like ffmpeg
from tkinter import messagebox # For displaying startup messages
import time # For potential debugging delays
import os # For setting environment variables

# Import core modules
from src.core.logger import get_application_logger, AppLogger # Ensure AppLogger is imported for initialization
from src.core.config_manager import get_application_config, ConfigManager # Ensure ConfigManager is imported for initialization
from src.modules.history_manager import get_application_history_manager, HistoryManager # Ensure HistoryManager is imported for initialization
from src.utils.font_manager import get_application_font_manager, FontManager # Ensure FontManager is imported for initialization

# Import main window class
from src.gui.main_window import MainWindow # Changed App to MainWindow

# --- Initialize Core Services ---
# This must happen before any other module attempts to get a logger or config.
# Ensure 'logs', 'config', 'assets', 'models', and 'bin' directories exist.
Path("logs").mkdir(exist_ok=True)
Path("config").mkdir(exist_ok=True)
Path("assets").mkdir(exist_ok=True) # Ensure assets directory exists for icon and fonts
Path("assets/fonts").mkdir(parents=True, exist_ok=True) # Ensure specific font directory
Path("models").mkdir(exist_ok=True) # Ensure models directory for rembg/vosk
Path("bin").mkdir(exist_ok=True) # Ensure bin directory for ffmpeg/other binaries

# Initialize the global logger instance
# AppLogger() is a singleton, so calling it here ensures it's configured.
AppLogger(log_dir="logs", log_level=logging.INFO)
logger = get_application_logger()
logger.info("Application startup process initiated.")

# Initialize the global config manager instance
ConfigManager(config_dir="config")
config_manager = get_application_config()
logger.info("Configuration manager initialized.")

# Initialize the global history manager instance
# Pass only the filename, as HistoryManager constructs the full path based on config_dir
HistoryManager(history_file_name="history.json")
history_manager = get_application_history_manager()
logger.info("History manager initialized.")

# Initialize the global font manager instance
FontManager(font_dir="assets/fonts") # Pass the dedicated font directory
font_manager = get_application_font_manager()
logger.info("Font manager initialized.")

# --- Set FFmpeg Binary Path (Crucial for MoviePy/Subprocess) ---
# Retrieve the binaries directory from the configuration.
# This assumes FFmpeg is extracted into `bin/ffmpeg` within the app's root.
ffmpeg_path = Path("bin") / "ffmpeg" / "bin" / "ffmpeg.exe" # Default expected path

# Attempt to find ffmpeg.exe based on typical installations or user configuration
ffmpeg_config_path = config_manager.get_setting("app_settings.ffmpeg_path")
if ffmpeg_config_path and Path(ffmpeg_config_path).is_file():
    ffmpeg_path = Path(ffmpeg_config_path)
    logger.info(f"Using FFmpeg path from config: {ffmpeg_path}")
elif Path("bin/ffmpeg/bin/ffmpeg.exe").is_file():
    ffmpeg_path = Path("bin/ffmpeg/bin/ffmpeg.exe")
    logger.info(f"Using default bundled FFmpeg path: {ffmpeg_path}")
elif Path("C:/ffmpeg/bin/ffmpeg.exe").is_file(): # Common install location
    ffmpeg_path = Path("C:/ffmpeg/bin/ffmpeg.exe")
    logger.info(f"Using common FFmpeg install path: {ffmpeg_path}")
else:
    logger.warning("FFmpeg executable not found at common paths or in config. Please ensure FFmpeg is installed and accessible via PATH, or configured.")
    # Fallback: Rely on FFmpeg being in system PATH, or let subprocess commands fail.
    # We still set the env var just in case it helps for some libraries like moviepy.
    ffmpeg_path = Path("ffmpeg") # This will make subprocess look in PATH

os.environ["FFMPEG_BINARY"] = str(ffmpeg_path)
logger.info(f"FFMPEG_BINARY environment variable set to: {os.environ['FFMPEG_BINARY']}")


# Set CustomTkinter appearance mode and color theme based on config
app_appearance_mode = config_manager.get_setting("app_settings.appearance_mode", "System")
app_theme = config_manager.get_setting("app_settings.theme", "dark-blue")

# Moved customtkinter import here as it relies on config values
customtkinter.set_appearance_mode(app_appearance_mode)
customtkinter.set_default_color_theme(app_theme)

if __name__ == "__main__":
    try:
        app = MainWindow() # Instantiate the main application window
        logger.debug("Calling app.mainloop()...")
        app.mainloop()
        logger.debug("app.mainloop() returned.")
    except Exception as e:
        logger.critical(f"An unhandled error occurred during application startup: {e}", exc_info=True)
        # Display a critical error message box before exiting
        messagebox.showerror("Application Critical Error",
                             f"An unexpected error occurred during application startup:\n\n{e}\n\n"
                             "Please check the application logs for more details.")
        sys.exit(1)

