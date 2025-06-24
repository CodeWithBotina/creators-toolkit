import customtkinter
from tkinter import filedialog, messagebox
import threading
from pathlib import Path
import logging

# Import core and module components
from src.core.logger import get_application_logger
from src.core.config_manager import get_application_config
from src.modules.audio_processor import AudioProcessor # Import our audio processing backend

class AudioEnhancementPage(customtkinter.CTkFrame):
    """
    CustomTkinter Frame for the Audio Enhancement functionality.
    Allows users to select input/output files, adjust parameters, and start processing.
    """
    def __init__(self, master, app_instance):
        super().__init__(master, fg_color="transparent")
        self.logger = get_application_logger()
        self.config_manager = get_application_config()
        self.app_instance = app_instance # Reference to the main App class for status updates
        self.audio_processor = AudioProcessor() # Instantiate the backend logic

        self.input_file_path = None
        self.output_file_path = None # Store the full output path suggested/chosen

        self.logger.info("Initializing AudioEnhancementPage UI.")

        # Configure grid layout for this page
        self.grid_columnconfigure(0, weight=0) # Labels column
        self.grid_columnconfigure(1, weight=1) # Entry fields and sliders column
        self.grid_columnconfigure(2, weight=0) # Buttons column
        self.grid_rowconfigure((0, 1, 2, 3, 4, 5, 6, 7, 8), weight=0) # Make rows take minimal space
        self.grid_rowconfigure(9, weight=1) # Empty row to push elements up if needed

        # --- Widgets ---

        # Title
        self.title_label = customtkinter.CTkLabel(self, text="Audio Enhancement Tools", font=customtkinter.CTkFont(size=24, weight="bold"))
        self.title_label.grid(row=0, column=0, columnspan=3, padx=20, pady=(20, 30), sticky="ew")

        # Input File Selection
        self.input_label = customtkinter.CTkLabel(self, text="Input Audio File:")
        self.input_label.grid(row=1, column=0, padx=(20, 10), pady=10, sticky="w")
        self.input_entry = customtkinter.CTkEntry(self, placeholder_text="No file selected...", state="readonly")
        self.input_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        self.input_button = customtkinter.CTkButton(self, text="Browse", command=self._browse_input_file)
        self.input_button.grid(row=1, column=2, padx=(10, 20), pady=10, sticky="e")

        # Output File Selection
        self.output_label = customtkinter.CTkLabel(self, text="Output Audio File:")
        self.output_label.grid(row=2, column=0, padx=(20, 10), pady=10, sticky="w")
        self.output_entry = customtkinter.CTkEntry(self, placeholder_text="Output path will be set automatically...", state="readonly")
        self.output_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
        self.output_button = customtkinter.CTkButton(self, text="Save As", command=self._browse_output_file)
        self.output_button.grid(row=2, column=2, padx=(10, 20), pady=10, sticky="e")

        # --- Processing Parameters ---
        self.params_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.params_frame.grid(row=3, column=0, columnspan=3, padx=20, pady=(10, 10), sticky="ew")
        self.params_frame.grid_columnconfigure(1, weight=1)

        # Noise Reduction Strength
        self.noise_reduction_label = customtkinter.CTkLabel(self.params_frame, text="Noise Reduction Strength:")
        self.noise_reduction_label.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")
        self.noise_reduction_slider = customtkinter.CTkSlider(self.params_frame, from_=0.0, to=1.0, number_of_steps=100,
                                                               command=self._update_noise_reduction_value)
        self.noise_reduction_slider.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        self.noise_reduction_value_label = customtkinter.CTkLabel(self.params_frame, text="0.5")
        self.noise_reduction_value_label.grid(row=0, column=2, padx=(10, 0), pady=5, sticky="e")
        
        initial_noise_strength = self.config_manager.get_setting("processing_parameters.audio_enhancement.noise_reduction_strength", 0.5)
        self.noise_reduction_slider.set(initial_noise_strength)
        self._update_noise_reduction_value(initial_noise_strength) # Initialize label

        # Normalization Level
        self.normalization_label = customtkinter.CTkLabel(self.params_frame, text="Normalization (dBFS):")
        self.normalization_label.grid(row=1, column=0, padx=(0, 10), pady=5, sticky="w")
        self.normalization_slider = customtkinter.CTkSlider(self.params_frame, from_=-30.0, to=0.0, number_of_steps=300,
                                                            command=self._update_normalization_value)
        self.normalization_slider.grid(row=1, column=1, padx=10, pady=5, sticky="ew")
        self.normalization_value_label = customtkinter.CTkLabel(self.params_frame, text="-3.0")
        self.normalization_value_label.grid(row=1, column=2, padx=(10, 0), pady=5, sticky="e")

        initial_norm_level = self.config_manager.get_setting("processing_parameters.audio_enhancement.normalization_level_dbfs", -3.0)
        self.normalization_slider.set(initial_norm_level)
        self._update_normalization_value(initial_norm_level) # Initialize label

        # Remove Silence Checkbox
        self.remove_silence_checkbox = customtkinter.CTkCheckBox(self.params_frame, text="Remove Silence (VAD)",
                                                                 command=self._update_remove_silence_setting)
        self.remove_silence_checkbox.grid(row=2, column=0, columnspan=2, padx=0, pady=10, sticky="w")
        initial_remove_silence = self.config_manager.get_setting("processing_parameters.audio_enhancement.remove_silence", False)
        if initial_remove_silence:
            self.remove_silence_checkbox.select()
        else:
            self.remove_silence_checkbox.deselect()
        
        # Min Silence Length (only visible if remove_silence is checked)
        self.min_silence_len_label = customtkinter.CTkLabel(self.params_frame, text="Min Silence Length (ms):")
        self.min_silence_len_label.grid(row=3, column=0, padx=(0, 10), pady=5, sticky="w")
        self.min_silence_len_entry = customtkinter.CTkEntry(self.params_frame, width=80)
        self.min_silence_len_entry.grid(row=3, column=1, padx=10, pady=5, sticky="w")
        
        initial_min_silence_len = self.config_manager.get_setting("processing_parameters.audio_enhancement.min_silence_len_ms", 1000)
        self.min_silence_len_entry.insert(0, str(initial_min_silence_len))
        self.min_silence_len_entry.bind("<FocusOut>", self._update_min_silence_len_setting)
        self.min_silence_len_entry.bind("<Return>", self._update_min_silence_len_setting)

        # Silence Threshold (only visible if remove_silence is checked)
        self.silence_thresh_label = customtkinter.CTkLabel(self.params_frame, text="Silence Threshold (dB):")
        self.silence_thresh_label.grid(row=4, column=0, padx=(0, 10), pady=5, sticky="w")
        self.silence_thresh_entry = customtkinter.CTkEntry(self.params_frame, width=80)
        self.silence_thresh_entry.grid(row=4, column=1, padx=10, pady=5, sticky="w")
        
        initial_silence_thresh = self.config_manager.get_setting("processing_parameters.audio_enhancement.silence_thresh_db", -35)
        self.silence_thresh_entry.insert(0, str(initial_silence_thresh))
        self.silence_thresh_entry.bind("<FocusOut>", self._update_silence_thresh_setting)
        self.silence_thresh_entry.bind("<Return>", self._update_silence_thresh_setting)

        # Update visibility of silence parameters
        self._toggle_silence_parameters_visibility(initial_remove_silence)


        # Delete Original Checkbox
        self.delete_original_checkbox = customtkinter.CTkCheckBox(self, text="Delete original file after successful processing",
                                                                  command=self._update_delete_original_setting)
        self.delete_original_checkbox.grid(row=6, column=0, columnspan=2, padx=20, pady=10, sticky="w")
        # Set initial state from config
        initial_delete_original = self.config_manager.get_setting("processing_parameters.audio_enhancement.delete_original_after_processing", False)
        if initial_delete_original:
            self.delete_original_checkbox.select()
        else:
            self.delete_original_checkbox.deselect()

        # Progress Bar
        self.progress_label = customtkinter.CTkLabel(self, text="Progress: 0%")
        self.progress_label.grid(row=7, column=0, columnspan=3, padx=20, pady=(10, 5), sticky="w")
        self.progress_bar = customtkinter.CTkProgressBar(self)
        self.progress_bar.grid(row=8, column=0, columnspan=3, padx=20, pady=(0, 20), sticky="ew")
        self.progress_bar.set(0) # Initialize to 0%

        # Convert Button
        self.process_button = customtkinter.CTkButton(self, text="Start Processing", command=self._start_processing)
        self.process_button.grid(row=9, column=0, columnspan=3, padx=20, pady=20, sticky="ew")

        self._update_ui_state(False) # Initial state: disable process button until files are chosen

    def _browse_input_file(self):
        """Opens a file dialog to select the input audio file."""
        filetypes = [("Audio files", "*.mp3 *.wav *.flac *.aac *.ogg"),
                     ("All files", "*.*")]
        file_path_str = filedialog.askopenfilename(title="Select Input Audio File", filetypes=filetypes)
        if file_path_str:
            self.input_file_path = Path(file_path_str)
            self._update_entry_text(self.input_entry, str(self.input_file_path))
            self.logger.info(f"Input audio file selected: {self.input_file_path}")
            self.app_instance.set_status(f"Selected: {self.input_file_path.name}")
            self._suggest_output_file_path()
            self._update_ui_state(True) # Enable process button if input selected
        else:
            self.logger.info("Input audio file selection cancelled.")
            self.app_instance.set_status("Input audio file selection cancelled.")
            self._update_ui_state(False) # Disable if input cancelled

    def _suggest_output_file_path(self):
        """
        Suggests an output file path based on the input file and default output directory.
        """
        if self.input_file_path:
            default_output_dir_str = self.config_manager.get_setting("output_directories.default_audio_output")
            default_output_dir = Path(default_output_dir_str)
            default_output_dir.mkdir(parents=True, exist_ok=True) # Ensure default output dir exists

            output_file_name = f"{self.input_file_path.stem}_processed.flac" # Default to FLAC for quality
            self.output_file_path = default_output_dir / output_file_name

            self._update_entry_text(self.output_entry, str(self.output_file_path))
            self.logger.info(f"Suggested output path: {self.output_file_path}")
        else:
            self._update_entry_text(self.output_entry, "Select an input file first.")
            self.output_file_path = None

    def _browse_output_file(self):
        """Opens a file dialog to select/save the output audio file."""
        if not self.input_file_path:
            messagebox.showwarning("No Input File", "Please select an input audio file first.")
            self.logger.warning("Output file browse cancelled: No input file selected.")
            return

        initial_dir = self.config_manager.get_setting("output_directories.default_audio_output")
        initial_filename = f"{self.input_file_path.stem}_processed.flac"

        file_path_str = filedialog.asksaveasfilename(
            title="Save Processed Audio As",
            initialdir=initial_dir,
            initialfile=initial_filename,
            filetypes=[("FLAC files", "*.flac"), ("WAV files", "*.wav"), ("MP3 files", "*.mp3"), ("All files", "*.*")],
            defaultextension=".flac" # Suggest FLAC by default for quality
        )
        if file_path_str:
            self.output_file_path = Path(file_path_str)
            # Ensure the output has a valid audio extension
            if self.output_file_path.suffix.lower() not in ['.flac', '.wav', '.mp3', '.aac', '.ogg']:
                self.output_file_path = self.output_file_path.with_suffix('.flac')
                self.logger.warning(f"Output file extension changed to '.flac' for compatibility: {self.output_file_path}")
            
            self._update_entry_text(self.output_entry, str(self.output_file_path))
            self.logger.info(f"Output audio file selected: {self.output_file_path}")
            self.app_instance.set_status(f"Output will be: {self.output_file_path.name}")
        else:
            self.logger.info("Output audio file selection cancelled.")
            self.app_instance.set_status("Output audio file selection cancelled.")

    def _update_entry_text(self, entry_widget, text: str):
        """Helper to update a readonly CTkEntry."""
        entry_widget.configure(state="normal")
        entry_widget.delete(0, customtkinter.END)
        entry_widget.insert(0, text)
        entry_widget.configure(state="readonly")

    def _update_noise_reduction_value(self, value):
        """Updates the noise reduction strength display and config."""
        rounded_value = round(value, 2)
        self.noise_reduction_value_label.configure(text=f"{rounded_value:.2f}")
        self.config_manager.set_setting("processing_parameters.audio_enhancement.noise_reduction_strength", rounded_value)
        self.logger.debug(f"Noise reduction strength set to: {rounded_value}")
        self.app_instance.set_status(f"Noise reduction: {rounded_value:.2f}")

    def _update_normalization_value(self, value):
        """Updates the normalization level display and config."""
        rounded_value = round(value, 1)
        self.normalization_value_label.configure(text=f"{rounded_value:.1f} dBFS")
        self.config_manager.set_setting("processing_parameters.audio_enhancement.normalization_level_dbfs", rounded_value)
        self.logger.debug(f"Normalization level set to: {rounded_value} dBFS")
        self.app_instance.set_status(f"Normalization: {rounded_value:.1f} dBFS")

    def _update_remove_silence_setting(self):
        """Updates the 'remove_silence' setting in config and toggles UI visibility."""
        is_checked = self.remove_silence_checkbox.get() == 1
        self.config_manager.set_setting("processing_parameters.audio_enhancement.remove_silence", is_checked)
        self.logger.info(f"Remove silence setting updated to: {is_checked}")
        self.app_instance.set_status(f"Remove silence: {is_checked}")
        self._toggle_silence_parameters_visibility(is_checked)

    def _toggle_silence_parameters_visibility(self, visible: bool):
        """Toggles the visibility of min silence length and threshold controls."""
        if visible:
            self.min_silence_len_label.grid()
            self.min_silence_len_entry.grid()
            self.silence_thresh_label.grid()
            self.silence_thresh_entry.grid()
        else:
            self.min_silence_len_label.grid_remove()
            self.min_silence_len_entry.grid_remove()
            self.silence_thresh_label.grid_remove()
            self.silence_thresh_entry.grid_remove()

    def _update_min_silence_len_setting(self, event=None):
        """Updates min_silence_len_ms setting from entry."""
        try:
            value = int(self.min_silence_len_entry.get())
            if value < 0:
                raise ValueError("Value must be non-negative.")
            self.config_manager.set_setting("processing_parameters.audio_enhancement.min_silence_len_ms", value)
            self.logger.debug(f"Min silence length set to: {value} ms")
            self.app_instance.set_status(f"Min silence: {value} ms")
        except ValueError:
            messagebox.showerror("Input Error", "Minimum silence length must be an integer (milliseconds).")
            self.min_silence_len_entry.delete(0, customtkinter.END)
            # Re-insert the last valid value from config or default
            self.min_silence_len_entry.insert(0, str(self.config_manager.get_setting("processing_parameters.audio_enhancement.min_silence_len_ms", 1000)))
            self.logger.warning("Invalid input for min silence length.")
            self.app_instance.set_status("Invalid min silence length.", level="warning")

    def _update_silence_thresh_setting(self, event=None):
        """Updates silence_thresh_db setting from entry."""
        try:
            value = float(self.silence_thresh_entry.get())
            # A common range for silence threshold is -20dB to -60dB, but allowing more flexibility
            if value > 0: # Silence threshold should typically be negative
                raise ValueError("Silence threshold should be a negative dB value.")
            self.config_manager.set_setting("processing_parameters.audio_enhancement.silence_thresh_db", value)
            self.logger.debug(f"Silence threshold set to: {value} dB")
            self.app_instance.set_status(f"Silence threshold: {value} dB")
        except ValueError:
            messagebox.showerror("Input Error", "Silence threshold must be a number (dB, usually negative).")
            self.silence_thresh_entry.delete(0, customtkinter.END)
            # Re-insert the last valid value from config or default
            self.silence_thresh_entry.insert(0, str(self.config_manager.get_setting("processing_parameters.audio_enhancement.silence_thresh_db", -35)))
            self.logger.warning("Invalid input for silence threshold.")
            self.app_instance.set_status("Invalid silence threshold.", level="warning")


    def _update_delete_original_setting(self):
        """Updates the 'delete_original_after_processing' setting in the config."""
        is_checked = self.delete_original_checkbox.get() == 1
        self.config_manager.set_setting("processing_parameters.audio_enhancement.delete_original_after_processing", is_checked)
        self.logger.info(f"Delete original (audio) setting updated to: {is_checked}")
        self.app_instance.set_status(f"Delete original (audio): {is_checked}")

    def _update_progress_bar(self, progress_percentage: int, message: str):
        """
        Callback from AudioProcessor to update the GUI progress bar and label.
        Schedules the actual GUI update on the main thread.
        """
        # print(f"DEBUG: _update_progress_bar called. master: {self.master}, progress_percentage: {progress_percentage}, message: {message}")
        if self.master:
            self.master.after(1, self.__update_progress_gui, progress_percentage, message)
        else:
            self.logger.error("Attempted to update GUI on a None master object in _update_progress_bar.")


    def __update_progress_gui(self, progress_percentage: int, message: str):
        """Actual GUI update function, called via master.after. Runs on main thread."""
        self.progress_bar.set(progress_percentage / 100.0) # CTkProgressBar expects float from 0.0 to 1.0
        self.progress_label.configure(text=f"Progress: {progress_percentage}% - {message}")
        self.app_instance.set_status(f"Processing audio: {progress_percentage}% - {message}")
        self.master.update_idletasks() # Force GUI update

    def _update_ui_state(self, enable_process_button: bool):
        """Sets the state of interactive widgets based on processing status."""
        is_processing = self.audio_processor.is_processing()

        self.process_button.configure(state="disabled") # Default to disabled
        if enable_process_button and not is_processing:
            self.process_button.configure(state="normal")

        browse_state = "disabled" if is_processing else "normal"
        self.input_button.configure(state=browse_state)
        self.output_button.configure(state=browse_state)
        self.noise_reduction_slider.configure(state=browse_state)
        self.normalization_slider.configure(state=browse_state)
        self.remove_silence_checkbox.configure(state=browse_state)
        self.delete_original_checkbox.configure(state=browse_state)
        
        # Also disable silence-specific entries if not visible or processing
        if not self.remove_silence_checkbox.get() or is_processing:
            self.min_silence_len_entry.configure(state="disabled")
            self.silence_thresh_entry.configure(state="disabled")
        else:
            self.min_silence_len_entry.configure(state="normal")
            self.silence_thresh_entry.configure(state="normal")


    def _start_processing(self):
        """
        Initiates the audio processing in a separate thread
        to keep the GUI responsive.
        """
        if not self.input_file_path or not self.input_file_path.is_file():
            messagebox.showerror("Input Error", "Please select a valid input audio file.")
            self.logger.warning("Audio processing attempt failed: No valid input file selected.")
            self.app_instance.set_status("Processing failed: No input.", level="warning")
            return

        if not self.output_file_path:
            messagebox.showerror("Output Error", "Please specify an output audio file path.")
            self.logger.warning("Audio processing attempt failed: No output file specified.")
            self.app_instance.set_status("Processing failed: No output path.", level="warning")
            return

        # Double check if processing is already running
        if self.audio_processor.is_processing():
            self.app_instance.set_status("Audio processing already in progress.", level="warning")
            return

        self._update_ui_state(False) # Disable UI during processing
        self.progress_bar.set(0)
        self.progress_label.configure(text="Progress: 0%")
        self.app_instance.set_status("Audio processing started...", level="info")
        self.logger.info("Audio processing initiated via GUI.")

        delete_original = self.delete_original_checkbox.get() == 1

        # Run processing in a separate thread
        self.processing_thread = threading.Thread(
            target=self._run_processing_task,
            args=(self.input_file_path, self.output_file_path, delete_original)
        )
        self.processing_thread.start()

    def _run_processing_task(self, input_path: Path, output_path: Path, delete_original: bool):
        """
        The actual audio processing task to be run in a separate thread.
        Handles calling the AudioProcessor and updating the GUI with results.
        """
        success, message = self.audio_processor.process_audio_file(
            input_filepath=input_path,
            output_filepath=output_path,
            delete_original=delete_original,
            progress_callback_func=self._update_progress_bar # Pass our GUI update method
        )

        # After processing (success or failure), schedule result handling on the main thread
        if self.master:
            self.master.after(0, self._handle_processing_result, success, message)
        else:
            self.logger.error("Master is None during _run_processing_task completion. Cannot update GUI.")

    def _handle_processing_result(self, success: bool, message: str):
        """
        Handles the result of the audio processing, updating status and re-enabling UI.
        Called on the main thread after processing completes.
        """
        if success:
            messagebox.showinfo("Processing Success", f"Audio processed successfully!\nOutput: {message.split(': ')[-1]}")
            self.logger.info(f"Audio processing UI completed successfully: {message}")
            self.progress_label.configure(text="Processing Complete!")
            self.progress_bar.set(1.0) # Ensure it shows 100%
        else:
            messagebox.showerror("Processing Failed", f"Audio processing failed:\n{message}")
            self.logger.error(f"Audio processing UI failed: {message}")
            self.progress_label.configure(text="Processing Failed!")
            self.progress_bar.set(0) # Reset progress on failure

        self._update_ui_state(True) # Re-enable UI elements
        self.app_instance.set_status(message, level="info" if success else "error")


# This __main__ block is for isolated testing of the page itself, not the full app.
if __name__ == "__main__":
    import sys
    # Add parent directory to path to allow imports from src.core and src.modules
    sys.path.append(str(Path(__file__).parent.parent.parent))

    # Initialize logger and config for standalone test
    from src.core.logger import AppLogger
    from src.core.config_manager import ConfigManager
    # Ensure logs and config directories exist for this isolated test context
    Path("../logs").mkdir(exist_ok=True)
    Path("../config").mkdir(exist_ok=True)
    AppLogger(log_dir="../logs", log_level=logging.DEBUG)
    ConfigManager(config_dir="../config") # Ensure theme is set to "dark-blue" in default_config here
    test_logger = get_application_logger()
    test_logger.info("--- Starting AudioEnhancementPage isolated test ---")


    class DummyApp:
        """A minimal mock for the main App class to satisfy AudioEnhancementPage's dependency."""
        def __init__(self):
            self.logger = get_application_logger()
        def set_status(self, message, level="info"):
            self.logger.info(f"[DummyApp Status] {message}")
            print(f"[DummyApp Status Bar]: {message}") # Print to console for test visibility

    root = customtkinter.CTk()
    root.title("Audio Enhancement Page Test")
    root.geometry("900x700") # Increased size to accommodate new controls
    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(0, weight=1)

    dummy_app = DummyApp()
    enhancement_page = AudioEnhancementPage(root, dummy_app)
    enhancement_page.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

    # Automatically set a dummy input file for easier testing if available
    dummy_test_audio = Path(__file__).parent.parent.parent / "test_media" / "test_audio.wav"
    if dummy_test_audio.exists():
        enhancement_page.input_file_path = dummy_test_audio
        enhancement_page._update_entry_text(enhancement_page.input_entry, str(dummy_test_audio))
        enhancement_page._suggest_output_file_path()
        enhancement_page._update_ui_state(True) # Enable process button since input is set
        test_logger.info(f"Pre-set dummy input audio for testing: {dummy_test_audio}")
    else:
        test_logger.warning(f"Dummy test audio not found at {dummy_test_audio}. Please create it or browse manually.")
        
    root.mainloop()
    test_logger.info("--- AudioEnhancementPage isolated test completed ---")

