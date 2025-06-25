# src/gui/main_window.py
import customtkinter
import logging
import sys
from pathlib import Path
from tkinter import messagebox
import time
import webbrowser # For opening external links

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
from src.gui.about_page import AboutPage # NEW: Import AboutPage
from src.gui.help_page import HelpPage # NEW: Import HelpPage


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
        self.history_manager = get_application_history_manager()

        self.title("Creator's Toolkit for Windows 11")
        self.geometry(f"{1100}x{700}")

        # Set application icon (for window and taskbar)
        # Ensure 'assets/icon.ico' exists. If not, the window will use a default icon.
        icon_path = Path("assets/icon.ico")
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
                self.logger.info(f"Application icon set from: {icon_path}")
            except Exception as e:
                self.logger.warning(f"Failed to set application icon from {icon_path}: {e}")
        else:
            self.logger.warning(f"Application icon file not found at: {icon_path}. Window will use default icon.")

        # Configure grid layout (2x2 grid: top menu bar, navigation frame, content frame, status bar)
        self.grid_rowconfigure(0, weight=0) # Top menu bar row
        self.grid_rowconfigure(1, weight=1) # Main content row (nav + main_content)
        self.grid_rowconfigure(2, weight=0) # Status bar row
        self.grid_columnconfigure(0, weight=0) # Navigation frame column
        self.grid_columnconfigure(1, weight=1) # Main content column

        # --- Create Top Menu Bar ---
        self.top_menu_frame = customtkinter.CTkFrame(self, corner_radius=0, height=40, fg_color=("gray75", "gray25"))
        self.top_menu_frame.grid(row=0, column=0, columnspan=2, sticky="ew") # Span across both columns
        self.top_menu_frame.grid_columnconfigure((0,1,2,3,4), weight=1) # Evenly distribute menu items

        self.about_button_top = customtkinter.CTkButton(self.top_menu_frame, text="About",
                                                        font=customtkinter.CTkFont(size=14, weight="bold"),
                                                        fg_color="transparent", hover_color=("gray60", "gray30"),
                                                        command=self._show_about_page)
        self.about_button_top.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.help_button_top = customtkinter.CTkButton(self.top_menu_frame, text="Help",
                                                       font=customtkinter.CTkFont(size=14, weight="bold"),
                                                       fg_color="transparent", hover_color=("gray60", "gray30"),
                                                       command=self._show_help_page)
        self.help_button_top.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        self.docs_button_top = customtkinter.CTkButton(self.top_menu_frame, text="Docs",
                                                       font=customtkinter.CTkFont(size=14, weight="bold"),
                                                       fg_color="transparent", hover_color=("gray60", "gray30"),
                                                       command=self._open_docs)
        self.docs_button_top.grid(row=0, column=2, padx=5, pady=5, sticky="w")


        # --- Create Navigation Frame (moved to row 1) ---
        self.navigation_frame = customtkinter.CTkFrame(self, corner_radius=0)
        self.navigation_frame.grid(row=1, column=0, sticky="nsew") # Changed row to 1
        
        # Configure navigation frame rows for buttons and appearance menu
        self.navigation_frame.grid_rowconfigure((1, 2, 3), weight=1) # Rows for Dashboard, History
        self.navigation_frame.grid_rowconfigure(4, weight=0) # Row for appearance menu (fixed size)

        self.navigation_frame_label = customtkinter.CTkLabel(self.navigation_frame,
                                                            text="Creator's Toolkit", # UI text in English
                                                            compound="left",
                                                            font=customtkinter.CTkFont(size=18, weight="bold"))
        self.navigation_frame_label.grid(row=0, column=0, padx=20, pady=20)

        # Navigation Buttons
        button_padx = 15
        button_pady = 5
        
        self.dashboard_button = customtkinter.CTkButton(self.navigation_frame,
                                                       corner_radius=0,
                                                       height=40,
                                                       text="Dashboard", # UI text in English
                                                       font=customtkinter.CTkFont(size=15),
                                                       fg_color="transparent",
                                                       text_color=("gray10", "gray90"),
                                                       hover_color=("gray70", "gray30"),
                                                       anchor="w",
                                                       command=self.dashboard_button_event)
        self.dashboard_button.grid(row=1, column=0, sticky="ew", padx=button_padx, pady=button_pady)

        self.history_button = customtkinter.CTkButton(self.navigation_frame,
                                                    corner_radius=0,
                                                    height=40,
                                                    text="History", # UI text in English
                                                    font=customtkinter.CTkFont(size=15),
                                                    fg_color="transparent",
                                                    text_color=("gray10", "gray90"),
                                                    hover_color=("gray70", "gray30"),
                                                    anchor="w",
                                                    command=self.history_button_event)
        self.history_button.grid(row=2, column=0, sticky="ew", padx=button_padx, pady=button_pady)

        # Appearance Mode Control
        self.appearance_mode_menu = customtkinter.CTkOptionMenu(self.navigation_frame,
                                                                values=["System", "Light", "Dark"],
                                                                command=self.change_appearance_mode_event)
        self.appearance_mode_menu.grid(row=4, column=0, padx=20, pady=20, sticky="s")

        # --- Create Main Content Frame (where pages are displayed) (moved to row 1, column 1) ---
        self.main_content_container = customtkinter.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_content_container.grid(row=1, column=1, sticky="nsew", padx=(15, 20), pady=(15, 10)) # Changed row to 1
        self.main_content_container.grid_columnconfigure(0, weight=1)
        self.main_content_container.grid_rowconfigure(0, weight=1)

        # --- Create Status Bar (moved to row 2) ---
        # This MUST be created before any pages are initialized if they try to use it
        self.status_bar = customtkinter.CTkLabel(self, text="Application ready.", # UI text in English
                                                font=customtkinter.CTkFont(size=12),
                                                anchor="w",
                                                padx=15,
                                                pady=8,
                                                fg_color="gray20",
                                                text_color="gray80",
                                                corner_radius=5)
        self.status_bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=5) # Changed row to 2

        self.pages = {} # Dictionary to hold all page instances
        self.current_page = None

        self._create_pages() # Initialize all content pages
        self.show_page("dashboard") # Set initial selected page to Dashboard

        self.set_status("Application ready. Welcome!") # UI text in English
        self.logger.info("Main window UI initialized.")

    def _create_pages(self):
        """Initializes all the application's content pages and stores them."""
        # Pages will receive a reference to this MainWindow instance for status updates and navigation
        self.pages["dashboard"] = DashboardPage(self.main_content_container, self)
        self.pages["video_converter"] = VideoConverterPage(self.main_content_container, self)
        self.pages["social_media_post"] = SocialMediaPostPage(self.main_content_container, self)
        self.pages["video_enhancement"] = VideoEnhancementPage(self.main_content_container, self)
        self.pages["video_bg_removal"] = VideoBgRemovalPage(self.main_content_container, self)
        self.pages["audio_enhancement"] = AudioEnhancementPage(self.main_content_container, self)
        self.pages["image_tools"] = ImageToolsPage(self.main_content_container, self)
        self.pages["history"] = HistoryPage(self.main_content_container, self)
        self.pages["about"] = AboutPage(self.main_content_container, self) # NEW: About Page
        self.pages["help"] = HelpPage(self.main_content_container, self) # NEW: Help Page

        # Grid all pages but hide them initially
        for page_name, page_instance in self.pages.items():
            page_instance.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
            page_instance.grid_remove() # Hide all initially

    def show_page(self, page_name: str):
        """Displays the specified page and hides others, updating the navigation highlight."""
        if page_name not in self.pages:
            self.logger.error(f"Attempted to show unknown page: {page_name}")
            self.set_status(f"Error: Page '{page_name}' not found.", level="error") # UI text in English
            return

        if self.current_page:
            self.current_page.grid_remove() # Hide current page

        self.current_page = self.pages[page_name]
        self.current_page.grid() # Show the new page
        self.logger.info(f"Navigated to page: {page_name}")

        self._update_navigation_button_highlight(page_name) # Update button highlight

    def _update_navigation_button_highlight(self, active_page_name: str):
        """Highlights the active navigation button based on the current page."""
        # Reset all main navigation button colors (Dashboard, History)
        for button in [self.dashboard_button, self.history_button]:
            button.configure(fg_color="transparent")
        
        # Reset all top menu button colors
        for button in [self.about_button_top, self.help_button_top, self.docs_button_top]:
            button.configure(fg_color="transparent")

        # Set active button color for main navigation
        if active_page_name == "dashboard":
            self.dashboard_button.configure(fg_color=customtkinter.ThemeManager.theme["CTkOptionMenu"]["button_color"])
        elif active_page_name == "history":
            self.history_button.configure(fg_color=customtkinter.ThemeManager.theme["CTkOptionMenu"]["button_color"])
        # No need to highlight other buttons directly in the nav frame
        # as they are navigated via the dashboard.

        # Set active button color for top menu (if it's an "internal" page)
        if active_page_name == "about":
            self.about_button_top.configure(fg_color=customtkinter.ThemeManager.theme["CTkOptionMenu"]["button_color"])
        elif active_page_name == "help":
            self.help_button_top.configure(fg_color=customtkinter.ThemeManager.theme["CTkOptionMenu"]["button_color"])


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
        self.set_status("Dashboard selected.") # UI text in English
        self.logger.debug("Dashboard button clicked.")

    def history_button_event(self):
        """Event handler for the History button."""
        self.show_page("history")
        self.set_status("History section selected.") # UI text in English
        self.logger.debug("History button clicked.")

    def change_appearance_mode_event(self, new_appearance_mode: str):
        """Handles changing the CustomTkinter appearance mode."""
        customtkinter.set_appearance_mode(new_appearance_mode)
        self.config_manager.set_setting("app_settings.appearance_mode", new_appearance_mode)
        self.set_status(f"Appearance mode changed to {new_appearance_mode}.") # UI text in English
        self.logger.info(f"Appearance mode changed to: {new_appearance_mode}")

    # --- Top Menu Bar Event Handlers ---
    def _show_about_page(self):
        """Displays the About page."""
        self.show_page("about")
        self.set_status("About section displayed.")
        self.logger.debug("About button clicked.")

    def _show_help_page(self):
        """Displays the Help page."""
        self.show_page("help")
        self.set_status("Help section displayed.")
        self.logger.debug("Help button clicked.")

    def _open_docs(self):
        """Opens the GitHub documentation link in the default browser."""
        docs_url = "https://github.com/CodeWithBotina/creators-toolkit"
        try:
            webbrowser.open_new_tab(docs_url)
            self.set_status(f"Opening documentation: {docs_url}")
            self.logger.info(f"Opened docs link: {docs_url}")
        except Exception as e:
            self.set_status(f"Failed to open documentation link: {e}", level="error")
            self.logger.error(f"Error opening docs link {docs_url}: {e}", exc_info=True)