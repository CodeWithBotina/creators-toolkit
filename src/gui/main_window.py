# src/gui/main_window.py
import customtkinter
import logging
import sys
from pathlib import Path
from tkinter import messagebox
import time # For potential debugging delays

# Import core modules
from src.core.logger import get_application_logger
from src.core.config_manager import get_application_config
from src.modules.history_manager import get_application_history_manager

# Import GUI pages
from src.gui.dashboard_page import DashboardPage
from src.gui.video_converter_page import VideoConverterPage
from src.gui.audio_enhancement_page import AudioEnhancementPage
from src.gui.image_tools_page import ImageToolsPage
from src.gui.video_enhancement_page import VideoEnhancementPage
from src.gui.video_bg_removal_page import VideoBgRemovalPage
from src.gui.social_media_post_page import SocialMediaPostPage
from src.gui.history_page import HistoryPage

class MainWindow(customtkinter.CTk):
    """
    Main application window class for Creator's Toolkit.
    Handles the primary window, overall UI layout, page navigation,
    and appearance settings.
    """
    def __init__(self):
        super().__init__()

        self.logger = get_application_logger()
        self.config_manager = get_application_config()
        self.history_manager = get_application_history_manager() # Access the global history manager

        self.title("Creator's Toolkit for Windows 11")
        self.geometry(f"{1100}x{700}")
        self.minsize(900, 600) # Set a minimum window size for responsiveness

        # Configure grid layout for the main window
        self.grid_rowconfigure(0, weight=1)  # Content area
        self.grid_columnconfigure(1, weight=1) # Content area

        # --- Create Sidebar Frame with Navigation ---
        self.sidebar_frame = customtkinter.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(7, weight=1) # Push settings to bottom

        self.logo_label = customtkinter.CTkLabel(self.sidebar_frame, text="Creator's Toolkit",
                                                font=customtkinter.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Navigation Buttons - Added sticky="ew" for horizontal expansion
        self.dashboard_button = customtkinter.CTkButton(self.sidebar_frame, text="Dashboard",
                                                        command=self.dashboard_button_event)
        self.dashboard_button.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

        self.video_converter_button = customtkinter.CTkButton(self.sidebar_frame, text="Video Converter",
                                                              command=self.video_converter_button_event)
        self.video_converter_button.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        self.audio_enhancement_button = customtkinter.CTkButton(self.sidebar_frame, text="Audio Enhancement",
                                                                 command=self.audio_enhancement_button_event)
        self.audio_enhancement_button.grid(row=3, column=0, padx=20, pady=10, sticky="ew")

        self.image_tools_button = customtkinter.CTkButton(self.sidebar_frame, text="Image Tools",
                                                           command=self.image_tools_button_event)
        self.image_tools_button.grid(row=4, column=0, padx=20, pady=10, sticky="ew")

        self.video_enhancement_button = customtkinter.CTkButton(self.sidebar_frame, text="Video Enhancement",
                                                                 command=self.video_enhancement_button_event)
        self.video_enhancement_button.grid(row=5, column=0, padx=20, pady=10, sticky="ew")
        
        self.video_bg_removal_button = customtkinter.CTkButton(self.sidebar_frame, text="Video Background Removal",
                                                               command=self.video_bg_removal_button_event)
        self.video_bg_removal_button.grid(row=6, column=0, padx=20, pady=10, sticky="ew")

        self.social_media_post_button = customtkinter.CTkButton(self.sidebar_frame, text="Social Media Post",
                                                                 command=self.social_media_post_button_event)
        self.social_media_post_button.grid(row=7, column=0, padx=20, pady=10, sticky="ew")

        self.history_button = customtkinter.CTkButton(self.sidebar_frame, text="History",
                                                      command=self.history_button_event)
        self.history_button.grid(row=8, column=0, padx=20, pady=10, sticky="ew")


        # Appearance Mode Settings (at the bottom of sidebar)
        self.appearance_mode_label = customtkinter.CTkLabel(self.sidebar_frame, text="Appearance Mode:", anchor="w")
        self.appearance_mode_label.grid(row=9, column=0, padx=20, pady=(10, 0), sticky="sw")
        self.appearance_mode_optionemenu = customtkinter.CTkOptionMenu(self.sidebar_frame, 
                                                                       values=["Light", "Dark", "System"],
                                                                       command=self.change_appearance_mode_event)
        self.appearance_mode_optionemenu.grid(row=10, column=0, padx=20, pady=(0, 20), sticky="s")
        # Set initial appearance mode based on config
        initial_appearance_mode = self.config_manager.get_setting("app_settings.appearance_mode", "System")
        self.appearance_mode_optionemenu.set(initial_appearance_mode)

        # --- Status Bar (Moved to be initialized earlier) ---
        # This needs to be created before any pages might try to update it.
        self.status_bar = customtkinter.CTkLabel(self, text="Application Ready", 
                                                font=customtkinter.CTkFont(size=12),
                                                anchor="w", fg_color=customtkinter.ThemeManager.theme["CTkFrame"]["fg_color"]) # Consistent background
        self.status_bar.grid(row=1, column=0, columnspan=2, padx=0, pady=0, sticky="ew") # Spans across sidebar and content
        self.set_status("Application ready.") # Set initial status bar message


        # --- Create Main Content Frame and Pages ---
        self.content_frame = customtkinter.CTkFrame(self, corner_radius=0, fg_color="transparent")
        # Note: The status bar is now at grid row 1. Content frame must be at row 0.
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        # Dictionary to hold page instances
        self.pages = {}
        self._create_pages() # Call method to create all page instances

        # Set default page to Dashboard
        self.show_page("dashboard")

    def _create_pages(self):
        """Initializes all page instances and stores them in a dictionary."""
        self.pages["dashboard"] = DashboardPage(self.content_frame, self)
        self.pages["video_converter"] = VideoConverterPage(self.content_frame, self)
        self.pages["audio_enhancement"] = AudioEnhancementPage(self.content_frame, self)
        self.pages["image_tools"] = ImageToolsPage(self.content_frame, self)
        self.pages["video_enhancement"] = VideoEnhancementPage(self.content_frame, self)
        self.pages["video_bg_removal"] = VideoBgRemovalPage(self.content_frame, self)
        self.pages["social_media_post"] = SocialMediaPostPage(self.content_frame, self)
        self.pages["history"] = HistoryPage(self.content_frame, self)
        self.logger.info("All application pages instantiated.")

    def show_page(self, page_name: str):
        """
        Displays the specified page and hides others.
        
        Args:
            page_name (str): The name of the page to show (key in self.pages).
        """
        # Hide all pages first
        for page in self.pages.values():
            page.grid_forget() # Remove from grid layout

        # Display the requested page
        page_to_show = self.pages.get(page_name)
        if page_to_show:
            page_to_show.grid(row=0, column=0, sticky="nsew") # Place in content frame
            self.logger.debug(f"Displayed page: {page_name}")
            # If the page has a refresh method (e.g., history page), call it
            if hasattr(page_to_show, 'refresh_page_content'):
                self.logger.debug(f"Refreshing content for {page_name}...")
                page_to_show.refresh_page_content()
        else:
            self.logger.error(f"Attempted to show unknown page: {page_name}")
            self.set_status(f"Error: Page '{page_name}' not found.", level="error")

    def set_status(self, message: str, level: str = "info"):
        """Updates the status bar message and logs it."""
        self.status_bar.configure(text=message)
        if level == "info":
            self.logger.info(f"STATUS: {message}")
        elif level == "warning":
            self.logger.warning(f"STATUS: {message}")
        elif level == "error":
            self.logger.error(f"STATUS: {message}")
        else:
            self.logger.debug(f"STATUS: {message}")

    # --- Navigation Button Events (from sidebar) ---
    def dashboard_button_event(self):
        """Event handler for the Dashboard button."""
        self.show_page("dashboard")
        self.set_status("Dashboard selected.")
        self.logger.debug("Dashboard button clicked.")

    def video_converter_button_event(self):
        """Event handler for the Video Converter button."""
        self.show_page("video_converter")
        self.set_status("Video Converter selected.")
        self.logger.debug("Video Converter button clicked.")

    def audio_enhancement_button_event(self):
        """Event handler for the Audio Enhancement button."""
        self.show_page("audio_enhancement")
        self.set_status("Audio Enhancement selected.")
        self.logger.debug("Audio Enhancement button clicked.")

    def image_tools_button_event(self):
        """Event handler for the Image Tools button."""
        self.show_page("image_tools")
        self.set_status("Image Tools selected.")
        self.logger.debug("Image Tools button clicked.")

    def video_enhancement_button_event(self):
        """Event handler for the Video Enhancement button."""
        self.show_page("video_enhancement")
        self.set_status("Video Enhancement selected.")
        self.logger.debug("Video Enhancement button clicked.")

    def video_bg_removal_button_event(self):
        """Event handler for the Video Background Removal button."""
        self.show_page("video_bg_removal")
        self.set_status("Video Background Removal selected.")
        self.logger.debug("Video Background Removal button clicked.")

    def social_media_post_button_event(self):
        """Event handler for the Social Media Post button."""
        self.show_page("social_media_post")
        self.set_status("Social Media Post section selected.")
        self.logger.debug("Social Media Post button clicked.")

    def history_button_event(self):
        """Event handler for the History button."""
        self.show_page("history")
        self.set_status("History section selected.")
        self.logger.debug("History button clicked.")

    def change_appearance_mode_event(self, new_appearance_mode: str):
        """Handles changing the CustomTkinter appearance mode."""
        customtkinter.set_appearance_mode(new_appearance_mode)
        self.config_manager.set_setting("app_settings.appearance_mode", new_appearance_mode)
        self.set_status(f"Appearance mode changed to {new_appearance_mode}.")
        self.logger.debug(f"Appearance mode changed to: {new_appearance_mode}")
