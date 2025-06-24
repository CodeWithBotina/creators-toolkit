import logging
import os
from datetime import datetime

class AppLogger:
    """
    Manages the application's logging system.
    Logs are written to a file and optionally to the console.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(AppLogger, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, log_dir="logs", log_level=logging.INFO):
        if self._initialized:
            return

        self.log_dir = log_dir
        self.log_level = log_level
        self._setup_logging()
        self._initialized = True

    def _setup_logging(self):
        """
        Configures the logging handlers and formatters.
        """
        os.makedirs(self.log_dir, exist_ok=True)

        # Get current date for log file naming
        log_file_name = datetime.now().strftime("app_%Y-%m-%d.log")
        log_file_path = os.path.join(self.log_dir, log_file_name)

        # Basic configuration for the root logger
        # This will set up default handlers if not already configured
        logging.basicConfig(
            level=self.log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file_path, encoding='utf-8'),
                # Optional: Console handler for development/debugging
                logging.StreamHandler()
            ]
        )

        # Prevent duplicate log messages if basicConfig is called multiple times
        # or if other modules also set up handlers
        for handler in logging.root.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(logging.INFO) # Set default console level to INFO
            if isinstance(handler, logging.FileHandler):
                handler.setLevel(self.log_level) # File handler uses configured level

        # Get the main application logger
        self.logger = logging.getLogger("CreatorToolkit")
        self.logger.setLevel(self.log_level)

        # Ensure the main logger does not propagate to root logger if root is also configured
        # This prevents duplicate messages if basicConfig is already running a StreamHandler
        self.logger.propagate = False

        # Add handlers explicitly if basicConfig didn't cover our specific needs
        # (This block is mostly for safety/advanced control, basicConfig usually suffices)
        if not any(isinstance(h, logging.FileHandler) and h.baseFilename == os.path.abspath(log_file_path) for h in self.logger.handlers):
            file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
            file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            file_handler.setLevel(self.log_level)
            self.logger.addHandler(file_handler)

        if not any(isinstance(h, logging.StreamHandler) for h in self.logger.handlers):
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            stream_handler.setLevel(logging.INFO) # Default to INFO for console
            self.logger.addHandler(stream_handler)

    def get_logger(self):
        """
        Returns the configured logger instance.
        """
        return self.logger

# Global instance for easy access throughout the application
# Initialize with default log directory and level
app_logger_instance = AppLogger(log_dir="logs", log_level=logging.INFO)

def get_application_logger():
    """
    Convenience function to get the global logger instance.
    """
    return app_logger_instance.get_logger()

if __name__ == "__main__":
    # Example Usage and Testing
    logger = get_application_logger()

    logger.debug("This is a DEBUG message.")
    logger.info("This is an INFO message.")
    logger.warning("This is a WARNING message.")
    logger.error("This is an ERROR message.")
    logger.critical("This is a CRITICAL message.")

    logger.info("Testing log rotation: a new file should be created daily.")
    logger.info(f"Log files are saved in: {os.path.abspath('logs')}")

    # You can also get specific loggers for modules
    module_logger = logging.getLogger("CreatorToolkit.VideoModule")
    module_logger.info("Message from VideoModule.")