import os
import shutil
import subprocess
import logging
import tempfile
import atexit
import io
from pathlib import Path
from PIL import Image
from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip # MoviePy for video/audio manipulation
from rembg import remove # For background removal
from typing import Tuple, Optional, Callable, List, Dict, Any

from src.core.logger import get_application_logger
from src.core.config_manager import get_application_config

class VideoBgRemoverError(Exception):
    """Custom exception for video background removal errors."""
    pass

class VideoBgRemover:
    """
    Handles background removal for video files.
    Extracts frames, processes them with 'rembg', and reassembles the video.
    Utilizes FFmpeg for video/audio extraction and reassembly.
    """
    def __init__(self):
        self.logger = get_application_logger()
        self.config = get_application_config()
        self._is_processing = False # Internal state to track if a process is in progress
        self._external_progress_callback = None # Callback for GUI progress updates

        # Retrieve the models directory from the configuration manager.
        # This path is set by the main application during startup, ensuring models
        # are looked for in the application's designated directory.
        self.models_dir = Path(self.config.get_setting("app_settings.models_dir"))
        self.logger.info(f"VideoBgRemover initialized. Models directory set to: {self.models_dir}")

    def _update_progress(self, progress_percentage: int, message: str, level: str = "info"):
        """
        Internal helper to update progress and log messages.
        Ensures progress_percentage is within a valid range [0, 100].
        """
        if self._external_progress_callback:
            # Clamp progress percentage to ensure it's always between 0 and 100
            clamped_percentage = max(0, min(100, progress_percentage))
            self._external_progress_callback(clamped_percentage, message)
        self.logger.log(getattr(logging, level.upper()), f"VIDEO_BG_REMOVE_PROGRESS: {message} ({progress_percentage}%)")

    def _run_ffmpeg_command(self, command: List[str], description: str, log_level: str = "info") -> Tuple[bool, str]:
        """
        Executes an FFmpeg command using subprocess.
        """
        self.logger.info(f"Executing FFmpeg command for {description}: {' '.join(command)}")
        try:
            process = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
            self.logger.debug(f"FFmpeg STDOUT: {process.stdout}")
            self.logger.debug(f"FFmpeg STDERR: {process.stderr}")
            self.logger.log(getattr(logging, log_level.upper()), f"FFmpeg command for {description} completed successfully.")
            return True, "Success"
        except subprocess.CalledProcessError as e:
            self.logger.error(f"FFmpeg command failed for {description}. Exit code: {e.returncode}", exc_info=True)
            self.logger.error(f"FFmpeg STDOUT: {e.stdout}")
            self.logger.error(f"FFmpeg STDERR: {e.stderr}")
            return False, f"FFmpeg command failed: {e.stderr}"
        except FileNotFoundError:
            self.logger.critical("FFmpeg executable not found. Please ensure FFmpeg is installed and in your system's PATH, or correctly configured.")
            return False, "FFmpeg not found. Please install it and add to PATH."
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while running FFmpeg command for {description}: {e}", exc_info=True)
            return False, f"Unexpected error: {e}"

    def remove_video_background(self, input_filepath: Path, output_filepath: Path, delete_original: bool = False, progress_callback_func=None):
        """
        Removes the background from a video file.

        Args:
            input_filepath (Path): The path to the input video file.
            output_filepath (Path): The desired path for the output processed video file (with transparent background).
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
        
        # Ensure output file has .webm or .mov (with alpha channel support) extension for transparency
        # WebM with VP9 (libvpx-vp9) is generally preferred for transparent video
        # MOV with ProRes 4444 (libx264 or libvpx-vp9 as wrapper) can also work but is larger
        if output_filepath.suffix.lower() not in [".webm", ".mov"]:
            self.logger.warning(f"Output file extension changed from '{output_filepath.suffix}' to '.webm' for transparency.")
            output_filepath = output_filepath.with_suffix(".webm")

        temp_dir_prefix = f"creators_toolkit_vid_bg_remove_{os.getpid()}_"
        temp_working_dir = Path(tempfile.mkdtemp(prefix=temp_dir_prefix))
        atexit.register(lambda: shutil.rmtree(temp_working_dir, ignore_errors=True))
        self.logger.info(f"Created temporary working directory: {temp_working_dir}")

        temp_extracted_audio_path = temp_working_dir / "extracted_audio.aac"
        temp_processed_frames_pattern = temp_working_dir / "processed_frame_%07d.png" # For reassembly
        
        video_clip = None # Initialize to None for finally block
        audio_clip = None # Initialize to None for finally block

        try:
            # Step 1: Extract video frames and audio
            self.logger.info("Extracting video frames and audio...")
            self._update_progress(5, "Extracting frames and audio...")
            
            # Extract video frames
            frames_output_pattern = temp_working_dir / "frame_%07d.png"
            cmd_extract_frames = [
                "ffmpeg",
                "-i", str(input_filepath),
                "-vf", "fps=25", # Extract at 25 FPS (adjust if needed for quality vs. speed)
                str(frames_output_pattern)
            ]
            success_frames, msg_frames = self._run_ffmpeg_command(cmd_extract_frames, "frame extraction")
            if not success_frames:
                raise VideoBgRemoverError(f"Failed to extract video frames: {msg_frames}")
            self.logger.info("Video frames extracted successfully.")

            # Extract audio (if present)
            cmd_extract_audio = [
                "ffmpeg",
                "-i", str(input_filepath),
                "-vn", # No video
                "-acodec", "aac", # Audio codec
                "-b:a", "192k", # Audio bitrate
                "-y", str(temp_extracted_audio_path)
            ]
            success_audio, msg_audio = self._run_ffmpeg_command(cmd_extract_audio, "audio extraction")
            if success_audio:
                self.logger.info("Audio extracted successfully.")
                audio_clip = AudioFileClip(str(temp_extracted_audio_path))
            else:
                self.logger.warning(f"Audio extraction failed or no audio stream: {msg_audio}. Proceeding without audio.")

            # Step 2: Process each frame with rembg
            self.logger.info("Processing frames for background removal...")
            input_frames = sorted(list(temp_working_dir.glob("frame_*.png")))
            if not input_frames:
                raise VideoBgRemoverError("No frames found to process.")

            total_frames = len(input_frames)
            for i, frame_path in enumerate(input_frames):
                self._update_progress(
                    int(10 + (i / total_frames) * 70), # Progress from 10% to 80%
                    f"Processing frame {i+1}/{total_frames} for background removal..."
                )
                try:
                    with open(frame_path, 'rb') as f_in:
                        input_bytes = f_in.read()
                    
                    # Call rembg.remove, explicitly setting the model_dir
                    # Ensure the model (e.g., u2net.onnx) is present in self.models_dir
                    output_bytes = remove(input_bytes, model_dir=str(self.models_dir), model_name="u2net")
                    
                    # Save the processed image to a new path
                    processed_frame_path = temp_working_dir / f"processed_frame_{i:07d}.png"
                    with open(processed_frame_path, 'wb') as f_out:
                        f_out.write(output_bytes)
                except Exception as e:
                    self.logger.error(f"Error processing frame {frame_path}: {e}", exc_info=True)
                    # If the rembg model is missing, this is where it might manifest.
                    if "onnxruntime.capi.onnxruntime_pybind11_state.Fail" in str(e) or "No such file or directory" in str(e) or "ONNX model not found" in str(e):
                        raise VideoBgRemoverError(f"Rembg model (u2net.onnx) might be missing or corrupted. Ensure it's downloaded in '{self.models_dir}'.")
                    raise VideoBgRemoverError(f"Failed to process frame {frame_path}: {e}")

            self.logger.info("All frames processed for background removal.")

            # Step 3: Reassemble video from processed frames
            self.logger.info("Reassembling video from processed frames...")
            self._update_progress(85, "Reassembling video from frames...")

            # Use MoviePy to create a clip from the image sequence
            # MoviePy will use FFmpeg internally for this
            processed_video_clip = VideoFileClip(str(temp_processed_frames_pattern), fps=25) # Match extraction FPS

            # Set output video codec based on desired output extension
            video_codec = "libvpx-vp9" # For WebM with alpha channel
            pixel_format = "yuva420p" # For alpha channel support

            if output_filepath.suffix.lower() == ".mov":
                video_codec = "prores_ks" # ProRes 4444 (supports alpha), requires ffmpeg to be built with --enable-libopenh264 for libopenh264
                pixel_format = "yuva444p10le" # For ProRes 4444
            
            # Combine video and audio
            final_clip = processed_video_clip
            if audio_clip:
                self.logger.info("Attaching extracted audio to the video.")
                final_clip = final_clip.set_audio(audio_clip)

            self._update_progress(90, "Finalizing video export...")
            final_clip.write_videofile(
                str(output_filepath),
                codec=video_codec,
                audio_codec="aac", # AAC for audio is widely supported
                pixel_format=pixel_format,
                preset="medium", # or "ultrafast" for faster but larger files
                threads=os.cpu_count(), # Utilize all available CPU cores
                fps=25, # Match source FPS
                logger="bar" # Show MoviePy's internal progress
            )

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

        except VideoBgRemoverError as e:
            self._is_processing = False
            self.logger.error(f"Video background removal failed: {e}", exc_info=True)
            return False, f"Video background removal failed: {e}"
        except Exception as e:
            self._is_processing = False
            self.logger.critical(f"An unexpected critical error occurred during video background removal from '{input_filepath}': {e}", exc_info=True)
            return False, f"An unexpected error occurred during background removal: {e}"
        finally:
            # Ensure MoviePy clips are closed
            if video_clip:
                video_clip.close()
            if audio_clip:
                audio_clip.close()
            # Cleanup temporary directory (already handled by atexit, but explicit here for clarity)
            if temp_working_dir.exists():
                self.logger.info(f"Cleaning up temporary directory: {temp_working_dir}")
                shutil.rmtree(temp_working_dir, ignore_errors=True)
            self._external_progress_callback = None # Clear callback to prevent stale references

    def is_processing(self) -> bool:
        """Returns True if a video background removal task is currently in progress, False otherwise."""
        return self._is_processing