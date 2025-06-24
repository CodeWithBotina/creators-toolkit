import os
import shutil
from pathlib import Path
from moviepy import VideoFileClip
# from moviepy.config import change_settings # This line is correctly commented out
from src.core.logger import get_application_logger
from src.core.config_manager import get_application_config
import logging # Import logging directly for lower-level control if needed
import subprocess # NEW: For potential use in testing dummy video creation

# --- NEW DIAGNOSTIC LINES (KEEP THESE!) ---
try:
    import moviepy
    print(f"DEBUG: MoviePy version being used: {moviepy.__version__}")
    print(f"DEBUG: MoviePy loaded from: {moviepy.__file__}")
except ImportError:
    print("DEBUG: MoviePy module not found.")
except AttributeError:
    print("DEBUG: MoviePy found, but __version__ or __file__ attribute missing.")
# --- END NEW DIAGNOSTIC LINES ---


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

        # Ensure moviepy knows where ffmpeg is, based on potential future config setting
        # For now, assumes ffmpeg is in PATH, but leaves room for configuration.
        # if self.config.get_setting("ffmpeg_path"):
        #    change_settings({"FFMPEG_BINARY": self.config.get_setting("ffmpeg_path")})
        
        # Suppress MoviePy's own excessive logging if not set via logger="bar"
        # logging.getLogger('moviepy').setLevel(logging.ERROR) # Only if we don't pass 'logger' to write_videofile

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
            
            # Call the external callback on the main thread if it's a CustomTkinter widget method
            # This is handled by the GUI side using .after()
            self._external_progress_callback(progress_percentage)
        self.logger.debug(f"MoviePy internal progress: {current_time:.2f}s / {total_duration:.2f}s")


    def convert_video_to_mp4(self, input_filepath: Path, output_filepath: Path, delete_original: bool = False, progress_callback_func=None):
        """
        Converts any video file to MP4 format.

        Args:
            input_filepath (Path): The path to the input video file.
            output_filepath (Path): The desired path for the output .mp4 file.
            delete_original (bool): If True, the original video file will be deleted after successful conversion.
            progress_callback_func (callable, optional): A function to call with progress updates (0-100 integer).
                                                        Signature: `progress_callback_func(progress_int: int)`
        Returns:
            tuple: (bool, str) - True if successful, False otherwise, and a message.
        Raises:
            # Exceptions are now caught internally and returned as (False, message)
        """
        if self._is_converting:
            self.logger.warning("Attempted to start conversion while another is in progress.")
            return False, "Another conversion is already in progress. Please wait."

        self._is_converting = True
        self._external_progress_callback = progress_callback_func
        self.logger.info(f"Attempting to convert '{input_filepath}' to '{output_filepath}'")

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
            try:
                clip = VideoFileClip(str(input_filepath))
                self.logger.debug(f"Successfully loaded clip. Duration: {clip.duration}s, FPS: {clip.fps}, Size: {clip.size}")
            except Exception as e:
                self.logger.error(f"Failed to load video clip from {input_filepath}: {e}", exc_info=True)
                self._is_converting = False
                return False, f"Failed to load video: {e}. Please ensure the file is a valid video and FFmpeg is correctly installed and accessible."

            if clip.duration is None or clip.duration <= 0:
                self.logger.warning(f"Clip duration is zero or unknown for {input_filepath}. This often indicates a corrupt or invalid video file.")
                if self._external_progress_callback:
                    self._external_progress_callback(0) # Report 0% as it's an invalid file
                
                # Check for 0 duration specifically from FFmpeg/MoviePy internal error
                # Note: The exact error message might vary slightly depending on FFmpeg version and actual issue
                if "video stream duration can not be less than 0" in str(e).lower() if 'e' in locals() else False:
                    error_message = f"Video duration is zero or invalid for '{input_filepath}'. This typically means the video file is corrupted or not a recognized format for FFmpeg. Please try with a different video file."
                else:
                    error_message = f"Video duration is zero or unknown for '{input_filepath}'. Please check the video file for corruption or if FFmpeg is correctly installed."
                
                if clip is not None: # Ensure clip is closed if it was partially created
                    clip.close()
                self._is_converting = False
                return False, error_message

            # Perform the conversion. We specify codecs for broad compatibility and good quality.
            # libx264 is a highly efficient H.264 video encoder for MP4.
            # aac is a common and good quality audio encoder for MP4.
            self.logger.info(f"Exporting to MP4 (codec: libx264, audio_codec: aac) as: {output_filepath}")
            
            # Pass our internal wrapper to MoviePy's progress_callback
            clip.write_videofile(
                str(output_filepath),
                codec="libx264",
                audio_codec="aac",
                logger="bar",       # Show MoviePy's internal progress bar in console (useful for dev)
                # verbose=False,      # THIS LINE HAS BEEN REMOVED AND SHOULD NOT BE HERE
                # progress_callback=self._moviepy_progress_wrapper, # Direct reference to the wrapper <--- UNCOMMENTED!
                preset="medium",     # Adjust for speed vs. quality: "ultrafast", "superfast", "fast", "medium" (default), "slow", "slower", "veryslow")
                threads=os.cpu_count() # Utilize all available CPU cores for FFmpeg encoding
            )
            
            # Note: clip.close() moved to finally block for guaranteed resource release.

            # Ensure final progress update
            if self._external_progress_callback:
                self._external_progress_callback(100) # Report 100% on success

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

# Example Usage (for testing this module independently)
if __name__ == "__main__":
    import time
    import subprocess # For creating dummy video

    # Setup logger for standalone testing
    current_dir = Path(__file__).parent
    logs_dir = current_dir.parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True) # Ensure logs directory exists
    from src.core.logger import AppLogger
    AppLogger(log_dir=str(logs_dir), log_level=logging.DEBUG)
    test_logger = get_application_logger()
    test_logger.info("--- Starting VideoConverter module test ---")

    test_input_dir = current_dir.parent.parent / "test_media"
    test_input_dir.mkdir(exist_ok=True)
    test_output_dir = current_dir.parent.parent / "test_output"
    test_output_dir.mkdir(exist_ok=True)

    dummy_avi_path = test_input_dir / "dummy_video.avi"
    dummy_mpg_path = test_input_dir / "another_dummy.mpg"
    dummy_mov_path = test_input_dir / "quicktime_dummy.mov"
    output_mp4_path_avi = test_output_dir / "dummy_video_converted.mp4"
    output_mp4_path_mpg = test_output_dir / "another_dummy_converted.mp4"
    output_mp4_path_mov = test_output_dir / "quicktime_dummy_converted.mp4"
    non_video_path = test_input_dir / "not_a_video.txt"

    def create_dummy_video(file_path: Path, video_codec: str, audio_codec: str):
        test_logger.info(f"Creating dummy video '{file_path}' (5 seconds black video)...")
        command = [
            "ffmpeg",
            "-y", # Overwrite output files without asking
            "-f", "lavfi", "-i", "color=c=black:s=640x480:d=5",
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
            "-c:v", video_codec,
            "-c:a", audio_codec,
            "-pix_fmt", "yuv420p", # For broader compatibility
            str(file_path)
        ]
        try:
            # Use subprocess.run for better control and error capture
            result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=10)
            test_logger.info(f"Dummy video '{file_path}' created successfully.")
            return True
        except subprocess.CalledProcessError as e:
            test_logger.error(f"Failed to create dummy video {file_path}. FFmpeg error: {e.stderr}")
            test_logger.error(f"STDOUT: {e.stdout}")
            return False
        except FileNotFoundError:
            test_logger.error("FFmpeg not found. Please ensure FFmpeg is installed and in your system's PATH.")
            return False
        except subprocess.TimeoutExpired:
            test_logger.error(f"FFmpeg command timed out while creating {file_path}. Is FFmpeg stuck?")
            return False
        except Exception as e:
            test_logger.error(f"An unexpected error occurred while creating dummy video: {e}")
            return False

    test_logger.info("Ensuring test media directory is clean...")
    for f in test_input_dir.iterdir():
        if f.is_file() and (f.suffix in [".avi", ".mpg", ".mov", ".txt"]):
            os.remove(f)
    for f in test_output_dir.iterdir():
        if f.is_file() and f.suffix == ".mp4":
            os.remove(f)

    # Create dummy video files for testing
    # Note: Using 'mp2' for MPG audio codec, as it's common for older MPG files.
    # If a specific error occurs, you might need to try 'aac' or 'libmp3lame'.
    created_avi = create_dummy_video(dummy_avi_path, "mpeg4", "aac")
    created_mpg = create_dummy_video(dummy_mpg_path, "mpeg1video", "mp2")
    created_mov = create_dummy_video(dummy_mov_path, "libx264", "aac") # Using libx264 for .mov for broader compatibility

    if created_avi and created_mpg and created_mov:
        test_logger.info("\n--- Starting conversion tests ---")
        converter = VideoConverter()

        def my_progress_callback(progress_value: int):
            """Simple progress callback for demonstration."""
            test_logger.info(f"Conversion Progress: {progress_value}%")

        # Test 1: Successful AVI to MP4 conversion
        test_logger.info(f"\n--- Test 1: Converting AVI to MP4 ({dummy_avi_path}) ---")
        success, message = converter.convert_video_to_mp4(dummy_avi_path, output_mp4_path_avi, progress_callback_func=my_progress_callback)
        test_logger.info(f"Result: {message} (Success: {success})")
        assert success and output_mp4_path_avi.exists()

        # Test 2: Successful MPG to MP4 conversion
        test_logger.info(f"\n--- Test 2: Converting MPG to MP4 ({dummy_mpg_path}) ---")
        success, message = converter.convert_video_to_mp4(dummy_mpg_path, output_mp4_path_mpg, progress_callback_func=my_progress_callback)
        test_logger.info(f"Result: {message} (Success: {success})")
        assert success and output_mp4_path_mpg.exists()

        # Test 3: Successful MOV to MP4 conversion
        test_logger.info(f"\n--- Test 3: Converting MOV to MP4 ({dummy_mov_path}) ---")
        success, message = converter.convert_video_to_mp4(dummy_mov_path, output_mp4_path_mov, progress_callback_func=my_progress_callback)
        test_logger.info(f"Result: {message} (Success: {success})")
        assert success and output_mp4_path_mov.exists()

        # Test 4: File not found
        test_logger.info(f"\n--- Test 4: Non-existent input file ({non_video_path}) ---")
        success, message = converter.convert_video_to_mp4(non_video_path, test_output_dir / "non_existent.mp4", progress_callback_func=my_progress_callback)
        test_logger.info(f"Result: {message} (Success: {success})")
        assert not success and "Input file does not exist" in message

        # Test 5: Invalid video file (simulate by creating a text file)
        test_logger.info(f"\n--- Test 5: Invalid video file (text file) ---")
        with open(non_video_path, "w") as f:
            f.write("This is not a video file.")
        success, message = converter.convert_video_to_mp4(non_video_path, test_output_dir / "invalid_input.mp4", progress_callback_func=my_progress_callback)
        test_logger.info(f"Result: {message} (Success: {success})")
        assert not success and "Failed to load video" in message # Expecting this specific error now
        os.remove(non_video_path) # Clean up dummy text file

        test_logger.info("\n--- All tests completed ---")
        test_logger.info("Please check the 'test_output' directory for converted videos.")
    else:
        test_logger.error("Could not create dummy video files. Please ensure FFmpeg is installed and in your system's PATH.")
        test_logger.info("Download FFmpeg from: https://ffmpeg.org/download.html")
    test_logger.info("--- VideoConverter module test completed ---")