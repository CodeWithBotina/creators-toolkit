import customtkinter
from tkinter import filedialog, messagebox
import threading
from pathlib import Path
import logging
import json # For handling overlay data
from typing import Dict, Any, List, Optional # Import Dict, Any, List, Optional from typing

# Import core and module components
from src.core.logger import get_application_logger
from src.core.config_manager import get_application_config
from src.utils.font_manager import get_application_font_manager
from src.modules.social_media_video_processor import SocialMediaVideoProcessor

class SocialMediaPostPage(customtkinter.CTkFrame):
    """
    CustomTkinter Frame for Social Media Video Post Processing functionality.
    Provides UI for intelligent cropping, subtitle generation, silent segment removal,
    automatic enhancements, and overlay management.
    """
    def __init__(self, master, app_instance):
        super().__init__(master, fg_color="transparent")
        self.logger = get_application_logger()
        self.config_manager = get_application_config()
        self.font_manager = get_application_font_manager() # For subtitle font list
        self.app_instance = app_instance # Reference to the main App/MainWindow class for status updates
        self.processor = SocialMediaVideoProcessor() # Instantiate the backend logic

        self.input_file_path: Optional[Path] = None
        self.output_file_path: Optional[Path] = None
        self.current_overlays: List[Dict[str, Any]] = [] # List to store overlay items for the current session

        self.logger.info("Initializing SocialMediaPostPage UI.")

        # Configure grid layout for this page
        self.grid_columnconfigure(0, weight=1) # Main content column
        self.grid_rowconfigure(0, weight=0) # Title
        self.grid_rowconfigure(1, weight=1) # Scrollable frame for parameters
        self.grid_rowconfigure(2, weight=0) # Progress and button row

        # Title
        self.title_label = customtkinter.CTkLabel(self, text="Social Media Video Processor", font=customtkinter.CTkFont(size=24, weight="bold"))
        self.title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

        # Scrollable Frame for Parameters (to handle many widgets)
        self.scrollable_frame = customtkinter.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self.scrollable_frame.grid_columnconfigure((0, 2), weight=0) # Labels, buttons
        self.scrollable_frame.grid_columnconfigure(1, weight=1) # Entry fields, sliders

        # --- Input/Output Section ---
        row_idx = 0
        self.input_label = customtkinter.CTkLabel(self.scrollable_frame, text="Input Video File:")
        self.input_label.grid(row=row_idx, column=0, padx=(0, 10), pady=10, sticky="w")
        self.input_entry = customtkinter.CTkEntry(self.scrollable_frame, placeholder_text="No file selected...", state="readonly")
        self.input_entry.grid(row=row_idx, column=1, padx=10, pady=10, sticky="ew")
        self.input_button = customtkinter.CTkButton(self.scrollable_frame, text="Browse", command=self._browse_input_file)
        self.input_button.grid(row=row_idx, column=2, padx=(10, 0), pady=10, sticky="e")
        row_idx += 1

        self.output_label = customtkinter.CTkLabel(self.scrollable_frame, text="Output Video File:")
        self.output_label.grid(row=row_idx, column=0, padx=(0, 10), pady=10, sticky="w")
        self.output_entry = customtkinter.CTkEntry(self.scrollable_frame, placeholder_text="Output path will be set automatically (.mp4)", state="readonly")
        self.output_entry.grid(row=row_idx, column=1, padx=10, pady=10, sticky="ew")
        self.output_button = customtkinter.CTkButton(self.scrollable_frame, text="Save As", command=self._browse_output_file)
        self.output_button.grid(row=row_idx, column=2, padx=(10, 0), pady=10, sticky="e")
        row_idx += 1

        # --- Processing Parameters Section ---
        self.params_label = customtkinter.CTkLabel(self.scrollable_frame, text="Processing Options", font=customtkinter.CTkFont(size=18, weight="bold"))
        self.params_label.grid(row=row_idx, column=0, columnspan=3, padx=0, pady=(30, 10), sticky="ew")
        row_idx += 1

        # Auto Crop Checkbox
        self.auto_crop_checkbox = customtkinter.CTkCheckBox(self.scrollable_frame, text="Intelligent Auto-Crop (to vertical format)", command=self._update_config_setting("auto_crop"))
        self.auto_crop_checkbox.grid(row=row_idx, column=0, columnspan=2, padx=0, pady=10, sticky="w")
        if self.config_manager.get_setting("processing_parameters.social_media.auto_crop", True): self.auto_crop_checkbox.select()
        else: self.auto_crop_checkbox.deselect()
        row_idx += 1

        # Target Resolution Dropdown
        self.target_res_label = customtkinter.CTkLabel(self.scrollable_frame, text="Target Resolution:")
        self.target_res_label.grid(row=row_idx, column=0, padx=(0, 10), pady=5, sticky="w")
        self.target_res_options = ["1080x1920 (Vertical)", "1920x1080 (Horizontal)", "1080x1080 (Square)", "720x1280 (Vertical HD)"]
        self.target_res_combobox = customtkinter.CTkComboBox(self.scrollable_frame, values=self.target_res_options,
                                                             command=self._update_target_resolution)
        self.target_res_combobox.grid(row=row_idx, column=1, padx=10, pady=5, sticky="ew")
        initial_target_res = self.config_manager.get_setting("processing_parameters.social_media.target_social_media_resolution", "1080x1920")
        if "1920x1080" in initial_target_res:
            self.target_res_combobox.set("1920x1080 (Horizontal)")
        elif "1080x1080" in initial_target_res:
            self.target_res_combobox.set("1080x1080 (Square)")
        elif "720x1280" in initial_target_res:
            self.target_res_combobox.set("720x1280 (Vertical HD)")
        else:
            self.target_res_combobox.set("1080x1920 (Vertical)")
        row_idx += 1

        # --- Subtitle Options ---
        self.subtitle_label_frame = customtkinter.CTkFrame(self.scrollable_frame, fg_color="transparent")
        self.subtitle_label_frame.grid(row=row_idx, column=0, columnspan=3, padx=0, pady=(20, 10), sticky="ew")
        self.subtitle_label_frame.grid_columnconfigure(0, weight=1)

        self.generate_subtitles_checkbox = customtkinter.CTkCheckBox(self.subtitle_label_frame, text="Generate Subtitles (Vosk Offline ASR)", command=self._toggle_subtitle_options)
        self.generate_subtitles_checkbox.grid(row=0, column=0, padx=0, pady=10, sticky="w")
        if self.config_manager.get_setting("processing_parameters.social_media.generate_subtitles", True): self.generate_subtitles_checkbox.select()
        else: self.generate_subtitles_checkbox.deselect()

        row_idx += 1
        # Subtitle Settings Container Frame
        self.subtitle_settings_frame = customtkinter.CTkFrame(self.scrollable_frame, fg_color="transparent")
        self.subtitle_settings_frame.grid(row=row_idx, column=0, columnspan=3, padx=20, pady=(0,10), sticky="ew")
        self.subtitle_settings_frame.grid_columnconfigure(1, weight=1)
        row_idx += 1

        sub_row_idx = 0
        self.subtitle_font_label = customtkinter.CTkLabel(self.subtitle_settings_frame, text="Font:")
        self.subtitle_font_label.grid(row=sub_row_idx, column=0, padx=(0, 10), pady=5, sticky="w")
        self.font_names = self.font_manager.get_available_font_names()
        self.subtitle_font_combobox = customtkinter.CTkComboBox(self.subtitle_settings_frame, values=self.font_names,
                                                                 command=self._update_config_setting_with_value("default_subtitle_font_name"))
        self.subtitle_font_combobox.grid(row=sub_row_idx, column=1, padx=10, pady=5, sticky="ew")
        initial_font = self.config_manager.get_setting("processing_parameters.social_media.default_subtitle_font_name", "Arial")
        if initial_font in self.font_names:
            self.subtitle_font_combobox.set(initial_font)
        else:
            self.subtitle_font_combobox.set("Arial") # Fallback
        sub_row_idx += 1

        self.subtitle_size_label = customtkinter.CTkLabel(self.subtitle_settings_frame, text="Font Size:")
        self.subtitle_size_label.grid(row=sub_row_idx, column=0, padx=(0, 10), pady=5, sticky="w")
        self.subtitle_size_entry = customtkinter.CTkEntry(self.subtitle_settings_frame, width=80)
        self.subtitle_size_entry.grid(row=sub_row_idx, column=1, padx=10, pady=5, sticky="w")
        initial_font_size = self.config_manager.get_setting("processing_parameters.social_media.subtitle_font_size", 40)
        self.subtitle_size_entry.insert(0, str(initial_font_size))
        self.subtitle_size_entry.bind("<FocusOut>", lambda e: self._update_numeric_config_setting("subtitle_font_size", int, e))
        self.subtitle_size_entry.bind("<Return>", lambda e: self._update_numeric_config_setting("subtitle_font_size", int, e))
        sub_row_idx += 1

        self.subtitle_color_label = customtkinter.CTkLabel(self.subtitle_settings_frame, text="Font Color (Hex):")
        self.subtitle_color_label.grid(row=sub_row_idx, column=0, padx=(0, 10), pady=5, sticky="w")
        self.subtitle_color_entry = customtkinter.CTkEntry(self.subtitle_settings_frame, width=100)
        self.subtitle_color_entry.grid(row=sub_row_idx, column=1, padx=10, pady=5, sticky="w")
        initial_font_color = self.config_manager.get_setting("processing_parameters.social_media.subtitle_color", "#FFFFFF")
        self.subtitle_color_entry.insert(0, initial_font_color)
        self.subtitle_color_entry.bind("<FocusOut>", lambda e: self._update_config_setting_from_entry("subtitle_color", e))
        self.subtitle_color_entry.bind("<Return>", lambda e: self._update_config_setting_from_entry("subtitle_color", e))
        sub_row_idx += 1

        self.subtitle_stroke_width_label = customtkinter.CTkLabel(self.subtitle_settings_frame, text="Stroke Width:")
        self.subtitle_stroke_width_label.grid(row=sub_row_idx, column=0, padx=(0, 10), pady=5, sticky="w")
        self.subtitle_stroke_width_entry = customtkinter.CTkEntry(self.subtitle_settings_frame, width=80)
        self.subtitle_stroke_width_entry.grid(row=sub_row_idx, column=1, padx=10, pady=5, sticky="w")
        initial_stroke_width = self.config_manager.get_setting("processing_parameters.social_media.subtitle_stroke_width", 2)
        self.subtitle_stroke_width_entry.insert(0, str(initial_stroke_width))
        self.subtitle_stroke_width_entry.bind("<FocusOut>", lambda e: self._update_numeric_config_setting("subtitle_stroke_width", int, e))
        self.subtitle_stroke_width_entry.bind("<Return>", lambda e: self._update_numeric_config_setting("subtitle_stroke_width", int, e))
        sub_row_idx += 1

        self.subtitle_stroke_color_label = customtkinter.CTkLabel(self.subtitle_settings_frame, text="Stroke Color (Hex):")
        self.subtitle_stroke_color_label.grid(row=sub_row_idx, column=0, padx=(0, 10), pady=5, sticky="w")
        self.subtitle_stroke_color_entry = customtkinter.CTkEntry(self.subtitle_settings_frame, width=100)
        self.subtitle_stroke_color_entry.grid(row=sub_row_idx, column=1, padx=10, pady=5, sticky="w")
        initial_stroke_color = self.config_manager.get_setting("processing_parameters.social_media.subtitle_stroke_color", "#000000")
        self.subtitle_stroke_color_entry.insert(0, initial_stroke_color)
        self.subtitle_stroke_color_entry.bind("<FocusOut>", lambda e: self._update_config_setting_from_entry("subtitle_stroke_color", e))
        self.subtitle_stroke_color_entry.bind("<Return>", lambda e: self._update_config_setting_from_entry("subtitle_stroke_color", e))
        sub_row_idx += 1

        self.subtitle_position_label = customtkinter.CTkLabel(self.subtitle_settings_frame, text="Vertical Position (% from top):")
        self.subtitle_position_label.grid(row=sub_row_idx, column=0, padx=(0, 10), pady=5, sticky="w")
        self.subtitle_position_slider = customtkinter.CTkSlider(self.subtitle_settings_frame, from_=0.0, to=1.0, number_of_steps=100,
                                                                 command=self._update_subtitle_position)
        self.subtitle_position_slider.grid(row=sub_row_idx, column=1, padx=10, pady=5, sticky="ew")
        self.subtitle_position_value_label = customtkinter.CTkLabel(self.subtitle_settings_frame, text="85%")
        self.subtitle_position_value_label.grid(row=sub_row_idx, column=2, padx=(10, 0), pady=5, sticky="e")
        initial_position_y = self.config_manager.get_setting("processing_parameters.social_media.subtitle_font_position_y", 0.85)
        self.subtitle_position_slider.set(initial_position_y)
        self._update_subtitle_position(initial_position_y)
        sub_row_idx += 1

        self.subtitle_words_per_line_label = customtkinter.CTkLabel(self.subtitle_settings_frame, text="Words Per Line:")
        self.subtitle_words_per_line_label.grid(row=sub_row_idx, column=0, padx=(0, 10), pady=5, sticky="w")
        self.subtitle_words_per_line_entry = customtkinter.CTkEntry(self.subtitle_settings_frame, width=80)
        self.subtitle_words_per_line_entry.grid(row=sub_row_idx, column=1, padx=10, pady=5, sticky="w")
        initial_words_per_line = self.config_manager.get_setting("processing_parameters.social_media.subtitle_words_per_line", 5)
        self.subtitle_words_per_line_entry.insert(0, str(initial_words_per_line))
        self.subtitle_words_per_line_entry.bind("<FocusOut>", lambda e: self._update_numeric_config_setting("subtitle_words_per_line", int, e))
        self.subtitle_words_per_line_entry.bind("<Return>", lambda e: self._update_numeric_config_setting("subtitle_words_per_line", int, e))
        sub_row_idx += 1

        self._toggle_subtitle_options() # Initial toggle based on config

        # --- Audio & Video Enhancement Checkboxes ---
        self.apply_video_enhancement_checkbox = customtkinter.CTkCheckBox(self.scrollable_frame, text="Apply Automatic Video Enhancement", command=self._update_config_setting("apply_auto_video_enhancement"))
        self.apply_video_enhancement_checkbox.grid(row=row_idx, column=0, columnspan=2, padx=0, pady=10, sticky="w")
        if self.config_manager.get_setting("processing_parameters.social_media.apply_auto_video_enhancement", True): self.apply_video_enhancement_checkbox.select()
        else: self.apply_video_enhancement_checkbox.deselect()
        row_idx += 1

        self.apply_audio_enhancement_checkbox = customtkinter.CTkCheckBox(self.scrollable_frame, text="Apply Automatic Audio Enhancement (Noise Reduction, Normalization)", command=self._update_config_setting("apply_auto_audio_enhancement"))
        self.apply_audio_enhancement_checkbox.grid(row=row_idx, column=0, columnspan=2, padx=0, pady=10, sticky="w")
        if self.config_manager.get_setting("processing_parameters.social_media.apply_auto_audio_enhancement", True): self.apply_audio_enhancement_checkbox.select()
        else: self.apply_audio_enhancement_checkbox.deselect()
        row_idx += 1

        # --- Overlays Section ---
        self.overlays_label_frame = customtkinter.CTkFrame(self.scrollable_frame, fg_color="transparent")
        self.overlays_label_frame.grid(row=row_idx, column=0, columnspan=3, padx=0, pady=(20, 10), sticky="ew")
        self.overlays_label_frame.grid_columnconfigure(0, weight=1)
        self.overlays_label = customtkinter.CTkLabel(self.overlays_label_frame, text="Overlays", font=customtkinter.CTkFont(size=18, weight="bold"))
        self.overlays_label.grid(row=0, column=0, padx=0, pady=0, sticky="w")
        row_idx += 1

        self.add_text_overlay_button = customtkinter.CTkButton(self.scrollable_frame, text="Add Text Overlay", command=self._add_text_overlay)
        self.add_text_overlay_button.grid(row=row_idx, column=0, padx=0, pady=5, sticky="w")
        self.add_image_overlay_button = customtkinter.CTkButton(self.scrollable_frame, text="Add Image Overlay", command=self._add_image_overlay)
        self.add_image_overlay_button.grid(row=row_idx, column=1, padx=10, pady=5, sticky="w")
        row_idx += 1

        self.overlays_display_frame = customtkinter.CTkScrollableFrame(self.scrollable_frame, fg_color="transparent", height=150)
        self.overlays_display_frame.grid(row=row_idx, column=0, columnspan=3, padx=0, pady=10, sticky="ew")
        self.overlays_display_frame.grid_columnconfigure(0, weight=1)
        row_idx += 1
        
        self._refresh_overlays_display() # Display any existing overlays (from config or session)

        # Delete Original Checkbox
        self.delete_original_checkbox = customtkinter.CTkCheckBox(self.scrollable_frame, text="Delete original file after successful processing", command=self._update_config_setting("delete_original_after_processing"))
        self.delete_original_checkbox.grid(row=row_idx, column=0, columnspan=3, padx=0, pady=10, sticky="w")
        if self.config_manager.get_setting("processing_parameters.social_media.delete_original_after_processing", False): self.delete_original_checkbox.select()
        else: self.delete_original_checkbox.deselect()
        row_idx += 1

        # --- Global Progress Bar and Button ---
        # These are outside the scrollable frame
        self.progress_label = customtkinter.CTkLabel(self, text="Progress: 0%")
        self.progress_label.grid(row=2, column=0, padx=20, pady=(10, 5), sticky="w")
        self.progress_bar = customtkinter.CTkProgressBar(self)
        self.progress_bar.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="ew")
        self.progress_bar.set(0)

        self.process_button = customtkinter.CTkButton(self, text="Start Processing", command=self._start_processing)
        self.process_button.grid(row=4, column=0, padx=20, pady=20, sticky="ew")

        self._update_ui_state(False) # Initial state: disable process button until files are chosen

    def _update_entry_text(self, entry_widget, text: str):
        """Helper to update a readonly CTkEntry."""
        entry_widget.configure(state="normal")
        entry_widget.delete(0, customtkinter.END)
        entry_widget.insert(0, text)
        entry_widget.configure(state="readonly")

    def _browse_input_file(self):
        """Opens a file dialog to select the input video file."""
        filetypes = [("Video files", "*.mp4 *.mov *.avi *.mkv *.webm *.mpg"),
                     ("All files", "*.*")]
        file_path_str = filedialog.askopenfilename(title="Select Input Video File", filetypes=filetypes)
        if file_path_str:
            self.input_file_path = Path(file_path_str)
            self._update_entry_text(self.input_entry, str(self.input_file_path))
            self.logger.info(f"Input video file selected: {self.input_file_path}")
            self.app_instance.set_status(f"Selected: {self.input_file_path.name}")
            self._suggest_output_file_path()
            self._update_ui_state(True) # Enable process button if input selected
        else:
            self.logger.info("Input video file selection cancelled.")
            self.app_instance.set_status("Input video file selection cancelled.")
            self._update_ui_state(False) # Disable if input cancelled

    def _suggest_output_file_path(self):
        """
        Suggests an output file path based on the input file and default output directory.
        """
        if self.input_file_path:
            default_output_dir_str = self.config_manager.get_setting("output_directories.default_video_output")
            default_output_dir = Path(default_output_dir_str)
            default_output_dir.mkdir(parents=True, exist_ok=True) # Ensure default output dir exists

            output_file_name = f"{self.input_file_path.stem}_social.mp4" # Default to MP4
            self.output_file_path = default_output_dir / output_file_name

            self._update_entry_text(self.output_entry, str(self.output_file_path))
            self.logger.info(f"Suggested output path: {self.output_file_path}")
        else:
            self._update_entry_text(self.output_entry, "Select an input file first.")
            self.output_file_path = None

    def _browse_output_file(self):
        """Opens a file dialog to select/save the output video file."""
        if not self.input_file_path:
            messagebox.showwarning("No Input File", "Please select an input video file first.")
            self.logger.warning("Output file browse cancelled: No input file selected.")
            return

        initial_dir = self.config_manager.get_setting("output_directories.default_video_output")
        initial_filename = f"{self.input_file_path.stem}_social.mp4"

        file_path_str = filedialog.asksaveasfilename(
            title="Save Processed Video As",
            initialdir=initial_dir,
            initialfile=initial_filename,
            filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")], # Suggest MP4 by default
            defaultextension=".mp4"
        )
        if file_path_str:
            self.output_file_path = Path(file_path_str)
            # Ensure the output has a .mp4 extension
            if self.output_file_path.suffix.lower() not in ['.mp4']:
                self.output_file_path = self.output_file_path.with_suffix('.mp4')
                self.logger.warning(f"Output file extension changed to '.mp4' for compatibility: {self.output_file_path}")
            
            self._update_entry_text(self.output_entry, str(self.output_file_path))
            self.logger.info(f"Output video file selected: {self.output_file_path}")
            self.app_instance.set_status(f"Output will be: {self.output_file_path.name}")
        else:
            self.logger.info("Output video file selection cancelled.")
            self.app_instance.set_status("Output video file selection cancelled.")

    def _update_config_setting(self, setting_key: str):
        """Returns a callable to update a boolean config setting based on checkbox state."""
        def callback():
            is_checked = getattr(self, f"{setting_key}_checkbox").get() == 1
            self.config_manager.set_setting(f"processing_parameters.social_media.{setting_key}", is_checked)
            self.logger.debug(f"Config setting '{setting_key}' updated to: {is_checked}")
            self.app_instance.set_status(f"{setting_key.replace('_', ' ').title()}: {is_checked}")
            # Special handling for subtitle options visibility
            if setting_key == "generate_subtitles":
                self._toggle_subtitle_options()
        return callback

    def _update_config_setting_with_value(self, setting_key: str):
        """Returns a callable to update a config setting with a combobox value."""
        def callback(value: str):
            self.config_manager.set_setting(f"processing_parameters.social_media.{setting_key}", value)
            self.logger.debug(f"Config setting '{setting_key}' updated to: {value}")
            self.app_instance.set_status(f"{setting_key.replace('_', ' ').title()}: {value}")
        return callback
    
    def _update_numeric_config_setting(self, setting_key: str, value_type: type, event=None):
        """Updates a numeric config setting from an entry widget."""
        entry_widget = getattr(self, f"{setting_key}_entry")
        try:
            value = value_type(entry_widget.get())
            if value_type == int and value < 0:
                raise ValueError("Value must be non-negative.")
            self.config_manager.set_setting(f"processing_parameters.social_media.{setting_key}", value)
            self.logger.debug(f"Config setting '{setting_key}' updated to: {value}")
            self.app_instance.set_status(f"{setting_key.replace('_', ' ').title()}: {value}")
        except ValueError:
            messagebox.showerror("Input Error", f"Invalid input for {setting_key.replace('_', ' ')}. Please enter a valid {value_type.__name__}.")
            entry_widget.delete(0, customtkinter.END)
            entry_widget.insert(0, str(self.config_manager.get_setting(f"processing_parameters.social_media.{setting_key}")))
            self.logger.warning(f"Invalid input for {setting_key}.")
            self.app_instance.set_status(f"Invalid {setting_key.replace('_', ' ')}.", level="warning")

    def _update_config_setting_from_entry(self, setting_key: str, event=None):
        """Updates a string config setting from an entry widget (e.g., color hex)."""
        entry_widget = getattr(self, f"{setting_key}_entry")
        value = entry_widget.get()
        self.config_manager.set_setting(f"processing_parameters.social_media.{setting_key}", value)
        self.logger.debug(f"Config setting '{setting_key}' updated to: {value}")
        self.app_instance.set_status(f"{setting_key.replace('_', ' ').title()}: {value}")

    def _update_target_resolution(self, selected_option: str):
        """Updates the target social media resolution in config."""
        resolution_map = {
            "1080x1920 (Vertical)": "1080x1920",
            "1920x1080 (Horizontal)": "1920x1080",
            "1080x1080 (Square)": "1080x1080",
            "720x1280 (Vertical HD)": "720x1280"
        }
        actual_resolution = resolution_map.get(selected_option, "1080x1920")
        self.config_manager.set_setting("processing_parameters.social_media.target_social_media_resolution", actual_resolution)
        self.logger.debug(f"Target resolution set to: {actual_resolution}")
        self.app_instance.set_status(f"Target Resolution: {selected_option}")


    def _update_subtitle_position(self, value: float):
        """Updates the subtitle vertical position display and config."""
        rounded_value = round(value, 2)
        self.subtitle_position_value_label.configure(text=f"{int(rounded_value * 100)}%")
        self.config_manager.set_setting("processing_parameters.social_media.subtitle_font_position_y", rounded_value)
        self.logger.debug(f"Subtitle position set to: {rounded_value}")
        self.app_instance.set_status(f"Subtitle Position: {int(rounded_value * 100)}%")

    def _toggle_subtitle_options(self):
        """Toggles the visibility and state of subtitle-related controls."""
        is_checked = self.generate_subtitles_checkbox.get() == 1
        widgets = [
            self.subtitle_font_label, self.subtitle_font_combobox,
            self.subtitle_size_label, self.subtitle_size_entry,
            self.subtitle_color_label, self.subtitle_color_entry,
            self.subtitle_stroke_width_label, self.subtitle_stroke_width_entry,
            self.subtitle_stroke_color_label, self.subtitle_stroke_color_entry,
            self.subtitle_position_label, self.subtitle_position_slider, self.subtitle_position_value_label,
            self.subtitle_words_per_line_label, self.subtitle_words_per_line_entry
        ]
        
        for widget in widgets:
            if is_checked:
                widget.grid()
                if isinstance(widget, (customtkinter.CTkEntry, customtkinter.CTkComboBox, customtkinter.CTkSlider)):
                    widget.configure(state="normal")
            else:
                widget.grid_remove()
                if isinstance(widget, (customtkinter.CTkEntry, customtkinter.CTkComboBox, customtkinter.CTkSlider)):
                    widget.configure(state="disabled")
        
        # Also update config for 'generate_subtitles' as this is the primary toggle
        self.config_manager.set_setting("processing_parameters.social_media.generate_subtitles", is_checked)
        self.logger.info(f"Generate subtitles setting updated to: {is_checked}. Subtitle options visibility toggled.")


    # --- Overlay Management ---
    def _add_text_overlay(self):
        """Opens a dialog to add a new text overlay."""
        dialog = customtkinter.CTkInputDialog(text="Enter text for overlay:", title="Add Text Overlay")
        text_input = dialog.get_input()
        if text_input:
            # For simplicity, default values for new overlays. User can't edit position/duration in this simple dialog.
            # A more advanced UI would allow full editing of overlay properties.
            new_overlay = {
                "type": "text",
                "text": text_input,
                "font_size": 50,
                "color": "#FFFFFF",
                "font_name": "Arial", # Could be configurable
                "stroke_color": "#000000",
                "stroke_width": 2,
                "position_x": "center",
                "position_y": "center",
                "start_time": 0, # Default to start of video
                "end_time": 99999 # Default to end of video (large number)
            }
            self.current_overlays.append(new_overlay)
            self.logger.info(f"Added text overlay: '{text_input}'")
            self.app_instance.set_status(f"Text overlay added: '{text_input}'")
            self._refresh_overlays_display()
        else:
            self.logger.info("Adding text overlay cancelled.")

    def _add_image_overlay(self):
        """Opens a file dialog to select an image for overlay."""
        filetypes = [("Image files", "*.png *.jpg *.jpeg *.gif"),
                     ("All files", "*.*")]
        image_path_str = filedialog.askopenfilename(title="Select Image for Overlay", filetypes=filetypes)
        if image_path_str:
            new_overlay = {
                "type": "image",
                "image_path": image_path_str,
                "height": 100, # Default height, can be configurable
                "position_x": "center",
                "position_y": "center",
                "start_time": 0, # Default to start of video
                "end_time": 99999 # Default to end of video (large number)
            }
            self.current_overlays.append(new_overlay)
            self.logger.info(f"Added image overlay: '{image_path_str}'")
            self.app_instance.set_status(f"Image overlay added: '{Path(image_path_str).name}'")
            self._refresh_overlays_display()
        else:
            self.logger.info("Adding image overlay cancelled.")

    def _remove_overlay(self, index: int):
        """Removes an overlay from the list by index."""
        if 0 <= index < len(self.current_overlays):
            removed_overlay = self.current_overlays.pop(index)
            self.logger.info(f"Removed overlay at index {index}: {removed_overlay.get('text') or removed_overlay.get('image_path')}")
            self.app_instance.set_status("Overlay removed.")
            self._refresh_overlays_display()
        else:
            self.logger.warning(f"Attempted to remove non-existent overlay at index {index}.")

    def _refresh_overlays_display(self):
        """Clears and re-populates the overlays display frame."""
        for widget in self.overlays_display_frame.winfo_children():
            widget.destroy()

        if not self.current_overlays:
            no_overlays_label = customtkinter.CTkLabel(self.overlays_display_frame, text="No overlays added yet.")
            no_overlays_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
            return

        for i, overlay in enumerate(self.current_overlays):
            overlay_frame = customtkinter.CTkFrame(self.overlays_display_frame)
            overlay_frame.grid(row=i, column=0, padx=5, pady=5, sticky="ew")
            overlay_frame.grid_columnconfigure(0, weight=1) # Description
            overlay_frame.grid_columnconfigure(1, weight=0) # Remove button

            display_text = ""
            if overlay["type"] == "text":
                display_text = f"Text: '{overlay['text']}'"
            elif overlay["type"] == "image":
                display_text = f"Image: '{Path(overlay['image_path']).name}'"
            
            overlay_label = customtkinter.CTkLabel(overlay_frame, text=display_text, wraplength=300)
            overlay_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

            remove_button = customtkinter.CTkButton(overlay_frame, text="X", width=30, height=24, fg_color="red", hover_color="darkred", command=lambda idx=i: self._remove_overlay(idx))
            remove_button.grid(row=0, column=1, padx=5, pady=5, sticky="e")

    # --- Progress and UI State ---
    def _update_progress_bar(self, progress_percentage: int, message: str):
        """
        Callback from SocialMediaVideoProcessor to update the GUI progress bar and label.
        Schedules the actual GUI update on the main thread.
        """
        if self.master:
            self.master.after(1, self.__update_progress_gui, progress_percentage, message)
        else:
            self.logger.error("Attempted to update GUI on a None master object in _update_progress_bar.")

    def __update_progress_gui(self, progress_percentage: int, message: str):
        """Actual GUI update function, called via master.after. Runs on main thread."""
        self.progress_bar.set(progress_percentage / 100.0) # CTkProgressBar expects float from 0.0 to 1.0
        self.progress_label.configure(text=f"Progress: {progress_percentage}% - {message}")
        self.app_instance.set_status(f"Social Media Processing: {progress_percentage}% - {message}")
        self.master.update_idletasks() # Force GUI update

    def _update_ui_state(self, enable_process_button: bool):
        """Sets the state of interactive widgets based on processing status."""
        is_processing = self.processor.is_processing()

        self.process_button.configure(state="disabled")
        if enable_process_button and not is_processing:
            self.process_button.configure(state="normal")

        browse_state = "disabled" if is_processing else "normal"
        self.input_button.configure(state=browse_state)
        self.output_button.configure(state=browse_state)
        self.auto_crop_checkbox.configure(state=browse_state)
        self.target_res_combobox.configure(state=browse_state)
        self.generate_subtitles_checkbox.configure(state=browse_state)
        self.apply_video_enhancement_checkbox.configure(state=browse_state)
        self.apply_audio_enhancement_checkbox.configure(state=browse_state)
        self.add_text_overlay_button.configure(state=browse_state)
        self.add_image_overlay_button.configure(state=browse_state)
        self.delete_original_checkbox.configure(state=browse_state)

        # Disable/enable individual subtitle controls based on generate_subtitles_checkbox state
        # and overall processing state
        subtitle_widgets = [
            self.subtitle_font_combobox, self.subtitle_size_entry, self.subtitle_color_entry,
            self.subtitle_stroke_width_entry, self.subtitle_stroke_color_entry,
            self.subtitle_position_slider, self.subtitle_words_per_line_entry
        ]
        
        sub_controls_state = "normal" if self.generate_subtitles_checkbox.get() == 1 and not is_processing else "disabled"
        for widget in subtitle_widgets:
            widget.configure(state=sub_controls_state)
        
        # Overlays remove buttons
        for child_frame in self.overlays_display_frame.winfo_children():
            remove_btn = child_frame.grid_slaves(column=1, row=0) # Get the 'X' button
            if remove_btn:
                remove_btn[0].configure(state=browse_state)


    def _start_processing(self):
        """
        Initiates the social media video processing in a separate thread
        to keep the GUI responsive.
        """
        if not self.input_file_path or not self.input_file_path.is_file():
            messagebox.showerror("Input Error", "Please select a valid input video file.")
            self.logger.warning("Processing attempt failed: No valid input file selected.")
            self.app_instance.set_status("Processing failed: No input.", level="warning")
            return

        if not self.output_file_path:
            messagebox.showerror("Output Error", "Please specify an output video file path.")
            self.logger.warning("Processing attempt failed: No output file specified.")
            self.app_instance.set_status("Processing failed: No output path.", level="warning")
            return

        if self.processor.is_processing():
            self.app_instance.set_status("Social media video processing already in progress.", level="warning")
            return

        self._update_ui_state(False) # Disable UI during processing
        self.progress_bar.set(0)
        self.progress_label.configure(text="Progress: 0%")
        self.app_instance.set_status("Social media video processing started...", level="info")
        self.logger.info("Social media video processing initiated via GUI.")

        # Gather all processing options from UI and config
        processing_options = {
            "auto_crop": self.auto_crop_checkbox.get() == 1,
            "target_social_media_resolution": self.config_manager.get_setting("processing_parameters.social_media.target_social_media_resolution"),
            "generate_subtitles": self.generate_subtitles_checkbox.get() == 1,
            "subtitle_font_size": int(self.subtitle_size_entry.get()),
            "default_subtitle_font_name": self.subtitle_font_combobox.get(),
            "subtitle_color": self.subtitle_color_entry.get(),
            "subtitle_stroke_width": int(self.subtitle_stroke_width_entry.get()),
            "subtitle_stroke_color": self.subtitle_stroke_color_entry.get(),
            "subtitle_font_position_y": self.subtitle_position_slider.get(),
            "subtitle_words_per_line": int(self.subtitle_words_per_line_entry.get()),
            "apply_auto_video_enhancement": self.apply_video_enhancement_checkbox.get() == 1,
            "apply_auto_audio_enhancement": self.apply_audio_enhancement_checkbox.get() == 1,
            "overlays": self.current_overlays, # Pass the list of overlays
            "delete_original_after_processing": self.delete_original_checkbox.get() == 1
            # Other audio enhancement parameters for AudioProcessor are read directly from its config path
            # via AudioProcessor itself, as we're reusing it.
        }
        
        # Run processing in a separate thread
        self.processing_thread = threading.Thread(
            target=self._run_processing_task,
            args=(self.input_file_path, self.output_file_path, processing_options)
        )
        self.processing_thread.start()

    def _run_processing_task(self, input_path: Path, output_path: Path, processing_options: Dict[str, Any]):
        """
        The actual social media video processing task to be run in a separate thread.
        Handles calling the SocialMediaVideoProcessor and updating the GUI with results.
        """
        success, message = self.processor.process_social_media_video(
            input_filepath=input_path,
            output_filepath=output_path,
            processing_options=processing_options,
            progress_callback_func=self._update_progress_bar # Pass our GUI update method
        )

        # After processing (success or failure), schedule result handling on the main thread
        if self.master:
            self.master.after(0, self._handle_processing_result, success, message, processing_options)
        else:
            self.logger.error("Master is None during _run_processing_task completion. Cannot update GUI.")

    def _handle_processing_result(self, success: bool, message: str, processing_options: Dict[str, Any]):
        """
        Handles the result of the social media video processing, updating status and re-enabling UI.
        Called on the main thread after processing completes.
        """
        if success:
            messagebox.showinfo("Processing Success", f"Social media video processed successfully!\nOutput: {message.split(': ')[-1]}")
            self.logger.info(f"Social media video processing UI completed successfully: {message}")
            self.progress_label.configure(text="Processing Complete!")
            self.progress_bar.set(1.0) # Ensure it shows 100%
            
            # Log to history
            self.app_instance.history_manager.log_task(
                "Social Media Post Creation",
                self.input_file_path,
                self.output_file_path,
                "Completed",
                message,
                processing_options # Log all processing options used
            )
        else:
            messagebox.showerror("Processing Failed", f"Social media post creation failed:\n{message}")
            self.logger.error(f"Social media video processing UI failed: {message}")
            self.progress_label.configure(text="Processing Failed!")
            self.progress_bar.set(0) # Reset progress on failure

            # Log to history
            self.app_instance.history_manager.log_task(
                "Social Media Post Creation",
                self.input_file_path,
                self.output_file_path,
                "Failed",
                message,
                processing_options # Log all processing options used
            )

        self._update_ui_state(True) # Re-enable UI elements
        self.app_instance.set_status(message, level="info" if success else "error")