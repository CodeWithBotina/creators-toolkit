import customtkinter
from tkinter import messagebox
from pathlib import Path
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime # Import datetime for formatting timestamps

from src.core.logger import get_application_logger
from src.modules.history_manager import get_application_history_manager # Import history manager

class HistoryPage(customtkinter.CTkFrame):
    """
    CustomTkinter Frame for displaying the application's processing history.
    Allows users to view past operations, their status, and details.
    """
    def __init__(self, master, app_instance):
        super().__init__(master, fg_color="transparent")
        self.logger = get_application_logger()
        self.app_instance = app_instance # Reference to the main App class for status updates
        self.history_manager = get_application_history_manager() # Instantiate the history manager

        self.logger.info("Initializing HistoryPage UI.")

        # Configure grid layout for this page
        self.grid_columnconfigure(0, weight=1) # Main content column
        self.grid_rowconfigure(0, weight=0) # Title
        self.grid_rowconfigure(1, weight=1) # History display area (scrollable)
        self.grid_rowconfigure(2, weight=0) # Buttons (Refresh/Clear)

        # Title
        self.title_label = customtkinter.CTkLabel(self, text="Processing History", font=customtkinter.CTkFont(size=24, weight="bold"))
        self.title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

        # Scrollable Frame for History Entries
        self.history_scroll_frame = customtkinter.CTkScrollableFrame(self, fg_color="transparent", label_text="Past Operations")
        self.history_scroll_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self.history_scroll_frame.grid_columnconfigure(0, weight=1) # For history entry labels

        # Control Buttons
        self.button_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.button_frame.grid(row=2, column=0, padx=20, pady=(10, 20), sticky="ew")
        self.button_frame.grid_columnconfigure((0, 1), weight=1)

        self.refresh_button = customtkinter.CTkButton(self.button_frame, text="Refresh History", command=self._display_history)
        self.refresh_button.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="ew")

        self.clear_button = customtkinter.CTkButton(self.button_frame, text="Clear History", command=self._clear_history_gui)
        self.clear_button.grid(row=0, column=1, padx=(10, 0), pady=5, sticky="ew")

        self._display_history() # Initial display of history

    def _display_history(self) -> None:
        """
        Fetches history from HistoryManager and displays it in the scrollable frame.
        """
        self.logger.info("Refreshing history display.")
        
        # Clear existing entries in the scrollable frame
        for widget in self.history_scroll_frame.winfo_children():
            widget.destroy()

        history_entries = self.history_manager.get_history()

        if not history_entries:
            empty_label = customtkinter.CTkLabel(self.history_scroll_frame, text="No processing history found yet.", text_color="gray")
            empty_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
            self.app_instance.set_status("History is empty.")
            return

        for i, entry in enumerate(history_entries):
            timestamp_dt = datetime.fromisoformat(entry['timestamp'])
            formatted_timestamp = timestamp_dt.strftime("%Y-%m-%d %H:%M:%S")

            task_type = entry.get('task_type', 'N/A')
            status = entry.get('status', 'Unknown')
            message = entry.get('message', 'No message.')
            input_file_name = Path(entry.get('input_file', 'N/A')).name
            output_file_name = Path(entry.get('output_file', 'N/A')).name if entry.get('output_file') else "N/A"
            details = entry.get('details', {})

            status_color = "green" if status == "Completed" else "red" if status == "Failed" else "orange"

            # Create a frame for each history entry for better organization
            entry_frame = customtkinter.CTkFrame(self.history_scroll_frame, fg_color="gray20", corner_radius=8)
            entry_frame.grid(row=i, column=0, padx=10, pady=5, sticky="ew")
            entry_frame.grid_columnconfigure(0, weight=1) # Label column
            entry_frame.grid_columnconfigure(1, weight=3) # Value column

            # Row for Timestamp and Task Type
            customtkinter.CTkLabel(entry_frame, text="Timestamp:", font=customtkinter.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=2, sticky="w")
            customtkinter.CTkLabel(entry_frame, text=formatted_timestamp).grid(row=0, column=1, padx=10, pady=2, sticky="w")
            
            customtkinter.CTkLabel(entry_frame, text="Task Type:", font=customtkinter.CTkFont(weight="bold")).grid(row=1, column=0, padx=10, pady=2, sticky="w")
            customtkinter.CTkLabel(entry_frame, text=task_type).grid(row=1, column=1, padx=10, pady=2, sticky="w")

            # Row for Status
            customtkinter.CTkLabel(entry_frame, text="Status:", font=customtkinter.CTkFont(weight="bold")).grid(row=2, column=0, padx=10, pady=2, sticky="w")
            customtkinter.CTkLabel(entry_frame, text=status, text_color=status_color, font=customtkinter.CTkFont(weight="bold")).grid(row=2, column=1, padx=10, pady=2, sticky="w")

            # Row for Input File
            customtkinter.CTkLabel(entry_frame, text="Input File:", font=customtkinter.CTkFont(weight="bold")).grid(row=3, column=0, padx=10, pady=2, sticky="w")
            customtkinter.CTkLabel(entry_frame, text=input_file_name, wraplength=400).grid(row=3, column=1, padx=10, pady=2, sticky="w")

            # Row for Output File
            customtkinter.CTkLabel(entry_frame, text="Output File:", font=customtkinter.CTkFont(weight="bold")).grid(row=4, column=0, padx=10, pady=2, sticky="w")
            customtkinter.CTkLabel(entry_frame, text=output_file_name, wraplength=400).grid(row=4, column=1, padx=10, pady=2, sticky="w")
            
            # Row for Message
            customtkinter.CTkLabel(entry_frame, text="Message:", font=customtkinter.CTkFont(weight="bold")).grid(row=5, column=0, padx=10, pady=2, sticky="w")
            customtkinter.CTkLabel(entry_frame, text=message, wraplength=400).grid(row=5, column=1, padx=10, pady=2, sticky="w")

            # Row for Details (if any)
            if details:
                customtkinter.CTkLabel(entry_frame, text="Details:", font=customtkinter.CTkFont(weight="bold")).grid(row=6, column=0, padx=10, pady=2, sticky="w")
                details_text = "\n".join([f"- {k}: {v}" for k, v in details.items()])
                customtkinter.CTkLabel(entry_frame, text=details_text, wraplength=400).grid(row=6, column=1, padx=10, pady=2, sticky="w")

        self.app_instance.set_status(f"History refreshed. {len(history_entries)} entries displayed.")
        self.logger.debug("History display updated successfully.")

    def _clear_history_gui(self) -> None:
        """
        Triggers the clear history operation and updates the GUI.
        """
        success, message = self.history_manager.clear_history()
        self.app_instance.set_status(message, level="info" if success else "warning")
        if success:
            self._display_history() # Refresh display after clearing
