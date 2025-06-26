import json
from pathlib import Path
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple


from src.core.logger import get_application_logger
from src.core.config_manager import get_application_config # To get config paths

class HistoryManagerError(Exception):
    """Custom exception for history manager errors."""
    pass

class HistoryManager:
    """
    Manages the application's processing history.
    Stores records of tasks performed (e.g., video conversions, enhancements).
    History is stored in a JSON file within the application's config directory.
    Implements a singleton pattern.
    """
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        """Ensures that only one instance of HistoryManager exists (Singleton pattern)."""
        if cls._instance is None:
            cls._instance = super(HistoryManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, history_file_name: str = "history.json"):
        """
        Initializes the HistoryManager.
        
        Args:
            history_file_name (str): The name of the JSON file to store history.
        """
        if self._initialized:
            return

        self.logger = get_application_logger()
        self.config_manager = get_application_config() # Get the global config instance

        # Determine history file path using the config_dir from ConfigManager
        config_dir_str = self.config_manager.get_setting("app_settings.config_dir", "config")
        self.history_dir = Path(config_dir_str)
        self.history_file_path = self.history_dir / history_file_name
        self.history_dir.mkdir(parents=True, exist_ok=True) # Ensure history directory exists

        self.history_data: List[Dict[str, Any]] = []
        self._load_history()
        
        self._initialized = True
        self.logger.info(f"HistoryManager initialized. History file: {self.history_file_path}")

    def _load_history(self):
        """
        Loads the processing history from the JSON file.
        Initializes an empty history if the file does not exist or is invalid.
        """
        if self.history_file_path.exists():
            try:
                with open(self.history_file_path, 'r', encoding='utf-8') as f:
                    self.history_data = json.load(f)
                self.logger.info(f"History loaded from {self.history_file_path}. {len(self.history_data)} entries found.")
            except json.JSONDecodeError as e:
                self.logger.error(f"Error decoding JSON from history file {self.history_file_path}: {e}", exc_info=True)
                self.history_data = [] # Reset to empty if file is corrupt
                self.logger.warning("History file corrupted or invalid. Initializing with empty history.")
            except Exception as e:
                self.logger.error(f"An unexpected error occurred while loading history from {self.history_file_path}: {e}", exc_info=True)
                self.history_data = []
                self.logger.warning("An unexpected error occurred during history load. Initializing with empty history.")
        else:
            self.logger.info(f"History file not found: {self.history_file_path}. Initializing with empty history.")
            self.history_data = []
            self._save_history() # Create an empty file

    def _save_history(self):
        """Saves the current processing history to the JSON file."""
        try:
            with open(self.history_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.history_data, f, indent=4)
            self.logger.debug(f"History saved to {self.history_file_path}.")
        except Exception as e:
            self.logger.error(f"Failed to save history to {self.history_file_path}: {e}", exc_info=True)
            raise HistoryManagerError(f"Could not save history: {e}")

    def log_task(self,
                 task_type: str,
                 input_path: Optional[Path],
                 output_path: Optional[Path],
                 status: str,
                 message: str,
                 details: Optional[Dict[str, Any]] = None):
        """
        Logs a task completion or failure into the history.

        Args:
            task_type (str): The type of task performed (e.g., "Video Conversion", "Image Background Removal").
            input_path (Optional[Path]): The path to the input file, if applicable.
            output_path (Optional[Path]): The path to the output file, if applicable.
            status (str): The status of the task ("Completed", "Failed", "Cancelled", "In Progress").
            message (str): A descriptive message about the task's outcome.
            details (Optional[Dict[str, Any]]): Optional dictionary for additional task-specific details.
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "task_type": task_type,
            "input_path": str(input_path) if input_path else None,
            "output_path": str(output_path) if output_path else None,
            "status": status,
            "message": message,
            "details": details if details is not None else {}
        }
        self.history_data.insert(0, entry) # Add to the beginning of the list for chronological display
        
        # Keep history file size manageable (e.g., last 100 entries)
        max_entries = self.config_manager.get_setting("app_settings.history_max_entries", 100)
        if len(self.history_data) > max_entries:
            self.history_data = self.history_data[:max_entries]
            self.logger.debug(f"History truncated to {max_entries} entries.")

        self._save_history()
        self.logger.info(f"Logged task: '{task_type}' - Status: '{status}' for '{input_path.name if input_path else 'N/A'}'")

    def get_history(self, task_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves the entire processing history or filters by task type.

        Args:
            task_type (Optional[str]): If provided, only returns entries matching this task type.

        Returns:
            List[Dict[str, Any]]: A list of history entries.
        """
        if task_type:
            return [entry for entry in self.history_data if entry.get("task_type") == task_type]
        return list(self.history_data) # Return a copy to prevent external modification

    def clear_history(self):
        """Clears all entries from the processing history."""
        self.history_data = []
        self._save_history()
        self.logger.info("Processing history cleared.")


# Global instance for easy access throughout the application
_app_history_manager_instance: Optional[HistoryManager] = None

def get_application_history_manager() -> HistoryManager:
    """
    Convenience function to get the global HistoryManager instance.
    Ensures it's initialized only once.
    This function should be called after HistoryManager() has been explicitly
    instantiated once in main.py.
    """
    global _app_history_manager_instance
    if _app_history_manager_instance is None:
        # This case should ideally not happen if main.py initializes HistoryManager first.
        # However, for robustness in isolated tests or unexpected call order, we
        # create a default instance.
        _app_history_manager_instance = HistoryManager()
        get_application_logger().warning("get_application_history_manager() called before HistoryManager was explicitly initialized. Using default setup.")
    return _app_history_manager_instance

