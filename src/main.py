import customtkinter
import logging
import sys
from pathlib import Path
import subprocess # For running external commands like ffmpeg
from tkinter import messagebox # For displaying startup messages
import time # For potential debugging delays

# Import core modules
from src.core.logger import get_application_logger
from src.core.config_manager import get_application_config

# Import GUI pages
from src.gui.video_converter_page import VideoConverterPage
from src.gui.audio_enhancement_page import AudioEnhancementPage
from src.gui.image_tools_page import ImageToolsPage
from src.gui.video_enhancement_page import VideoEnhancementPage
from src.gui.video_bg_removal_page import VideoBgRemovalPage # NEW: Import the video background removal page

# --- Initialize Core Services ---
# This must happen before any other module attempts to get a logger or config.
# Ensure 'logs' and 'config' directories exist for the respective managers.
Path("logs").mkdir(exist_ok=True)
Path("config").mkdir(exist_ok=True)

# Initialize the global logger instance
logger = get_application_logger()
logger.info("Application starting...")

# Initialize the global config manager instance
config_manager = get_application_config()
logger.info("Configuration manager initialized.")

# Set CustomTkinter appearance mode and color theme based on config
app_appearance_mode = config_manager.get_setting("app_settings.appearance_mode", "System")
app_theme = config_manager.get_setting("app_settings.theme", "dark-blue") # Fallback to a default CustomTkinter theme

customtkinter.set_appearance_mode(app_appearance_mode)
customtkinter.set_default_color_theme(app_theme)

class App(customtkinter.CTk):
    """
    Main application class for Creator's Toolkit.
    Handles the primary window and overall UI layout, including page navigation.
    """
    def __init__(self):
        super().__init__()
        self.logger = logger
        self.config_manager = config_manager

        # --- Window Setup ---
        self.title("Creator's Toolkit")
        self.geometry("1000x700") # Initial size, adjust as needed
        self.minsize(800, 600) # Minimum size to prevent distortion

        # Configure grid layout (1x2 grid: sidebar and main frame)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Sidebar Frame ---
        self.sidebar_frame = customtkinter.CTkFrame(self, width=140, corner_radius=0)
        # Updated rowspan to account for the new "Video BG Removal" button + appearance controls
        self.sidebar_frame.grid(row=0, column=0, rowspan=8, sticky="nsew") # Total rows used: 0-7, rowspan = 8
        self.sidebar_frame.grid_rowconfigure(7, weight=1) # Makes the last row (below appearance mode) expand to push elements up

        # Sidebar title
        self.logo_label = customtkinter.CTkLabel(self.sidebar_frame, text="Creator's Toolkit", font=customtkinter.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=20)

        # Navigation buttons
        self.video_conversion_button = customtkinter.CTkButton(self.sidebar_frame, text="Video Conversion", command=self.video_conversion_button_event)
        self.video_conversion_button.grid(row=1, column=0, padx=20, pady=10)

        self.video_enhance_button = customtkinter.CTkButton(self.sidebar_frame, text="Video Enhancement", command=self.video_enhancement_button_event)
        self.video_enhance_button.grid(row=2, column=0, padx=20, pady=10)

        self.video_bg_removal_button = customtkinter.CTkButton(self.sidebar_frame, text="Video BG Removal", command=self.video_bg_removal_button_event) # NEW button
        self.video_bg_removal_button.grid(row=3, column=0, padx=20, pady=10) # NEW row

        self.audio_button = customtkinter.CTkButton(self.sidebar_frame, text="Audio Enhancement", command=self.audio_button_event)
        self.audio_button.grid(row=4, column=0, padx=20, pady=10) # Adjusted row

        self.image_button = customtkinter.CTkButton(self.sidebar_frame, text="Image Tools", command=self.image_button_event)
        self.image_button.grid(row=5, column=0, padx=20, pady=10) # Adjusted row

        self.history_button = customtkinter.CTkButton(self.sidebar_frame, text="History", command=self.history_button_event)
        self.history_button.grid(row=6, column=0, padx=20, pady=10, sticky="n") # Adjusted row

        # Appearance Mode Control
        self.appearance_mode_label = customtkinter.CTkLabel(self.sidebar_frame, text="Appearance Mode:")
        self.appearance_mode_label.grid(row=7, column=0, padx=20, pady=(10, 0)) # Adjusted row
        self.appearance_mode_optionemenu = customtkinter.CTkOptionMenu(self.sidebar_frame, values=["System", "Light", "Dark"],
                                                                       command=self.change_appearance_mode_event)
        self.appearance_mode_optionemenu.grid(row=8, column=0, padx=20, pady=(10, 20)) # Adjusted row
        self.appearance_mode_optionemenu.set(app_appearance_mode)

        # --- Main Content Frame Container ---
        self.main_content_container = customtkinter.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_content_container.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_content_container.grid_columnconfigure(0, weight=1)
        self.main_content_container.grid_rowconfigure(0, weight=1)

        # --- Footer (e.g., status bar) ---
        # IMPORTANT: These must be initialized BEFORE any pages that might call set_status
        self.status_bar_frame = customtkinter.CTkFrame(self, height=30, corner_radius=0)
        self.status_bar_frame.grid(row=1, column=1, sticky="ew", padx=20, pady=(0, 20))
        self.status_bar_frame.grid_columnconfigure(0, weight=1)

        self.status_label = customtkinter.CTkLabel(self.status_bar_frame, text="Ready.")
        self.status_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.logger.info("Main application UI initialized.")
        self.set_status("Application ready.") # This call now happens AFTER status_label is created

        # --- Initialize Pages ---
        # This now happens AFTER the status bar is ready
        self.pages = {}
        self._create_pages() # Create all content pages
        
        # Show initial active page
        self.show_page("video_converter") # Show video converter page by default

        # Display FFmpeg version on startup
        self.after(100, self._show_ffmpeg_version_on_startup) # Delay slightly to ensure GUI is visible

    def _create_pages(self):
        """
        Creates instances of all content pages and stores them in a dictionary.
        """
        self.pages["video_converter"] = VideoConverterPage(self.main_content_container, self)
        self.pages["video_enhancement"] = VideoEnhancementPage(self.main_content_container, self)
        self.pages["video_background_removal"] = VideoBgRemovalPage(self.main_content_container, self) # NEW: Video background removal page
        self.pages["audio_enhancement"] = AudioEnhancementPage(self.main_content_container, self)
        self.pages["image_tools"] = ImageToolsPage(self.main_content_container, self)
        # Future pages will be added here:
        # self.pages["history"] = HistoryPage(self.main_content_container, self)

        # Grid all pages, but hide them initially
        for page_name, page_frame in self.pages.items():
            page_frame.grid(row=0, column=0, sticky="nsew") # All pages occupy the same grid cell
            page_frame.grid_remove() # Hide them initially

    def show_page(self, page_name: str):
        """
        Displays the selected page and hides all others.
        """
        if page_name not in self.pages:
            self.logger.error(f"Attempted to show unknown page: {page_name}")
            self.set_status(f"Error: Page '{page_name}' not found.", level="error")
            return

        for name, page_frame in self.pages.items():
            if name == page_name:
                page_frame.grid() # Show the selected page
                self.logger.info(f"Displayed page: {page_name}")
            else:
                page_frame.grid_remove() # Hide other pages
        self.set_status(f"Switched to {page_name.replace('_', ' ').title()} section.")
        self.logger.debug(f"Current page: {page_name}")

    def _show_ffmpeg_version_on_startup(self):
        """
        Checks FFmpeg version and displays it in a messagebox.
        """
        try:
            # Run ffmpeg -version command
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW # Hide console window on Windows
            )
            # Extract the first line which usually contains the version
            version_line = result.stdout.split('\n')[0].strip()
            self.logger.info(f"FFmpeg detected: {version_line}")
            messagebox.showinfo("FFmpeg Version Detected", f"FFmpeg is installed and accessible:\n\n{version_line}")
        except FileNotFoundError:
            self.logger.error("FFmpeg executable not found in PATH.")
            messagebox.showerror("FFmpeg Not Found",
                                 "FFmpeg is required for video processing.\n"
                                 "Please ensure it is installed and its directory is added to your system's PATH environment variable.")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error running ffmpeg -version: {e.stderr}", exc_info=True)
            messagebox.showerror("FFmpeg Error",
                                 f"Failed to get FFmpeg version.\n"
                                 f"Error: {e.stderr.strip()}\n"
                                 "Please check your FFmpeg installation.")
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while checking FFmpeg: {e}", exc_info=True)
            messagebox.showerror("Unexpected Error", f"An unexpected error occurred while checking FFmpeg: {e}")


    def change_appearance_mode_event(self, new_appearance_mode: str):
        """
        Handles changing the application's appearance mode (Light/Dark/System).
        Updates the CustomTkinter setting and saves it to config.
        """
        customtkinter.set_appearance_mode(new_appearance_mode)
        self.config_manager.set_setting("app_settings.appearance_mode", new_appearance_mode)
        self.logger.info(f"Appearance mode changed to: {new_appearance_mode}")
        self.set_status(f"Appearance mode set to {new_appearance_mode}.")

    def set_status(self, message: str, level: str = "info"):
        """
        Updates the status bar with a message and logs it.
        """
        self.status_label.configure(text=message)
        if level == "info":
            self.logger.info(f"STATUS: {message}")
        elif level == "warning":
            self.logger.warning(f"STATUS: {message}")
        elif level == "error":
            self.logger.error(f"STATUS: {message}")
        else:
            self.logger.debug(f"STATUS: {message}") # Default for unrecognized levels

    # --- Navigation Button Events ---
    def video_conversion_button_event(self):
        self.show_page("video_converter")
        self.set_status("Video Conversion section selected.")
        self.logger.debug("Video Conversion button clicked.")

    def video_enhancement_button_event(self):
        self.show_page("video_enhancement")
        self.set_status("Video Enhancement section selected.")
        self.logger.debug("Video Enhancement button clicked.")

    def video_bg_removal_button_event(self): # NEW function
        self.show_page("video_background_removal")
        self.set_status("Video Background Removal section selected.")
        self.logger.debug("Video Background Removal button clicked.")

    def audio_button_event(self):
        self.show_page("audio_enhancement")
        self.set_status("Audio Enhancement section selected.")
        self.logger.debug("Audio button clicked.")

    def image_button_event(self):
        self.show_page("image_tools")
        self.set_status("Image Tools section selected.")
        self.logger.debug("Image button clicked.")

    def history_button_event(self):
        self.set_status("History section selected (not implemented yet).")
        self.logger.debug("History button clicked.")
        # Future: self.show_page("history")

if __name__ == "__main__":
    try:
        app = App()
        logger.debug("Calling app.mainloop()...")
        app.mainloop()
        logger.debug("app.mainloop() returned.")
    except Exception as e:
        logger.critical(f"An unhandled error occurred during application startup: {e}", exc_info=True)
        # Display a critical error message box before exiting
        messagebox.showerror("Critical Application Error",
                             f"An unhandled error occurred during application startup:\n\n{e}\n\n"
                             "Please check the application logs for more details.")
        sys.exit(1)
    finally:
        logger.info("Application exited.")
