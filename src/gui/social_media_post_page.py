import customtkinter
from tkinter import filedialog, messagebox
import threading
from pathlib import Path
import logging
import json # For handling overlay data

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
        self.font_manager = get_application_font_manager()
        self.processor = SocialMediaVideoProcessor() # Instantiate the backend logic

        self.input_file_path = None
        self.output_file_path = None
        self.current_overlays = [] # List to store overlay items for the current session

        self.logger.info("Initializing SocialMediaPostPage UI.")

        # Configure grid layout for this page
        self.grid_columnconfigure(0, weight=1) # Main content column
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1) # Scrollable frame for parameters
        self.grid_rowconfigure(2, weight=0) # Progress and button row

        # Title
        self.title_label = customtkinter.CTkLabel(self, text="Social Media Post Creator", font=customtkinter.CTkFont(size=24, weight="bold"))
        self.title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

        # Scrollable Frame for Parameters (to handle many widgets)
        self.scrollable_frame = customtkinter.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self.scrollable_frame.grid_columnconfigure(0, weight=0) # Labels
        self.scrollable_frame.grid_columnconfigure(1, weight=1) # Entries/Controls
        self.scrollable_frame.grid_columnconfigure(2, weight=0) # Buttons for browse/color

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

        # --- Subtitle Customization Section ---
        self.subtitle_section_label = customtkinter.CTkLabel(self.scrollable_frame, text="Subtitle Settings", font=customtkinter.CTkFont(size=18, weight="bold"))
        self.subtitle_section_label.grid(row=row_idx, column=0, columnspan=3, padx=0, pady=(30, 10), sticky="ew")
        row_idx += 1

        # Font Selection
        self.font_label = customtkinter.CTkLabel(self.scrollable_frame, text="Font:")
        self.font_label.grid(row=row_idx, column=0, padx=(0, 10), pady=5, sticky="w")
        self.font_optionmenu = customtkinter.CTkOptionMenu(self.scrollable_frame, values=["Loading..."], command=self._update_subtitle_font)
        self.font_optionmenu.grid(row=row_idx, column=1, padx=10, pady=5, sticky="ew")
        self.download_font_button = customtkinter.CTkButton(self.scrollable_frame, text="Download Selected Font", command=self._download_selected_font)
        self.download_font_button.grid(row=row_idx, column=2, padx=(10,0), pady=5, sticky="e")
        row_idx += 1
        # Populate fonts after UI is built
        self.master.after(100, self._populate_font_options) # Schedule after init to allow CTk to be ready

        # Font Size
        self.font_size_label = customtkinter.CTkLabel(self.scrollable_frame, text="Font Size:")
        self.font_size_label.grid(row=row_idx, column=0, padx=(0, 10), pady=5, sticky="w")
        self.font_size_slider = customtkinter.CTkSlider(self.scrollable_frame, from_=20, to=100, number_of_steps=80, command=self._update_subtitle_font_size)
        self.font_size_slider.grid(row=row_idx, column=1, padx=10, pady=5, sticky="ew")
        self.font_size_value_label = customtkinter.CTkLabel(self.scrollable_frame, text="60")
        self.font_size_value_label.grid(row=row_idx, column=2, padx=(10, 0), pady=5, sticky="e")
        initial_font_size = self.config_manager.get_setting("processing_parameters.social_media_post_processing.default_subtitle_font_size", 60)
        self.font_size_slider.set(initial_font_size)
        self._update_subtitle_font_size(initial_font_size)
        row_idx += 1

        # Font Color
        self.font_color_label = customtkinter.CTkLabel(self.scrollable_frame, text="Font Color:")
        self.font_color_label.grid(row=row_idx, column=0, padx=(0, 10), pady=5, sticky="w")
        self.font_color_display_frame = customtkinter.CTkFrame(self.scrollable_frame, width=80, height=24, corner_radius=5)
        self.font_color_display_frame.grid(row=row_idx, column=1, padx=10, pady=5, sticky="w")
        self.font_color_display_frame.grid_propagate(False)
        self.pick_font_color_button = customtkinter.CTkButton(self.scrollable_frame, text="Pick Color", command=self._pick_subtitle_font_color)
        self.pick_font_color_button.grid(row=row_idx, column=2, padx=(10, 0), pady=5, sticky="e")
        initial_font_color = self.config_manager.get_setting("processing_parameters.social_media_post_processing.default_subtitle_color", "#FFFFFF")
        self._update_color_display(self.font_color_display_frame, initial_font_color)
        row_idx += 1

        # Stroke Color
        self.stroke_color_label = customtkinter.CTkLabel(self.scrollable_frame, text="Stroke Color:")
        self.stroke_color_label.grid(row=row_idx, column=0, padx=(0, 10), pady=5, sticky="w")
        self.stroke_color_display_frame = customtkinter.CTkFrame(self.scrollable_frame, width=80, height=24, corner_radius=5)
        self.stroke_color_display_frame.grid(row=row_idx, column=1, padx=10, pady=5, sticky="w")
        self.stroke_color_display_frame.grid_propagate(False)
        self.pick_stroke_color_button = customtkinter.CTkButton(self.scrollable_frame, text="Pick Color", command=self._pick_subtitle_stroke_color)
        self.pick_stroke_color_button.grid(row=row_idx, column=2, padx=(10, 0), pady=5, sticky="e")
        initial_stroke_color = self.config_manager.get_setting("processing_parameters.social_media_post_processing.default_subtitle_stroke_color", "#000000")
        self._update_color_display(self.stroke_color_display_frame, initial_stroke_color)
        row_idx += 1

        # Stroke Width
        self.stroke_width_label = customtkinter.CTkLabel(self.scrollable_frame, text="Stroke Width:")
        self.stroke_width_label.grid(row=row_idx, column=0, padx=(0, 10), pady=5, sticky="w")
        self.stroke_width_slider = customtkinter.CTkSlider(self.scrollable_frame, from_=0, to=5, number_of_steps=10, command=self._update_subtitle_stroke_width)
        self.stroke_width_slider.grid(row=row_idx, column=1, padx=10, pady=5, sticky="ew")
        self.stroke_width_value_label = customtkinter.CTkLabel(self.scrollable_frame, text="2")
        self.stroke_width_value_label.grid(row=row_idx, column=2, padx=(10, 0), pady=5, sticky="e")
        initial_stroke_width = self.config_manager.get_setting("processing_parameters.social_media_post_processing.default_subtitle_stroke_width", 2)
        self.stroke_width_slider.set(initial_stroke_width)
        self._update_subtitle_stroke_width(initial_stroke_width)
        row_idx += 1

        # Subtitle Position (Y)
        self.subtitle_pos_label = customtkinter.CTkLabel(self.scrollable_frame, text="Subtitle Vertical Pos.:")
        self.subtitle_pos_label.grid(row=row_idx, column=0, padx=(0, 10), pady=5, sticky="w")
        self.subtitle_pos_slider = customtkinter.CTkSlider(self.scrollable_frame, from_=0.0, to=1.0, number_of_steps=100, command=self._update_subtitle_position_y)
        self.subtitle_pos_slider.grid(row=row_idx, column=1, padx=10, pady=5, sticky="ew")
        self.subtitle_pos_value_label = customtkinter.CTkLabel(self.scrollable_frame, text="0.8")
        self.subtitle_pos_value_label.grid(row=row_idx, column=2, padx=(10, 0), pady=5, sticky="e")
        initial_pos_y = self.config_manager.get_setting("processing_parameters.social_media_post_processing.default_subtitle_position_y", 0.8)
        self.subtitle_pos_slider.set(initial_pos_y)
        self._update_subtitle_position_y(initial_pos_y)
        row_idx += 1

        # --- General Processing Options ---
        self.general_options_label = customtkinter.CTkLabel(self.scrollable_frame, text="General Options", font=customtkinter.CTkFont(size=18, weight="bold"))
        self.general_options_label.grid(row=row_idx, column=0, columnspan=3, padx=0, pady=(30, 10), sticky="ew")
        row_idx += 1

        self.remove_silent_checkbox = customtkinter.CTkCheckBox(self.scrollable_frame, text="Automatically remove silent segments", command=self._update_remove_silent_setting)
        self.remove_silent_checkbox.grid(row=row_idx, column=0, columnspan=3, padx=(0,10), pady=5, sticky="w")
        initial_remove_silent = self.config_manager.get_setting("processing_parameters.social_media_post_processing.auto_remove_silent_segments", True)
        if initial_remove_silent: self.remove_silent_checkbox.select()
        else: self.remove_silent_checkbox.deselect()
        row_idx += 1

        self.delete_original_checkbox = customtkinter.CTkCheckBox(self.scrollable_frame, text="Delete original file after successful processing", command=self._update_delete_original_setting)
        self.delete_original_checkbox.grid(row=row_idx, column=0, columnspan=3, padx=(0,10), pady=5, sticky="w")
        initial_delete_original = self.config_manager.get_setting("processing_parameters.social_media_post_processing.delete_original_after_processing", False)
        if initial_delete_original: self.delete_original_checkbox.select()
        else: self.delete_original_checkbox.deselect()
        row_idx += 1
        
        # --- Overlays Section ---
        self.overlays_section_label = customtkinter.CTkLabel(self.scrollable_frame, text="Overlays (Images, Text, Audio)", font=customtkinter.CTkFont(size=18, weight="bold"))
        self.overlays_section_label.grid(row=row_idx, column=0, columnspan=3, padx=0, pady=(30, 10), sticky="ew")
        row_idx += 1

        self.overlay_listbox = customtkinter.CTkScrollableFrame(self.scrollable_frame, label_text="Current Overlays", height=150)
        self.overlay_listbox.grid(row=row_idx, column=0, columnspan=3, padx=(0,10), pady=10, sticky="ew")
        self.overlay_listbox.grid_columnconfigure(0, weight=1)
        self._populate_overlay_listbox() # Initial population
        row_idx += 1

        self.add_overlay_frame = customtkinter.CTkFrame(self.scrollable_frame, fg_color="transparent")
        self.add_overlay_frame.grid(row=row_idx, column=0, columnspan=3, padx=0, pady=5, sticky="ew")
        self.add_overlay_frame.grid_columnconfigure((0,1,2,3), weight=1)

        self.add_image_button = customtkinter.CTkButton(self.add_overlay_frame, text="Add Image", command=self._add_image_overlay)
        self.add_image_button.grid(row=0, column=0, padx=(0,5), pady=5, sticky="ew")
        self.add_text_button = customtkinter.CTkButton(self.add_overlay_frame, text="Add Text", command=self._add_text_overlay)
        self.add_text_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.add_audio_button = customtkinter.CTkButton(self.add_overlay_frame, text="Add Audio", command=self._add_audio_overlay)
        self.add_audio_button.grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        self.remove_overlay_button = customtkinter.CTkButton(self.add_overlay_frame, text="Remove Selected", command=self._remove_selected_overlay)
        self.remove_overlay_button.grid(row=0, column=3, padx=(5,0), pady=5, sticky="ew")
        row_idx += 1
        
        # --- Global Progress Bar and Button ---
        # These are outside the scrollable frame
        self.progress_label = customtkinter.CTkLabel(self, text="Progress: 0%")
        self.progress_label.grid(row=2, column=0, padx=20, pady=(10, 5), sticky="w")
        self.progress_bar = customtkinter.CTkProgressBar(self)
        self.progress_bar.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="ew")
        self.progress_bar.set(0)

        self.process_button = customtkinter.CTkButton(self, text="Start Creating Post", command=self._start_processing)
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

            output_file_name = f"{self.input_file_path.stem}_social_post.mp4" # Default to MP4 for compatibility
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
        initial_filename = f"{self.input_file_path.stem}_social_post.mp4"

        file_path_str = filedialog.asksaveasfilename(
            title="Save Social Media Post As",
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

    # --- Subtitle Settings Callbacks ---
    def _populate_font_options(self):
        """Populates the font selection dropdown with available fonts."""
        fonts = ["System Font"] + self.font_manager.get_available_font_names() # Add a generic system font option
        self.font_optionmenu.configure(values=fonts)
        
        # Set default font from config
        default_font_name = self.config_manager.get_setting("processing_parameters.social_media_post_processing.default_subtitle_font_name", "Arial")
        if default_font_name in fonts:
            self.font_optionmenu.set(default_font_name)
        else:
            self.font_optionmenu.set("Arial") # Fallback to a common default
        self.logger.debug(f"Font options populated. Default: {self.font_optionmenu.get()}")

    def _update_subtitle_font(self, selected_font: str):
        """Updates the default subtitle font in configuration."""
        self.config_manager.set_setting("processing_parameters.social_media_post_processing.default_subtitle_font_name", selected_font)
        self.logger.debug(f"Subtitle font set to: {selected_font}")
        self.app_instance.set_status(f"Subtitle font: {selected_font}")

    def _download_selected_font(self):
        """Attempts to download the currently selected font."""
        selected_font_name = self.font_optionmenu.get()
        if selected_font_name == "System Font":
            messagebox.showinfo("Font Info", "No custom font selected for download. 'System Font' uses a font available on your operating system.")
            return

        self.app_instance.set_status(f"Attempting to download {selected_font_name}...", level="info")
        self.logger.info(f"User requested download of font: {selected_font_name}")
        # FontManager's get_font_path handles the download if not local
        font_path = self.font_manager.get_font_path(selected_font_name)
        if font_path and font_path.exists():
            messagebox.showinfo("Download Complete", f"Font '{selected_font_name}' is now available at:\n{font_path}")
            self.app_instance.set_status(f"Font '{selected_font_name}' downloaded.", level="info")
        else:
            messagebox.showerror("Download Failed", f"Could not download font '{selected_font_name}'. Check logs for details.")
            self.app_instance.set_status(f"Font '{selected_font_name}' download failed.", level="error")

    def _update_subtitle_font_size(self, value):
        """Updates the subtitle font size display and config."""
        rounded_value = int(value)
        self.font_size_value_label.configure(text=str(rounded_value))
        self.config_manager.set_setting("processing_parameters.social_media_post_processing.default_subtitle_font_size", rounded_value)
        self.logger.debug(f"Subtitle font size set to: {rounded_value}")
        self.app_instance.set_status(f"Subtitle size: {rounded_value}")

    def _pick_subtitle_font_color(self):
        """Opens a color chooser dialog for font color."""
        current_color = self.config_manager.get_setting("processing_parameters.social_media_post_processing.default_subtitle_color", "#FFFFFF")
        initial_rgb = tuple(int(current_color[i:i+2], 16) for i in (1, 3, 5))
        color_code = filedialog.askcolor(initialcolor=initial_rgb)
        if color_code[1]: # If a color was selected (not cancelled)
            selected_hex_color = color_code[1]
            self.config_manager.set_setting("processing_parameters.social_media_post_processing.default_subtitle_color", selected_hex_color)
            self._update_color_display(self.font_color_display_frame, selected_hex_color)
            self.logger.info(f"Subtitle font color updated to: {selected_hex_color}")
            self.app_instance.set_status(f"Font color: {selected_hex_color}")
        else:
            self.logger.info("Subtitle font color selection cancelled.")

    def _pick_subtitle_stroke_color(self):
        """Opens a color chooser dialog for stroke color."""
        current_color = self.config_manager.get_setting("processing_parameters.social_media_post_processing.default_subtitle_stroke_color", "#000000")
        initial_rgb = tuple(int(current_color[i:i+2], 16) for i in (1, 3, 5))
        color_code = filedialog.askcolor(initialcolor=initial_rgb)
        if color_code[1]:
            selected_hex_color = color_code[1]
            self.config_manager.set_setting("processing_parameters.social_media_post_processing.default_subtitle_stroke_color", selected_hex_color)
            self._update_color_display(self.stroke_color_display_frame, selected_hex_color)
            self.logger.info(f"Subtitle stroke color updated to: {selected_hex_color}")
            self.app_instance.set_status(f"Stroke color: {selected_hex_color}")
        else:
            self.logger.info("Subtitle stroke color selection cancelled.")

    def _update_subtitle_stroke_width(self, value):
        """Updates the subtitle stroke width display and config."""
        rounded_value = int(value)
        self.stroke_width_value_label.configure(text=str(rounded_value))
        self.config_manager.set_setting("processing_parameters.social_media_post_processing.default_subtitle_stroke_width", rounded_value)
        self.logger.debug(f"Subtitle stroke width set to: {rounded_value}")
        self.app_instance.set_status(f"Stroke width: {rounded_value}")

    def _update_subtitle_position_y(self, value):
        """Updates the subtitle vertical position display and config."""
        rounded_value = round(value, 2)
        self.subtitle_pos_value_label.configure(text=f"{rounded_value:.2f}")
        self.config_manager.set_setting("processing_parameters.social_media_post_processing.default_subtitle_position_y", rounded_value)
        self.logger.debug(f"Subtitle vertical position set to: {rounded_value}")
        self.app_instance.set_status(f"Subtitle Y-pos: {rounded_value}")

    def _update_color_display(self, frame_widget, hex_color: str):
        """Updates the background color of a display frame."""
        frame_widget.configure(fg_color=hex_color)

    # --- General Options Callbacks ---
    def _update_remove_silent_setting(self):
        """Updates the 'auto_remove_silent_segments' setting in the config."""
        is_checked = self.remove_silent_checkbox.get() == 1
        self.config_manager.set_setting("processing_parameters.social_media_post_processing.auto_remove_silent_segments", is_checked)
        self.logger.info(f"Auto remove silent segments setting updated to: {is_checked}")
        self.app_instance.set_status(f"Remove silent segments: {is_checked}")

    def _update_delete_original_setting(self):
        """Updates the 'delete_original_after_processing' setting in the config."""
        is_checked = self.delete_original_checkbox.get() == 1
        self.config_manager.set_setting("processing_parameters.social_media_post_processing.delete_original_after_processing", is_checked)
        self.logger.info(f"Delete original (social media) setting updated to: {is_checked}")
        self.app_instance.set_status(f"Delete original (social media): {is_checked}")

    # --- Overlay Management Callbacks ---
    def _populate_overlay_listbox(self):
        """Populates the overlay listbox with current overlays."""
        # Clear existing labels
        for widget in self.overlay_listbox.winfo_children():
            widget.destroy()

        if not self.current_overlays:
            customtkinter.CTkLabel(self.overlay_listbox, text="No overlays added yet.").grid(row=0, column=0, padx=10, pady=5, sticky="w")
            return

        for i, overlay_item in enumerate(self.current_overlays):
            item_type = overlay_item['type'].capitalize()
            item_text = ""
            if item_type == "Image":
                item_text = f"{item_type}: {Path(overlay_item['path']).name}"
            elif item_type == "Text":
                item_text = f"{item_type}: \"{overlay_item['text'][:30]}...\""
            elif item_type == "Audio":
                item_text = f"{item_type}: {Path(overlay_item['path']).name}"
            
            display_text = f"[{i+1}] {item_text} ({overlay_item.get('start',0):.1f}s - {overlay_item.get('end', 'End'):.1f}s)"
            
            # Use a button or clickable label to allow selection/editing
            item_button = customtkinter.CTkButton(self.overlay_listbox, text=display_text, 
                                                  command=lambda idx=i: self._select_overlay_for_editing(idx),
                                                  fg_color="transparent", text_color_disabled="gray",
                                                  hover_color=customtkinter.ThemeManager.theme["CTkButton"]["hover_color"])
            item_button.grid(row=i, column=0, padx=5, pady=2, sticky="ew")
        self.overlay_listbox.update_idletasks() # Refresh scrollable frame

    def _select_overlay_for_editing(self, index: int):
        """Selects an overlay in the listbox and can potentially open an edit dialog."""
        self.logger.info(f"Overlay {index} selected for editing: {self.current_overlays[index]}")
        messagebox.showinfo("Edit Overlay", f"Editing functionality for overlay '{self.current_overlays[index]['type']}' not yet implemented in detail. Displaying info:\n\n{json.dumps(self.current_overlays[index], indent=2)}")
        # Future: Open a new CTkTopLevel window for editing overlay properties

    def _add_image_overlay(self):
        """Opens a dialog to add an image overlay."""
        filetypes = [("Image files", "*.png *.jpg *.jpeg *.webp"), ("All files", "*.*")]
        img_path_str = filedialog.askopenfilename(title="Select Image Overlay", filetypes=filetypes)
        if img_path_str:
            # Prompt for start/end time and optional scale/position
            # For simplicity, we'll use a basic input for now, but a custom dialog would be better.
            start_time_str = customtkinter.CTkInputDialog(text="Enter start time (seconds):", title="Overlay Start Time").get_input()
            end_time_str = customtkinter.CTkInputDialog(text="Enter end time (seconds) (leave empty for end of video):", title="Overlay End Time").get_input()
            
            try:
                start = float(start_time_str)
                end = float(end_time_str) if end_time_str else None
                if end is not None and end <= start:
                    raise ValueError("End time must be greater than start time.")
            except (ValueError, TypeError):
                messagebox.showerror("Input Error", "Invalid start/end time. Please enter numbers.")
                self.logger.warning("Invalid time input for image overlay.")
                return

            overlay_item = {
                'type': 'image',
                'path': img_path_str,
                'start': start,
                'end': end,
                'position': ('center', 'center'), # Default position
                'scale': 0.3 # Default scale
            }
            self.current_overlays.append(overlay_item)
            self._populate_overlay_listbox()
            self.logger.info(f"Added image overlay: {overlay_item}")
            self.app_instance.set_status("Image overlay added.")
        else:
            self.logger.info("Image overlay selection cancelled.")

    def _add_text_overlay(self):
        """Opens a dialog to add a text overlay."""
        text = customtkinter.CTkInputDialog(text="Enter text for overlay:", title="Text Overlay Content").get_input()
        if not text:
            self.logger.info("Text overlay creation cancelled (no text entered).")
            return

        start_time_str = customtkinter.CTkInputDialog(text="Enter start time (seconds):", title="Overlay Start Time").get_input()
        end_time_str = customtkinter.CTkInputDialog(text="Enter end time (seconds) (leave empty for end of video):", title="Overlay End Time").get_input()

        try:
            start = float(start_time_str)
            end = float(end_time_str) if end_time_str else None
            if end is not None and end <= start:
                raise ValueError("End time must be greater than start time.")
        except (ValueError, TypeError):
            messagebox.showerror("Input Error", "Invalid start/end time. Please enter numbers.")
            self.logger.warning("Invalid time input for text overlay.")
            return

        overlay_item = {
            'type': 'text',
            'text': text,
            'start': start,
            'end': end,
            'font_name': self.config_manager.get_setting("processing_parameters.social_media_post_processing.default_subtitle_font_name"),
            'font_size': self.config_manager.get_setting("processing_parameters.social_media_post_processing.default_subtitle_font_size"),
            'color': self.config_manager.get_setting("processing_parameters.social_media_post_processing.default_subtitle_color"),
            'position': ('center', 'center') # Default position
        }
        self.current_overlays.append(overlay_item)
        self._populate_overlay_listbox()
        self.logger.info(f"Added text overlay: {overlay_item}")
        self.app_instance.set_status("Text overlay added.")

    def _add_audio_overlay(self):
        """Opens a dialog to add an audio overlay."""
        filetypes = [("Audio files", "*.mp3 *.wav *.aac *.flac"), ("All files", "*.*")]
        audio_path_str = filedialog.askopenfilename(title="Select Audio Overlay", filetypes=filetypes)
        if audio_path_str:
            start_time_str = customtkinter.CTkInputDialog(text="Enter start time (seconds):", title="Overlay Start Time").get_input()
            volume_str = customtkinter.CTkInputDialog(text="Enter volume (0.0 to 1.0, 1.0 for original):", title="Audio Volume").get_input()
            
            try:
                start = float(start_time_str)
                volume = float(volume_str) if volume_str else 1.0
                if not (0.0 <= volume <= 1.0):
                    raise ValueError("Volume must be between 0.0 and 1.0.")
            except (ValueError, TypeError):
                messagebox.showerror("Input Error", "Invalid start time or volume. Please enter numbers.")
                self.logger.warning("Invalid time/volume input for audio overlay.")
                return

            overlay_item = {
                'type': 'audio',
                'path': audio_path_str,
                'start': start,
                'volume': volume
            }
            self.current_overlays.append(overlay_item)
            self._populate_overlay_listbox()
            self.logger.info(f"Added audio overlay: {overlay_item}")
            self.app_instance.set_status("Audio overlay added.")
        else:
            self.logger.info("Audio overlay selection cancelled.")

    def _remove_selected_overlay(self):
        """Removes the selected overlay from the list."""
        # CTkScrollableFrame does not have a direct selection method like Listbox.
        # This requires iterating through its children and determining which one was last clicked,
        # or implementing a custom selection logic.
        # For simplicity, we'll use a basic prompt based on index for now.
        if not self.current_overlays:
            messagebox.showinfo("No Overlays", "There are no overlays to remove.")
            return

        index_str = customtkinter.CTkInputDialog(text="Enter the number of the overlay to remove (e.g., 1 for the first):", title="Remove Overlay").get_input()
        try:
            index_to_remove = int(index_str) - 1 # Convert to 0-based index
            if 0 <= index_to_remove < len(self.current_overlays):
                removed_item = self.current_overlays.pop(index_to_remove)
                self._populate_overlay_listbox()
                self.logger.info(f"Removed overlay: {removed_item}")
                self.app_instance.set_status(f"Overlay {index_to_remove + 1} removed.")
            else:
                messagebox.showwarning("Invalid Index", "Invalid overlay number.")
        except (ValueError, TypeError):
            messagebox.showerror("Input Error", "Please enter a valid number.")
        
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
        self.app_instance.set_status(f"Processing post: {progress_percentage}% - {message}")
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
        self.font_optionmenu.configure(state=browse_state)
        self.download_font_button.configure(state=browse_state)
        self.font_size_slider.configure(state=browse_state)
        self.pick_font_color_button.configure(state=browse_state)
        self.pick_stroke_color_button.configure(state=browse_state)
        self.stroke_width_slider.configure(state=browse_state)
        self.subtitle_pos_slider.configure(state=browse_state)
        self.remove_silent_checkbox.configure(state=browse_state)
        self.delete_original_checkbox.configure(state=browse_state)
        self.add_image_button.configure(state=browse_state)
        self.add_text_button.configure(state=browse_state)
        self.add_audio_button.configure(state=browse_state)
        self.remove_overlay_button.configure(state=browse_state)


    def _start_processing(self):
        """
        Initiates the social media video processing in a separate thread
        to keep the GUI responsive.
        """
        if not self.input_file_path or not self.input_file_path.is_file():
            messagebox.showerror("Input Error", "Please select a valid input video file.")
            self.logger.warning("Post creation attempt failed: No valid input file selected.")
            self.app_instance.set_status("Creation failed: No input.", level="warning")
            return

        if not self.output_file_path:
            messagebox.showerror("Output Error", "Please specify an output video file path.")
            self.logger.warning("Post creation attempt failed: No output file specified.")
            self.app_instance.set_status("Creation failed: No output path.", level="warning")
            return

        if self.processor.is_processing():
            self.app_instance.set_status("Video post creation already in progress.", level="warning")
            return

        self._update_ui_state(False) # Disable UI during processing
        self.progress_bar.set(0)
        self.progress_label.configure(text="Progress: 0%")
        self.app_instance.set_status("Video post creation started...", level="info")
        self.logger.info("Social media video post creation initiated via GUI.")

        # Prepare processing options for the backend processor
        processing_options = {
            'auto_remove_silent_segments': self.remove_silent_checkbox.get() == 1,
            'delete_original_after_processing': self.delete_original_checkbox.get() == 1,
            'overlay_items': self.current_overlays, # Pass the list of configured overlays
            # Additional options from config for backend processing, e.g., enhancement strengths
            # The processor will fetch its own config values, but explicit overrides could be passed here.
        }

        # Run processing in a separate thread
        self.processing_thread = threading.Thread(
            target=self._run_processing_task,
            args=(self.input_file_path, self.output_file_path, processing_options)
        )
        self.processing_thread.start()

    def _run_processing_task(self, input_path: Path, output_path: Path, options: Dict[str, Any]):
        """
        The actual social media video processing task to be run in a separate thread.
        Handles calling the SocialMediaVideoProcessor and updating the GUI with results.
        """
        success, message = self.processor.process_video_for_social_media(
            input_filepath=input_path,
            output_filepath=output_path,
            processing_options=options,
            progress_callback_func=self._update_progress_bar # Pass our GUI update method
        )

        # After processing (success or failure), schedule result handling on the main thread
        if self.master:
            self.master.after(0, self._handle_processing_result, success, message)
        else:
            self.logger.error("Master is None during _run_processing_task completion. Cannot update GUI.")

    def _handle_processing_result(self, success: bool, message: str):
        """
        Handles the result of the social media video processing, updating status and re-enabling UI.
        Called on the main thread after processing completes.
        """
        if success:
            messagebox.showinfo("Post Creation Success", f"Video post created successfully!\nOutput: {message.split(': ')[-1]}")
            self.logger.info(f"Social media video post UI completed successfully: {message}")
            self.progress_label.configure(text="Creation Complete!")
            self.progress_bar.set(1.0) # Ensure it shows 100%
        else:
            messagebox.showerror("Post Creation Failed", f"Video post creation failed:\n{message}")
            self.logger.error(f"Social media video post UI failed: {message}")
            self.progress_label.configure(text="Creation Failed!")
            self.progress_bar.set(0) # Reset progress on failure

        self._update_ui_state(True) # Re-enable UI elements
        self.app_instance.set_status(message, level="info" if success else "error")


# This __main__ block is for isolated testing of the page itself, not the full app.
if __name__ == "__main__":
    import sys
    # Add parent directory to path to allow imports from src.core, src.modules, src.utils
    sys.path.append(str(Path(__file__).parent.parent.parent))

    # Initialize logger and config for standalone test
    from src.core.logger import AppLogger
    from src.core.config_manager import ConfigManager
    # Ensure logs and config directories exist for this isolated test context
    Path("../logs").mkdir(exist_ok=True)
    Path("../config").mkdir(exist_ok=True)
    Path("../assets/fonts").mkdir(parents=True, exist_ok=True) # Ensure fonts directory for FontManager
    Path("../assets/overlays").mkdir(parents=True, exist_ok=True) # Ensure overlays directory for test images

    AppLogger(log_dir="../logs", log_level=logging.DEBUG)
    ConfigManager(config_dir="../config") 
    test_logger = get_application_logger()
    test_logger.info("--- Starting SocialMediaPostPage isolated test ---")


    class DummyApp:
        """A minimal mock for the main App class to satisfy SocialMediaPostPage's dependency."""
        def __init__(self):
            self.logger = get_application_logger()
        def set_status(self, message, level="info"):
            self.logger.info(f"[DummyApp Status] {message}")
            print(f"[DummyApp Status Bar]: {message}") # Print to console for test visibility

    root = customtkinter.CTk()
    root.title("Social Media Post Page Test")
    root.geometry("1000x800") 
    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(0, weight=1)

    dummy_app = DummyApp()
    post_page = SocialMediaPostPage(root, dummy_app)
    post_page.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

    # Automatically set a dummy input file for easier testing if available
    dummy_test_video = Path(__file__).parent.parent.parent / "test_media" / "test_video_for_social_media.mp4"
    if dummy_test_video.exists():
        post_page.input_file_path = dummy_test_video
        post_page._update_entry_text(post_page.input_entry, str(dummy_test_video))
        post_page._suggest_output_file_path()
        post_page._update_ui_state(True) # Enable process button since input is set
        test_logger.info(f"Pre-set dummy input video for testing: {dummy_test_video}")
    else:
        test_logger.warning(f"Dummy test video for social media processing not found at {dummy_test_video}. Please create it or browse manually.")
        
    root.mainloop()
    test_logger.info("--- SocialMediaPostPage isolated test completed ---")
