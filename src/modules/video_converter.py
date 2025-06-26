import os
import shutil
from pathlib import Path
from moviepy import VideoFileClip
# from moviepy.config import change_settings # Removed: This import is causing the ImportError
from src.core.logger import get_application_logger
from src.core.config_manager import get_application_config
import logging
import subprocess # For creating dummy video in example usage

class VideoConverterError(Exception):
    """Custom exception for video conversion errors."""
    pass

class VideoConverter:
    """
    Handles video conversion operations from various formats to MP4.
    Designed for efficiency and includes logging for process tracking.
    """
    def __init__(self):
        self.logger = get_application_logger()
        self.config = get_application_config()
        self._is_converting = False # Internal state to track if a conversion is in progress
        self._external_progress_callback = None # To store the callback from the GUI

        # The FFmpeg binary path should be set as an environment variable (FFMPEG_BINARY)
        # by the application's main entry point (main.py) before this module is imported.
        # This ensures MoviePy finds the correct bundled FFmpeg executable.
        self.logger.info("VideoConverter initialized. Assuming FFMPEG_BINARY environment variable is set.")

    def _moviepy_progress_wrapper(self, current_time, total_duration):
        """
        Internal wrapper for MoviePy's progress_callback.
        Converts MoviePy's time-based progress to a 0-100 integer percentage
        and calls the external progress callback if available.
        """
        if self._external_progress_callback:
            if total_duration and total_duration > 0:
                progress_percentage = int(min(max(0.0, current_time / total_duration), 1.0) * 100)
            else:
                progress_percentage = 0 # Or a small initial value if duration is unknown
            
            # The actual GUI update needs to be scheduled on the main thread from the GUI page.
            # This wrapper simply calculates and passes the value.
            self._external_progress_callback(progress_percentage, f"Converting: {progress_percentage}%")
        self.logger.debug(f"MoviePy internal progress: {current_time:.2f}s / {total_duration:.2f}s")


    def convert_video_to_mp4(self, input_filepath: Path, output_filepath: Path, delete_original: bool = False, progress_callback_func=None):
        """
        Converts any video file to MP4 format.

        Args:
            input_filepath (Path): The path to the input video file.
            output_filepath (Path): The desired path for the output .mp4 file.
            delete_original (bool): If True, the original video file will be deleted after successful conversion.
            progress_callback_func (callable, optional): A function to call with progress updates (0-100 integer, message).
                                                        Signature: `progress_callback_func(progress_int: int, message: str)`
        Returns:
            tuple: (bool, str) - True if successful, False otherwise, and a message.
        """
        if self._is_converting:
            self.logger.warning("Attempted to start conversion while another is in progress.")
            return False, "Another conversion is already in progress. Please wait."

        self._is_converting = True
        self._external_progress_callback = progress_callback_func
        self.logger.info(f"Attempting to convert '{input_filepath}' to '{output_filepath}'")
        self._external_progress_callback(0, "Starting conversion...") # Initial progress update

        if not input_filepath.exists():
            self._is_converting = False
            self.logger.error(f"Input file not found: {input_filepath}")
            return False, f"Input file does not exist: {input_filepath}"
        
        if not input_filepath.is_file():
            self._is_converting = False
            self.logger.error(f"Input path is not a file: {input_filepath}")
            return False, f"Input path is not a file: {input_filepath}"

        # Ensure output directory exists
        output_filepath.parent.mkdir(parents=True, exist_ok=True)

        # Ensure output file has .mp4 extension
        if output_filepath.suffix.lower() != ".mp4":
            self.logger.warning(f"Output file extension changed from '{output_filepath.suffix}' to '.mp4'")
            output_filepath = output_filepath.with_suffix(".mp4")

        clip = None # Initialize clip to None
        try:
            self.logger.info(f"Trying to load video clip from: {input_filepath}")
            self._external_progress_callback(10, "Loading video clip...")
            try:
                # MoviePy implicitly uses the FFMPEG_BINARY environment variable set in main.py
                clip = VideoFileClip(str(input_filepath))
                self.logger.debug(f"Successfully loaded clip. Duration: {clip.duration}s, FPS: {clip.fps}, Size: {clip.size}")
            except Exception as e:
                self.logger.error(f"Failed to load video clip from {input_filepath}: {e}", exc_info=True)
                self._is_converting = False
                return False, f"Failed to load video: {e}. Please ensure the file is a valid video and FFmpeg is correctly installed and accessible via the 'FFMPEG_BINARY' environment variable."

            if clip.duration is None or clip.duration <= 0:
                self.logger.warning(f"Clip duration is zero or unknown for {input_filepath}. This often indicates a corrupt or invalid video file.")
                if self._external_progress_callback:
                    self._external_progress_callback(0, "Error: Invalid video file.")
                
                error_message = f"Video duration is zero or invalid for '{input_filepath}'. This typically means the video file is corrupted or not a recognized format for FFmpeg. Please try with a different video file."
                
                if clip is not None: # Ensure clip is closed if it was partially created
                    clip.close()
                self._is_converting = False
                return False, error_message

            # Perform the conversion. We specify codecs for broad compatibility and good quality.
            # libx264 is a highly efficient H.264 video encoder for MP4.
            # aac is a common and good quality audio encoder for MP4.
            self.logger.info(f"Exporting to MP4 (codec: libx264, audio_codec: aac) as: {output_filepath}")
            self._external_progress_callback(20, "Starting video encoding...")
            
            # Pass our internal wrapper to MoviePy's progress_callback
            clip.write_videofile(
                str(output_filepath),
                codec="libx264",
                audio_codec="aac",
                logger="bar",       # Show MoviePy's internal progress bar in console (useful for dev)
                progress_callback=self._moviepy_progress_wrapper,
                preset="medium",     # Adjust for speed vs. quality: "ultrafast", "superfast", "fast", "medium" (default), "slow", "slower", "veryslow")
                threads=os.cpu_count() # Utilize all available CPU cores for FFmpeg encoding
            )
            
            # Note: clip.close() moved to finally block for guaranteed resource release.

            # Ensure final progress update
            if self._external_progress_callback:
                self._external_progress_callback(100, "Conversion complete!") # Report 100% on success

            self.logger.info(f"Conversion completed successfully: {output_filepath}")

            if delete_original:
                self.logger.info(f"Attempting to delete original file: {input_filepath}")
                try:
                    os.remove(input_filepath)
                    self.logger.info(f"Original file deleted: {input_filepath}")
                except OSError as e:
                    self.logger.warning(f"Failed to delete original file {input_filepath}: {e}. Skipping deletion.")
            
            self._is_converting = False
            return True, f"Conversion complete! Saved to: {output_filepath}"

        except Exception as e:
            self._is_converting = False
            self.logger.error(f"An unexpected error occurred during video conversion from '{input_filepath}' to '{output_filepath}': {e}", exc_info=True)
            # Clean up partially created output file if error occurs
            if output_filepath.exists():
                try:
                    os.remove(output_filepath)
                    self.logger.info(f"Cleaned up partial output file: {output_filepath}")
                except Exception as cleanup_e:
                    self.logger.warning(f"Failed to clean up partial output file {output_filepath}: {cleanup_e}")
            
            return False, f"Conversion failed: {e}"
        finally:
            if clip is not None:
                try:
                    clip.close()
                except Exception as e:
                    self.logger.error(f"Error closing video clip in finally block: {e}")
            self._external_progress_callback = None # Clear callback to prevent stale references

    def is_converting(self) -> bool:
        """Returns True if a conversion is currently in progress, False otherwise."""
        return self._is_converting