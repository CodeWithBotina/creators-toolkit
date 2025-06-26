import customtkinter
from tkinter import filedialog, messagebox
import threading
from pathlib import Path
import logging
from typing import Optional # Import Optional for type hinting

# Import core and module components
from src.core.logger import get_application_logger
from src.core.config_manager import get_application_config
from src.modules.video_converter import VideoConverter # Import the backend logic

class VideoConverterPage(customtkinter.CTkFrame):
    """
    CustomTkinter Frame for the Video Converter functionality.
    Allows users to select input/output video files and initiate the conversion process.
    """
    def __init__(self, master, app_instance):
        super().__init__(master, fg_color="transparent")
        self.logger = get_application_logger()
        self.config_manager = get_application_config()
        self.app_instance = app_instance # Reference to the main App class for status updates
        self.video_converter = VideoConverter() # Instantiate the backend logic

        self.input_file_path: Optional[Path] = None
        self.output_file_path: Optional[Path] = None # Store the full output path suggested/chosen

        self.logger.info("Initializing VideoConverterPage UI.")

        # Configure grid layout for this page
        self.grid_columnconfigure(0, weight=0) # Labels column
        self.grid_columnconfigure(1, weight=1) # Entry fields and controls column
        self.grid_columnconfigure(2, weight=0) # Buttons column
        self.grid_rowconfigure((0, 1, 2, 3, 4, 5, 6), weight=0) # Make rows take minimal space
        self.grid_rowconfigure(7, weight=1) # Empty row to push elements up if needed

        # --- Widgets ---

        # Title
        self.title_label = customtkinter.CTkLabel(self, text="Video Converter", font=customtkinter.CTkFont(size=24, weight="bold"))
        self.title_label.grid(row=0, column=0, columnspan=3, padx=20, pady=(20, 30), sticky="ew")

        # Input File Selection
        self.input_label = customtkinter.CTkLabel(self, text="Input Video File:")
        self.input_label.grid(row=1, column=0, padx=(20, 10), pady=10, sticky="w")
        self.input_entry = customtkinter.CTkEntry(self, placeholder_text="No file selected...", state="readonly")
        self.input_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        self.input_button = customtkinter.CTkButton(self, text="Browse", command=self._browse_input_file)
        self.input_button.grid(row=1, column=2, padx=(10, 20), pady=10, sticky="e")

        # Output File Selection
        self.output_label = customtkinter.CTkLabel(self, text="Output MP4 File:")
        self.output_label.grid(row=2, column=0, padx=(20, 10), pady=10, sticky="w")
        self.output_entry = customtkinter.CTkEntry(self, placeholder_text="Output path will be set automatically (.mp4)", state="readonly")
        self.output_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
        self.output_button = customtkinter.CTkButton(self, text="Save As", command=self._browse_output_file)
        self.output_button.grid(row=2, column=2, padx=(10, 20), pady=10, sticky="e")

        # Delete Original Checkbox
        self.delete_original_checkbox = customtkinter.CTkCheckBox(self, text="Delete original file after successful conversion",
                                                                  command=self._update_delete_original_setting)
        self.delete_original_checkbox.grid(row=3, column=0, columnspan=2, padx=20, pady=10, sticky="w")
        # Set initial state from config
        initial_delete_original = self.config_manager.get_setting("processing_parameters.video_conversion.delete_original_after_processing", False)
        if initial_delete_original:
            self.delete_original_checkbox.select()
        else:
            self.delete_original_checkbox.deselect()

        # Progress Bar
        self.progress_label = customtkinter.CTkLabel(self, text="Progress: 0%")
        self.progress_label.grid(row=4, column=0, columnspan=3, padx=20, pady=(10, 5), sticky="w")
        self.progress_bar = customtkinter.CTkProgressBar(self)
        self.progress_bar.grid(row=5, column=0, columnspan=3, padx=20, pady=(0, 20), sticky="ew")
        self.progress_bar.set(0) # Initialize to 0%

        # Convert Button
        self.convert_button = customtkinter.CTkButton(self, text="Start Conversion", command=self._start_conversion)
        self.convert_button.grid(row=6, column=0, columnspan=3, padx=20, pady=20, sticky="ew")

        self._update_ui_state(False) # Initial state: disable convert button until files are chosen

    def _browse_input_file(self):
        """Opens a file dialog to select the input video file."""
        filetypes = [("Video files", "*.mp4 *.mov *.avi *.mkv *.webm *.mpg *.mpeg *.wmv"),
                     ("All files", "*.*")]
        file_path_str = filedialog.askopenfilename(title="Select Input Video File", filetypes=filetypes)
        if file_path_str:
            self.input_file_path = Path(file_path_str)
            self._update_entry_text(self.input_entry, str(self.input_file_path))
            self.logger.info(f"Input video file selected: {self.input_file_path}")
            self.app_instance.set_status(f"Selected: {self.input_file_path.name}")
            self._suggest_output_file_path()
            self._update_ui_state(True) # Enable convert button if input selected
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

            output_file_name = f"{self.input_file_path.stem}_converted.mp4" # Always suggest .mp4
            self.output_file_path = default_output_dir / output_file_name

            self._update_entry_text(self.output_entry, str(self.output_file_path))
            self.logger.info(f"Suggested output path: {self.output_file_path}")
        else:
            self._update_entry_text(self.output_entry, "Select an input file first.")
            self.output_file_path = None

    def _browse_output_file(self):
        """Opens a file dialog to select/save the output MP4 file."""
        if not self.input_file_path:
            messagebox.showwarning("No Input File", "Please select an input video file first.")
            self.logger.warning("Output file browse cancelled: No input file selected.")
            return

        initial_dir = self.config_manager.get_setting("output_directories.default_video_output")
        initial_filename = f"{self.input_file_path.stem}_converted.mp4"

        file_path_str = filedialog.asksaveasfilename(
            title="Save Converted Video As",
            initialdir=initial_dir,
            initialfile=initial_filename,
            filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")], # Only allow MP4
            defaultextension=".mp4" 
        )
        if file_path_str:
            self.output_file_path = Path(file_path_str)
            # Ensure the output has a .mp4 extension regardless of user input
            if self.output_file_path.suffix.lower() != '.mp4':
                self.output_file_path = self.output_file_path.with_suffix('.mp4')
                self.logger.warning(f"Output file extension changed to '.mp4': {self.output_file_path}")
            
            self._update_entry_text(self.output_entry, str(self.output_file_path))
            self.logger.info(f"Output video file selected: {self.output_file_path}")
            self.app_instance.set_status(f"Output will be: {self.output_file_path.name}")
        else:
            self.logger.info("Output video file selection cancelled.")
            self.app_instance.set_status("Output video file selection cancelled.")

    def _update_entry_text(self, entry_widget, text: str):
        """Helper to update a readonly CTkEntry."""
        entry_widget.configure(state="normal")
        entry_widget.delete(0, customtkinter.END)
        entry_widget.insert(0, text)
        entry_widget.configure(state="readonly")

    def _update_delete_original_setting(self):
        """Updates the 'delete_original_after_processing' setting in the config."""
        is_checked = self.delete_original_checkbox.get() == 1
        self.config_manager.set_setting("processing_parameters.video_conversion.delete_original_after_processing", is_checked)
        self.logger.info(f"Delete original (video conversion) setting updated to: {is_checked}")
        self.app_instance.set_status(f"Delete original (video conv): {is_checked}")

    def _update_progress_bar(self, progress_percentage: int):
        """
        Callback from VideoConverter to update the GUI progress bar and label.
        Schedules the actual GUI update on the main thread.
        """
        if self.master:
            self.master.after(1, self.__update_progress_gui, progress_percentage)
        else:
            self.logger.error("Attempted to update GUI on a None master object in _update_progress_bar.")

    def __update_progress_gui(self, progress_percentage: int):
        """Actual GUI update function, called via master.after. Runs on main thread."""
        self.progress_bar.set(progress_percentage / 100.0) # CTkProgressBar expects float from 0.0 to 1.0
        self.progress_label.configure(text=f"Progress: {progress_percentage}%")
        self.app_instance.set_status(f"Converting: {progress_percentage}%")
        self.master.update_idletasks() # Force GUI update


    def _update_ui_state(self, enable_convert_button: bool):
        """Sets the state of interactive widgets based on conversion status."""
        is_converting = self.video_converter.is_converting()

        self.convert_button.configure(state="disabled") # Default to disabled
        if enable_convert_button and not is_converting:
            self.convert_button.configure(state="normal")

        browse_state = "disabled" if is_converting else "normal"
        self.input_button.configure(state=browse_state)
        self.output_button.configure(state=browse_state)
        self.delete_original_checkbox.configure(state=browse_state)


    def _start_conversion(self):
        """
        Initiates the video conversion process in a separate thread
        to keep the GUI responsive.
        """
        if not self.input_file_path or not self.input_file_path.is_file():
            messagebox.showerror("Input Error", "Please select a valid input video file.")
            self.logger.warning("Conversion attempt failed: No valid input file selected.")
            self.app_instance.set_status("Conversion failed: No input.", level="warning")
            return

        if not self.output_file_path:
            messagebox.showerror("Output Error", "Please specify an output MP4 file path.")
            self.logger.warning("Conversion attempt failed: No output file specified.")
            self.app_instance.set_status("Conversion failed: No output path.", level="warning")
            return

        # Double check if conversion is already running
        if self.video_converter.is_converting():
            self.app_instance.set_status("Video conversion already in progress.", level="warning")
            return

        self._update_ui_state(False) # Disable UI during conversion
        self.progress_bar.set(0)
        self.progress_label.configure(text="Progress: 0%")
        self.app_instance.set_status("Video conversion started...", level="info")
        self.logger.info("Video conversion initiated via GUI.")

        delete_original = self.delete_original_checkbox.get() == 1

        # Run conversion in a separate thread
        self.conversion_thread = threading.Thread(
            target=self._run_conversion_task,
            args=(self.input_file_path, self.output_file_path, delete_original)
        )
        self.conversion_thread.start()

    def _run_conversion_task(self, input_path: Path, output_path: Path, delete_original: bool):
        """
        The actual video conversion task to be run in a separate thread.
        Handles calling the VideoConverter and updating the GUI with results.
        """
        success, message = self.video_converter.convert_video_to_mp4(
            input_filepath=input_path,
            output_filepath=output_path,
            delete_original=delete_original,
            progress_callback_func=self._update_progress_bar # Pass our GUI update method
        )

        # After conversion (success or failure), schedule result handling on the main thread
        if self.master:
            self.master.after(0, self._handle_conversion_result, success, message)
        else:
            self.logger.error("Master is None during _run_conversion_task completion. Cannot update GUI.")

    def _handle_conversion_result(self, success: bool, message: str):
        """
        Handles the result of the video conversion, updating status and re-enabling UI.
        Called on the main thread after conversion completes.
        """
        if success:
            messagebox.showinfo("Conversion Success", f"Video converted successfully!\nOutput: {message.split(': ')[-1]}")
            self.logger.info(f"Video conversion UI completed successfully: {message}")
            self.progress_label.configure(text="Conversion Complete!")
            self.progress_bar.set(1.0) # Ensure it shows 100%
        else:
            messagebox.showerror("Conversion Failed", f"Video conversion failed:\n{message}")
            self.logger.error(f"Video conversion UI failed: {message}")
            self.progress_label.configure(text="Conversion Failed!")
            self.progress_bar.set(0) # Reset progress on failure

        self._update_ui_state(True) # Re-enable UI elements
        self.app_instance.set_status(message, level="info" if success else "error")