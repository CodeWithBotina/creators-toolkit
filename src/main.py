import customtkinter
import logging
import sys
from pathlib import Path
import subprocess # For running external commands like ffmpeg
from tkinter import messagebox # For displaying startup messages
import time # For potential debugging delays

# Import core modules
from src.core.logger import get_application_logger, AppLogger # Ensure AppLogger is imported for initialization
from src.core.config_manager import get_application_config, ConfigManager # Ensure ConfigManager is imported for initialization
from src.modules.history_manager import get_application_history_manager, HistoryManager # Ensure HistoryManager is imported for initialization

# Import main window class
from src.gui.main_window import MainWindow # Changed App to MainWindow

# --- Initialize Core Services ---
# This must happen before any other module attempts to get a logger or config.
# Ensure 'logs', 'config', and 'assets' directories exist.
Path("logs").mkdir(exist_ok=True)
Path("config").mkdir(exist_ok=True)
Path("assets").mkdir(exist_ok=True) # Ensure assets directory exists for icon

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
        messagebox.showerror("Critical Application Error", # UI text in English
                             f"An unhandled error occurred during application startup:\n\n{e}\n\n" # UI text in English
                             "Please check the application logs for more details.") # UI text in English
        sys.exit(1)