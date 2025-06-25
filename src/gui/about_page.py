import customtkinter
import logging
import webbrowser # For opening social media links
from pathlib import Path

from src.core.logger import get_application_logger

class AboutPage(customtkinter.CTkFrame):
    """
    CustomTkinter Frame for displaying information about the application,
    including project overview, features, and social media links.
    """
    def __init__(self, master, app_instance):
        super().__init__(master, fg_color="transparent")
        self.logger = get_application_logger()
        self.app_instance = app_instance # Reference to the main App/MainWindow class for status updates

        self.logger.info("Initializing AboutPage UI.")

        # Configure grid layout for this page
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0) # Title
        self.grid_rowconfigure(1, weight=1) # Scrollable content

        # Title
        self.title_label = customtkinter.CTkLabel(self,
                                                  text="About Creator's Toolkit",
                                                  font=customtkinter.CTkFont(size=28, weight="bold"))
        self.title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

        # Scrollable frame for content
        self.content_scroll_frame = customtkinter.CTkScrollableFrame(self, fg_color="transparent")
        self.content_scroll_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self.content_scroll_frame.grid_columnconfigure(0, weight=1)

        self._create_about_content()

    def _create_about_content(self):
        """Populates the about page with content from README and social links."""
        row_idx = 0

        # Project Overview Section
        overview_title = customtkinter.CTkLabel(self.content_scroll_frame, text="🚀 Project Overview",
                                                font=customtkinter.CTkFont(size=20, weight="bold"),
                                                anchor="w")
        overview_title.grid(row=row_idx, column=0, padx=10, pady=(15, 5), sticky="ew")
        row_idx += 1
        overview_text = (
            "The \"Creator's Toolkit\" is a desktop application designed for content creators, "
            "offering a unified graphical interface (GUI) for automating common media processing tasks. "
            "Built with Python 3.11 and leveraging powerful libraries like FFmpeg, MoviePy, OpenCV, "
            "and Rembg, this application aims to provide a streamlined, efficient, and high-quality "
            "solution for video conversions, audio enhancements, background removal, and more, "
            "specifically optimized for Windows 11.\n\n"
            "This project evolved from a collection of command-line scripts previously used on Fedora, "
            "now being re-engineered to deliver a native, clean, and intuitive user experience on Windows. "
            "Our primary focus is on performance efficiency, especially on systems with less powerful CPUs "
            "but ample RAM, ensuring smooth operation and superior output quality."
        )
        overview_label = customtkinter.CTkLabel(self.content_scroll_frame, text=overview_text,
                                                font=customtkinter.CTkFont(size=14),
                                                wraplength=700, justify="left", anchor="nw")
        overview_label.grid(row=row_idx, column=0, padx=10, pady=5, sticky="ew")
        row_idx += 1

        # Key Features Section
        features_title = customtkinter.CTkLabel(self.content_scroll_frame, text="✨ Key Features",
                                                font=customtkinter.CTkFont(size=20, weight="bold"),
                                                anchor="w")
        features_title.grid(row=row_idx, column=0, padx=10, pady=(15, 5), sticky="ew")
        row_idx += 1
        features_list = [
            "Video Conversion: Seamlessly convert .mpg videos to optimized .mp4 format.",
            "Professional Video Processing: Advanced video styling, including subtitles, optimized face tracking, and quality enhancements.",
            "Audio Cleaning & Enhancement: Professional-grade noise reduction and vocal clarity improvements for audio files.",
            "Image Background Removal: Quickly remove backgrounds from images with enhanced quality output.",
            "Video Background Removal: Transform video clips by removing or replacing their backgrounds.",
            "Stylized Video Enhancements: Apply various visual improvements like denoising, sharpening, contrast, saturation, and more to videos.",
            "Intuitive User Interface: A clean, modern, Canva-like UI built with CustomTkinter for a native Windows 11 feel.",
            "Operation History: Keep track of all processed tasks, including inputs, outputs, and status.",
            "User-Defined Paths: Full control over input and output file selection and naming.",
            "Efficient Resource Management: Optimized for performance on systems with varying hardware capabilities, focusing on multiprocessing and RAM efficiency.",
            "Comprehensive Logging & Error Handling: Robust system for logging operations and gracefully handling errors."
        ]
        features_text = "\n".join([f"• {feature}" for feature in features_list])
        features_label = customtkinter.CTkLabel(self.content_scroll_frame, text=features_text,
                                                font=customtkinter.CTkFont(size=14),
                                                wraplength=700, justify="left", anchor="nw")
        features_label.grid(row=row_idx, column=0, padx=10, pady=5, sticky="ew")
        row_idx += 1

        # System Requirements Section
        requirements_title = customtkinter.CTkLabel(self.content_scroll_frame, text="💻 System Requirements",
                                                    font=customtkinter.CTkFont(size=20, weight="bold"),
                                                    anchor="w")
        requirements_title.grid(row=row_idx, column=0, padx=10, pady=(15, 5), sticky="ew")
        row_idx += 1
        requirements_list = [
            "Operating System: Windows 11 (64-bit)",
            "Python: Version 3.11",
            "FFmpeg: A recent, full-featured FFmpeg build installed and accessible via system's PATH.",
            "Recommended RAM: 8GB or more (40GB as in the developer's machine is excellent for demanding video tasks).",
            "Disk Space: Sufficient space for input/output media files and application installation."
        ]
        requirements_text = "\n".join([f"• {req}" for req in requirements_list])
        requirements_label = customtkinter.CTkLabel(self.content_scroll_frame, text=requirements_text,
                                                    font=customtkinter.CTkFont(size=14),
                                                    wraplength=700, justify="left", anchor="nw")
        requirements_label.grid(row=row_idx, column=0, padx=10, pady=5, sticky="ew")
        row_idx += 1

        # License Section
        license_title = customtkinter.CTkLabel(self.content_scroll_frame, text="📄 License",
                                               font=customtkinter.CTkFont(size=20, weight="bold"),
                                               anchor="w")
        license_title.grid(row=row_idx, column=0, padx=10, pady=(15, 5), sticky="ew")
        row_idx += 1
        license_text = "This project is licensed under the MIT License - see the LICENSE file for details."
        license_label = customtkinter.CTkLabel(self.content_scroll_frame, text=license_text,
                                               font=customtkinter.CTkFont(size=14),
                                               wraplength=700, justify="left", anchor="nw")
        license_label.grid(row=row_idx, column=0, padx=10, pady=5, sticky="ew")
        row_idx += 1

        # Special Thanks Section
        thanks_title = customtkinter.CTkLabel(self.content_scroll_frame, text="Special Thanks",
                                              font=customtkinter.CTkFont(size=20, weight="bold"),
                                              anchor="w")
        thanks_title.grid(row=row_idx, column=0, padx=10, pady=(15, 5), sticky="ew")
        row_idx += 1
        thanks_text = "Special thanks to the developers of Python, CustomTkinter, FFmpeg, MoviePy, OpenCV, Rembg, and all other open-source libraries that make this project possible."
        thanks_label = customtkinter.CTkLabel(self.content_scroll_frame, text=thanks_text,
                                              font=customtkinter.CTkFont(size=14),
                                              wraplength=700, justify="left", anchor="nw")
        thanks_label.grid(row=row_idx, column=0, padx=10, pady=5, sticky="ew")
        row_idx += 1


        # Social Media Links
        social_media_title = customtkinter.CTkLabel(self.content_scroll_frame, text="Connect with Us!",
                                                    font=customtkinter.CTkFont(size=20, weight="bold"),
                                                    anchor="w")
        social_media_title.grid(row=row_idx, column=0, padx=10, pady=(20, 10), sticky="ew")
        row_idx += 1

        social_media_frame = customtkinter.CTkFrame(self.content_scroll_frame, fg_color="transparent")
        social_media_frame.grid(row=row_idx, column=0, padx=10, pady=5, sticky="ew")
        social_media_frame.grid_columnconfigure((0, 1, 2, 3), weight=1) # Evenly space buttons
        row_idx += 1

        social_links = [
            {"name": "Instagram", "url": "https://www.instagram.com/codewithbotina/", "color": "#E1306C"},
            {"name": "TikTok", "url": "https://www.tiktok.com/@codewithbotina", "color": "#69C9D0"},
            {"name": "YouTube", "url": "https://www.youtube.com/@CodeWithBotina", "color": "#FF0000"},
            {"name": "Facebook", "url": "https://www.facebook.com/profile.php?id=61572879398634", "color": "#1877F2"},
        ]

        for i, link in enumerate(social_links):
            social_button = customtkinter.CTkButton(social_media_frame,
                                                    text=link["name"],
                                                    fg_color=link["color"],
                                                    text_color="white",
                                                    hover_color=link["color"], # Keep hover same as fg for simpler look
                                                    command=lambda url=link["url"]: self._open_link(url),
                                                    font=customtkinter.CTkFont(size=14, weight="bold"),
                                                    corner_radius=8,
                                                    height=40)
            social_button.grid(row=0, column=i, padx=5, pady=5, sticky="ew")

        self.logger.info("AboutPage content created.")

    def _open_link(self, url: str):
        """Opens the given URL in the default web browser."""
        try:
            webbrowser.open_new_tab(url)
            self.app_instance.set_status(f"Opening link: {url}")
            self.logger.info(f"Opened external link: {url}")
        except Exception as e:
            self.app_instance.set_status(f"Failed to open link: {url}", level="error")
            self.logger.error(f"Error opening link {url}: {e}", exc_info=True)