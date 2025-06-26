import os
import shutil
import subprocess
import logging
import cv2
import numpy as np
from pathlib import Path
from moviepy import VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip, ImageClip # MoviePy for complex overlays/compositing
from moviepy.video.fx.Crop import Crop as moviepy_crop_fx # Renamed to avoid conflict
from moviepy.video.fx.Resize import Resize as moviepy_resize_fx # Renamed to avoid conflict
from pydub import AudioSegment
from typing import List, Dict, Any, Optional, Callable, Tuple
# from pydub.silence import split_on_silence # No longer needed, handled by AudioProcessor or Vosk timestamps
import speech_recognition as sr # For initial transcription concept, will be replaced with Vosk
from vosk import Model, KaldiRecognizer # Removed set_log_level, as it's causing ImportError
import math
import tempfile
import atexit
import json # For Vosk model info, and subtitle timing details

# Core modules
from src.core.logger import get_application_logger
from src.core.config_manager import get_application_config
from src.utils.font_manager import get_application_font_manager

# Import specific modules for enhancements if needed (DRY principle)
from src.modules.audio_processor import AudioProcessor # Reusing for audio enhancement
from src.modules.video_enhancer import VideoEnhancer # Reusing for video enhancement

class SocialMediaVideoProcessorError(Exception):
    """Custom exception for social media video processor errors."""
    pass

class SocialMediaVideoProcessor:
    """
    Processes videos for social media platforms, including intelligent cropping,
    subtitle generation, silent segment removal, and automatic enhancements.
    Optimized for efficiency using FFmpeg, OpenCV, Vosk for offline ASR,
    and reusing existing audio/video enhancement modules.
    """
    def __init__(self):
        self.logger = get_application_logger()
        self.config = get_application_config()
        self.font_manager = get_application_font_manager()
        self.audio_processor = AudioProcessor() # Reusing the audio processing module
        self.video_enhancer = VideoEnhancer() # Reusing the video enhancement module

        self._is_processing = False # Internal state to track if a process is in progress
        self._external_progress_callback = None # Callback for GUI progress updates

        # Retrieve models directory from config for Vosk
        self.models_dir = Path(self.config.get_setting("app_settings.models_dir"))
        self.vosk_model_path = self.models_dir / "vosk-model-en-us-0.22" # Example Vosk model name
        self.vosk_recognizer = None # Will be initialized on demand

        self.logger.info("SocialMediaVideoProcessor initialized.")

    def _update_progress(self, progress_percentage: int, message: str, level: str = "info"):
        """
        Internal helper to update progress and log messages.
        Ensures progress_percentage is within a valid range [0, 100].
        """
        if self._external_progress_callback:
            clamped_percentage = max(0, min(100, progress_percentage))
            self._external_progress_callback(clamped_percentage, message)
        self.logger.log(getattr(logging, level.upper()), f"SOCIAL_MEDIA_PROCESS_PROGRESS: {message} ({progress_percentage}%)")

    def _run_ffmpeg_command(self, command: List[str], description: str, log_level: str = "info") -> Tuple[bool, str]:
        """
        Executes an FFmpeg command using subprocess.
        """
        self.logger.info(f"Executing FFmpeg command for {description}: {' '.join(command)}")
        try:
            # Use CREATE_NO_WINDOW on Windows to prevent a console window from popping up
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            process = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8', creationflags=creationflags)
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

    def _get_main_content_bounding_box(self, video_path: Path) -> Optional[Tuple[int, int, int, int]]:
        """
        Analyzes video frames to find a bounding box that contains the most significant
        motion or visual content, to assist in intelligent cropping.
        
        Args:
            video_path (Path): Path to the input video file.
            
        Returns:
            Optional[Tuple[int, int, int, int]]: (x, y, width, height) of the content,
                                                or None if detection fails.
        """
        self.logger.info(f"Analyzing video '{video_path}' for main content bounding box...")
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            self.logger.error(f"Could not open video file for analysis: {video_path}")
            return None

        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')

        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Convert to grayscale for motion detection or content analysis
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Apply threshold to find significant pixels (adjust threshold as needed)
            # This can be improved with background subtraction or more advanced techniques
            _, thresh = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY) # Simple threshold
            
            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                # Combine all bounding boxes of detected contours
                x_coords = []
                y_coords = []
                for contour in contours:
                    x, y, w, h = cv2.boundingRect(contour)
                    x_coords.extend([x, x + w])
                    y_coords.extend([y, y + h])
                
                if x_coords and y_coords:
                    min_x = min(min_x, min(x_coords))
                    min_y = min(min_y, min(y_coords))
                    max_x = max(max_x, max(x_coords))
                    max_y = max(max_y, max(y_coords))
            frame_count += 1
            if frame_count % 50 == 0: # Process every 50th frame for speed
                self.logger.debug(f"Analyzed {frame_count} frames for content box...")
        
        cap.release()

        if min_x == float('inf') or max_x == float('-inf'):
            self.logger.warning("No significant content detected for cropping. Returning None.")
            return None # No content detected

        content_width = max_x - min_x
        content_height = max_y - min_y
        
        self.logger.info(f"Detected content bounding box: ({min_x}, {min_y}, {content_width}, {content_height})")
        return (min_x, min_y, content_width, content_height)


    def _transcribe_audio_vosk(self, audio_filepath: Path) -> List[Dict[str, Any]]:
        """
        Transcribes audio using the offline Vosk speech recognition engine.
        Returns a list of dictionaries with 'text', 'start', and 'end' for each word.
        
        Args:
            audio_filepath (Path): Path to the audio file (preferably WAV, 16kHz, mono).
            
        Returns:
            List[Dict[str, Any]]: A list of word-level transcription results.
        """
        self.logger.info(f"Transcribing audio with Vosk from: {audio_filepath}")
        
        # Ensure Vosk model is loaded
        if self.vosk_recognizer is None:
            if not self.vosk_model_path.exists():
                self.logger.error(f"Vosk model not found at: {self.vosk_model_path}")
                raise SocialMediaVideoProcessorError(
                    f"Vosk model not found. Please ensure the Vosk model "
                    f"'{self.vosk_model_path.name}' is downloaded in '{self.vosk_model_path.parent}'."
                )
            # set_log_level(-1) # Removed as it's causing ImportError
            self.vosk_recognizer = KaldiRecognizer(Model(str(self.vosk_model_path)), 16000) # 16kHz sample rate

        words_info = []
        
        # Convert audio to a format suitable for Vosk (16kHz, mono, WAV)
        temp_mono_wav = audio_filepath.parent / f"{audio_filepath.stem}_16khz_mono.wav"
        
        cmd_convert_audio = [
            "ffmpeg",
            "-i", str(audio_filepath),
            "-ac", "1",      # Convert to mono
            "-ar", "16000",  # Resample to 16kHz
            "-f", "wav",     # Output WAV format
            "-y", str(temp_mono_wav)
        ]
        success, msg = self._run_ffmpeg_command(cmd_convert_audio, "audio conversion for Vosk")
        if not success:
            raise SocialMediaVideoProcessorError(f"Failed to convert audio for Vosk transcription: {msg}")

        try:
            with open(temp_mono_wav, "rb") as wf:
                while True:
                    data = wf.read(4000) # Read in chunks
                    if len(data) == 0:
                        break
                    if self.vosk_recognizer.AcceptWaveform(data):
                        result = json.loads(self.vosk_recognizer.Result())
                        if "result" in result:
                            for word_data in result["result"]:
                                words_info.append({
                                    "text": word_data["word"],
                                    "start": word_data["start"],
                                    "end": word_data["end"]
                                })
            # Get any remaining result after the loop
            final_result = json.loads(self.vosk_recognizer.FinalResult())
            if "result" in final_result:
                for word_data in final_result["result"]:
                    words_info.append({
                        "text": word_data["word"],
                        "start": word_data["start"],
                        "end": word_data["end"]
                    })
        finally:
            if temp_mono_wav.exists():
                os.remove(temp_mono_wav) # Clean up temporary WAV file
            
        self.logger.info(f"Vosk transcription complete. Found {len(words_info)} words.")
        return words_info

    def _generate_srt_content(self, words_info: List[Dict[str, Any]], words_per_line: int) -> str:
        """
        Generates SRT content from word-level transcription results with intelligent line breaks.
        
        Args:
            words_info (List[Dict[str, Any]]): List of dictionaries, each with 'text', 'start', 'end'.
            words_per_line (int): Maximum number of words per subtitle line.
            
        Returns:
            str: The formatted SRT content.
        """
        srt_content = []
        subtitle_number = 1
        
        if not words_info:
            return ""

        current_line_words = []
        
        for i, word_data in enumerate(words_info):
            current_line_words.append(word_data)
            
            # Check if we should break the line:
            # 1. If we reached words_per_line
            # 2. If it's the last word
            # 3. If the gap to the next word is large (e.g., > 0.5 seconds) - helps with natural pauses
            if (len(current_line_words) == words_per_line or
                i == len(words_info) - 1 or
                (i + 1 < len(words_info) and (words_info[i+1]["start"] - word_data["end"]) > 0.5)):
                
                # Form the text for the current line
                line_text = " ".join([w["text"] for w in current_line_words])
                
                # Determine start and end times for the line
                start_time_seconds = current_line_words[0]["start"]
                end_time_seconds = current_line_words[-1]["end"]
                
                # Format times to SRT format (HH:MM:SS,ms)
                start_h, start_m, start_s, start_ms = self._split_seconds_to_srt_components(start_time_seconds)
                end_h, end_m, end_s, end_ms = self._split_seconds_to_srt_components(end_time_seconds)

                srt_content.append(str(subtitle_number))
                srt_content.append(f"{start_h:02}:{start_m:02}:{start_s:02},{start_ms:03} --> {end_h:02}:{end_m:02}:{end_s:02},{end_ms:03}")
                srt_content.append(line_text)
                srt_content.append("") # Empty line separates entries

                current_line_words = []
                subtitle_number += 1

        return "\n".join(srt_content)

    def _split_seconds_to_srt_components(self, total_seconds: float) -> Tuple[int, int, int, int]:
        """Helper to convert total seconds to SRT time format components (H, M, S, MS)."""
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        milliseconds = int((total_seconds * 1000) % 1000)
        return hours, minutes, seconds, milliseconds

    def process_social_media_video(
        self,
        input_filepath: Path,
        output_filepath: Path,
        processing_options: Dict[str, Any],
        progress_callback_func: Optional[Callable[[int, str], None]] = None
    ) -> Tuple[bool, str]:
        """
        Processes a video for social media platforms based on a dictionary of options.

        Args:
            input_filepath (Path): The path to the input video file.
            output_filepath (Path): The desired path for the output processed video file.
            processing_options (Dict[str, Any]): A dictionary containing processing settings:
                                                  - auto_crop (bool)
                                                  - generate_subtitles (bool)
                                                  - subtitle_font_size (int)
                                                  - default_subtitle_font_name (str)
                                                  - subtitle_color (str, e.g., "#FFFFFF")
                                                  - subtitle_stroke_width (int)
                                                  - subtitle_stroke_color (str, e.g., "#000000")
                                                  - subtitle_font_position_y (float, 0.0 to 1.0, relative to height)
                                                  - subtitle_words_per_line (int)
                                                  - auto_remove_silent_segments (bool)
                                                  - min_silence_duration_ms (int)
                                                  - silence_threshold_db (float)
                                                  - apply_auto_video_enhancement (bool)
                                                  - apply_auto_audio_enhancement (bool)
                                                  - overlays (List[Dict])
                                                  - delete_original_after_processing (bool)
                                                  - target_social_media_resolution (str, e.g., "1080x1920")
            progress_callback_func (callable, optional): A function to call with progress updates.
        
        Returns:
            tuple: (bool, str) - True if successful, False otherwise, and a message.
        """
        if self._is_processing:
            self.logger.warning("Attempted to start social media video processing while another is in progress.")
            return False, "Another social media video processing task is already in progress. Please wait."

        self._is_processing = True
        self._external_progress_callback = progress_callback_func
        self.logger.info(f"Starting social media video processing for: {input_filepath}")
        self._update_progress(0, "Initializing social media video processing...")

        if not input_filepath.exists() or not input_filepath.is_file():
            self._is_processing = False
            self.logger.error(f"Input video file not found: {input_filepath}")
            return False, f"Input video file does not exist: {input_filepath}"

        output_filepath.parent.mkdir(parents=True, exist_ok=True)

        temp_dir_prefix = f"creators_toolkit_social_media_{os.getpid()}_"
        temp_working_dir = Path(tempfile.mkdtemp(prefix=temp_dir_prefix))
        atexit.register(lambda: shutil.rmtree(temp_working_dir, ignore_errors=True))
        self.logger.info(f"Created temporary working directory: {temp_working_dir}")

        temp_video_path = temp_working_dir / "temp_video.mp4"
        temp_audio_path = temp_working_dir / "temp_audio.wav" # For ASR
        temp_enhanced_audio_path = temp_working_dir / "temp_enhanced_audio.wav"
        temp_enhanced_video_path = temp_working_dir / "temp_enhanced_video.mp4"
        temp_cropped_video_path = temp_working_dir / "temp_cropped_video.mp4"
        temp_final_video_no_subtitles_path = temp_working_dir / "temp_final_video_no_subtitles.mp4"
        temp_subtitles_file = temp_working_dir / "subtitles.srt"

        video_clip = None
        audio_clip = None
        final_clip = None

        try:
            # Load video clip using MoviePy to get duration and dimensions
            self.logger.info(f"Loading video clip to determine properties: {input_filepath}")
            self._update_progress(5, "Analyzing video properties...")
            video_clip = VideoFileClip(str(input_filepath))
            original_duration = video_clip.duration
            original_width, original_height = video_clip.size
            self.logger.info(f"Video loaded. Duration: {original_duration:.2f}s, Dimensions: {original_width}x{original_height}")

            # Step 1: Apply Video Enhancements (if enabled)
            if processing_options.get("apply_auto_video_enhancement"):
                self.logger.info("Applying automatic video enhancements.")
                self._update_progress(10, "Applying video enhancements...")
                # Fetch enhancement parameters from config (or pass custom ones)
                video_enhance_params = self.config.get_setting("processing_parameters.video_enhancement")
                success, msg = self.video_enhancer.enhance_video(
                    input_filepath, temp_enhanced_video_path, video_enhance_params,
                    progress_callback_func=lambda p, m: self._update_progress(int(10 + p * 0.1), m) # Scale progress
                )
                if not success:
                    raise SocialMediaVideoProcessorError(f"Video enhancement failed: {msg}")
                self.logger.info("Video enhancements applied.")
                input_filepath_for_next_step = temp_enhanced_video_path
            else:
                self.logger.info("Skipping automatic video enhancements.")
                input_filepath_for_next_step = input_filepath

            # Step 2: Extract Audio for processing/transcription
            self.logger.info("Extracting audio from video for processing...")
            self._update_progress(20, "Extracting audio...")
            cmd_extract_audio = [
                "ffmpeg",
                "-i", str(input_filepath_for_next_step), # Use enhanced video if applicable
                "-vn", "-acodec", "pcm_s16le", # Extract as PCM WAV for high quality and compatibility
                "-ar", "48000", # Desired sample rate for processing
                "-ac", "1", # Mono channel
                "-y", str(temp_audio_path)
            ]
            success, msg = self._run_ffmpeg_command(cmd_extract_audio, "audio extraction")
            if not success:
                self.logger.warning(f"Audio extraction failed: {msg}. Proceeding without audio processing/transcription.")
                temp_audio_path = None # Mark audio as not available

            # Step 3: Apply Audio Enhancements (if enabled)
            audio_for_transcription_path = None
            if temp_audio_path and processing_options.get("apply_auto_audio_enhancement"):
                self.logger.info("Applying automatic audio enhancements.")
                self._update_progress(30, "Applying audio enhancements...")
                # Fetch audio enhancement parameters from config
                audio_enhance_params = self.config.get_setting("processing_parameters.audio_enhancement")
                success, msg = self.audio_processor.process_audio_file(
                    temp_audio_path, temp_enhanced_audio_path, False, # Do not delete original temp_audio_path
                    progress_callback_func=lambda p, m: self._update_progress(int(30 + p * 0.1), m) # Scale progress
                )
                if not success:
                    raise SocialMediaVideoProcessorError(f"Audio enhancement failed: {msg}")
                self.logger.info("Audio enhancements applied.")
                audio_for_transcription_path = temp_enhanced_audio_path
            else:
                self.logger.info("Skipping automatic audio enhancements.")
                audio_for_transcription_path = temp_audio_path # Use original extracted audio if no enhancement

            # Step 4: Generate Subtitles (if enabled)
            subtitle_clip = None
            if processing_options.get("generate_subtitles") and audio_for_transcription_path and audio_for_transcription_path.exists():
                self.logger.info("Generating subtitles from audio.")
                self._update_progress(40, "Transcribing audio for subtitles...")
                
                # Transcribe using Vosk (offline ASR)
                words_info = self._transcribe_audio_vosk(audio_for_transcription_path)
                
                if words_info:
                    words_per_line = processing_options.get("subtitle_words_per_line", 3)
                    srt_content = self._generate_srt_content(words_info, words_per_line)
                    
                    with open(temp_subtitles_file, "w", encoding="utf-8") as f:
                        f.write(srt_content)
                    self.logger.info(f"SRT subtitles generated to: {temp_subtitles_file}")

                    # Use MoviePy's TextClip to create subtitle overlay
                    font_name = processing_options.get("default_subtitle_font_name", "Arial")
                    font_path = self.font_manager.get_font_path(font_name) or self.font_manager.get_default_font_path()
                    
                    if not font_path.exists():
                        self.logger.error(f"Subtitle font not found: {font_path}. Using system default.")
                        font_path = self.font_manager.get_default_font_path() # Fallback to a guaranteed font
                        
                    font_size = processing_options.get("subtitle_font_size", 40)
                    font_color = processing_options.get("subtitle_color", "#FFFFFF")
                    stroke_width = processing_options.get("subtitle_stroke_width", 2)
                    stroke_color = processing_options.get("subtitle_stroke_color", "#000000")
                    # position_y_ratio: 0.0 (top) to 1.0 (bottom)
                    position_y_ratio = processing_options.get("subtitle_font_position_y", 0.85)

                    # Subtitle styling can be complex. MoviePy TextClip offers good control.
                    # This example creates a single TextClip that will be dynamically updated
                    # using FFmpeg's subtitles filter for better performance with complex videos.
                    self.logger.info("Preparing subtitles for video embedding.")
                    self._update_progress(50, "Embedding subtitles...")
                else:
                    self.logger.warning("No words transcribed, skipping subtitle generation.")
            else:
                self.logger.info("Skipping subtitle generation.")

            # Determine the current video source for cropping/finalization
            current_video_source = input_filepath_for_next_step

            # Step 5: Apply Intelligent Cropping (if enabled)
            if processing_options.get("auto_crop"):
                self.logger.info("Applying intelligent cropping.")
                self._update_progress(60, "Detecting content for smart cropping...")
                
                bounding_box = self._get_main_content_bounding_box(current_video_source)
                
                if bounding_box:
                    x, y, w, h = bounding_box
                    target_resolution_str = processing_options.get("target_social_media_resolution", "1080x1920")
                    target_width, target_height = map(int, target_resolution_str.split('x'))

                    # Calculate target aspect ratio
                    target_aspect_ratio = target_width / target_height

                    # Calculate crop box to fit target aspect ratio around content
                    # This is a simplified approach; a more advanced one would consider
                    # motion tracking and dynamic cropping over time.
                    
                    # Current content aspect ratio
                    content_aspect_ratio = w / h

                    if content_aspect_ratio > target_aspect_ratio:
                        # Content is wider than target. Fit width, calculate new height.
                        new_h = int(w / target_aspect_ratio)
                        offset_y = max(0, y - (new_h - h) // 2)
                        # Ensure offset_y doesn't go negative or beyond video height
                        offset_y = min(offset_y, original_height - new_h) if new_h < original_height else 0
                        crop_x, crop_y, crop_w, crop_h = x, offset_y, w, new_h
                    else:
                        # Content is taller or same aspect ratio as target. Fit height, calculate new width.
                        new_w = int(h * target_aspect_ratio)
                        offset_x = max(0, x - (new_w - w) // 2)
                        # Ensure offset_x doesn't go negative or beyond video width
                        offset_x = min(offset_x, original_width - new_w) if new_w < original_width else 0
                        crop_x, crop_y, crop_w, crop_h = offset_x, y, new_w, h

                    # Ensure crop dimensions are within original video boundaries
                    crop_x = max(0, crop_x)
                    crop_y = max(0, crop_y)
                    crop_w = min(crop_w, original_width - crop_x)
                    crop_h = min(crop_h, original_height - crop_y)

                    self.logger.info(f"Calculated crop: x={crop_x}, y={crop_y}, w={crop_w}, h={crop_h}")
                    self._update_progress(70, "Applying crop and resizing...")

                    # Use FFmpeg to apply crop and resize in one go for efficiency
                    cmd_crop_resize = [
                        "ffmpeg",
                        "-i", str(current_video_source),
                        "-vf", f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale={target_width}:{target_height}",
                        "-c:v", "libx264", # Re-encode with h264
                        "-preset", "medium",
                        "-crf", "23",
                        "-c:a", "copy", # Copy audio
                        "-y", str(temp_cropped_video_path)
                    ]
                    success_crop, msg_crop = self._run_ffmpeg_command(cmd_crop_resize, "intelligent cropping and resizing")
                    if not success_crop:
                        raise SocialMediaVideoProcessorError(f"Intelligent cropping failed: {msg_crop}")
                    current_video_source = temp_cropped_video_path
                else:
                    self.logger.warning("Intelligent cropping enabled but no main content detected. Skipping crop.")
            else:
                self.logger.info("Skipping intelligent cropping.")

            # Step 6: Compose final video (subtitles, overlays)
            self.logger.info("Composing final video with subtitles and overlays.")
            self._update_progress(80, "Compositing final video...")

            # Reload video clip after potential enhancements/cropping
            final_video_clip_no_audio = VideoFileClip(str(current_video_source))

            # Apply subtitles using FFmpeg's subtitles filter for better performance
            if processing_options.get("generate_subtitles") and temp_subtitles_file.exists():
                self.logger.info("Applying subtitles to video via FFmpeg filter.")
                
                # FFmpeg subtitle filter requires font config in a specific way
                # Escape font path for FFmpeg, especially on Windows
                escaped_font_path = str(font_path).replace("\\", "/") # Convert backslashes to forward slashes for FFmpeg
                
                # Subtitle text style directly in filter string (simplistic, for advanced, consider ASS)
                # FFmpeg subtitles filter: subtitles='path/to/sub.srt':force_style='Fontname=Arial,FontSize=24,PrimaryColour=&H00FFFFFF'
                # Note: FFmpeg colors are usually BGR hex or by name
                # Convert #RRGGBB to FFmpeg's &HBBGGRR format, plus transparency if needed
                subtitle_color_rgb = processing_options.get("subtitle_color", "#FFFFFF").lstrip('#')
                # BBGGRR for FFmpeg
                subtitle_color_bgr = f"&H00{subtitle_color_rgb[4:6]}{subtitle_color_rgb[2:4]}{subtitle_color_rgb[0:2]}"

                # Font styling for FFmpeg subtitles filter
                # PrimaryColour (for text color), OutlineColour (for stroke/outline)
                # Outline (for stroke width)
                stroke_color_rgb = processing_options.get("subtitle_stroke_color", "#000000").lstrip('#')
                subtitle_stroke_color_bgr = f"&H00{stroke_color_rgb[4:6]}{stroke_color_rgb[2:4]}{stroke_color_rgb[0:2]}"


                subtitle_style_string = (
                    f"Fontname={Path(font_path).stem}," # Use stem if font path is too complex
                    f"FontSize={processing_options.get('subtitle_font_size', 40)},"
                    f"PrimaryColour={subtitle_color_bgr},"
                    f"OutlineColour={subtitle_stroke_color_bgr}," # Convert to BGR for outline
                    f"Outline={processing_options.get('subtitle_stroke_width', 2)},"
                    f"Alignment=2," # 2 is bottom center in some contexts, but usually a number based on position. ASS uses this.
                    f"MarginV={int(final_video_clip_no_audio.h * (1.0 - processing_options.get('subtitle_font_position_y', 0.85)))}" # Vertical margin from bottom
                )
                
                # Create a temporary video with subtitles embedded
                cmd_add_subtitles = [
                    "ffmpeg",
                    "-i", str(current_video_source),
                    "-vf", f"subtitles='{str(temp_subtitles_file)}':force_style='{subtitle_style_string}'",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                    "-c:a", "copy",
                    "-y", str(temp_final_video_no_subtitles_path)
                ]
                success_subtitles, msg_subtitles = self._run_ffmpeg_command(cmd_add_subtitles, "embedding subtitles")
                if not success_subtitles:
                    self.logger.warning(f"Failed to embed subtitles: {msg_subtitles}. Proceeding without subtitles.")
                    final_video_with_subs = final_video_clip_no_audio
                else:
                    self.logger.info("Subtitles embedded successfully.")
                    final_video_with_subs = VideoFileClip(str(temp_final_video_no_subtitles_path))
                
                # Clean up the intermediate video created just for subtitles
                final_video_clip_no_audio.close() # Close previous clip
                current_video_source = temp_final_video_no_subtitles_path # Update source for next step

            else:
                self.logger.info("Skipping subtitle embedding.")
                final_video_with_subs = VideoFileClip(str(current_video_source)) # Use current video directly

            # Apply overlays (if any)
            overlays_data = processing_options.get("overlays", [])
            if overlays_data:
                self.logger.info(f"Applying {len(overlays_data)} overlays.")
                composite_clip = final_video_with_subs
                for overlay_info in overlays_data:
                    overlay_text = overlay_info.get("text")
                    overlay_image_path = overlay_info.get("image_path")
                    start_time = overlay_info.get("start_time", 0)
                    end_time = overlay_info.get("end_time", final_video_with_subs.duration)
                    position_x = overlay_info.get("position_x", "center") # "center" or pixel value
                    position_y = overlay_info.get("position_y", "center") # "center" or pixel value
                    overlay_duration = overlay_info.get("duration", None)

                    if overlay_text:
                        text_clip = TextClip(
                            overlay_text,
                            fontsize=overlay_info.get("font_size", 50),
                            color=overlay_info.get("color", "white"),
                            font=overlay_info.get("font_name", "Arial"),
                            stroke_color=overlay_info.get("stroke_color", None),
                            stroke_width=overlay_info.get("stroke_width", 0),
                            bg_color=overlay_info.get("bg_color", None)
                        )
                        # Set position
                        text_clip = text_clip.set_position((position_x, position_y))
                        # Set duration
                        text_clip = text_clip.set_start(start_time).set_end(end_time)
                        if overlay_duration:
                            text_clip = text_clip.set_duration(overlay_duration)
                        
                        composite_clip = CompositeVideoClip([composite_clip, text_clip])
                        self.logger.debug(f"Added text overlay: '{overlay_text}'")

                    elif overlay_image_path:
                        if Path(overlay_image_path).exists():
                            img_clip = ImageClip(str(overlay_image_path))
                            # Resize if needed
                            img_clip = img_clip.resize(height=overlay_info.get("height", 100)) # Default height for images
                            # Set position
                            img_clip = img_clip.set_position((position_x, position_y))
                            # Set duration
                            img_clip = img_clip.set_start(start_time).set_end(end_time)
                            if overlay_duration:
                                img_clip = img_clip.set_duration(overlay_duration)

                            composite_clip = CompositeVideoClip([composite_clip, img_clip])
                            self.logger.debug(f"Added image overlay: '{overlay_image_path}'")
                        else:
                            self.logger.warning(f"Overlay image not found: {overlay_image_path}")
                final_clip = composite_clip
            else:
                self.logger.info("No overlays to apply.")
                final_clip = final_video_with_subs # Use the video with subtitles if any

            # Final audio assembly
            if audio_for_transcription_path and audio_for_transcription_path.exists():
                self.logger.info("Attaching final audio to video.")
                final_audio_clip = AudioFileClip(str(audio_for_transcription_path))
                final_clip = final_clip.set_audio(final_audio_clip)
            else:
                self.logger.warning("No audio to attach to the final video.")
                final_clip = final_clip.without_audio() # Ensure no audio if not explicitly added

            # Step 7: Export Final Video
            self.logger.info(f"Exporting final social media video to: {output_filepath}")
            self._update_progress(95, "Exporting final video...")
            
            # Ensure final output resolution is correct after all transformations
            target_resolution_str = processing_options.get("target_social_media_resolution", "1080x1920")
            target_width, target_height = map(int, target_resolution_str.split('x'))

            # Resize the final clip to the target social media resolution
            if final_clip.size != (target_width, target_height):
                self.logger.info(f"Resizing final video from {final_clip.size} to {target_width}x{target_height}.")
                final_clip = moviepy_resize_fx(final_clip, newsize=(target_width, target_height))

            final_clip.write_videofile(
                str(output_filepath),
                codec="libx264", # H.264 for broad compatibility
                audio_codec="aac",
                preset="medium",
                threads=os.cpu_count(),
                logger="bar" # Show MoviePy's internal progress
            )

            self._update_progress(100, "Social media video processing complete!")
            self.logger.info(f"Social media video processing completed successfully: {output_filepath}")

            if processing_options.get("delete_original_after_processing", False):
                self.logger.info(f"Attempting to delete original file: {input_filepath}")
                try:
                    os.remove(input_filepath)
                    self.logger.info(f"Original file deleted: {input_filepath}")
                except OSError as e:
                    self.logger.warning(f"Failed to delete original file {input_filepath}: {e}. Skipping deletion.")
            
            self._is_processing = False
            return True, f"Social media video processed successfully! Saved to: {output_filepath}"

        except SocialMediaVideoProcessorError as e:
            self._is_processing = False
            self.logger.error(f"Social media video processing failed: {e}", exc_info=True)
            if output_filepath.exists():
                try:
                    os.remove(output_filepath)
                    self.logger.info(f"Cleaned up partial output file: {output_filepath}")
                except Exception as cleanup_e:
                    self.logger.warning(f"Failed to clean up partial output file {output_filepath}: {cleanup_e}")
            return False, f"Social media video processing failed: {e}"
        except Exception as e:
            self._is_processing = False
            self.logger.critical(f"An unexpected critical error occurred during social media video processing from '{input_filepath}': {e}", exc_info=True)
            if output_filepath.exists():
                try:
                    os.remove(output_filepath)
                    self.logger.info(f"Cleaned up partial output file: {output_filepath}")
                except Exception as cleanup_e:
                    self.logger.warning(f"Failed to clean up partial output file {output_filepath}: {cleanup_e}")
            return False, f"An unexpected error occurred during processing: {e}"
        finally:
            if video_clip: video_clip.close()
            if audio_clip: audio_clip.close()
            if final_clip: final_clip.close()
            if temp_working_dir.exists():
                self.logger.info(f"Cleaning up temporary directory: {temp_working_dir}")
                shutil.rmtree(temp_working_dir, ignore_errors=True)
            self._external_progress_callback = None # Clear callback


    def is_processing(self) -> bool:
        """Returns True if a video processing task is currently in progress, False otherwise."""
        return self._is_processing