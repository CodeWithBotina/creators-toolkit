import customtkinter
from tkinter import messagebox
from pathlib import Path
import logging
from typing import List, Dict, Any, Optional

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

        # Scrollable frame for history entries
        self.history_scroll_frame = customtkinter.CTkScrollableFrame(self, fg_color="transparent")
        self.history_scroll_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self.history_scroll_frame.grid_columnconfigure(0, weight=1) # Column for history entries

        # Buttons Frame
        self.buttons_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.buttons_frame.grid(row=2, column=0, padx=20, pady=(10, 20), sticky="ew")
        self.buttons_frame.grid_columnconfigure((0, 1), weight=1) # Two columns for buttons

        self.refresh_button = customtkinter.CTkButton(self.buttons_frame, text="Refresh History", command=self.refresh_page_content)
        self.refresh_button.grid(row=0, column=0, padx=(0, 10), pady=0, sticky="w")

        self.clear_button = customtkinter.CTkButton(self.buttons_frame, text="Clear All History", command=self._confirm_clear_history)
        self.clear_button.grid(row=0, column=1, padx=(10, 0), pady=0, sticky="e")

        self.refresh_page_content() # Initial display of history

    def refresh_page_content(self):
        """
        Refreshes the history display by clearing existing entries and loading current history.
        This method is called when the page is shown or the refresh button is pressed.
        """
        self.logger.info("Refreshing history display.")
        self._display_history()
        self.app_instance.set_status("History refreshed.")

    def _display_history(self):
        """
        Loads history from the HistoryManager and displays it in the scrollable frame.
        Clears previous entries before displaying new ones.
        """
        # Clear existing entries
        for widget in self.history_scroll_frame.winfo_children():
            widget.destroy()

        history_entries = self.history_manager.get_history()

        if not history_entries:
            no_history_label = customtkinter.CTkLabel(self.history_scroll_frame, text="No processing history available yet.")
            no_history_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
            self.logger.info("No history entries found to display.")
            return

        # Display entries in reverse chronological order (newest first)
        for i, entry in enumerate(reversed(history_entries)):
            entry_frame = customtkinter.CTkFrame(self.history_scroll_frame, fg_color=("gray90", "gray15"), corner_radius=8)
            entry_frame.grid(row=i, column=0, padx=10, pady=5, sticky="ew")
            entry_frame.grid_columnconfigure(0, weight=1) # For text content

            # Prepare display text
            timestamp = entry.get("timestamp", "N/A")
            task_type = entry.get("task_type", "Unknown Task")
            status = entry.get("status", "N/A")
            message = entry.get("message", "No detailed message.")
            
            input_file = Path(entry.get("input_file", "N/A")).name if entry.get("input_file") else "N/A"
            output_file = Path(entry.get("output_file", "N/A")).name if entry.get("output_file") else "N/A"
            
            details = entry.get("details", {})
            details_str = json.dumps(details, indent=2) if details else "No additional details."

            display_text = (
                f"Timestamp: {timestamp}\n"
                f"Task Type: {task_type}\n"
                f"Status: {status}\n"
                f"Input: {input_file}\n"
                f"Output: {output_file}\n"
                f"Message: {message}\n"
                f"Details: {details_str}"
            )
            
            entry_label = customtkinter.CTkLabel(entry_frame, text=display_text, justify="left", wraplength=self.winfo_width() - 80) # Adjust wraplength
            entry_label.grid(row=0, column=0, padx=15, pady=10, sticky="ew")
            
            self.logger.debug(f"Displayed history entry: {task_type} - {status} at {timestamp}")

        # Ensure the scrollable frame updates its scroll region
        self.history_scroll_frame.update_idletasks()


    def _confirm_clear_history(self):
        """Asks for user confirmation before clearing the entire history."""
        # CustomTkinter does not have a direct confirm dialog, so we use tkinter's messagebox.
        # For a more integrated look, a custom CTk dialog could be implemented.
        response = messagebox.askyesno(
            "Clear History",
            "Are you sure you want to clear ALL processing history? This action cannot be undone."
        )
        if response:
            self._clear_history()
        else:
            self.logger.info("Clear history action cancelled by user.")
            self.app_instance.set_status("Clear history cancelled.")


    def _clear_history(self):
        """Clears all processing history."""
        success, message = self.history_manager.clear_history()
        if success:
            self.logger.info("All processing history cleared successfully.")
            self.app_instance.set_status("All history cleared.")
            self.refresh_page_content() # Refresh display to show empty history
            messagebox.showinfo("History Cleared", "All processing history has been successfully cleared.")
        else:
            self.logger.error(f"Failed to clear history: {message}")
            self.app_instance.set_status(f"Failed to clear history: {message}", level="error")
            messagebox.showerror("Error", f"Failed to clear history: {message}")