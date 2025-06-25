import customtkinter
import logging
from pathlib import Path

from src.core.logger import get_application_logger

class HelpPage(customtkinter.CTkFrame):
    """
    CustomTkinter Frame for displaying help and troubleshooting information.
    """
    def __init__(self, master, app_instance):
        super().__init__(master, fg_color="transparent")
        self.logger = get_application_logger()
        self.app_instance = app_instance # Reference to the main App/MainWindow class for status updates

        self.logger.info("Initializing HelpPage UI.")

        # Configure grid layout for this page
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0) # Title
        self.grid_rowconfigure(1, weight=1) # Scrollable content

        # Title
        self.title_label = customtkinter.CTkLabel(self,
                                                  text="Help & Troubleshooting",
                                                  font=customtkinter.CTkFont(size=28, weight="bold"))
        self.title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

        # Scrollable frame for content
        self.content_scroll_frame = customtkinter.CTkScrollableFrame(self, fg_color="transparent")
        self.content_scroll_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self.content_scroll_frame.grid_columnconfigure(0, weight=1)

        self._create_help_content()

    def _create_help_content(self):
        """Populates the help page with common troubleshooting tips."""
        row_idx = 0

        # Common Issues Section
        common_issues_title = customtkinter.CTkLabel(self.content_scroll_frame, text="Common Issues",
                                                     font=customtkinter.CTkFont(size=20, weight="bold"),
                                                     anchor="w")
        common_issues_title.grid(row=row_idx, column=0, padx=10, pady=(15, 5), sticky="ew")
        row_idx += 1

        issues_data = [
            {
                "question": "Application not starting or crashing on launch?",
                "answer": (
                    "Ensure FFmpeg is correctly installed and its 'bin' directory is added to your system's PATH. "
                    "Check the 'logs' directory for error messages. Also, verify that all Python dependencies "
                    "from 'requirements.txt' are installed correctly."
                )
            },
            {
                "question": "Video or audio processing fails without clear error?",
                "answer": (
                    "This often indicates a problem with FFmpeg. Make sure it's the correct 64-bit version for Windows "
                    "and that it's accessible globally via PATH. Sometimes, corrupted input files can also cause this. "
                    "Check the application logs for more detailed FFmpeg output."
                )
            },
            {
                "question": "Output file not found after successful processing?",
                "answer": (
                    "Verify the default output directories in the application's settings or when selecting output paths. "
                    "Ensure you have write permissions to the selected output location."
                )
            },
            {
                "question": "Application is slow or unresponsive?",
                "answer": (
                    "Media processing is resource-intensive. Ensure your system meets the recommended RAM requirements. "
                    "Closing other demanding applications can help. For very large files, processing times will naturally be longer."
                )
            },
            {
                "question": "Cannot change appearance mode?",
                "answer": (
                    "Restarting the application after changing the appearance mode might be required for some systems or themes. "
                    "Ensure CustomTkinter is updated to the latest version."
                )
            }
        ]

        for i, issue in enumerate(issues_data):
            question_label = customtkinter.CTkLabel(self.content_scroll_frame, text=f"Q: {issue['question']}",
                                                    font=customtkinter.CTkFont(size=16, weight="bold"),
                                                    wraplength=700, justify="left", anchor="nw")
            question_label.grid(row=row_idx, column=0, padx=10, pady=(10, 2), sticky="ew")
            row_idx += 1

            answer_label = customtkinter.CTkLabel(self.content_scroll_frame, text=f"A: {issue['answer']}",
                                                  font=customtkinter.CTkFont(size=14),
                                                  wraplength=700, justify="left", anchor="nw",
                                                  text_color=("gray40", "gray60"))
            answer_label.grid(row=row_idx, column=0, padx=10, pady=(2, 10), sticky="ew")
            row_idx += 1
        
        self.logger.info("HelpPage content created.")

