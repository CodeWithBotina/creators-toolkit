import logging
from pathlib import Path
from typing import Optional
import sys

# Global variable to hold the single instance of AppLogger
_app_logger_instance: Optional["AppLogger"] = None

class AppLoggerError(Exception):
    """Custom exception for application logger errors."""
    pass

class AppLogger:
    """
    Manages the application's logging system.
    Implements a singleton pattern to ensure a single, consistent logger instance
    across the entire application.
    """
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        """Ensures that only one instance of AppLogger exists (Singleton pattern)."""
        if cls._instance is None:
            cls._instance = super(AppLogger, cls).__new__(cls)
        return cls._instance

    def __init__(self, log_dir: str = "logs", log_level: int = logging.INFO):
        """
        Initializes the AppLogger. This method sets up the logger, file handler,
        and formatter. It is designed to be called once at application startup.
        
        Args:
            log_dir (str): The absolute path to the directory where log files should be stored.
                           This path should be provided by the ConfigManager, which gets it from main.py.
            log_level (int): The minimum logging level to capture (e.g., logging.INFO, logging.DEBUG).
        """
        if self._initialized:
            return

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True) # Ensure the log directory exists

        self.logger = logging.getLogger("CreatorToolkit")
        self.logger.setLevel(log_level)
        self.logger.propagate = False # Prevent logs from going to the root logger

        # Clear existing handlers to prevent duplicate logs on re-initialization (e.g., during tests)
        if self.logger.handlers:
            for handler in self.logger.handlers:
                self.logger.removeHandler(handler)

        # File Handler: Logs all messages to a file
        log_file_path = self.log_dir / "application.log"
        try:
            file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
            file_handler.setLevel(log_level)
            # Format: Timestamp - LoggerName - LevelName - Message
            file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
        except Exception as e:
            # Fallback to console if file logging fails (e.g., permissions)
            print(f"ERROR: Could not set up file logger at {log_file_path}: {e}")
            self.logger.addHandler(logging.StreamHandler(sys.stdout)) # Add a basic console handler
            self.logger.error(f"Failed to set up file logger at {log_file_path}. Logging to console instead.", exc_info=True)
            raise AppLoggerError(f"Failed to set up file logger: {e}") # Re-raise to indicate critical error

        # Console Handler: Logs INFO and above to console (optional, can be removed in final executable)
        # We might want different levels for console vs. file. For now, matching for simplicity.
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_formatter = logging.Formatter('%(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        self._initialized = True
        self.logger.info("AppLogger initialized successfully.")

    def get_logger(self) -> logging.Logger:
        """
        Returns the configured logging.Logger instance.
        """
        return self.logger

def get_application_logger() -> logging.Logger:
    """
    Convenience function to get the global AppLogger's logging.Logger instance.
    Ensures the AppLogger is initialized before returning its logger.
    This function should be called after AppLogger() has been explicitly
    instantiated once in main.py.
    """
    global _app_logger_instance
    if _app_logger_instance is None:
        # This case should ideally not happen if main.py initializes AppLogger first.
        # For robustness, we could create a default instance, but it's better to
        # ensure proper initialization at the application's entry point.
        # Log a warning if this is called before explicit initialization.
        print("WARNING: get_application_logger() called before AppLogger was explicitly initialized. Using default setup.")
        _app_logger_instance = AppLogger() # Initialize with defaults if called prematurely
    return _app_logger_instance.get_logger()