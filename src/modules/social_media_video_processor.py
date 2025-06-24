import os
import shutil
import subprocess
import logging
import cv2
import numpy as np
from pathlib import Path
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip, ImageClip
from moviepy.video.fx.all import crop as moviepy_crop_fx, resize as moviepy_resize_fx, set_position
from pydub import AudioSegment
from pydub.silence import split_on_silence
import speech_recognition as sr
from typing import List, Dict, Any, Optional, Tuple
import math
import tempfile
import atexit # For ensuring cleanup of temporary files/dirs

# Core modules
from src.core.logger import get_application_logger
from src.core.config_manager import get_application_config
from src.utils.font_manager import get_application_font_manager

# Import specific modules for enhancements if needed, or implement basic logic here
# For now, integrating basic enhancement logic directly for simplicity,
# but can be refactored to use VideoEnhancer/AudioProcessor modules in the future.
import noisereduce as nr
import librosa # For audio processing, if needed beyond pydub

class SocialMediaVideoProcessorError(Exception):
    """Custom exception for social media video processor errors."""
    pass

class SocialMediaVideoProcessor:
    """
    Processes video for social media platforms, focusing on:
    - Intelligent cropping to 9:16 aspect ratio with subject tracking.
    - Automatic and precisely synchronized subtitle generation with customization options.
    - Intelligent removal of silent or non-speech segments.
    - Automatic video and audio quality enhancements.
    - Support for overlaying images, text, and additional audio tracks.
    """
    def __init__(self):
        self.logger = get_application_logger()
        self.config = get_application_config()
        self.font_manager = get_application_font_manager()
        self._is_processing = False
        self._external_progress_callback = None
        self.temp_dir = None # To store temporary files for the current processing session

        # Load OpenCV's Haar Cascade for face detection
        # Ensure this file is accessible. It's usually part of OpenCV installation.
        self.face_cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        if not Path(self.face_cascade_path).exists():
            self.logger.error(f"Haar cascade file not found: {self.face_cascade_path}. Face tracking will be disabled.")
            self.face_cascade = None # Disable face detection if file is missing
        else:
            self.face_cascade = cv2.CascadeClassifier(self.face_cascade_path)
            if self.face_cascade.empty():
                self.logger.error(f"Could not load Haar cascade classifier from {self.face_cascade_path}. Face tracking will be disabled.")
                self.face_cascade = None

        self.recognizer = sr.Recognizer()

        self.logger.info("SocialMediaVideoProcessor initialized.")
        atexit.register(self._cleanup_temp_dir_on_exit) # Register cleanup on app exit

    def _update_progress(self, progress_percentage: int, message: str, level: str = "info"):
        """
        Internal helper to update progress and log messages.
        """
        if self._external_progress_callback:
            # Ensure progress_percentage is within [0, 100]
            progress_percentage = max(0, min(100, progress_percentage))
            self._external_progress_callback(progress_percentage, message)
        self.logger.log(getattr(logging, level.upper()), f"SOCIAL_MEDIA_PROCESS_PROGRESS: {message} ({progress_percentage}%)")

    def _create_temp_directory(self):
        """Creates a temporary directory for the current processing session."""
        self.temp_dir = Path(tempfile.mkdtemp(prefix="creators_toolkit_social_media_"))
        self.logger.debug(f"Created temporary directory: {self.temp_dir}")

    def _cleanup_temp_dir_on_exit(self):
        """Cleanup temporary directory if it exists."""
        if self.temp_dir and self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
                self.logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
                self.temp_dir = None
            except Exception as e:
                self.logger.warning(f"Failed to remove temporary directory {self.temp_dir}: {e}")

    def _get_video_info(self, video_path: Path) -> Dict[str, Any]:
        """
        Uses ffprobe to get video duration, width, height, and FPS.
        """
        command = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0", # Select only video stream
            "-show_entries", "stream=width,height,avg_frame_rate,duration",
            "-of", "json",
            str(video_path)
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            info = json.loads(result.stdout)
            
            width = info['streams'][0]['width']
            height = info['streams'][0]['height']
            avg_frame_rate_str = info['streams'][0]['avg_frame_rate']
            # Convert fraction to float (e.g., "30000/1001" to 29.97)
            num, den = map(int, avg_frame_rate_str.split('/'))
            fps = num / den
            duration = float(info['streams'][0]['duration'])

            return {"width": width, "height": height, "fps": fps, "duration": duration}
        except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError, IndexError, ValueError) as e:
            self.logger.error(f"Failed to get video info for {video_path} using ffprobe: {e}", exc_info=True)
            raise SocialMediaVideoProcessorError(f"Could not determine video info. Is FFprobe installed and is the video valid? Error: {e}")
        except FileNotFoundError:
            self.logger.error("ffprobe executable not found. Please ensure FFmpeg (which includes ffprobe) is installed and in your PATH.")
            raise SocialMediaVideoProcessorError("FFprobe not found. Please install FFmpeg.")


    def _extract_audio(self, video_path: Path, output_audio_path: Path):
        """Extracts audio from video and saves it to a temporary file."""
        self._update_progress(5, "Extracting audio...")
        self.logger.info(f"Extracting audio from '{video_path}' to '{output_audio_path}'")
        command = [
            "ffmpeg",
            "-i", str(video_path),
            "-vn",             # No video
            "-c:a", "aac",     # Encode to AAC for broader compatibility and smaller size
            "-b:a", "192k",    # Audio bitrate
            "-y",              # Overwrite output file
            str(output_audio_path)
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            self.logger.info("Audio extraction successful.")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"FFmpeg audio extraction failed: {e.stderr}", exc_info=True)
            raise SocialMediaVideoProcessorError(f"Failed to extract audio: {e.stderr.strip()}")
        except FileNotFoundError:
            raise SocialMediaVideoProcessorError("FFmpeg not found. Please ensure FFmpeg is installed and in your system's PATH.")

    def _transcribe_audio(self, audio_path: Path) -> List[Dict[str, Any]]:
        """
        Transcribes audio to text with timestamps using Google Web Speech API.
        Returns a list of dictionaries: [{'text': ..., 'start': ..., 'end': ...}].
        """
        self._update_progress(10, "Transcribing audio (this may take a while)...")
        self.logger.info(f"Transcribing audio from: {audio_path}")
        
        try:
            audio = AudioSegment.from_file(audio_path)
            # Adjust frame rate for WebRTCVAD compatible segmentation later if needed, but SR handles chunks
            # For accurate timing, it's better to process in chunks.
            
            # Split audio into manageable chunks if very long, but for now, SR can handle larger files.
            # SpeechRecognition's recognize_google can often handle the chunking internally for larger files,
            # but for more robust timestamping, manual chunking might be considered with silence detection.
            
            # Using recognizer.record(source) with AudioFile allows it to read the whole file
            with sr.AudioFile(str(audio_path)) as source:
                audio_listened = self.recognizer.record(source)
            
            # Use recognize_google for transcription.
            # Currently, speech_recognition's built-in Google API does not return word-level timestamps directly.
            # To get word-level timestamps, one would typically need to use:
            # 1. A different API (e.g., Google Cloud Speech-to-Text API with word-level confidence).
            # 2. A more complex offline model (e.g., Vosk, Whisper).
            #
            # Given the current setup, we can only get sentence/phrase-level timestamps by:
            # a) Splitting audio by silence first, then transcribing each segment.
            # b) Using a library like `aeneas` for forced alignment (more complex setup).
            
            # For "precise synchronization" and "3 words per line", splitting by silence first is key.
            # Let's adapt the strategy to split by silence, then transcribe.

            # Load audio for silence splitting
            audio_segment = AudioSegment.from_file(audio_path)
            
            min_silence_len_ms = self.config.get_setting("processing_parameters.social_media_post_processing.min_silence_duration_ms", 1000)
            silence_thresh_db = self.config.get_setting("processing_parameters.social_media_post_processing.silence_threshold_db", -40)

            audio_chunks = split_on_silence(
                audio_segment,
                min_silence_len=min_silence_len_ms,
                silence_thresh=silence_thresh_db,
                keep_silence=200 # Keep 200ms of silence at chunk edges for natural sound
            )

            transcripts = []
            current_time_ms = 0
            total_chunks = len(audio_chunks)
            self.logger.debug(f"Audio split into {total_chunks} chunks for transcription.")

            for i, chunk in enumerate(audio_chunks):
                chunk_start_ms = current_time_ms
                chunk_end_ms = current_time_ms + len(chunk)

                # Export chunk to a temporary WAV file for speech_recognition
                chunk_file = self.temp_dir / f"chunk_{i}.wav"
                chunk.export(chunk_file, format="wav")

                with sr.AudioFile(str(chunk_file)) as source:
                    audio_listened = self.recognizer.record(source)
                    try:
                        text = self.recognizer.recognize_google(audio_listened, language="en-US") # Assuming English for now
                        self.logger.debug(f"Chunk {i} transcribed: '{text}'")
                        
                        # Here's the critical part: breaking into 3-word segments
                        words = text.split()
                        words_per_line = self.config.get_setting("processing_parameters.social_media_post_processing.subtitle_words_per_line", 3)
                        
                        for j in range(0, len(words), words_per_line):
                            line_text = " ".join(words[j : j + words_per_line])
                            # Approximate timing for each line within the chunk.
                            # This is a simplification; for true word-level, a different SR setup is needed.
                            # But for "aligned with what is said", chunk-level accuracy is a start.
                            # We can refine this later if real-time word-level SR is integrated.
                            line_start_ms = chunk_start_ms + (j / len(words)) * len(chunk) if len(words) > 0 else chunk_start_ms
                            line_end_ms = chunk_start_ms + ((j + words_per_line) / len(words)) * len(chunk) if len(words) > 0 else chunk_end_ms
                            line_end_ms = min(line_end_ms, chunk_end_ms) # Ensure end time doesn't exceed chunk end

                            transcripts.append({
                                'text': line_text,
                                'start': line_start_ms / 1000.0, # Convert to seconds
                                'end': line_end_ms / 1000.0 # Convert to seconds
                            })
                    except sr.UnknownValueError:
                        self.logger.warning(f"Could not understand audio in chunk {i}")
                    except sr.RequestError as e:
                        self.logger.error(f"Could not request results from Google Speech Recognition service; {e}", exc_info=True)
                        raise SocialMediaVideoProcessorError(f"Speech Recognition service error: {e}")
                    except Exception as e:
                        self.logger.error(f"Error during chunk transcription: {e}", exc_info=True)
                
                current_time_ms = chunk_end_ms # Move time forward for next chunk
                self._update_progress(10 + int((i / total_chunks) * 20), f"Transcribing audio chunk {i+1}/{total_chunks}...")

            return transcripts
        except Exception as e:
            self.logger.error(f"Error during audio transcription: {e}", exc_info=True)
            raise SocialMediaVideoProcessorError(f"Audio transcription failed: {e}")

    def _identify_and_remove_silent_segments(self, original_clip: VideoFileClip, original_audio_path: Path) -> VideoFileClip:
        """
        Identifies silent segments in the audio and removes corresponding parts from the video.
        Returns a new video clip without silent parts.
        """
        if not self.config.get_setting("processing_parameters.social_media_post_processing.auto_remove_silent_segments", True):
            self.logger.info("Automatic silent segment removal is disabled by configuration.")
            return original_clip

        self._update_progress(30, "Analyzing audio for silent segments...")
        self.logger.info("Identifying silent segments for removal.")

        try:
            audio_segment = AudioSegment.from_file(original_audio_path)
            min_silence_len_ms = self.config.get_setting("processing_parameters.social_media_post_processing.min_silence_duration_ms", 1000)
            silence_thresh_db = self.config.get_setting("processing_parameters.social_media_post_processing.silence_threshold_db", -40)

            # This splits the audio into non-silent parts, keeping silence at edges for smooth transitions
            audio_parts = split_on_silence(
                audio_segment,
                min_silence_len=min_silence_len_ms,
                silence_thresh=silence_thresh_db,
                keep_silence=200 # Keep a short silence to prevent abrupt cuts
            )

            # Reconstruct transcript based on speech parts to only keep spoken content
            # (If _transcribe_audio was used to split by silence, this step might be redundant)
            
            # Create a list of (start_time_sec, end_time_sec) for the *spoken* parts
            spoken_intervals = []
            current_time_ms = 0
            for part in audio_parts:
                start_sec = current_time_ms / 1000.0
                end_sec = (current_time_ms + len(part)) / 1000.0
                spoken_intervals.append((start_sec, end_sec))
                current_time_ms += len(part)

            if not spoken_intervals:
                self.logger.warning("No speech detected in the audio. Returning original video.")
                return original_clip # Return original if no speech

            self.logger.info(f"Identified {len(spoken_intervals)} spoken intervals.")
            
            # Create subclips from the original video based on spoken intervals
            clips_to_concatenate = []
            for i, (start, end) in enumerate(spoken_intervals):
                self.logger.debug(f"Extracting subclip from {start:.2f}s to {end:.2f}s (Part {i+1}).")
                # Ensure start and end times are within the video's duration
                start = max(0, start)
                end = min(original_clip.duration, end)
                if end > start: # Only add if valid duration
                    clips_to_concatenate.append(original_clip.subclip(start, end))

            if not clips_to_concatenate:
                self.logger.warning("No valid video segments to concatenate after silent removal. Returning original video.")
                return original_clip

            final_video = MoviePyEditor.concatenate_videoclips(clips_to_concatenate) # Using MoviePy directly here
            self.logger.info(f"Video trimmed by removing silent segments. New duration: {final_video.duration:.2f}s")
            self._update_progress(35, "Silent segments removed.")
            return final_video

        except Exception as e:
            self.logger.error(f"Error identifying or removing silent segments: {e}", exc_info=True)
            self._update_progress(35, "Failed to remove silent segments (continuing with full video).", "warning")
            return original_clip # Fallback to original clip if silent removal fails

    def _auto_crop_and_resize(self, original_clip: VideoFileClip, target_aspect_ratio: float = 9/16, smoothing_frames: int = 5) -> VideoFileClip:
        """
        Analyzes video frames for faces, calculates a smoothed center, and creates a new
        VideoFileClip that is cropped and resized to the target aspect ratio,
        following the main subject(s).
        """
        self._update_progress(40, "Analyzing video for intelligent cropping...")
        self.logger.info(f"Applying intelligent cropping to aspect ratio {target_aspect_ratio:.2f}.")

        if not self.face_cascade:
            self.logger.warning("Face detection not available. Skipping intelligent cropping. Video will be center-cropped.")
            # Fallback to simple center crop if face detection is not available
            return original_clip.fx(moviepy_resize_fx, width=original_clip.h * target_aspect_ratio).set_pos("center") # Resize to target width and center

        # Determine target dimensions
        original_width, original_height = original_clip.w, original_clip.h
        target_height = original_height # Keep original height, crop width
        target_width = int(target_height * target_aspect_ratio)

        if target_width > original_width:
            self.logger.warning(f"Target width ({target_width}) is greater than original width ({original_width}). Resizing original video to fit target aspect ratio.")
            original_clip = original_clip.fx(moviepy_resize_fx, width=target_width) # Scale up if necessary
            original_width = original_clip.w
            original_height = original_clip.h # Update original dimensions

        # Analyze frames to find face positions
        face_centers = [] # List of (x, y) coordinates for each frame
        self.logger.debug("Detecting faces in each frame...")

        # Process frames in batches or iteratively to save memory
        frame_iter = original_clip.iter_frames(fps=5, progress_callback=lambda x: self._update_progress(40 + int(x/original_clip.duration * 10), "Detecting faces...")) # Sample at 5 FPS for speed

        for i, frame in enumerate(frame_iter):
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            faces = self.face_cascade.detectMultiScale(gray_frame, 1.1, 5) # scaleFactor, minNeighbors

            if len(faces) > 0:
                # Use the largest face or the average of all faces
                main_face = max(faces, key=lambda rect: rect[2] * rect[3]) # Face with largest area
                (x, y, w, h) = main_face
                center_x = x + w // 2
                center_y = y + h // 2
                face_centers.append((center_x, center_y))
            else:
                # If no face, keep the last known position or center
                if face_centers:
                    face_centers.append(face_centers[-1]) # Use last known position
                else:
                    face_centers.append((original_width // 2, original_height // 2)) # Default to center

        if not face_centers:
            self.logger.warning("No faces detected throughout the video. Falling back to simple center crop.")
            return original_clip.fx(moviepy_crop_fx, width=target_width, height=target_height, x_center=original_width/2, y_center=original_height/2)


        # Smooth the face center trajectory
        smoothed_centers = []
        for i in range(len(face_centers)):
            start_idx = max(0, i - smoothing_frames // 2)
            end_idx = min(len(face_centers), i + smoothing_frames // 2 + 1)
            
            # Calculate average for smoothing window
            x_coords = [c[0] for c in face_centers[start_idx:end_idx]]
            y_coords = [c[1] for c in face_centers[start_idx:end_idx]]
            
            smoothed_centers.append((int(np.mean(x_coords)), int(np.mean(y_coords))))
        
        # Now, create a function for MoviePy's custom transform based on smoothed centers
        # This function determines the x-offset for the crop for each frame.
        def get_crop_x(t):
            # Map time 't' (seconds) to frame index
            frame_idx = int(t * original_clip.fps)
            if frame_idx >= len(smoothed_centers):
                frame_idx = len(smoothed_centers) - 1 # Cap to last known center

            center_x, _ = smoothed_centers[frame_idx]
            
            # Calculate the x-position for the crop, ensuring it stays within bounds
            # The crop's left edge is (center_x - target_width / 2)
            # The crop's right edge is (center_x + target_width / 2)
            
            # Ensure the crop window does not go beyond the original video edges
            left_bound = 0
            right_bound = original_width - target_width

            desired_x_start = center_x - target_width // 2
            
            # Clamp the desired x_start within valid bounds
            final_x_start = max(left_bound, min(right_bound, desired_x_start))

            return final_x_start

        self._update_progress(50, "Applying dynamic cropping...")
        cropped_clip = original_clip.fx(
            moviepy_crop_fx, 
            width=target_width, 
            height=target_height, 
            x=get_crop_x, # Dynamic x position
            y_center=original_height // 2 # Keep y-center constant for now (vertical centering assumed for 9:16)
        )
        self.logger.info(f"Video cropped dynamically to {target_width}x{target_height}.")
        self._update_progress(55, "Video intelligently cropped.")
        return cropped_clip

    def _apply_automatic_enhancements(self, video_clip: VideoFileClip, audio_clip: AudioFileClip) -> Tuple[VideoFileClip, AudioFileClip]:
        """
        Applies automatic video and audio quality enhancements based on configuration.
        This is a simplified integration. For full control, external modules should be used.
        """
        self._update_progress(60, "Applying automatic video and audio enhancements...")
        self.logger.info("Starting automatic quality enhancements.")

        # --- Video Enhancement ---
        apply_video_enhancement = self.config.get_setting("processing_parameters.social_media_post_processing.apply_auto_video_enhancement", True)
        if apply_video_enhancement:
            self.logger.debug("Applying video enhancements.")
            params = self.config.get_setting("processing_parameters.video_enhancement") # Reuse params from video_enhancer

            filters = []
            denoise_strength = params.get("denoise_strength", 2.0)
            if denoise_strength > 0:
                filters.append(f"hqdn3d={denoise_strength}:{denoise_strength}:{denoise_strength}:{denoise_strength}")

            sharpen_strength = params.get("sharpen_strength", 0.5)
            if sharpen_strength > 0:
                amount = 0.5 + (sharpen_strength * 1.0)
                filters.append(f"unsharp=5:5:{amount}:5:5:0.0")

            contrast = params.get("contrast_enhance", 1.1)
            brightness = params.get("brightness", 0.0)
            saturation = params.get("saturation", 1.1)
            gamma = params.get("gamma", 1.0)
            shadow_highlight = params.get("shadow_highlight", 0.2) # Use for slight adjustment

            adjusted_contrast = contrast + (shadow_highlight * 0.1)
            adjusted_brightness = brightness + (shadow_highlight * 0.05)

            filters.append(f"eq=contrast={adjusted_contrast}:brightness={adjusted_brightness}:saturation={saturation}:gamma={gamma}")

            if filters:
                video_clip = video_clip.fx(lambda clip: clip.fl_image(
                    lambda img_array: self._apply_ffmpeg_filters_to_image(img_array, ",".join(filters)))
                )
                self.logger.debug("Video filters applied via MoviePy's fl_image.")
            else:
                self.logger.debug("No video filters to apply.")
        else:
            self.logger.info("Automatic video enhancement disabled.")

        # --- Audio Enhancement ---
        apply_audio_enhancement = self.config.get_setting("processing_parameters.social_media_post_processing.apply_auto_audio_enhancement", True)
        if apply_audio_enhancement:
            self.logger.debug("Applying audio enhancements.")
            audio_params = self.config.get_setting("processing_parameters.audio_enhancement") # Reuse params from audio_enhancement

            # Convert MoviePy AudioFileClip to pydub AudioSegment for processing
            audio_segment_path = self.temp_dir / "temp_audio_for_enhancement.wav"
            audio_clip.write_audiofile(str(audio_segment_path), logger=None)
            
            try:
                audio_segment = AudioSegment.from_file(audio_segment_path)

                # Noise Reduction
                noise_reduction_strength = audio_params.get("noise_reduction_strength", 0.5)
                if noise_reduction_strength > 0:
                    self.logger.debug(f"Applying noise reduction with strength: {noise_reduction_strength}")
                    # noisereduce works on numpy arrays
                    y, sr = librosa.load(str(audio_segment_path), sr=audio_params.get("sample_rate", 48000), mono=True) # Load as mono for NR
                    # Estimate noise profile (e.g., from first 0.5 seconds or a dedicated silent part)
                    noise_len = min(int(0.5 * sr), len(y)) # Estimate noise from first 0.5s
                    noise_profile = y[0:noise_len]
                    reduced_noise_audio = nr.reduce_noise(audio_clip=y, noise_clip=noise_profile, verbose=False,
                                                          prop_decrease=noise_reduction_strength) # prop_decrease controls strength

                    # Convert back to AudioSegment
                    enhanced_audio_segment = AudioSegment(
                        reduced_noise_audio.tobytes(), 
                        frame_rate=sr,
                        sample_width=reduced_noise_audio.dtype.itemsize,
                        channels=1 # Assuming mono after noise reduction
                    )
                    # If original was stereo, convert back to stereo by duplicating channel
                    if audio_clip.nchannels == 2:
                        enhanced_audio_segment = enhanced_audio_segment.set_channels(2)
                    self.logger.debug("Noise reduction applied.")
                else:
                    enhanced_audio_segment = audio_segment

                # Normalization
                normalization_level_dbfs = audio_params.get("normalization_level_dbfs", -3.0)
                if normalization_level_dbfs is not None:
                    self.logger.debug(f"Applying normalization to {normalization_level_dbfs} dBFS.")
                    enhanced_audio_segment = enhanced_audio_segment.normalize(headroom=abs(normalization_level_dbfs))
                    self.logger.debug("Normalization applied.")
                
                # Re-export to MoviePy AudioFileClip
                enhanced_audio_path = self.temp_dir / "temp_enhanced_audio.wav"
                enhanced_audio_segment.export(enhanced_audio_path, format="wav")
                audio_clip = AudioFileClip(str(enhanced_audio_path))
                self.logger.info("Audio enhancements applied.")

            except Exception as e:
                self.logger.error(f"Error applying audio enhancements: {e}", exc_info=True)
                self._update_progress(65, "Failed to apply audio enhancements.", "warning")
                # Continue with original audio clip if enhancement fails
        else:
            self.logger.info("Automatic audio enhancement disabled.")

        self._update_progress(65, "Automatic enhancements applied.")
        return video_clip, audio_clip

    # Helper function for applying FFmpeg filters to a single image (from a frame)
    def _apply_ffmpeg_filters_to_image(self, img_array: np.ndarray, filter_string: str) -> np.ndarray:
        """
        Applies FFmpeg video filters to a single NumPy image array.
        This is a workaround to apply FFmpeg filters within MoviePy's fl_image.
        It's not highly efficient for every frame but good for a few filters.
        """
        if not filter_string:
            return img_array

        # Convert numpy array (RGB) to bytes for ffmpeg input
        # Use stdin pipe for input, stdout pipe for output
        h, w, _ = img_array.shape
        command = [
            "ffmpeg",
            "-y", # Overwrite if exists
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{w}x{h}", # Size of the image
            "-pix_fmt", "rgb24", # Input pixel format
            "-r", "1", # Frame rate (dummy for single frame)
            "-i", "-", # Input from stdin
            "-vf", filter_string,
            "-pix_fmt", "rgb24", # Output pixel format
            "-f", "image2pipe", # Output to pipe as raw image
            "-" # Output to stdout
        ]
        
        try:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
            output_bytes, stderr_output = process.communicate(input=img_array.tobytes())
            
            if process.returncode != 0:
                self.logger.error(f"FFmpeg filter application failed: {stderr_output.decode().strip()}")
                return img_array # Return original image on failure

            # Convert output bytes back to numpy array
            return np.frombuffer(output_bytes, np.uint8).reshape((h, w, 3))
        except Exception as e:
            self.logger.error(f"Error applying FFmpeg filters via subprocess: {e}", exc_info=True)
            return img_array # Return original image on error


    def _generate_subtitle_clips(self, transcript: List[Dict[str, Any]], video_width: int, video_height: int) -> List[TextClip]:
        """
        Creates MoviePy TextClips for each subtitle entry.
        Applies styling and positioning from config.
        """
        self._update_progress(70, "Generating subtitle clips...")
        self.logger.info("Creating subtitle clips.")

        subtitle_clips = []
        params = self.config.get_setting("processing_parameters.social_media_post_processing")

        font_name = params.get("default_subtitle_font_name", "Arial")
        font_size = params.get("default_subtitle_font_size", 60)
        font_color = params.get("default_subtitle_color", "#FFFFFF")
        stroke_color = params.get("default_subtitle_stroke_color", "#000000")
        stroke_width = params.get("default_subtitle_stroke_width", 2)
        position_y_ratio = params.get("default_subtitle_position_y", 0.8) # From top, 0.0 to 1.0

        # Get font path from FontManager
        font_path = self.font_manager.get_font_path(font_name)
        if not font_path:
            self.logger.error(f"Could not find or download font '{font_name}'. Falling back to default system font.")
            font_path = self.font_manager.get_default_font_path() # Fallback to a system-found default

        for entry in transcript:
            text = entry['text']
            start_time = entry['start']
            end_time = entry['end']

            # MoviePy TextClip
            clip = TextClip(
                txt=text,
                fontsize=font_size,
                color=font_color,
                stroke_color=stroke_color,
                stroke_width=stroke_width,
                font=str(font_path) # MoviePy expects string path
            )
            clip = clip.set_duration(end_time - start_time)
            clip = clip.set_start(start_time)

            # Position the subtitle at the bottom center of the video
            # Positional argument can be a tuple (x,y), string ('center'), or function
            # Here, we set y based on ratio, and x to center.
            clip = clip.set_position(lambda t: ('center', video_height * position_y_ratio - clip.h / 2)) # Center horizontally, fixed Y

            subtitle_clips.append(clip)
        
        self.logger.info(f"Generated {len(subtitle_clips)} subtitle clips.")
        self._update_progress(75, "Subtitle clips created.")
        return subtitle_clips

    def _prepare_overlay_clips(self, overlay_items: List[Dict[str, Any]], video_width: int, video_height: int) -> List[Any]:
        """
        Prepares MoviePy clips for images, additional text, and audio overlays.
        `overlay_items` structure:
        [
            {'type': 'image', 'path': 'assets/overlays/subscribe.png', 'start': 2.0, 'end': 5.0, 'position': ('center', 'bottom'), 'scale': 0.2},
            {'type': 'text', 'text': 'Check out my channel!', 'font_size': 40, 'color': 'yellow', 'start': 6.0, 'end': 8.0, 'position': ('center', 'top')},
            {'type': 'audio', 'path': 'assets/sounds/ding.mp3', 'start': 2.5, 'volume': 0.5}
        ]
        """
        self._update_progress(80, "Preparing overlay clips...")
        self.logger.info("Preparing various overlay content.")

        clips = []
        for item in overlay_items:
            clip = None
            if item['type'] == 'image':
                img_path = Path(item['path'])
                if img_path.exists() and img_path.is_file():
                    try:
                        clip = ImageClip(str(img_path))
                        if 'scale' in item:
                            clip = clip.fx(moviepy_resize_fx, newsize=lambda s: [s[0] * item['scale'], s[1] * item['scale']])
                        elif 'width' in item:
                             clip = clip.fx(moviepy_resize_fx, width=item['width'])
                        elif 'height' in item:
                            clip = clip.fx(moviepy_resize_fx, height=item['height'])

                        clip = clip.set_start(item.get('start', 0))
                        clip = clip.set_duration(item.get('end', clip.duration) - item.get('start', 0))
                        
                        # Set position, supports 'center', 'bottom', 'top', (x,y) tuple
                        pos = item.get('position', ('center', 'center'))
                        if isinstance(pos, tuple) and isinstance(pos[0], str) and isinstance(pos[1], str):
                            clip = clip.set_position(pos)
                        elif isinstance(pos, tuple) and isinstance(pos[0], (int, float)) and isinstance(pos[1], (int, float)):
                            clip = clip.set_position(pos)
                        elif isinstance(pos, str): # e.g., 'center'
                             clip = clip.set_position(pos)
                        else: # Default if complex logic fails
                             clip = clip.set_position(('center', 'center'))

                        self.logger.debug(f"Added image overlay: {item['path']}")
                    except Exception as e:
                        self.logger.warning(f"Failed to load image overlay {item['path']}: {e}", exc_info=True)
                else:
                    self.logger.warning(f"Image overlay path not found: {img_path}")

            elif item['type'] == 'text':
                try:
                    font_path = self.font_manager.get_font_path(item.get('font_name', self.config.get_setting("processing_parameters.social_media_post_processing.default_subtitle_font_name", "Arial")))
                    if not font_path:
                        font_path = self.font_manager.get_default_font_path()

                    clip = TextClip(
                        txt=item['text'],
                        fontsize=item.get('font_size', 40),
                        color=item.get('color', 'white'),
                        stroke_color=item.get('stroke_color', 'black'),
                        stroke_width=item.get('stroke_width', 1),
                        font=str(font_path)
                    )
                    clip = clip.set_start(item.get('start', 0))
                    clip = clip.set_duration(item.get('end', clip.duration) - item.get('start', 0))
                    clip = clip.set_position(item.get('position', ('center', 'center')))
                    self.logger.debug(f"Added text overlay: '{item['text']}'")
                except Exception as e:
                    self.logger.warning(f"Failed to create text overlay '{item['text']}': {e}", exc_info=True)

            elif item['type'] == 'audio':
                audio_path = Path(item['path'])
                if audio_path.exists() and audio_path.is_file():
                    try:
                        clip = AudioFileClip(str(audio_path))
                        clip = clip.set_start(item.get('start', 0))
                        if 'volume' in item:
                            clip = clip.volumex(item['volume'])
                        self.logger.debug(f"Added audio overlay: {item['path']}")
                    except Exception as e:
                        self.logger.warning(f"Failed to load audio overlay {item['path']}: {e}", exc_info=True)
                else:
                    self.logger.warning(f"Audio overlay path not found: {audio_path}")
            
            if clip:
                clips.append(clip)
        
        self.logger.info(f"Prepared {len(clips)} overlay clips.")
        return clips


    def _compose_final_video(self, video_clip: VideoFileClip, audio_clip: AudioFileClip, subtitle_clips: List[TextClip], overlay_clips: List[Any]) -> VideoFileClip:
        """
        Composes all video, audio, subtitle, and overlay clips into a final video.
        """
        self._update_progress(85, "Composing final video...")
        self.logger.info("Composing all elements into final video clip.")

        final_video_clips = [video_clip] + subtitle_clips + [c for c in overlay_clips if isinstance(c, VideoFileClip) or isinstance(c, ImageClip)]
        final_audio_clips = [audio_clip] + [c for c in overlay_clips if isinstance(c, AudioFileClip)]

        # Combine video layers
        # CompositeVideoClip requires all clips to have the same duration or be explicitly set.
        # Ensure that overlay clips have their duration explicitly set or they will expand to longest clip.
        # Here, overlays are already set with start/duration, so they will blend correctly.

        # Ensure all video clips have a defined duration before compositing
        for clip in final_video_clips:
            if not hasattr(clip, 'duration') or clip.duration is None:
                clip.set_duration(video_clip.duration) # Default to main video duration

        final_video = CompositeVideoClip(final_video_clips, size=video_clip.size)
        
        # Combine audio layers
        # Need to handle multiple audio tracks by summing them
        if final_audio_clips:
            # Set duration for all audio clips to match the video
            for audio_c in final_audio_clips:
                if not hasattr(audio_c, 'duration') or audio_c.duration is None:
                    audio_c = audio_c.set_duration(video_clip.duration) # Ensure audio clips match video duration
            
            # Use audioclips_array to mix
            mixed_audio = MoviePyEditor.CompositeAudioClip(final_audio_clips) # Using MoviePy directly
            final_video = final_video.set_audio(mixed_audio)
            self.logger.info("Audio tracks mixed and set to final video.")
        else:
            self.logger.info("No audio tracks to mix. Video will have no audio.")
            final_video = final_video.set_audio(None) # Explicitly set no audio if none are provided or loaded

        self.logger.info("Final video composition complete.")
        self._update_progress(90, "Video composition done.")
        return final_video

    def process_video_for_social_media(
        self, 
        input_filepath: Path, 
        output_filepath: Path, 
        processing_options: Dict[str, Any], 
        progress_callback_func=None
    ) -> Tuple[bool, str]:
        """
        Main orchestration method for social media video processing.

        Args:
            input_filepath (Path): Path to the input video file.
            output_filepath (Path): Desired path for the output processed video.
            processing_options (Dict[str, Any]): Dictionary of options for processing, e.g.:
                - 'auto_remove_silent_segments': bool
                - 'delete_original_after_processing': bool
                - 'overlay_items': List[Dict] (for images, text, extra audio)
            progress_callback_func (callable, optional): Callback for progress updates.
        Returns:
            Tuple[bool, str]: True if successful, False otherwise, and a message.
        """
        if self._is_processing:
            self.logger.warning("Attempted to start social media video processing while another is in progress.")
            return False, "Another social media video processing task is already in progress. Please wait."

        self._is_processing = True
        self._external_progress_callback = progress_callback_func
        self._create_temp_directory()

        self.logger.info(f"Starting social media video processing for: {input_filepath}")
        self._update_progress(0, "Initializing processing...")

        try:
            if not input_filepath.exists() or not input_filepath.is_file():
                raise SocialMediaVideoProcessorError(f"Input video file not found or is not a file: {input_filepath}")
            
            output_filepath.parent.mkdir(parents=True, exist_ok=True) # Ensure output directory exists

            # Step 1: Load original video and audio
            self._update_progress(1, "Loading video and preparing audio...")
            original_clip = VideoFileClip(str(input_filepath), verbose=False)
            
            # Ensure FFmpeg has enough memory, if specific env variable needed
            # os.environ["IMAGEIO_FFMPEG_OPTIONS"] = "-threads 4 -f" # Example, typically not needed unless MoviePy struggles
            
            # Get video info for cropping/resizing
            video_info = self._get_video_info(input_filepath)
            
            # Extract audio to a temporary file for speech recognition and silence detection
            temp_audio_path = self.temp_dir / "extracted_original_audio.wav"
            self._extract_audio(input_filepath, temp_audio_path)
            
            audio_clip_original = AudioFileClip(str(temp_audio_path))

            # Step 2: Automatic Quality Enhancements (Video and Audio)
            processed_video_clip, processed_audio_clip = self._apply_automatic_enhancements(original_clip, audio_clip_original)
            self._update_progress(65, "Automatic enhancements completed.")

            # Step 3: Identify and remove silent segments
            video_after_silence_removal = self._identify_and_remove_silent_segments(processed_video_clip, temp_audio_path)
            self._update_progress(70, "Silence removal handled.")

            # Step 4: Transcribe audio and generate subtitles
            transcript = self._transcribe_audio(temp_audio_path)
            subtitle_clips = self._generate_subtitle_clips(transcript, video_after_silence_removal.w, video_after_silence_removal.h)
            self._update_progress(78, "Subtitles generated.")
            
            # Step 5: Intelligent Cropping and Resizing to 9:16
            # This should happen *after* silence removal as duration might change
            # and before overlays are positioned relative to final dimensions.
            target_aspect_ratio = 9 / 16.0
            smoothing_frames = self.config.get_setting("processing_parameters.social_media_post_processing.face_tracking_smoothing_frames", 5)
            final_video_base = self._auto_crop_and_resize(video_after_silence_removal, target_aspect_ratio, smoothing_frames)
            self._update_progress(80, "Video dynamically cropped and resized.")


            # Step 6: Prepare overlay clips (images, custom text, additional audio)
            overlay_items_from_options = processing_options.get('overlay_items', [])
            overlay_clips = self._prepare_overlay_clips(overlay_items_from_options, final_video_base.w, final_video_base.h)
            self._update_progress(85, "Overlays prepared.")

            # Step 7: Compose final video with all elements
            final_composed_video = self._compose_final_video(final_video_base, processed_audio_clip, subtitle_clips, overlay_clips)
            self._update_progress(95, "Final video composition done.")

            # Step 8: Write the final video file
            self.logger.info(f"Writing final video to: {output_filepath}")
            final_composed_video.write_videofile(
                str(output_filepath),
                codec="libx264",
                audio_codec="aac",
                fps=final_composed_video.fps, # Use the FPS of the final clip
                threads=os.cpu_count(), # Use all available CPU cores for encoding
                preset="medium", # For good balance of speed and quality
                ffmpeg_params=["-crf", "23"], # Constant Rate Factor for quality
                logger="bar" # Use MoviePy's progress bar (if compatible with our custom one)
                # Note: This logger will output to console/moviepy log. Our custom progress bar is separate.
            )
            self._update_progress(100, "Video processing completed successfully!")
            self.logger.info(f"Social media video processing completed: {output_filepath}")

            if processing_options.get('delete_original_after_processing', False):
                self.logger.info(f"Attempting to delete original file: {input_filepath}")
                try:
                    os.remove(input_filepath)
                    self.logger.info(f"Original file deleted: {input_filepath}")
                except OSError as e:
                    self.logger.warning(f"Failed to delete original file {input_filepath}: {e}. Skipping deletion.")
            
            self._is_processing = False
            return True, f"Social media video processing complete! Saved to: {output_filepath}"

        except SocialMediaVideoProcessorError as e:
            self._is_processing = False
            self.logger.error(f"Social media video processing failed: {e}", exc_info=True)
            if output_filepath.exists():
                try:
                    os.remove(output_filepath)
                    self.logger.info(f"Cleaned up partial output file: {output_filepath}")
                except Exception as cleanup_e:
                    self.logger.warning(f"Failed to clean up partial output file {output_filepath}: {cleanup_e}")
            return False, f"Video processing failed: {e}"
        except Exception as e:
            self._is_processing = False
            self.logger.critical(f"An unexpected critical error occurred during social media video processing from '{input_filepath}': {e}", exc_info=True)
            if output_filepath.exists():
                try:
                    os.remove(output_filepath)
                    self.logger.info(f"Cleaned up partial output file: {output_filepath}")
                except Exception as cleanup_e:
                    self.logger.warning(f"Failed to clean up partial output file {output_filepath}: {cleanup_e}")
            return False, f"An unexpected error occurred: {e}"
        finally:
            self._external_progress_callback = None # Clear callback
            self._cleanup_temp_dir_on_exit() # Ensure temporary directory is cleaned up

    def is_processing(self) -> bool:
        """Returns True if a social media video processing task is currently in progress, False otherwise."""
        return self._is_processing

# Aliases for MoviePy functions to avoid name conflicts and make it explicit
class MoviePyEditor:
    """Helper class to encapsulate direct MoviePy functions for clarity."""
    @staticmethod
    def concatenate_videoclips(clips, method="compose"):
        from moviepy.editor import concatenate_videoclips
        return concatenate_videoclips(clips, method=method)

    @staticmethod
    def CompositeAudioClip(clips):
        from moviepy.editor import CompositeAudioClip
        return CompositeAudioClip(clips)


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
    test_logger.info("--- Starting SocialMediaVideoProcessor module test ---")

    test_input_dir = current_dir.parent.parent / "test_media"
    test_input_dir.mkdir(exist_ok=True)
    test_output_dir = current_dir.parent.parent / "test_output"
    test_output_dir.mkdir(exist_ok=True)

    # Assets for overlays
    overlay_assets_dir = current_dir.parent.parent / "assets" / "overlays"
    overlay_assets_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a dummy image overlay if it doesn't exist
    dummy_overlay_image = overlay_assets_dir / "subscribe.png"
    if not dummy_overlay_image.exists():
        test_logger.info(f"Creating dummy overlay image: {dummy_overlay_image}")
        try:
            from PIL import Image, ImageDraw
            img = Image.new('RGBA', (200, 50), color = (255, 0, 0, 150)) # Red, semi-transparent
            d = ImageDraw.Draw(img)
            d.text((10, 10), "SUBSCRIBE", fill=(255,255,255,255))
            img.save(dummy_overlay_image)
            test_logger.info("Dummy overlay image created.")
        except Exception as e:
            test_logger.warning(f"Could not create dummy overlay image: {e}. Skipping image overlay test.", exc_info=True)
            dummy_overlay_image = None
    
    # Create a dummy audio overlay if it doesn't exist
    dummy_audio_overlay = overlay_assets_dir / "ding.mp3"
    if not dummy_audio_overlay.exists():
        test_logger.info(f"Creating dummy audio overlay: {dummy_audio_overlay}")
        try:
            from pydub.generators import Sine
            sine_wave = Sine(440).to_audio_segment(duration=1000).set_frame_rate(44100)
            sine_wave.export(dummy_audio_overlay, format="mp3")
            test_logger.info("Dummy audio overlay created.")
        except Exception as e:
            test_logger.warning(f"Could not create dummy audio overlay: {e}. Skipping audio overlay test.", exc_info=True)
            dummy_audio_overlay = None


    dummy_video_path = test_input_dir / "test_video_for_social_media.mp4" 
    output_social_media_video_path = test_output_dir / "social_media_post.mp4"

    # Create a dummy video file if it doesn't exist (with a moving subject for face detection)
    if not dummy_video_path.exists():
        test_logger.info(f"Creating a dummy video file: {dummy_video_path} (10 seconds, with a face-like moving square)...")
        try:
            # Using FFmpeg to create a video with a moving "face" (red square) on a blue background
            # This is a simplification, but helps test the face tracking logic.
            subprocess.run([
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "color=c=blue:s=1280x720:d=10:r=25,drawbox=x=w/2+sin(t)*w/4:y=h/2+cos(t)*h/4:w=100:h=100:c=red:t=fill", # Moving red square
                "-f", "lavfi", "-i", "sine=frequency=1000:duration=10", # Dummy audio
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", "-preset", "ultrafast",
                "-c:a", "aac", "-b:a", "128k",
                str(dummy_video_path)
            ], check=True, capture_output=True, text=True, timeout=30)
            test_logger.info("Dummy video file created.")
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            test_logger.error(f"Could not create dummy video file: {e}. Please manually create {dummy_video_path} for testing. Ensure FFmpeg is in PATH.", exc_info=True)
            dummy_video_path = None # Mark as not available for testing
    
    # Initialize ConfigManager for testing environment
    config_dir_path = current_dir.parent.parent / "config"
    config_dir_path.mkdir(exist_ok=True)
    from src.core.config_manager import ConfigManager
    # Ensure social_media_post_processing parameters are in default config for testing
    # Will need to manually add them to default config if running this as isolated test before updating config_manager.py
    # This is handled by ensuring config_manager.py is updated first, or by loading a dummy config here.
    ConfigManager(config_dir=str(config_dir_path)) # Re-initialize to ensure it picks up any config changes

    if dummy_video_path and dummy_video_path.exists():
        test_logger.info("\n--- Starting social media video processing tests ---")
        processor = SocialMediaVideoProcessor()

        def my_progress_callback(progress_value: int, message: str):
            """Simple progress callback for demonstration."""
            test_logger.info(f"Processing Progress: {progress_value}% - {message}")

        processing_options = {
            'auto_remove_silent_segments': True,
            'delete_original_after_processing': False,
            'overlay_items': [
                # Example image overlay
                {'type': 'image', 'path': str(dummy_overlay_image), 'start': 1.0, 'end': 4.0, 'position': ('center', 0.8), 'scale': 0.5} if dummy_overlay_image else None,
                # Example text overlay
                {'type': 'text', 'text': 'My Awesome Post!', 'font_size': 80, 'color': 'yellow', 'stroke_color': 'blue', 'stroke_width': 3, 'start': 0.5, 'end': 3.5, 'position': ('center', 0.1)},
                # Example additional audio overlay
                {'type': 'audio', 'path': str(dummy_audio_overlay), 'start': 1.5, 'volume': 0.8} if dummy_audio_overlay else None,
            ]
        }
        # Filter out None items if dummy assets failed to create
        processing_options['overlay_items'] = [item for item in processing_options['overlay_items'] if item is not None]


        # Test 1: Successful video processing
        test_logger.info(f"\n--- Test 1: Processing video ({dummy_video_path}) ---")
        success, message = processor.process_video_for_social_media(
            dummy_video_path, 
            output_social_media_video_path, 
            processing_options,
            progress_callback_func=my_progress_callback
        )
        test_logger.info(f"Result: {message} (Success: {success})")
        assert success and output_social_media_video_path.exists()

        # Test 2: File not found
        test_logger.info(f"\n--- Test 2: Non-existent input file ---")
        non_existent_path = test_input_dir / "non_existent_video.mp4"
        success, message = processor.process_video_for_social_media(
            non_existent_path, 
            test_output_dir / "non_existent_output.mp4", 
            processing_options,
            progress_callback_func=my_progress_callback
        )
        test_logger.info(f"Result: {message} (Success: {success})")
        assert not success and ("Input video file not found" in message or "invalid" in message)

        test_logger.info("\n--- All social media video processing tests completed ---")
        test_logger.info("Please check the 'test_output' directory for processed video files.")
    else:
        test_logger.error("Skipping social media video processing tests due to missing dummy video file or creation failure. Please ensure FFmpeg is installed and accessible, and test_media directory is ready.")
    test_logger.info("--- SocialMediaVideoProcessor module test completed ---")
