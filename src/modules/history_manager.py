import json
from pathlib import Path
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple # Added Tuple import

from src.core.logger import get_application_logger
from src.core.config_manager import get_application_config # To get config paths

class HistoryManager:
    """
    Manages the application's processing history.
    Stores records of tasks performed (e.g., video conversions, enhancements).
    History is stored in a JSON file.
    """
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(HistoryManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, history_file_name="history.json"):
        """
        Initializes the HistoryManager.
        
        Args:
            history_file_name (str): The name of the JSON file to store history.
        """
        if self._initialized:
            return

        self.logger = get_application_logger()
        self.config_manager = get_application_config() # Get the global config instance

        # Determine history file path
        # History file will be stored directly in the main config directory
        config_dir = Path(self.config_manager.get_setting("app_settings.config_dir", "config"))
        self.history_dir = config_dir 
        self.history_dir.mkdir(parents=True, exist_ok=True) # Ensure the directory exists

        self.history_file_path = self.history_dir / history_file_name
        self.logger.info(f"HistoryManager initialized. History file: {self.history_file_path}")

        self._load_history()
        self._initialized = True

    def _load_history(self) -> None:
        """Loads the processing history from the JSON file."""
        if self.history_file_path.exists():
            try:
                with open(self.history_file_path, 'r', encoding='utf-8') as f:
                    self.history_data = json.load(f)
                self.logger.info(f"History loaded from {self.history_file_path}. {len(self.history_data)} entries found.")
            except json.JSONDecodeError as e:
                self.logger.error(f"Error decoding history file {self.history_file_path}: {e}. Initializing with empty history.", exc_info=True)
                self.history_data = [] # Reset to empty if file is corrupt
            except Exception as e:
                self.logger.error(f"An unexpected error occurred loading history file {self.history_file_path}: {e}. Initializing with empty history.", exc_info=True)
                self.history_data = [] # Reset to empty on other errors
        else:
            self.history_data = []
            self.logger.info(f"History file not found at {self.history_file_path}. Starting with empty history.")

    def _save_history(self) -> None:
        """Saves the current processing history to the JSON file."""
        try:
            with open(self.history_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.history_data, f, indent=4)
            self.logger.debug(f"History saved to {self.history_file_path}. Current entries: {len(self.history_data)}")
        except Exception as e:
            self.logger.error(f"Failed to save history to {self.history_file_path}: {e}", exc_info=True)

    def log_task(
        self, 
        task_type: str, 
        input_file: Path, 
        output_file: Optional[Path] = None, 
        status: str = "Completed", 
        message: str = "Successfully processed.",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Logs a completed or failed processing task to the history.

        Args:
            task_type (str): The type of task (e.g., "Video Conversion", "Video Enhancement").
            input_file (Path): The path to the input file.
            output_file (Optional[Path]): The path to the output file, if applicable.
            status (str): The status of the task ("Completed", "Failed", "Cancelled").
            message (str): A brief message describing the outcome.
            details (Optional[Dict[str, Any]]): Optional dictionary for additional task-specific details.
        """
        task_record = {
            "timestamp": datetime.now().isoformat(),
            "task_type": task_type,
            "input_file": str(input_file),
            "output_file": str(output_file) if output_file else None,
            "status": status,
            "message": message,
            "details": details if details is not None else {}
        }
        self.history_data.append(task_record)
        self._save_history()
        self.logger.info(f"Logged task: '{task_type}' - Status: '{status}' for '{input_file.name}'")

    def get_history(self, limit: Optional[int] = None, task_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves the processing history, optionally filtered and limited.

        Args:
            limit (Optional[int]): Maximum number of history entries to return.
            task_type (Optional[str]): Filter history by a specific task type.

        Returns:
            List[Dict[str, Any]]: A list of history records, newest first.
        """
        filtered_history = self.history_data

        if task_type:
            filtered_history = [
                record for record in filtered_history if record.get("task_type") == task_type
            ]
        
        # Sort by timestamp (newest first)
        sorted_history = sorted(filtered_history, key=lambda x: x.get("timestamp", ""), reverse=True)

        if limit is not None:
            return sorted_history[:limit]
        
        return sorted_history

    def clear_history(self) -> Tuple[bool, str]:
        """
        Clears all entries from the processing history.
        This method includes a confirmation dialog when called in a GUI context.
        """
        try:
            # Import messagebox locally to avoid issues if tkinter is not available in non-GUI contexts
            from tkinter import messagebox 
            confirm = messagebox.askyesno("Confirm Clear History", "Are you sure you want to clear all history entries? This action cannot be undone.")
            if confirm:
                self.history_data = []
                self._save_history()
                self.logger.info("All history entries cleared.")
                return True, "History cleared successfully."
            else:
                self.logger.info("Clear history cancelled by user.")
                return False, "Clear history cancelled."
        except ImportError:
            # Fallback for non-GUI testing or environments without tkinter
            self.logger.warning("tkinter.messagebox not available. Clearing history without confirmation.")
            self.history_data = []
            self._save_history()
            self.logger.info("All history entries cleared (no GUI confirmation).")
            return True, "History cleared successfully (no confirmation)."


# Global instance for easy access throughout the application
_app_history_manager_instance = None

def get_application_history_manager():
    """
    Convenience function to get the global HistoryManager instance.
    Ensures it's initialized only once.
    """
    global _app_history_manager_instance
    if _app_history_manager_instance is None:
        _app_history_manager_instance = HistoryManager()
    return _app_history_manager_instance