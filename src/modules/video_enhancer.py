import os
import shutil
import subprocess
from pathlib import Path
import logging
import json # For parsing FFmpeg output if needed for more advanced checks

from src.core.logger import get_application_logger
from src.core.config_manager import get_application_config

class VideoEnhancementError(Exception):
    """Custom exception for video enhancement errors."""
    pass

class VideoEnhancer:
    """
    Handles video enhancement operations using FFmpeg filters.
    Applies denoising, sharpening, contrast, saturation, gamma, brightness, and shadow/highlight adjustments.
    Designed for efficiency and includes progress tracking for UI updates.
    """
    def __init__(self):
        self.logger = get_application_logger()
        self.config = get_application_config()
        self._is_processing = False # Internal state to track if a process is in progress
        self._external_progress_callback = None # Callback for GUI progress updates
        
        self.logger.info("VideoEnhancer initialized.")

    def _update_progress(self, progress_percentage: int, message: str, level: str = "info"):
        """
        Internal helper to update progress and log messages.
        """
        if self._external_progress_callback:
            self._external_progress_callback(progress_percentage, message)
        self.logger.log(getattr(logging, level.upper()), f"VIDEO_ENHANCE_PROGRESS: {message} ({progress_percentage}%)")

    def _get_ffmpeg_filter_string(self) -> str:
        """
        Constructs the FFmpeg filter complex string based on current configuration.
        """
        params = self.config.get_setting("processing_parameters.video_enhancement")
        
        filters = []

        # Denoising (hqdn3d filter)
        # For simplicity, we use a single strength value for luma_spatial, chroma_spatial, luma_tmp, chroma_tmp
        # Default: 2.0 (based on original stylize-videos.py)
        denoise_strength = params.get("denoise_strength", 2.0)
        if denoise_strength > 0:
            filters.append(f"hqdn3d={denoise_strength}:{denoise_strength}:{denoise_strength}:{denoise_strength}")
            self.logger.debug(f"Added hqdn3d filter with strength: {denoise_strength}")

        # Sharpening (unsharp filter)
        # unsharp=luma_matrix_width:luma_matrix_height:luma_amount:chroma_matrix_width:chroma_matrix_height:chroma_amount
        # Common values for a mild sharpen: 5:5:1.0:5:5:0.0
        sharpen_strength = params.get("sharpen_strength", 0.5)
        if sharpen_strength > 0:
            # Adjust the third parameter (amount) based on strength
            # A value around 0.5-1.5 is common for unsharp
            amount = 0.5 + (sharpen_strength * 1.0) # Scale strength from 0-0.5 to 0.5-1.5
            filters.append(f"unsharp=5:5:{amount}:5:5:0.0") # Apply only to luma for simplicity
            self.logger.debug(f"Added unsharp filter with strength: {sharpen_strength} (amount: {amount})")

        # Color and Tone adjustments (eq filter)
        # eq=contrast:brightness:saturation:gamma:gamma_r:gamma_g:gamma_b:gamma_weight:eval:initial_eval:color_pre_scale
        contrast = params.get("contrast_enhance", 1.1)
        brightness = params.get("brightness", 0.0)
        saturation = params.get("saturation", 1.1)
        gamma = params.get("gamma", 1.0) # Overall gamma
        shadow_highlight = params.get("shadow_highlight", 0.2) # This is a custom interpretation for eq

        # The 'eq' filter does not directly have a shadow/highlight parameter.
        # We can simulate a mild shadow/highlight adjustment using gamma, brightness, or contrast subtly,
        # but for true shadow/highlight, a more complex filter or separate passes might be needed.
        # For this implementation, we'll primarily use the direct eq parameters.
        # If shadow_highlight is used, it could gently adjust contrast or gamma range.
        
        # A simple approach for shadow/highlight might be to slightly increase contrast if shadow_highlight > 0
        # or adjust gamma. Given the complexity, let's keep it to direct eq parameters for now.
        # Original script used 'shadow_highlight', implying a subtle curve adjustment.
        # For direct eq, we use standard values.
        
        # Applying a slight boost based on shadow_highlight to contrast/brightness as a proxy
        adjusted_contrast = contrast + (shadow_highlight * 0.1) # Small boost to contrast
        adjusted_brightness = brightness + (shadow_highlight * 0.05) # Small boost to brightness

        filters.append(f"eq=contrast={adjusted_contrast}:brightness={adjusted_brightness}:saturation={saturation}:gamma={gamma}")
        self.logger.debug(f"Added eq filter with contrast={adjusted_contrast}, brightness={adjusted_brightness}, saturation={saturation}, gamma={gamma}")


        # Combine all filters
        filter_complex_string = ",".join(filters)
        self.logger.debug(f"Constructed FFmpeg filter string: {filter_complex_string}")
        return filter_complex_string

    def enhance_video(self, input_filepath: Path, output_filepath: Path, delete_original: bool = False, progress_callback_func=None):
        """
        Enhances a video file using FFmpeg filters based on configured parameters.

        Args:
            input_filepath (Path): The path to the input video file.
            output_filepath (Path): The desired path for the output enhanced video file.
            delete_original (bool): If True, the original video file will be deleted after successful processing.
            progress_callback_func (callable, optional): A function to call with progress updates (0-100 integer, message).
                                                        Signature: `progress_callback_func(progress_int: int, message: str)`
        Returns:
            tuple: (bool, str) - True if successful, False otherwise, and a message.
        """
        if self._is_processing:
            self.logger.warning("Attempted to start video enhancement while another is in progress.")
            return False, "Another video enhancement task is already in progress. Please wait."

        self._is_processing = True
        self._external_progress_callback = progress_callback_func
        self.logger.info(f"Attempting to enhance video from '{input_filepath}' to '{output_filepath}'")
        self._update_progress(0, "Starting video enhancement...")

        if not input_filepath.exists():
            self._is_processing = False
            self.logger.error(f"Input video file not found: {input_filepath}")
            return False, f"Input video file does not exist: {input_filepath}"
        
        if not input_filepath.is_file():
            self._is_processing = False
            self.logger.error(f"Input path is not a file: {input_filepath}")
            return False, f"Input path is not a file: {input_filepath}"

        # Ensure output directory exists
        output_filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Get the filter string
        filter_string = self._get_ffmpeg_filter_string()

        # Construct FFmpeg command
        # Use -i for input, -vf for video filters, -c:v for video codec, -c:a for audio codec, -preset for encoding speed/quality
        # -y to overwrite output file without asking
        # Add '-progress pipe:1' to capture progress. This requires parsing stderr/stdout.
        # For simplicity in this example, we'll rely on the exit code and overall duration,
        # but for real-time progress, a more complex subprocess output parsing would be needed.

        # A more robust FFmpeg command for quality and compatibility
        ffmpeg_command = [
            "ffmpeg",
            "-i", str(input_filepath),
            "-vf", filter_string,
            "-c:v", "libx264",         # High quality H.264 video codec
            "-preset", "medium",       # Encoding preset (ultrafast, superfast, medium, slow, etc.)
            "-crf", "23",              # Constant Rate Factor (0-51, lower is higher quality, 23 is good default)
            "-c:a", "aac",             # AAC audio codec
            "-b:a", "192k",            # Audio bitrate
            "-y",                      # Overwrite output file if it exists
            str(output_filepath)
        ]

        self.logger.info(f"Executing FFmpeg command: {' '.join(ffmpeg_command)}")
        self._update_progress(10, "Starting FFmpeg process...")

        try:
            # We'll run FFmpeg in a subprocess. The progress parsing from FFmpeg's stderr
            # is complex. For a simple UI, we'll do block updates, or rely on a wrapper
            # that provides more granular info.
            
            # This simplified approach relies on FFmpeg's general progress via duration.
            # For real-time frame-by-frame updates, you'd monitor stderr for 'frame=', 'time=', 'speed=' lines.
            
            # Fetch video duration for progress calculation if possible
            # moviepy's VideoFileClip can do this, but it also uses FFprobe internally.
            # A direct FFprobe call might be more reliable if MoviePy is causing issues.
            
            # Let's get duration using FFprobe explicitly to be robust
            duration_command = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(input_filepath)
            ]
            
            try:
                probe_result = subprocess.run(duration_command, capture_output=True, text=True, check=True)
                total_duration = float(probe_result.stdout.strip())
                self.logger.debug(f"Video duration detected: {total_duration} seconds.")
            except (subprocess.CalledProcessError, ValueError) as e:
                self.logger.warning(f"Could not get video duration with ffprobe: {e}. Progress bar might not be accurate.", exc_info=True)
                total_duration = 0 # Cannot get duration, progress bar will be limited

            # Run the main FFmpeg command
            process = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
            
            current_time = 0.0
            last_progress = 0

            # This is a basic way to read stderr for progress.
            # FFmpeg's progress output format varies slightly by version and flags.
            # The 'time=' field is usually reliable.
            self._update_progress(15, "Processing video frames...")
            for line in process.stderr:
                # self.logger.debug(f"FFmpeg stderr: {line.strip()}") # Uncomment for detailed FFmpeg output debugging
                if "time=" in line and total_duration > 0:
                    try:
                        time_str = line.split("time=")[1].split(" ")[0].strip()
                        # Format: HH:MM:SS.ms
                        h, m, s = map(float, time_str.split(':'))
                        current_time = h * 3600 + m * 60 + s
                        
                        progress_percentage = int((current_time / total_duration) * 100)
                        if progress_percentage > last_progress + 1 or progress_percentage == 100: # Update only if significant change or complete
                            last_progress = progress_percentage
                            self._update_progress(min(progress_percentage, 99), f"Processing {time_str} / {total_duration:.2f}s...")
                    except (ValueError, IndexError):
                        pass # Ignore lines that don't parse as time progress
            
            process.wait() # Wait for the process to finish
            
            if process.returncode != 0:
                error_output = process.stderr.read()
                self.logger.error(f"FFmpeg failed with error code {process.returncode}: {error_output}")
                raise VideoEnhancementError(f"FFmpeg conversion failed: {error_output.strip()}")

            # Ensure final progress update
            self._update_progress(100, "Video enhancement complete!")
            self.logger.info(f"Video enhancement completed successfully: {output_filepath}")

            if delete_original:
                self.logger.info(f"Attempting to delete original file: {input_filepath}")
                try:
                    os.remove(input_filepath)
                    self.logger.info(f"Original file deleted: {input_filepath}")
                except OSError as e:
                    self.logger.warning(f"Failed to delete original file {input_filepath}: {e}. Skipping deletion.")
            
            self._is_processing = False
            return True, f"Video enhancement complete! Saved to: {output_filepath}"

        except VideoEnhancementError as e:
            self._is_processing = False
            self.logger.error(f"Video enhancement failed: {e}", exc_info=True)
            if output_filepath.exists():
                try:
                    os.remove(output_filepath)
                    self.logger.info(f"Cleaned up partial output file: {output_filepath}")
                except Exception as cleanup_e:
                    self.logger.warning(f"Failed to clean up partial output file {output_filepath}: {cleanup_e}")
            return False, f"Video enhancement failed: {e}"
        except FileNotFoundError:
            self._is_processing = False
            self.logger.error("FFmpeg or FFprobe executable not found in PATH. Please install FFmpeg.")
            return False, "FFmpeg or FFprobe not found. Please ensure FFmpeg is installed and in your system's PATH."
        except Exception as e:
            self._is_processing = False
            self.logger.error(f"An unexpected error occurred during video enhancement from '{input_filepath}' to '{output_filepath}': {e}", exc_info=True)
            if output_filepath.exists():
                try:
                    os.remove(output_filepath)
                    self.logger.info(f"Cleaned up partial output file: {output_filepath}")
                except Exception as cleanup_e:
                    self.logger.warning(f"Failed to clean up partial output file {output_filepath}: {cleanup_e}")
            return False, f"Video enhancement failed: {e}"
        finally:
            self._external_progress_callback = None # Clear callback to prevent stale references


    def is_processing(self) -> bool:
        """Returns True if a video enhancement task is currently in progress, False otherwise."""
        return self._is_processing

# Example Usage (for testing this module independently)
if __name__ == "__main__":
    import time
    
    # Setup logger for standalone testing
    current_dir = Path(__file__).parent
    logs_dir = current_dir.parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True) # Ensure logs directory exists
    from src.core.logger import AppLogger
    AppLogger(log_dir=str(logs_dir), log_level=logging.DEBUG)
    test_logger = get_application_logger()
    test_logger.info("--- Starting VideoEnhancer module test ---")

    test_input_dir = current_dir.parent.parent / "test_media"
    test_input_dir.mkdir(exist_ok=True)
    test_output_dir = current_dir.parent.parent / "test_output"
    test_output_dir.mkdir(exist_ok=True)

    dummy_video_path = test_input_dir / "test_video_for_enhance.mp4" # Ensure this file exists for testing
    output_enhanced_video_path = test_output_dir / "enhanced_test_video.mp4"

    # Create a dummy video file if it doesn't exist (for testing purposes)
    # This requires FFmpeg to be in PATH for the test script itself
    if not dummy_video_path.exists():
        test_logger.info(f"Creating a dummy video file: {dummy_video_path} (5 seconds black video)...")
        try:
            subprocess.run([
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "color=c=black:s=640x480:d=5:r=25", # 5 seconds, 640x480, 25 FPS
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100", # Dummy audio
                "-t", "5", # Duration
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                str(dummy_video_path)
            ], check=True, capture_output=True, text=True, timeout=15)
            test_logger.info("Dummy video file created.")
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            test_logger.error(f"Could not create dummy video file: {e}. Please manually create {dummy_video_path} for testing. Ensure FFmpeg is in PATH.", exc_info=True)
            dummy_video_path = None # Mark as not available for testing

    if dummy_video_path and dummy_video_path.exists():
        test_logger.info("\n--- Starting video enhancement tests ---")
        enhancer = VideoEnhancer()

        def my_progress_callback(progress_value: int, message: str):
            """Simple progress callback for demonstration."""
            test_logger.info(f"Enhancement Progress: {progress_value}% - {message}")

        # Test 1: Successful video enhancement
        test_logger.info(f"\n--- Test 1: Enhancing video ({dummy_video_path}) ---")
        success, message = enhancer.enhance_video(dummy_video_path, output_enhanced_video_path, progress_callback_func=my_progress_callback)
        test_logger.info(f"Result: {message} (Success: {success})")
        assert success and output_enhanced_video_path.exists()

        # Test 2: File not found
        test_logger.info(f"\n--- Test 2: Non-existent input file ---")
        non_existent_path = test_input_dir / "non_existent_video.mp4"
        success, message = enhancer.enhance_video(non_existent_path, test_output_dir / "non_existent_output.mp4", progress_callback_func=my_progress_callback)
        test_logger.info(f"Result: {message} (Success: {success})")
        assert not success and "Input video file does not exist" in message

        test_logger.info("\n--- All video enhancement tests completed ---")
        test_logger.info("Please check the 'test_output' directory for enhanced video files.")
    else:
        test_logger.error("Skipping video enhancement tests due to missing dummy video file or creation failure. Please ensure FFmpeg is installed and accessible.")
    test_logger.info("--- VideoEnhancer module test completed ---")
