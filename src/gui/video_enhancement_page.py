import customtkinter
from tkinter import filedialog, messagebox
import threading
from pathlib import Path
import logging
from typing import Dict, Any, Optional # Import Dict, Any, Optional for type hinting

# Import core and module components
from src.core.logger import get_application_logger
from src.core.config_manager import get_application_config
from src.modules.video_enhancer import VideoEnhancer # Import the backend logic

class VideoEnhancementPage(customtkinter.CTkFrame):
    """
    CustomTkinter Frame for Video Enhancement functionality.
    Allows users to select input/output files and apply various video quality enhancements.
    """
    def __init__(self, master, app_instance):
        super().__init__(master, fg_color="transparent")
        self.logger = get_application_logger()
        self.config_manager = get_application_config()
        self.app_instance = app_instance # Reference to the main App class for status updates
        self.video_enhancer = VideoEnhancer() # Instantiate the backend logic

        self.input_file_path: Optional[Path] = None
        self.output_file_path: Optional[Path] = None # Store the full output path suggested/chosen

        self.logger.info("Initializing VideoEnhancementPage UI.")

        # Configure grid layout for this page
        self.grid_columnconfigure(0, weight=1) # Main content column
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1) # Scrollable frame for parameters
        self.grid_rowconfigure(2, weight=0) # Progress and button row

        # Title
        self.title_label = customtkinter.CTkLabel(self, text="Video Enhancement", font=customtkinter.CTkFont(size=24, weight="bold"))
        self.title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

        # Scrollable Frame for Parameters (to handle many widgets)
        self.scrollable_frame = customtkinter.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self.scrollable_frame.grid_columnconfigure(0, weight=0) # Labels
        self.scrollable_frame.grid_columnconfigure(1, weight=1) # Sliders/Entries
        self.scrollable_frame.grid_columnconfigure(2, weight=0) # Value labels/buttons

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

        # --- Enhancement Parameters Section ---
        self.params_label = customtkinter.CTkLabel(self.scrollable_frame, text="Enhancement Parameters", font=customtkinter.CTkFont(size=18, weight="bold"))
        self.params_label.grid(row=row_idx, column=0, columnspan=3, padx=0, pady=(30, 10), sticky="ew")
        row_idx += 1

        # Denoise Strength
        self.denoise_label = customtkinter.CTkLabel(self.scrollable_frame, text="Denoise Strength:")
        self.denoise_label.grid(row=row_idx, column=0, padx=(0, 10), pady=5, sticky="w")
        self.denoise_slider = customtkinter.CTkSlider(self.scrollable_frame, from_=0.0, to=4.0, number_of_steps=40, command=self._update_denoise_strength)
        self.denoise_slider.grid(row=row_idx, column=1, padx=10, pady=5, sticky="ew")
        self.denoise_value_label = customtkinter.CTkLabel(self.scrollable_frame, text="2.0")
        self.denoise_value_label.grid(row=row_idx, column=2, padx=(10, 0), pady=5, sticky="e")
        initial_denoise = self.config_manager.get_setting("processing_parameters.video_enhancement.denoise_strength", 2.0)
        self.denoise_slider.set(initial_denoise)
        self._update_denoise_strength(initial_denoise) # Update label initially
        row_idx += 1

        # Sharpen Strength
        self.sharpen_label = customtkinter.CTkLabel(self.scrollable_frame, text="Sharpen Strength:")
        self.sharpen_label.grid(row=row_idx, column=0, padx=(0, 10), pady=5, sticky="w")
        self.sharpen_slider = customtkinter.CTkSlider(self.scrollable_frame, from_=0.0, to=2.0, number_of_steps=20, command=self._update_sharpen_strength)
        self.sharpen_slider.grid(row=row_idx, column=1, padx=10, pady=5, sticky="ew")
        self.sharpen_value_label = customtkinter.CTkLabel(self.scrollable_frame, text="0.5")
        self.sharpen_value_label.grid(row=row_idx, column=2, padx=(10, 0), pady=5, sticky="e")
        initial_sharpen = self.config_manager.get_setting("processing_parameters.video_enhancement.sharpen_strength", 0.5)
        self.sharpen_slider.set(initial_sharpen)
        self._update_sharpen_strength(initial_sharpen)
        row_idx += 1

        # Contrast Enhance
        self.contrast_label = customtkinter.CTkLabel(self.scrollable_frame, text="Contrast:")
        self.contrast_label.grid(row=row_idx, column=0, padx=(0, 10), pady=5, sticky="w")
        self.contrast_slider = customtkinter.CTkSlider(self.scrollable_frame, from_=0.5, to=1.5, number_of_steps=100, command=self._update_contrast_enhance)
        self.contrast_slider.grid(row=row_idx, column=1, padx=10, pady=5, sticky="ew")
        self.contrast_value_label = customtkinter.CTkLabel(self.scrollable_frame, text="1.0")
        self.contrast_value_label.grid(row=row_idx, column=2, padx=(10, 0), pady=5, sticky="e")
        initial_contrast = self.config_manager.get_setting("processing_parameters.video_enhancement.contrast_enhance", 1.0)
        self.contrast_slider.set(initial_contrast)
        self._update_contrast_enhance(initial_contrast)
        row_idx += 1

        # Saturation
        self.saturation_label = customtkinter.CTkLabel(self.scrollable_frame, text="Saturation:")
        self.saturation_label.grid(row=row_idx, column=0, padx=(0, 10), pady=5, sticky="w")
        self.saturation_slider = customtkinter.CTkSlider(self.scrollable_frame, from_=0.0, to=2.0, number_of_steps=200, command=self._update_saturation)
        self.saturation_slider.grid(row=row_idx, column=1, padx=10, pady=5, sticky="ew")
        self.saturation_value_label = customtkinter.CTkLabel(self.scrollable_frame, text="1.0")
        self.saturation_value_label.grid(row=row_idx, column=2, padx=(10, 0), pady=5, sticky="e")
        initial_saturation = self.config_manager.get_setting("processing_parameters.video_enhancement.saturation", 1.0)
        self.saturation_slider.set(initial_saturation)
        self._update_saturation(initial_saturation)
        row_idx += 1

        # Gamma
        self.gamma_label = customtkinter.CTkLabel(self.scrollable_frame, text="Gamma:")
        self.gamma_label.grid(row=row_idx, column=0, padx=(0, 10), pady=5, sticky="w")
        self.gamma_slider = customtkinter.CTkSlider(self.scrollable_frame, from_=0.5, to=2.0, number_of_steps=150, command=self._update_gamma)
        self.gamma_slider.grid(row=row_idx, column=1, padx=10, pady=5, sticky="ew")
        self.gamma_value_label = customtkinter.CTkLabel(self.scrollable_frame, text="1.0")
        self.gamma_value_label.grid(row=row_idx, column=2, padx=(10, 0), pady=5, sticky="e")
        initial_gamma = self.config_manager.get_setting("processing_parameters.video_enhancement.gamma", 1.0)
        self.gamma_slider.set(initial_gamma)
        self._update_gamma(initial_gamma)
        row_idx += 1

        # Brightness
        self.brightness_label = customtkinter.CTkLabel(self.scrollable_frame, text="Brightness:")
        self.brightness_label.grid(row=row_idx, column=0, padx=(0, 10), pady=5, sticky="w")
        self.brightness_slider = customtkinter.CTkSlider(self.scrollable_frame, from_=-0.5, to=0.5, number_of_steps=100, command=self._update_brightness)
        self.brightness_slider.grid(row=row_idx, column=1, padx=10, pady=5, sticky="ew")
        self.brightness_value_label = customtkinter.CTkLabel(self.scrollable_frame, text="0.0")
        self.brightness_value_label.grid(row=row_idx, column=2, padx=(10, 0), pady=5, sticky="e")
        initial_brightness = self.config_manager.get_setting("processing_parameters.video_enhancement.brightness", 0.0)
        self.brightness_slider.set(initial_brightness)
        self._update_brightness(initial_brightness)
        row_idx += 1

        # Shadow/Highlight Balance
        self.shadow_highlight_label = customtkinter.CTkLabel(self.scrollable_frame, text="Shadow/Highlight:")
        self.shadow_highlight_label.grid(row=row_idx, column=0, padx=(0, 10), pady=5, sticky="w")
        self.shadow_highlight_slider = customtkinter.CTkSlider(self.scrollable_frame, from_=-0.5, to=0.5, number_of_steps=100, command=self._update_shadow_highlight)
        self.shadow_highlight_slider.grid(row=row_idx, column=1, padx=10, pady=5, sticky="ew")
        self.shadow_highlight_value_label = customtkinter.CTkLabel(self.scrollable_frame, text="0.0")
        self.shadow_highlight_value_label.grid(row=row_idx, column=2, padx=(10, 0), pady=5, sticky="e")
        initial_shadow_highlight = self.config_manager.get_setting("processing_parameters.video_enhancement.shadow_highlight", 0.0)
        self.shadow_highlight_slider.set(initial_shadow_highlight)
        self._update_shadow_highlight(initial_shadow_highlight)
        row_idx += 1

        # Delete original checkbox
        self.delete_original_checkbox = customtkinter.CTkCheckBox(self.scrollable_frame, text="Delete original file after successful enhancement", command=self._update_delete_original_setting)
        self.delete_original_checkbox.grid(row=row_idx, column=0, columnspan=3, padx=(0,10), pady=15, sticky="w")
        initial_delete_original = self.config_manager.get_setting("processing_parameters.video_enhancement.delete_original_after_processing", False)
        if initial_delete_original: self.delete_original_checkbox.select()
        else: self.delete_original_checkbox.deselect()
        row_idx += 1

        # --- Global Progress Bar and Button ---
        # These are outside the scrollable frame
        self.progress_label = customtkinter.CTkLabel(self, text="Progress: 0%")
        self.progress_label.grid(row=2, column=0, padx=20, pady=(10, 5), sticky="w")
        self.progress_bar = customtkinter.CTkProgressBar(self)
        self.progress_bar.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="ew")
        self.progress_bar.set(0)

        self.enhance_button = customtkinter.CTkButton(self, text="Start Enhancement", command=self._start_enhancement)
        self.enhance_button.grid(row=4, column=0, padx=20, pady=20, sticky="ew")

        self._update_ui_state(False) # Initial state: disable enhance button until files are chosen

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
            self._update_ui_state(True) # Enable enhance button if input selected
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

            output_file_name = f"{self.input_file_path.stem}_enhanced.mp4" # Default to MP4
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
        initial_filename = f"{self.input_file_path.stem}_enhanced.mp4"

        file_path_str = filedialog.asksaveasfilename(
            title="Save Enhanced Video As",
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

    # --- Slider and Checkbox Callbacks (Update Config and UI Labels) ---
    def _update_denoise_strength(self, value):
        rounded_value = round(value, 2)
        self.denoise_value_label.configure(text=f"{rounded_value:.1f}")
        self.config_manager.set_setting("processing_parameters.video_enhancement.denoise_strength", rounded_value)
        self.logger.debug(f"Denoise strength set to: {rounded_value}")
        self.app_instance.set_status(f"Denoise: {rounded_value:.1f}")

    def _update_sharpen_strength(self, value):
        rounded_value = round(value, 2)
        self.sharpen_value_label.configure(text=f"{rounded_value:.1f}")
        self.config_manager.set_setting("processing_parameters.video_enhancement.sharpen_strength", rounded_value)
        self.logger.debug(f"Sharpen strength set to: {rounded_value}")
        self.app_instance.set_status(f"Sharpen: {rounded_value:.1f}")

    def _update_contrast_enhance(self, value):
        rounded_value = round(value, 2)
        self.contrast_value_label.configure(text=f"{rounded_value:.2f}")
        self.config_manager.set_setting("processing_parameters.video_enhancement.contrast_enhance", rounded_value)
        self.logger.debug(f"Contrast set to: {rounded_value}")
        self.app_instance.set_status(f"Contrast: {rounded_value:.2f}")

    def _update_saturation(self, value):
        rounded_value = round(value, 2)
        self.saturation_value_label.configure(text=f"{rounded_value:.2f}")
        self.config_manager.set_setting("processing_parameters.video_enhancement.saturation", rounded_value)
        self.logger.debug(f"Saturation set to: {rounded_value}")
        self.app_instance.set_status(f"Saturation: {rounded_value:.2f}")

    def _update_gamma(self, value):
        rounded_value = round(value, 2)
        self.gamma_value_label.configure(text=f"{rounded_value:.2f}")
        self.config_manager.set_setting("processing_parameters.video_enhancement.gamma", rounded_value)
        self.logger.debug(f"Gamma set to: {rounded_value}")
        self.app_instance.set_status(f"Gamma: {rounded_value:.2f}")

    def _update_brightness(self, value):
        rounded_value = round(value, 2)
        self.brightness_value_label.configure(text=f"{rounded_value:.2f}")
        self.config_manager.set_setting("processing_parameters.video_enhancement.brightness", rounded_value)
        self.logger.debug(f"Brightness set to: {rounded_value}")
        self.app_instance.set_status(f"Brightness: {rounded_value:.2f}")

    def _update_shadow_highlight(self, value):
        rounded_value = round(value, 2)
        self.shadow_highlight_value_label.configure(text=f"{rounded_value:.2f}")
        self.config_manager.set_setting("processing_parameters.video_enhancement.shadow_highlight", rounded_value)
        self.logger.debug(f"Shadow/Highlight set to: {rounded_value}")
        self.app_instance.set_status(f"Shadow/Highlight: {rounded_value:.2f}")

    def _update_delete_original_setting(self):
        """Updates the 'delete_original_after_processing' setting in the config."""
        is_checked = self.delete_original_checkbox.get() == 1
        self.config_manager.set_setting("processing_parameters.video_enhancement.delete_original_after_processing", is_checked)
        self.logger.info(f"Delete original (video enhancement) setting updated to: {is_checked}")
        self.app_instance.set_status(f"Delete original (enhancement): {is_checked}")

    # --- Progress and UI State ---
    def _update_progress_bar(self, progress_percentage: int, message: str):
        """
        Callback from VideoEnhancer to update the GUI progress bar and label.
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
        self.app_instance.set_status(f"Enhancing: {progress_percentage}% - {message}")
        self.master.update_idletasks() # Force GUI update

    def _update_ui_state(self, enable_enhance_button: bool):
        """Sets the state of interactive widgets based on processing status."""
        is_processing = self.video_enhancer.is_processing()

        self.enhance_button.configure(state="disabled")
        if enable_enhance_button and not is_processing:
            self.enhance_button.configure(state="normal")

        browse_state = "disabled" if is_processing else "normal"
        self.input_button.configure(state=browse_state)
        self.output_button.configure(state=browse_state)
        
        # Sliders and Checkbox
        slider_state = "disabled" if is_processing else "normal"
        self.denoise_slider.configure(state=slider_state)
        self.sharpen_slider.configure(state=slider_state)
        self.contrast_slider.configure(state=slider_state)
        self.saturation_slider.configure(state=slider_state)
        self.gamma_slider.configure(state=slider_state)
        self.brightness_slider.configure(state=slider_state)
        self.shadow_highlight_slider.configure(state=slider_state)
        self.delete_original_checkbox.configure(state=slider_state)

    def _start_enhancement(self):
        """
        Initiates the video enhancement process in a separate thread
        to keep the GUI responsive.
        """
        if not self.input_file_path or not self.input_file_path.is_file():
            messagebox.showerror("Input Error", "Please select a valid input video file.")
            self.logger.warning("Enhancement attempt failed: No valid input file selected.")
            self.app_instance.set_status("Enhancement failed: No input.", level="warning")
            return

        if not self.output_file_path:
            messagebox.showerror("Output Error", "Please specify an output video file path.")
            self.logger.warning("Enhancement attempt failed: No output file specified.")
            self.app_instance.set_status("Enhancement failed: No output path.", level="warning")
            return

        if self.video_enhancer.is_processing():
            self.app_instance.set_status("Video enhancement already in progress.", level="warning")
            return

        self._update_ui_state(False) # Disable UI during processing
        self.progress_bar.set(0)
        self.progress_label.configure(text="Progress: 0%")
        self.app_instance.set_status("Video enhancement started...", level="info")
        self.logger.info("Video enhancement initiated via GUI.")

        # Gather current enhancement parameters from config
        enhancement_params = self.config_manager.get_setting("processing_parameters.video_enhancement")
        # Ensure we have a mutable copy if we intend to modify it, though here we just pass it.
        # It's good practice to pass a deep copy if the module might modify it.
        params_for_processor = enhancement_params.copy()

        # Run enhancement in a separate thread
        self.processing_thread = threading.Thread(
            target=self._run_enhancement_task,
            args=(self.input_file_path, self.output_file_path, params_for_processor)
        )
        self.processing_thread.start()

    def _run_enhancement_task(self, input_path: Path, output_path: Path, params: Dict[str, Any]):
        """
        The actual video enhancement task to be run in a separate thread.
        Handles calling the VideoEnhancer and updating the GUI with results.
        """
        success, message = self.video_enhancer.enhance_video(
            input_filepath=input_path,
            output_filepath=output_path,
            enhancement_params=params,
            progress_callback_func=self._update_progress_bar # Pass our GUI update method
        )

        # After processing (success or failure), schedule result handling on the main thread
        if self.master:
            self.master.after(0, self._handle_enhancement_result, success, message)
        else:
            self.logger.error("Master is None during _run_enhancement_task completion. Cannot update GUI.")

    def _handle_enhancement_result(self, success: bool, message: str):
        """
        Handles the result of the video enhancement, updating status and re-enabling UI.
        Called on the main thread after enhancement completes.
        """
        if success:
            messagebox.showinfo("Enhancement Success", f"Video enhanced successfully!\nOutput: {message.split(': ')[-1]}")
            self.logger.info(f"Video enhancement UI completed successfully: {message}")
            self.progress_label.configure(text="Enhancement Complete!")
            self.progress_bar.set(1.0) # Ensure it shows 100%
        else:
            messagebox.showerror("Enhancement Failed", f"Video enhancement failed:\n{message}")
            self.logger.error(f"Video enhancement UI failed: {message}")
            self.progress_label.configure(text="Enhancement Failed!")
            self.progress_bar.set(0) # Reset progress on failure

        self._update_ui_state(True) # Re-enable UI elements
        self.app_instance.set_status(message, level="info" if success else "error")