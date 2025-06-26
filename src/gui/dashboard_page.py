import customtkinter
import logging
from pathlib import Path
from typing import Callable, Optional

from src.core.logger import get_application_logger
from src.core.config_manager import get_application_config # Import config manager to retrieve settings

class DashboardPage(customtkinter.CTkFrame):
    """
    CustomTkinter Frame for the main application dashboard.
    Displays cards for each tool, allowing easy navigation.
    """
    def __init__(self, master, app_instance):
        super().__init__(master, fg_color="transparent")
        self.logger = get_application_logger()
        self.config_manager = get_application_config() # Access the global config manager
        self.app_instance = app_instance # Reference to the main App/MainWindow class for navigation

        self.logger.info("Initializing DashboardPage UI.")

        # Configure grid layout for this page
        self.grid_columnconfigure(0, weight=1) # Main content column
        self.grid_rowconfigure(0, weight=0) # Title row
        self.grid_rowconfigure(1, weight=1) # Content (cards) row

        # Title
        self.title_label = customtkinter.CTkLabel(self,
                                                  text="Welcome to Creator's Toolkit", # UI text in English
                                                  font=customtkinter.CTkFont(size=28, weight="bold"))
        self.title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

        # Scrollable frame for cards
        self.cards_scroll_frame = customtkinter.CTkScrollableFrame(self, fg_color="transparent")
        self.cards_scroll_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        
        # Configure the grid for cards within the scrollable frame
        # This will allow cards to wrap based on available width
        self.cards_scroll_frame.grid_columnconfigure((0, 1, 2, 3), weight=1, minsize=200) # Max 4 columns, min width 200px
        # We don't set grid_rowconfigure for cards_scroll_frame as rows will expand as needed.

        self._create_tool_cards()

    def _create_tool_cards(self):
        """Creates and places individual tool cards on the dashboard."""
        self.logger.info("Creating tool cards for the dashboard.")
        # Define tool information with corresponding page names
        tools = [
            {"name": "Video Converter", "description": "Convert video files to MP4 format.", "page": "video_converter"},
            {"name": "Audio Enhancement", "description": "Reduce noise and normalize audio files.", "page": "audio_enhancement"},
            {"name": "Image Background Remover", "description": "Remove backgrounds from images with enhanced quality.", "page": "image_tools"},
            {"name": "Video Enhancement", "description": "Apply various quality enhancements to your videos.", "page": "video_enhancement"},
            {"name": "Video Background Removal", "description": "Remove backgrounds from video footage (requires strong GPU).", "page": "video_bg_removal"},
            {"name": "Social Media Post Creator", "description": "Prepare videos for social media: crop, subtitles, effects.", "page": "social_media_post"},
            # Add more tools here as they are developed
        ]

        # Get current UI scaling factor to adjust card width and height (optional, for better responsiveness)
        # Safely access the 'Scaling' factor from the theme manager
        current_scaling = 1.0 # Default value
        if hasattr(customtkinter.ThemeManager, "theme") and "Scaling" in customtkinter.ThemeManager.theme:
            if "factor" in customtkinter.ThemeManager.theme["Scaling"]:
                current_scaling = customtkinter.ThemeManager.theme["Scaling"]["factor"]
            else:
                self.logger.warning("CustomTkinter theme 'Scaling' dictionary found, but 'factor' key is missing. Using default scaling 1.0.")
        else:
            self.logger.warning("CustomTkinter ThemeManager.theme or 'Scaling' key not found. Using default scaling 1.0.")

        card_width = int(250 * current_scaling)
        card_height = int(180 * current_scaling)

        for i, tool in enumerate(tools):
            row = i // 3  # 3 cards per row
            column = i % 3

            card_frame = customtkinter.CTkFrame(self.cards_scroll_frame, width=card_width, height=card_height,
                                                corner_radius=10, fg_color=("gray85", "gray20"))
            card_frame.grid(row=row, column=column, padx=15, pady=15, sticky="nsew")
            
            # Ensure the inner grid of the card expands correctly
            card_frame.grid_rowconfigure(0, weight=0) # Title
            card_frame.grid_rowconfigure(1, weight=1) # Description
            card_frame.grid_rowconfigure(2, weight=0) # Button
            card_frame.grid_columnconfigure(0, weight=1) # Single column

            # Card Title
            card_title = customtkinter.CTkLabel(card_frame, text=tool["name"],
                                                font=customtkinter.CTkFont(size=16, weight="bold"))
            card_title.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="ew")

            # Card Description
            card_description = customtkinter.CTkLabel(card_frame, text=tool["description"],
                                                      font=customtkinter.CTkFont(size=12),
                                                      wraplength=card_width - 30, # Wrap text within card width
                                                      justify="left")
            card_description.grid(row=1, column=0, padx=15, pady=(5, 10), sticky="nsw")

            # Learn More/Go to Tool Button
            card_button = customtkinter.CTkButton(card_frame, text="Open Tool",
                                                  command=lambda p=tool["page"]: self.app_instance.show_page(p))
            card_button.grid(row=2, column=0, padx=15, pady=(0, 15), sticky="ew")

            self.logger.debug(f"Created card for tool: {tool['name']}")

    def refresh_page_content(self):
        """
        Refreshes any dynamic content on the dashboard page.
        Currently, just logs, but could reload cards or status.
        """
        self.logger.info("DashboardPage content refreshed.")
        # No dynamic content to refresh on dashboard besides initial card creation.
        # This method is here for consistency with other pages that might have it.