import customtkinter
from tkinter import filedialog, messagebox
import threading
from pathlib import Path
import logging

# Import core and module components
from src.core.logger import get_application_logger
from src.core.config_manager import get_application_config
from src.modules.video_bg_remover import VideoBgRemover # Import our video background remover backend

class VideoBgRemovalPage(customtkinter.CTkFrame):
    """
    CustomTkinter Frame for Video Background Removal functionality.
    Allows users to select input/output files, adjust parameters, and start processing.
    """
    def __init__(self, master, app_instance):
        super().__init__(master, fg_color="transparent")
        self.logger = get_application_logger()
        self.config_manager = get_application_config()
        self.app_instance = app_instance # Reference to the main App class for status updates
        self.video_bg_remover = VideoBgRemover() # Instantiate the backend logic

        self.input_file_path = None
        self.output_file_path = None # Store the full output path suggested/chosen

        self.logger.info("Initializing VideoBgRemovalPage UI.")

        # Configure grid layout for this page
        self.grid_columnconfigure(0, weight=0) # Labels column
        self.grid_columnconfigure(1, weight=1) # Entry fields and controls column
        self.grid_columnconfigure(2, weight=0) # Buttons column
        self.grid_rowconfigure((0, 1, 2, 3, 4, 5, 6, 7), weight=0) # Make rows take minimal space
        self.grid_rowconfigure(8, weight=1) # Empty row to push elements up if needed

        # --- Widgets ---

        # Title
        self.title_label = customtkinter.CTkLabel(self, text="Video Background Removal", font=customtkinter.CTkFont(size=24, weight="bold"))
        self.title_label.grid(row=0, column=0, columnspan=3, padx=20, pady=(20, 30), sticky="ew")

        # Input File Selection
        self.input_label = customtkinter.CTkLabel(self, text="Input Video File:")
        self.input_label.grid(row=1, column=0, padx=(20, 10), pady=10, sticky="w")
        self.input_entry = customtkinter.CTkEntry(self, placeholder_text="No file selected...", state="readonly")
        self.input_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        self.input_button = customtkinter.CTkButton(self, text="Browse", command=self._browse_input_file)
        self.input_button.grid(row=1, column=2, padx=(10, 20), pady=10, sticky="e")

        # Output File Selection
        self.output_label = customtkinter.CTkLabel(self, text="Output Video File:")
        self.output_label.grid(row=2, column=0, padx=(20, 10), pady=10, sticky="w")
        self.output_entry = customtkinter.CTkEntry(self, placeholder_text="Output path will be set automatically...", state="readonly")
        self.output_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
        self.output_button = customtkinter.CTkButton(self, text="Save As", command=self._browse_output_file)
        self.output_button.grid(row=2, column=2, padx=(10, 20), pady=10, sticky="e")

        # Background Color Selector (for solid color replacement)
        self.bg_color_label = customtkinter.CTkLabel(self, text="New Background Color (Hex or None for Transparent):")
        self.bg_color_label.grid(row=3, column=0, padx=(20, 10), pady=10, sticky="w")
        self.bg_color_entry = customtkinter.CTkEntry(self, placeholder_text="#000000 (Black) or leave empty for transparent")
        self.bg_color_entry.grid(row=3, column=1, padx=10, pady=10, sticky="ew")
        # Set default from config
        initial_bg_color = self.config_manager.get_setting("processing_parameters.video_background_removal.default_background_color", "#000000")
        self.bg_color_entry.insert(0, initial_bg_color)
        self.bg_color_entry.bind("<FocusOut>", self._update_background_color_setting)
        self.bg_color_entry.bind("<Return>", self._update_background_color_setting)


        # Target Resolution for Processing (Optimization)
        self.target_res_label = customtkinter.CTkLabel(self, text="Target Processing Resolution (e.g., 640x360):")
        self.target_res_label.grid(row=4, column=0, padx=(20, 10), pady=10, sticky="w")
        self.target_res_entry = customtkinter.CTkEntry(self, placeholder_text="Leave empty for original resolution")
        self.target_res_entry.grid(row=4, column=1, padx=10, pady=10, sticky="ew")
        initial_target_res = self.config_manager.get_setting("processing_parameters.video_background_removal.target_resolution", "")
        if initial_target_res: # Only insert if not None
            self.target_res_entry.insert(0, initial_target_res)
        self.target_res_entry.bind("<FocusOut>", self._update_target_resolution_setting)
        self.target_res_entry.bind("<Return>", self._update_target_resolution_setting)


        # Delete Original Checkbox
        self.delete_original_checkbox = customtkinter.CTkCheckBox(self, text="Delete original file after successful processing",
                                                                  command=self._update_delete_original_setting)
        self.delete_original_checkbox.grid(row=5, column=0, columnspan=2, padx=20, pady=10, sticky="w")
        # Set initial state from config
        initial_delete_original = self.config_manager.get_setting("processing_parameters.video_background_removal.delete_original_after_processing", False)
        if initial_delete_original:
            self.delete_original_checkbox.select()
        else:
            self.delete_original_checkbox.deselect()

        # Progress Bar
        self.progress_label = customtkinter.CTkLabel(self, text="Progress: 0%")
        self.progress_label.grid(row=6, column=0, columnspan=3, padx=20, pady=(10, 5), sticky="w")
        self.progress_bar = customtkinter.CTkProgressBar(self)
        self.progress_bar.grid(row=7, column=0, columnspan=3, padx=20, pady=(0, 20), sticky="ew")
        self.progress_bar.set(0) # Initialize to 0%

        # Process Button
        self.process_button = customtkinter.CTkButton(self, text="Start Background Removal", command=self._start_processing)
        self.process_button.grid(row=8, column=0, columnspan=3, padx=20, pady=20, sticky="ew")

        self._update_ui_state(False) # Initial state: disable process button until files are chosen

    def _browse_input_file(self):
        """Opens a file dialog to select the input video file."""
        filetypes = [("Video files", "*.mp4 *.avi *.mov *.mkv *.webm"),
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

            # Default to .mp4 for most cases, but .webm if transparent background is chosen
            suggested_suffix = ".mp4"
            if not self.bg_color_entry.get().strip(): # If background color is empty/None
                suggested_suffix = ".webm" # WebM typically supports transparency better

            output_file_name = f"{self.input_file_path.stem}_nobg{suggested_suffix}"
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
        
        # Determine initial filename and filetypes based on background color choice
        if not self.bg_color_entry.get().strip(): # If background color is empty/None (transparent)
            initial_filename = f"{self.input_file_path.stem}_nobg.webm"
            filetypes = [("WebM files (Transparent)", "*.webm"), ("MOV files (Transparent)", "*.mov"), ("All files", "*.*")]
            defaultextension = ".webm"
        else: # Solid background
            initial_filename = f"{self.input_file_path.stem}_nobg.mp4"
            filetypes = [("MP4 files", "*.mp4"), ("All files", "*.*")]
            defaultextension = ".mp4"


        file_path_str = filedialog.asksaveasfilename(
            title="Save Processed Video As",
            initialdir=initial_dir,
            initialfile=initial_filename,
            filetypes=filetypes,
            defaultextension=defaultextension
        )
        if file_path_str:
            self.output_file_path = Path(file_path_str)
            # Ensure the output has a valid video extension, prioritizing transparency if selected
            current_suffix = self.output_file_path.suffix.lower()
            if not self.bg_color_entry.get().strip() and current_suffix not in ['.webm', '.mov']:
                self.output_file_path = self.output_file_path.with_suffix('.webm')
                self.logger.warning(f"Output file extension changed to '.webm' for transparency: {self.output_file_path}")
            elif self.bg_color_entry.get().strip() and current_suffix not in ['.mp4', '.avi', '.mov']:
                 self.output_file_path = self.output_file_path.with_suffix('.mp4')
                 self.logger.warning(f"Output file extension changed to '.mp4' for solid background: {self.output_file_path}")

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

    def _update_background_color_setting(self, event=None):
        """Updates the background color setting in config and adjusts output suggestion."""
        color_value = self.bg_color_entry.get().strip()
        if color_value and not (color_value.startswith("#") and len(color_value) == 7 and all(c in '0123456789abcdefABCDEF' for c in color_value[1:])):
            messagebox.showerror("Input Error", "Background color must be a valid hex color code (e.g., #RRGGBB) or left empty for transparent.")
            # Revert to last valid config value or default
            last_valid_color = self.config_manager.get_setting("processing_parameters.video_background_removal.default_background_color", "#000000")
            self.bg_color_entry.delete(0, customtkinter.END)
            self.bg_color_entry.insert(0, last_valid_color)
            self.logger.warning("Invalid input for background color.")
            self.app_instance.set_status("Invalid background color.", level="warning")
            return
        
        # If empty, store None to signal transparent background
        color_to_save = color_value if color_value else None
        self.config_manager.set_setting("processing_parameters.video_background_removal.default_background_color", color_to_save)
        self.logger.info(f"Background color setting updated to: {color_to_save}")
        self.app_instance.set_status(f"Background color: {color_to_save if color_to_save else 'Transparent'}")
        self._suggest_output_file_path() # Resuggest output path based on color choice


    def _update_target_resolution_setting(self, event=None):
        """Updates the target processing resolution setting."""
        resolution_value = self.target_res_entry.get().strip()
        if resolution_value and not (len(resolution_value.split('x')) == 2 and all(p.isdigit() for p in resolution_value.split('x'))):
            messagebox.showerror("Input Error", "Target resolution must be in 'WIDTHxHEIGHT' format (e.g., 640x480) or left empty.")
            # Revert to last valid config value or default
            last_valid_res = self.config_manager.get_setting("processing_parameters.video_background_removal.target_resolution", "")
            self.target_res_entry.delete(0, customtkinter.END)
            if last_valid_res:
                self.target_res_entry.insert(0, last_valid_res)
            self.logger.warning("Invalid input for target resolution.")
            self.app_instance.set_status("Invalid target resolution.", level="warning")
            return
        
        resolution_to_save = resolution_value if resolution_value else None
        self.config_manager.set_setting("processing_parameters.video_background_removal.target_resolution", resolution_to_save)
        self.logger.info(f"Target resolution setting updated to: {resolution_to_save}")
        self.app_instance.set_status(f"Target resolution: {resolution_to_save if resolution_to_save else 'Original'}")


    def _update_delete_original_setting(self):
        """Updates the 'delete_original_after_processing' setting in the config."""
        is_checked = self.delete_original_checkbox.get() == 1
        self.config_manager.set_setting("processing_parameters.video_background_removal.delete_original_after_processing", is_checked)
        self.logger.info(f"Delete original (video bg removal) setting updated to: {is_checked}")
        self.app_instance.set_status(f"Delete original (video bg removal): {is_checked}")

    def _update_progress_bar(self, progress_percentage: int, message: str):
        """
        Callback from VideoBgRemover to update the GUI progress bar and label.
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
        self.app_instance.set_status(f"Processing video background: {progress_percentage}% - {message}")
        self.master.update_idletasks() # Force GUI update

    def _update_ui_state(self, enable_process_button: bool):
        """Sets the state of interactive widgets based on processing status."""
        is_processing = self.video_bg_remover.is_processing()

        self.process_button.configure(state="disabled") # Default to disabled
        if enable_process_button and not is_processing:
            self.process_button.configure(state="normal")

        browse_state = "disabled" if is_processing else "normal"
        self.input_button.configure(state=browse_state)
        self.output_button.configure(state=browse_state)
        self.bg_color_entry.configure(state=browse_state)
        self.target_res_entry.configure(state=browse_state)
        self.delete_original_checkbox.configure(state=browse_state)


    def _start_processing(self):
        """
        Initiates the video background removal in a separate thread
        to keep the GUI responsive.
        """
        if not self.input_file_path or not self.input_file_path.is_file():
            messagebox.showerror("Input Error", "Please select a valid input video file.")
            self.logger.warning("Video background removal attempt failed: No valid input file selected.")
            self.app_instance.set_status("Processing failed: No input.", level="warning")
            return

        if not self.output_file_path:
            messagebox.showerror("Output Error", "Please specify an output video file path.")
            self.logger.warning("Video background removal attempt failed: No output file specified.")
            self.app_instance.set_status("Processing failed: No output path.", level="warning")
            return

        # Double check if processing is already running
        if self.video_bg_remover.is_processing():
            self.app_instance.set_status("Video background removal already in progress.", level="warning")
            return

        self._update_ui_state(False) # Disable UI during processing
        self.progress_bar.set(0)
        self.progress_label.configure(text="Progress: 0%")
        self.app_instance.set_status("Video background removal started...", level="info")
        self.logger.info("Video background removal initiated via GUI.")

        delete_original = self.delete_original_checkbox.get() == 1
        background_color = self.bg_color_entry.get().strip()
        background_color = background_color if background_color else None # Convert empty string to None
        target_resolution = self.target_res_entry.get().strip()
        target_resolution = target_resolution if target_resolution else None # Convert empty string to None


        # Run processing in a separate thread
        self.processing_thread = threading.Thread(
            target=self._run_processing_task,
            args=(self.input_file_path, self.output_file_path, delete_original, background_color, target_resolution)
        )
        self.processing_thread.start()

    def _run_processing_task(self, input_path: Path, output_path: Path, delete_original: bool, background_color: str, target_resolution: str):
        """
        The actual video background removal task to be run in a separate thread.
        Handles calling the VideoBgRemover and updating the GUI with results.
        """
        success, message = self.video_bg_remover.remove_video_background( # Corrected method name
            input_filepath=input_path,
            output_filepath=output_path,
            delete_original=delete_original,
            background_color=background_color,
            target_resolution=target_resolution, # Pass target_resolution
            progress_callback_func=self._update_progress_bar # Pass our GUI update method
        )

        # After processing (success or failure), schedule result handling on the main thread
        if self.master:
            self.master.after(0, self._handle_processing_result, success, message)
        else:
            self.logger.error("Master is None during _run_processing_task completion. Cannot update GUI.")

    def _handle_processing_result(self, success: bool, message: str):
        """
        Handles the result of the video background removal, updating status and re-enabling UI.
        Called on the main thread after processing completes.
        """
        if success:
            messagebox.showinfo("Processing Success", f"Video background removed successfully!\nOutput: {message.split(': ')[-1]}")
            self.logger.info(f"Video background removal UI completed successfully: {message}")
            self.progress_label.configure(text="Processing Complete!")
            self.progress_bar.set(1.0) # Ensure it shows 100%
            
            # Log to history
            self.app_instance.history_manager.log_task(
                "Video Background Removal",
                self.input_file_path,
                self.output_file_path,
                "Completed",
                message,
                {"background_color": self.bg_color_entry.get().strip(), "target_resolution": self.target_res_entry.get().strip()}
            )
        else:
            messagebox.showerror("Processing Failed", f"Video background removal failed:\n{message}")
            self.logger.error(f"Video background removal UI failed: {message}")
            self.progress_label.configure(text="Processing Failed!")
            self.progress_bar.set(0) # Reset progress on failure

            # Log to history
            self.app_instance.history_manager.log_task(
                "Video Background Removal",
                self.input_file_path,
                self.output_file_path,
                "Failed",
                message,
                {"background_color": self.bg_color_entry.get().strip(), "target_resolution": self.target_res_entry.get().strip()}
            )


        self._update_ui_state(True) # Re-enable UI elements
        self.app_instance.set_status(message, level="info" if success else "error")