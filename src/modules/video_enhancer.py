import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import os
import numpy as np
import cv2 # For potential frame analysis or pre-processing if needed

from moviepy import VideoFileClip
# from moviepy.config import change_settings # Uncomment if ffmpeg path needs explicit setting

from src.core.logger import get_application_logger
from src.core.config_manager import get_application_config

class VideoEnhancerError(Exception):
    """Custom exception for video enhancement errors."""
    pass

class VideoEnhancer:
    """
    Handles video quality enhancement operations.
    Applies various FFmpeg filters (denoise, sharpen, color adjustments) to video files.
    Designed for efficiency and includes logging for process tracking.
    """
    def __init__(self):
        self.logger = get_application_logger()
        self.config = get_application_config()
        self._is_processing = False # Internal state to track if a conversion is in progress
        self._external_progress_callback = None # To store the callback from the GUI

        self.logger.info("VideoEnhancer initialized.")

    def _update_progress(self, progress_percentage: int, message: str, level: str = "info"):
        """
        Internal helper to update progress and log messages.
        """
        if self._external_progress_callback:
            # Ensure progress_percentage is within [0, 100]
            progress_percentage = max(0, min(100, progress_percentage))
            self._external_progress_callback(progress_percentage, message)
        self.logger.log(getattr(logging, level.upper()), f"VIDEO_ENHANCE_PROGRESS: {message} ({progress_percentage}%)")


    def _build_ffmpeg_filter_string(self, enhancement_params: Dict[str, Any]) -> str:
        """
        Builds a complex FFmpeg filter string based on provided enhancement parameters.
        Parameters are typically loaded from config_manager.

        Args:
            enhancement_params (Dict[str, Any]): Dictionary containing enhancement settings.
                                                 Expected keys (with example defaults):
                                                 - denoise_strength (float, default 2.0)
                                                 - sharpen_strength (float, default 0.5)
                                                 - contrast_enhance (float, default 1.0)
                                                 - saturation (float, default 1.0)
                                                 - gamma (float, default 1.0)
                                                 - brightness (float, default 0.0)
                                                 - shadow_highlight (float, default 0.0)
        Returns:
            str: A single FFmpeg filter string (e.g., "hqdn3d,unsharp,eq").
        """
        filters = []

        # Denoise (hqdn3d filter)
        denoise_strength = enhancement_params.get("denoise_strength", 2.0)
        if denoise_strength > 0:
            # hqdn3d expects strength for luma, chroma. Using same for all.
            filters.append(f"hqdn3d={denoise_strength}:{denoise_strength}:{denoise_strength}:{denoise_strength}")
            self.logger.debug(f"Added hqdn3d denoise filter with strength: {denoise_strength}")

        # Sharpen (unsharp filter)
        sharpen_strength = enhancement_params.get("sharpen_strength", 0.5)
        if sharpen_strength > 0:
            # unsharp: luma_matrix_width:luma_matrix_height:luma_amount:chroma_matrix_width:chroma_matrix_height:chroma_amount
            # A common setup: 5x5 matrix, amount typically 0.5 to 2.0
            amount = 0.5 + (sharpen_strength * 1.5) # Scale strength to a reasonable FFmpeg range (0.5 to 2.0)
            filters.append(f"unsharp=5:5:{amount}:5:5:0.0") # Apply to luma only
            self.logger.debug(f"Added unsharp sharpen filter with strength: {sharpen_strength} (amount={amount})")

        # Color/Exposure Adjustments (eq filter)
        contrast = enhancement_params.get("contrast_enhance", 1.0)
        saturation = enhancement_params.get("saturation", 1.0)
        gamma = enhancement_params.get("gamma", 1.0)
        brightness = enhancement_params.get("brightness", 0.0)
        shadow_highlight = enhancement_params.get("shadow_highlight", 0.0) # Used to adjust contrast/brightness subtly

        # Adjust contrast and brightness based on shadow_highlight
        # Positive shadow_highlight: lifts shadows, reduces highlights (milder contrast)
        # Negative shadow_highlight: darkens shadows, brightens highlights (stronger contrast)
        adjusted_contrast = contrast + (shadow_highlight * 0.1) # Small effect
        adjusted_brightness = brightness + (shadow_highlight * 0.05) # Even smaller effect

        # Clamp values to reasonable ranges for FFmpeg eq filter
        adjusted_contrast = max(0.0, min(2.0, adjusted_contrast))
        saturation = max(0.0, min(3.0, saturation))
        gamma = max(0.1, min(10.0, gamma))
        adjusted_brightness = max(-1.0, min(1.0, adjusted_brightness))


        color_adjustments = []
        if adjusted_contrast != 1.0:
            color_adjustments.append(f"contrast={adjusted_contrast:.2f}")
        if saturation != 1.0:
            color_adjustments.append(f"saturation={saturation:.2f}")
        if gamma != 1.0:
            color_adjustments.append(f"gamma={gamma:.2f}")
        if adjusted_brightness != 0.0:
            color_adjustments.append(f"brightness={adjusted_brightness:.2f}")
        
        if color_adjustments:
            filters.append(f"eq={':'.join(color_adjustments)}")
            self.logger.debug(f"Added eq color adjustments: {', '.join(color_adjustments)}")

        return ",".join(filters) if filters else ""

    def enhance_video(
        self, 
        input_filepath: Path, 
        output_filepath: Path, 
        enhancement_params: Dict[str, Any],
        progress_callback_func=None
    ) -> Tuple[bool, str]:
        """
        Applies video enhancements to an input video and saves the result.

        Args:
            input_filepath (Path): Path to the input video file.
            output_filepath (Path): Desired path for the output enhanced video.
            enhancement_params (Dict[str, Any]): Dictionary of enhancement settings.
            progress_callback_func (callable, optional): Callback for progress updates.
                                                          Expected signature: func(percentage: int, message: str)
        Returns:
            Tuple[bool, str]: True if successful, False otherwise, and a message.
        """
        if self._is_processing:
            self.logger.warning("Attempted to start video enhancement while another is in progress.")
            return False, "Another video enhancement task is already in progress. Please wait."

        self._is_processing = True
        self._external_progress_callback = progress_callback_func

        self.logger.info(f"Starting video enhancement for: {input_filepath}")
        self._update_progress(0, "Initializing video enhancement...")

        try:
            if not input_filepath.exists() or not input_filepath.is_file():
                raise VideoEnhancerError(f"Input video file not found or is not a file: {input_filepath}")
            
            output_filepath.parent.mkdir(parents=True, exist_ok=True) # Ensure output directory exists

            # Build the FFmpeg filter string
            filter_string = self._build_ffmpeg_filter_string(enhancement_params)
            
            if not filter_string:
                self.logger.info("No enhancement filters specified. Copying input video to output.")
                shutil.copy(input_filepath, output_filepath)
                self._update_progress(100, "No enhancements applied, file copied.", "info")
                self._is_processing = False
                return True, f"No enhancements applied. File copied to: {output_filepath}"

            self._update_progress(10, f"Applying filters: {filter_string}")

            # MoviePy uses FFmpeg under the hood. Using VideoFileClip.write_videofile
            # directly is often the most straightforward way to apply filters.
            
            clip = VideoFileClip(str(input_filepath))

            # Apply video filters. MoviePy's internal `fl_image` is typically for frame-by-frame
            # custom Python processing. For FFmpeg filters, it's more direct to pass them
            # to `ffmpeg_options` or rely on MoviePy's `fx` methods if available.
            # However, for complex filter chains like those built here, using direct `ffmpeg_params`
            # during write_videofile is most robust.
            
            # Temporary output path for MoviePy's internal processing if it creates one
            temp_output = output_filepath.with_suffix(".temp.mp4")

            self._update_progress(20, "Encoding video with enhancements...")

            # FFmpeg command to apply filters (more robust than MoviePy's fx for complex chains)
            # This method directly calls subprocess, bypassing some MoviePy overhead for filters.
            command = [
                "ffmpeg",
                "-i", str(input_filepath),
                "-vf", filter_string, # Video filtergraph
                "-c:v", "libx264",    # Video codec (H.264)
                "-preset", "medium",  # Encoding preset (medium for balance of speed/quality)
                "-crf", "23",         # Constant Rate Factor for quality (23 is good default)
                "-c:a", "copy",       # Copy audio stream without re-encoding
                "-y",                 # Overwrite output file without asking
                "-progress", "pipe:1", # Enable progress reporting to stdout
                str(output_filepath)
            ]

            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True, creationflags=subprocess.CREATE_NO_WINDOW)

            duration_secs = None
            if clip.duration:
                duration_secs = clip.duration
                self.logger.debug(f"Video duration detected: {duration_secs:.2f} seconds.")

            for line in process.stdout:
                if "frame=" in line and "time=" in line and duration_secs:
                    try:
                        # Extract time (HH:MM:SS.ms)
                        time_str_match = next((s for s in line.split() if s.startswith("time=")), None)
                        if time_str_match:
                            time_parts = list(map(float, time_str_match.split("=")[1].split(':')))
                            current_time_secs = time_parts[0] * 3600 + time_parts[1] * 60 + time_parts[2]
                            percentage = int((current_time_secs / duration_secs) * 100)
                            self._update_progress(percentage, "Applying enhancements...")
                    except Exception as prog_e:
                        self.logger.debug(f"Error parsing FFmpeg progress line: {line.strip()} - {prog_e}")
                elif "progress=end" in line:
                    break # End of progress

            process.wait() # Wait for the process to finish
            
            if process.returncode != 0:
                stderr_output = process.stderr.read()
                self.logger.error(f"FFmpeg enhancement failed with error: {stderr_output}", exc_info=True)
                raise VideoEnhancerError(f"FFmpeg enhancement failed: {stderr_output.strip()}")

            self._update_progress(100, "Video enhancement completed successfully!")
            self.logger.info(f"Video enhancement completed: {output_filepath}")

            if enhancement_params.get('delete_original_after_processing', False):
                self.logger.info(f"Attempting to delete original file: {input_filepath}")
                try:
                    os.remove(input_filepath)
                    self.logger.info(f"Original file deleted: {input_filepath}")
                except OSError as e:
                    self.logger.warning(f"Failed to delete original file {input_filepath}: {e}. Skipping deletion.")
            
            self._is_processing = False
            return True, f"Video enhanced successfully! Saved to: {output_filepath}"

        except VideoEnhancerError as e:
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
            self.logger.critical("FFmpeg executable not found. Please ensure FFmpeg is installed and in your PATH.", exc_info=True)
            return False, "FFmpeg not found. Please install FFmpeg and add it to your system's PATH."
        except Exception as e:
            self._is_processing = False
            self.logger.critical(f"An unexpected critical error occurred during video enhancement from '{input_filepath}': {e}", exc_info=True)
            if output_filepath.exists():
                try:
                    os.remove(output_filepath)
                    self.logger.info(f"Cleaned up partial output file: {output_filepath}")
                except Exception as cleanup_e:
                    self.logger.warning(f"Failed to clean up partial output file {output_filepath}: {cleanup_e}")
            return False, f"An unexpected error occurred during enhancement: {e}"
        finally:
            self._external_progress_callback = None # Clear callback

    def is_processing(self) -> bool:
        """Returns True if a video enhancement task is currently in progress, False otherwise."""
        return self._is_processing

if __name__ == "__main__":
    # Example Usage and Testing for VideoEnhancer module
    import time
    import shutil
    
    # Setup logger for standalone testing
    current_dir = Path(__file__).parent
    logs_dir = current_dir.parent.parent / "logs"
    config_dir = current_dir.parent.parent / "config"
    logs_dir.mkdir(exist_ok=True) # Ensure logs directory exists
    config_dir.mkdir(exist_ok=True) # Ensure config directory exists

    from src.core.logger import AppLogger
    from src.core.config_manager import ConfigManager
    AppLogger(log_dir=str(logs_dir), log_level=logging.DEBUG)
    ConfigManager(config_dir=str(config_dir)) 
    test_logger = get_application_logger()
    test_logger.info("--- Starting VideoEnhancer module isolated test ---")

    test_input_dir = current_dir.parent.parent / "test_media"
    test_input_dir.mkdir(exist_ok=True)
    test_output_dir = current_dir.parent.parent / "test_output"
    test_output_dir.mkdir(exist_ok=True)

    dummy_video_path = test_input_dir / "test_video_for_enhancement.mp4" 
    output_enhanced_video_path = test_output_dir / "enhanced_video.mp4"

    # Create a dummy video file if it doesn't exist
    if not dummy_video_path.exists():
        test_logger.info(f"Creating a dummy video file: {dummy_video_path} (5 seconds, testcard with audio)...")
        try:
            subprocess.run([
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "testsrc=size=640x480:rate=30:duration=5", # 5s test pattern
                "-f", "lavfi", "-i", "sine=frequency=1000:duration=5",          # 5s sine wave audio
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", "-preset", "ultrafast",
                "-c:a", "aac", "-b:a", "128k",
                str(dummy_video_path)
            ], check=True, capture_output=True, text=True, timeout=30)
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

        # Enhancement parameters (example values)
        enhancement_params = {
            "denoise_strength": 1.5,
            "sharpen_strength": 0.8,
            "contrast_enhance": 1.2,
            "saturation": 1.1,
            "gamma": 0.9,
            "brightness": 0.05,
            "shadow_highlight": 0.1,
            "delete_original_after_processing": False
        }

        # Test 1: Successful video enhancement
        test_logger.info(f"\n--- Test 1: Enhancing video ({dummy_video_path}) ---")
        success, message = enhancer.enhance_video(
            dummy_video_path, 
            output_enhanced_video_path, 
            enhancement_params,
            progress_callback_func=my_progress_callback
        )
        test_logger.info(f"Result: {message} (Success: {success})")
        assert success and output_enhanced_video_path.exists()

        # Test 2: File not found
        test_logger.info(f"\n--- Test 2: Non-existent input file ---")
        non_existent_path = test_input_dir / "non_existent_video.mp4"
        success, message = enhancer.enhance_video(
            non_existent_path, 
            test_output_dir / "non_existent_enhanced.mp4", 
            enhancement_params,
            progress_callback_func=my_progress_callback
        )
        test_logger.info(f"Result: {message} (Success: {success})")
        assert not success and "Input video file not found" in message

        # Test 3: No filters specified (should copy file)
        test_logger.info(f"\n--- Test 3: No enhancement filters (should copy file) ---")
        output_copied_video_path = test_output_dir / "copied_video.mp4"
        no_filter_params = {
            "denoise_strength": 0.0,
            "sharpen_strength": 0.0,
            "contrast_enhance": 1.0,
            "saturation": 1.0,
            "gamma": 1.0,
            "brightness": 0.0,
            "shadow_highlight": 0.0,
            "delete_original_after_processing": False
        }
        success, message = enhancer.enhance_video(
            dummy_video_path,
            output_copied_video_path,
            no_filter_params,
            progress_callback_func=my_progress_callback
        )
        test_logger.info(f"Result: {message} (Success: {success})")
        assert success and output_copied_video_path.exists()
        assert "No enhancements applied, file copied." in message


        test_logger.info("\n--- All video enhancement tests completed ---")
        test_logger.info("Please check the 'test_output' directory for enhanced video files.")
    else:
        test_logger.error("Skipping video enhancement tests due to missing dummy video file or creation failure. Please ensure FFmpeg is installed and accessible, and test_media directory is ready.")
    test_logger.info("--- VideoEnhancer module test completed ---")
