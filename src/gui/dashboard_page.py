import customtkinter
import logging
from pathlib import Path

from src.core.logger import get_application_logger

class DashboardPage(customtkinter.CTkFrame):
    """
    CustomTkinter Frame for the main application dashboard.
    Displays cards for each tool, allowing easy navigation.
    """
    def __init__(self, master, app_instance):
        super().__init__(master, fg_color="transparent")
        self.logger = get_application_logger()
        self.app_instance = app_instance # Reference to the main App/MainWindow class for navigation

        self.logger.info("Initializing DashboardPage UI.")

        # Configure grid layout for this page
        self.grid_columnconfigure(0, weight=1)
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
        self.cards_scroll_frame.grid_columnconfigure((0, 1, 2), weight=1) # Three columns for cards

        self._create_tool_cards()

    def _create_tool_cards(self):
        """
        Dynamically creates tool cards for the dashboard.
        Each card is a clickable frame that navigates to the corresponding page.
        """
        tool_data = [
            {
                "name": "Video Conversion",
                "description": "Convert various video formats to optimized MP4.",
                "page_name": "video_converter"
            },
            {
                "name": "Social Media Post",
                "description": "Crop, subtitle, and enhance videos for social media platforms.",
                "page_name": "social_media_post"
            },
            {
                "name": "Video Enhancement",
                "description": "Improve video quality with noise reduction and color correction.",
                "page_name": "video_enhancement"
            },
            {
                "name": "Video Background Removal",
                "description": "Remove or replace backgrounds in video clips.",
                "page_name": "video_bg_removal"
            },
            {
                "name": "Audio Enhancement",
                "description": "Clean audio, reduce noise, and normalize levels.",
                "page_name": "audio_enhancement"
            },
            {
                "name": "Image Tools",
                "description": "Perform various image operations, such as background removal and resizing.",
                "page_name": "image_tools"
            },
            # History is now a primary nav item, so it's not a card here
        ]

        row_idx = 0
        col_idx = 0
        num_columns = 3 # Number of cards per row
        
        # Define base card dimensions (approximate) for hover effect
        base_card_height = 160 # Fixed height for normal state
        expanded_card_height = 220 # Height when hovered (increased for more description space)

        for i, tool in enumerate(tool_data):
            # Create a card frame for each tool
            card_frame = customtkinter.CTkFrame(self.cards_scroll_frame, 
                                                corner_radius=10,
                                                fg_color=("gray85", "gray20"), 
                                                border_width=1,
                                                border_color=("gray70", "gray30"),
                                                height=base_card_height) # Set initial height
            card_frame.grid(row=row_idx, column=col_idx, padx=15, pady=15, sticky="nsew")
            
            # Configure card_frame's internal grid
            card_frame.grid_columnconfigure(0, weight=1)
            card_frame.grid_rowconfigure(0, weight=0) # For title
            card_frame.grid_rowconfigure(1, weight=1) # For description (expands)
            card_frame.grid_propagate(False) # Prevent frame from resizing to fit content automatically

            # Card Title (Name of the tool)
            tool_name_label = customtkinter.CTkLabel(card_frame,
                                                     text=tool["name"],
                                                     font=customtkinter.CTkFont(size=18, weight="bold"),
                                                     wraplength=200, # Wrap text to fit card width
                                                     anchor="w") # Align text to west (left)
            tool_name_label.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="nw")

            # Card Description
            tool_desc_label = customtkinter.CTkLabel(card_frame,
                                                     text=tool["description"],
                                                     font=customtkinter.CTkFont(size=13),
                                                     wraplength=200, # Initial wrap for normal state
                                                     justify="left", # Use justify for label text alignment
                                                     anchor="nw", # Align text to north-west (top-left)
                                                     text_color=("gray40", "gray60"))
            tool_desc_label.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="nsew") # Allows description to take available space

            # Bind click events to the card_frame itself and its children
            card_frame.bind("<Button-1>", lambda event, p=tool["page_name"]: self._navigate_to_page(p))
            tool_name_label.bind("<Button-1>", lambda event, p=tool["page_name"]: self._navigate_to_page(p))
            tool_desc_label.bind("<Button-1>", lambda event, p=tool["page_name"]: self._navigate_to_page(p))


            # Bind hover events to the card_frame and propagate to children
            card_frame.bind("<Enter>", lambda event, cf=card_frame, dl=tool_desc_label, tn=tool["name"], desc=tool["description"]: self._on_card_hover_enter(event, cf, dl, tn, desc, expanded_card_height))
            card_frame.bind("<Leave>", lambda event, cf=card_frame, dl=tool_desc_label, tn=tool["name"], desc=tool["description"]: self._on_card_hover_leave(event, cf, dl, tn, desc, base_card_height))
            
            tool_name_label.bind("<Enter>", lambda e, cf=card_frame: cf.event_generate("<Enter>", x=e.x, y=e.y))
            tool_name_label.bind("<Leave>", lambda e, cf=card_frame: cf.event_generate("<Leave>", x=e.x, y=e.y))
            tool_desc_label.bind("<Enter>", lambda e, cf=card_frame: cf.event_generate("<Enter>", x=e.x, y=e.y))
            tool_desc_label.bind("<Leave>", lambda e, cf=card_frame: cf.event_generate("<Leave>", x=e.x, y=e.y))


            # Increment column and row indices
            col_idx += 1
            if col_idx >= num_columns:
                col_idx = 0
                row_idx += 1
        
        self.logger.info(f"Created {len(tool_data)} dashboard cards.")

    def _on_card_hover_enter(self, event, card_frame, desc_label, tool_name, full_description, expanded_height):
        """Handles mouse entering the card frame."""
        self.logger.debug(f"Mouse entered card: {tool_name}")
        # Expand card height
        card_frame.configure(height=expanded_height)
        # Show full description by adjusting wraplength to allow more space
        # Use card_frame's actual width minus padding for wrapping
        current_width = card_frame.winfo_width()
        desc_label.configure(wraplength=current_width - 30) # Allow more wrapping
        # Change card background color for hover effect
        card_frame.configure(fg_color=customtkinter.ThemeManager.theme["CTkButton"]["hover_color"]) # Use a standard hover color
        self.app_instance.set_status(f"Hovering over: {tool_name}") # Set status message

    def _on_card_hover_leave(self, event, card_frame, desc_label, tool_name, full_description, base_height):
        """Handles mouse leaving the card frame."""
        self.logger.debug(f"Mouse left card: {tool_name}")
        # Revert card height
        card_frame.configure(height=base_height)
        # Revert description wrapping
        desc_label.configure(wraplength=200) # Revert to initial wrap
        # Revert card background color
        card_frame.configure(fg_color=("gray85", "gray20"))
        self.app_instance.set_status("Application ready. Welcome!") # Revert status message to English


    def _navigate_to_page(self, page_name: str):
        """
        Navigates to the specified page using the main application instance.
        """
        self.app_instance.show_page(page_name)
        # Convert page_name to a more readable format for status message
        display_name = page_name.replace('_', ' ').title()
        self.app_instance.set_status(f"Navigating to: {display_name}") # UI text in English
        self.logger.debug(f"Dashboard navigated to {page_name}.")
