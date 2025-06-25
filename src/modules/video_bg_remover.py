import os
import shutil
import subprocess
from pathlib import Path
import logging
import cv2
import numpy as np
from PIL import Image
import io
from rembg import remove # Make sure 'rembg' is installed: pip install rembg

from src.core.logger import get_application_logger
from src.core.config_manager import get_application_config

class VideoBgRemovalError(Exception):
    """Custom exception for video background removal errors."""
    pass

class VideoBgRemover:
    """
    Handles background removal for video files.
    Processes video frame-by-frame using rembg, and merges with original audio.
    Optimized for resource management and provides progress tracking.
    """
    def __init__(self):
        self.logger = get_application_logger()
        self.config = get_application_config()
        self._is_processing = False # Internal state to track if a process is in progress
        self._external_progress_callback = None # Callback for GUI progress updates
        
        self.logger.info("VideoBgRemover initialized.")

    def _update_progress(self, progress_percentage: int, message: str, level: str = "info"):
        """
        Internal helper to update progress and log messages.
        """
        if self._external_progress_callback:
            self._external_progress_callback(progress_percentage, message)
        self.logger.log(getattr(logging, level.upper()), f"VIDEO_BG_REMOVE_PROGRESS: {message} ({progress_percentage}%)")

    def _get_video_duration(self, video_path: Path) -> float:
        """
        Uses ffprobe to get the duration of a video in seconds.
        """
        command = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return float(result.stdout.strip())
        except (subprocess.CalledProcessError, ValueError) as e:
            self.logger.error(f"Failed to get video duration for {video_path} using ffprobe: {e}", exc_info=True)
            raise VideoBgRemovalError(f"Could not determine video duration. Is FFprobe installed and is the video valid? Error: {e}")
        except FileNotFoundError:
            self.logger.error("ffprobe executable not found. Please ensure FFmpeg (which includes ffprobe) is installed and in your PATH.")
            raise VideoBgRemovalError("FFprobe not found. Please install FFmpeg.")


    def remove_background_from_video(self, input_filepath: Path, output_filepath: Path, delete_original: bool = False, progress_callback_func=None):
        """
        Removes background from a video file frame-by-frame and merges with original audio.

        Args:
            input_filepath (Path): The path to the input video file.
            output_filepath (Path): The desired path for the output processed video file.
            delete_original (bool): If True, the original video file will be deleted after successful processing.
            progress_callback_func (callable, optional): A function to call with progress updates (0-100 integer, message).
                                                        Signature: `progress_callback_func(progress_int: int, message: str)`
        Returns:
            tuple: (bool, str) - True if successful, False otherwise, and a message.
        """
        if self._is_processing:
            self.logger.warning("Attempted to start video background removal while another is in progress.")
            return False, "Another video background removal task is already in progress. Please wait."

        self._is_processing = True
        self._external_progress_callback = progress_callback_func
        self.logger.info(f"Attempting to remove background from video '{input_filepath}' to '{output_filepath}'")
        self._update_progress(0, "Starting video background removal...")

        if not input_filepath.exists() or not input_filepath.is_file():
            self._is_processing = False
            self.logger.error(f"Input video file not found or is not a file: {input_filepath}")
            return False, f"Input video file does not exist or is invalid: {input_filepath}"
        
        # Ensure output directory exists
        output_filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Ensure output file is MP4 for broad compatibility
        if output_filepath.suffix.lower() not in [".mp4"]:
            self.logger.warning(f"Output file extension changed from '{output_filepath.suffix}' to '.mp4' for compatibility.")
            output_filepath = output_filepath.with_suffix(".mp4")

        temp_dir = None
        temp_silent_video_path = None
        temp_audio_path = None

        try:
            temp_dir = Path(os.path.join(input_filepath.parent, f"{input_filepath.stem}_temp_bg_remove"))
            temp_dir.mkdir(exist_ok=True)
            self.logger.debug(f"Created temporary directory: {temp_dir}")

            temp_silent_video_path = temp_dir / "silent_processed_video.mp4"
            temp_audio_path = temp_dir / "original_audio.aac" # Using aac for common audio format

            # --- Step 1: Extract Original Audio ---
            self._update_progress(5, "Extracting original audio...")
            self.logger.info(f"Extracting audio from '{input_filepath}' to '{temp_audio_path}'")
            audio_extract_command = [
                "ffmpeg",
                "-i", str(input_filepath),
                "-vn",             # No video
                "-c:a", "copy",    # Copy audio stream without re-encoding
                str(temp_audio_path)
            ]
            try:
                subprocess.run(audio_extract_command, check=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                self.logger.info("Audio extraction successful.")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"FFmpeg audio extraction failed: {e.stderr}", exc_info=True)
                raise VideoBgRemovalError(f"Failed to extract audio: {e.stderr.strip()}")
            except FileNotFoundError:
                raise VideoBgRemovalError("FFmpeg not found. Please ensure FFmpeg is installed and in your system's PATH.")

            # --- Step 2: Process Video Frames (Remove Background) ---
            self._update_progress(15, "Processing video frames (removing background)...")
            self.logger.info("Starting frame-by-frame background removal.")

            cap = cv2.VideoCapture(str(input_filepath))
            if not cap.isOpened():
                raise VideoBgRemovalError(f"Could not open video file: {input_filepath}")

            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            # Use configurable FPS if provided, otherwise original
            output_fps = self.config.get_setting("processing_parameters.video_background_removal.output_fps", None)
            if output_fps is None:
                output_fps = fps
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.logger.debug(f"Input video properties: {frame_width}x{frame_height}, {fps} FPS, {total_frames} frames.")

            # Define the output video writer (silent video for now)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v') # Codec for .mp4, commonly supported
            out = cv2.VideoWriter(str(temp_silent_video_path), fourcc, output_fps, (frame_width, frame_height))
            if not out.isOpened():
                raise VideoBgRemovalError(f"Could not create output video writer for: {temp_silent_video_path}")

            # Get background color from config, convert hex to BGR tuple for OpenCV
            bg_color_hex = self.config.get_setting("processing_parameters.video_background_removal.default_background_color", "#000000")
            bg_color_rgb = tuple(int(bg_color_hex[i:i+2], 16) for i in (1, 3, 5)) # (R, G, B)
            bg_color_bgr = bg_color_rgb[::-1] # (B, G, R) for OpenCV

            frame_count = 0
            while True:
                ret, frame_bgr = cap.read()
                if not ret:
                    break

                frame_count += 1
                if frame_count % 50 == 0: # Update progress every 50 frames
                    current_progress = int(20 + (frame_count / total_frames) * 60) # Scale progress from 20% to 80%
                    self._update_progress(min(current_progress, 80), f"Processing frame {frame_count}/{total_frames}...")

                # Convert BGR frame to RGB for PIL/rembg
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(frame_rgb)

                # Remove background using rembg
                # rembg.remove returns an RGBA PIL image with the alpha channel indicating transparency
                output_pil_image_rgba = remove(pil_image)

                # Convert PIL RGBA image back to OpenCV BGR format for writing
                output_np_rgba = np.array(output_pil_image_rgba)
                
                # Extract foreground (RGB) and alpha channel
                foreground = output_np_rgba[:, :, :3] # RGB channels
                alpha_channel = output_np_rgba[:, :, 3] / 255.0 # Alpha channel (0.0 to 1.0)

                # Create a solid color background image
                background_solid = np.full(frame_bgr.shape, bg_color_bgr, dtype=np.uint8) # BGR background

                # Composite foreground onto the solid background using alpha blending
                # output_frame_bgr = (foreground * alpha_channel[..., np.newaxis] +
                #                     background_solid * (1.0 - alpha_channel[..., np.newaxis]))
                # The above is for RGB foreground over RGB background. For BGR:
                
                # Need to convert foreground to BGR first if it's RGB
                foreground_bgr = cv2.cvtColor(foreground, cv2.COLOR_RGB2BGR)

                output_frame_bgr = np.zeros_like(frame_bgr, dtype=np.float32)
                for c in range(3): # For B, G, R channels
                    output_frame_bgr[:, :, c] = (foreground_bgr[:, :, c] * alpha_channel +
                                                  background_solid[:, :, c] * (1.0 - alpha_channel))
                
                final_frame_bgr = output_frame_bgr.astype(np.uint8)
                out.write(final_frame_bgr)

            cap.release()
            out.release()
            self.logger.info("Frame processing and silent video creation complete.")
            self._update_progress(85, "Merging video with original audio...")

            # --- Step 3: Merge Processed Video with Original Audio ---
            final_output_path_str = str(output_filepath) # Ensure it's a string for subprocess
            
            merge_command = [
                "ffmpeg",
                "-i", str(temp_silent_video_path), # Input 0: Processed silent video
                "-i", str(temp_audio_path),        # Input 1: Original audio
                "-c:v", "copy",                    # Copy video stream without re-encoding (already processed)
                "-c:a", "copy",                    # Copy audio stream without re-encoding
                "-map", "0:v:0",                   # Map video stream from first input
                "-map", "1:a:0",                   # Map audio stream from second input
                "-y",                              # Overwrite output file
                final_output_path_str
            ]
            self.logger.info(f"Executing FFmpeg merge command: {' '.join(merge_command)}")
            subprocess.run(merge_command, check=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            self.logger.info("Video and audio merged successfully.")

            self._update_progress(100, "Video background removal complete!")
            self.logger.info(f"Video background removal completed successfully: {output_filepath}")

            if delete_original:
                self.logger.info(f"Attempting to delete original file: {input_filepath}")
                try:
                    os.remove(input_filepath)
                    self.logger.info(f"Original file deleted: {input_filepath}")
                except OSError as e:
                    self.logger.warning(f"Failed to delete original file {input_filepath}: {e}. Skipping deletion.")
            
            self._is_processing = False
            return True, f"Video background removal complete! Saved to: {output_filepath}"

        except VideoBgRemovalError as e:
            self._is_processing = False
            self.logger.error(f"Video background removal failed: {e}", exc_info=True)
            # Clean up partially created output file if error occurs
            if output_filepath.exists():
                try:
                    os.remove(output_filepath)
                    self.logger.info(f"Cleaned up partial final output file: {output_filepath}")
                except Exception as cleanup_e:
                    self.logger.warning(f"Failed to clean up partial final output file {output_filepath}: {cleanup_e}")
            return False, f"Video background removal failed: {e}"
        except FileNotFoundError:
            self._is_processing = False
            self.logger.error("A required executable (ffmpeg or ffprobe) was not found in PATH.")
            return False, "FFmpeg or FFprobe not found. Please ensure FFmpeg is installed and in your system's PATH."
        except Exception as e:
            self._is_processing = False
            self.logger.critical(f"An unexpected critical error occurred during video background removal from '{input_filepath}': {e}", exc_info=True)
            if output_filepath.exists():
                try:
                    os.remove(output_filepath)
                    self.logger.info(f"Cleaned up partial final output file: {output_filepath}")
                except Exception as cleanup_e:
                    self.logger.warning(f"Failed to clean up partial final output file {output_filepath}: {cleanup_e}")
            return False, f"An unexpected error occurred during background removal: {e}"
        finally:
            self._external_progress_callback = None # Clear callback
            if temp_dir and temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    self.logger.info(f"Cleaned up temporary directory: {temp_dir}")
                except Exception as e:
                    self.logger.warning(f"Failed to remove temporary directory {temp_dir}: {e}")

    def is_processing(self) -> bool:
        """Returns True if a video background removal task is currently in progress, False otherwise."""
        return self._is_processing