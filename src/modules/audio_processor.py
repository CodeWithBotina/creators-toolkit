import os
import shutil
from pathlib import Path
import logging
import numpy as np
from pydub import AudioSegment
from pydub.silence import split_on_silence
import noisereduce as nr
import librosa
import soundfile as sf
from scipy.signal import butter, sosfiltfilt
import webrtcvad # For Voice Activity Detection

from src.core.logger import get_application_logger
from src.core.config_manager import get_application_config

class AudioProcessingError(Exception):
    """Custom exception for audio processing errors."""
    pass

class AudioProcessor:
    """
    Handles audio processing operations, including noise reduction and normalization.
    Designed for efficiency and includes progress tracking for UI updates.
    """
    def __init__(self):
        self.logger = get_application_logger()
        self.config = get_application_config()
        self._is_processing = False # Internal state to track if a process is in progress
        self._external_progress_callback = None # Callback for GUI progress updates

        # Initialize VAD (Voice Activity Detection) - Mode 3 is aggressive
        # Higher mode numbers (0-3) are more aggressive, meaning they are more likely to filter out speech.
        self.vad = webrtcvad.Vad(3) 

        self.logger.info("AudioProcessor initialized.")

    def _update_progress(self, current_step, total_steps, message="", level="info"):
        """
        Internal helper to update progress and log messages.
        Converts step-based progress to a 0-100 integer percentage.
        """
        if self._external_progress_callback:
            if total_steps > 0:
                progress_percentage = int((current_step / total_steps) * 100)
            else:
                progress_percentage = 0 # Or initial value if total_steps is 0
            self._external_progress_callback(progress_percentage, message)
        self.logger.log(getattr(logging, level.upper()), f"AUDIO_PROGRESS: {message} ({current_step}/{total_steps})")


    def process_audio_file(self, input_filepath: Path, output_filepath: Path, delete_original: bool = False, progress_callback_func=None):
        """
        Processes an audio file for noise reduction and normalization.

        Args:
            input_filepath (Path): The path to the input audio file.
            output_filepath (Path): The desired path for the output processed audio file.
            delete_original (bool): If True, the original audio file will be deleted after successful processing.
            progress_callback_func (callable, optional): A function to call with progress updates (0-100 integer, message).
                                                        Signature: `progress_callback_func(progress_int: int, message: str)`
        Returns:
            tuple: (bool, str) - True if successful, False otherwise, and a message.
        """
        if self._is_processing:
            self.logger.warning("Attempted to start audio processing while another is in progress.")
            return False, "Another audio processing task is already in progress. Please wait."

        self._is_processing = True
        self._external_progress_callback = progress_callback_func
        self.logger.info(f"Attempting to process audio from '{input_filepath}' to '{output_filepath}'")
        self._update_progress(0, 100, "Starting audio processing...")

        if not input_filepath.exists():
            self._is_processing = False
            self.logger.error(f"Input audio file not found: {input_filepath}")
            return False, f"Input audio file does not exist: {input_filepath}"

        # Ensure output directory exists
        output_filepath.parent.mkdir(parents=True, exist_ok=True)
        
        audio_segment = None # Initialize to None for finally block
        try:
            # Step 1: Load audio
            self.logger.info(f"Loading audio from: {input_filepath}")
            self._update_progress(5, 100, "Loading audio file...")
            
            # Using pydub to load for broad format support
            audio_segment = AudioSegment.from_file(input_filepath)
            
            # Convert to numpy array for noisereduce and librosa, using 16-bit PCM for VAD
            # Ensure target sample rate (sr) matches what noisereduce/librosa expect and VAD supports (8k, 16k, 32k, 48k)
            target_sr = self.config.get_setting("processing_parameters.audio_enhancement.sample_rate", 48000)
            
            if audio_segment.frame_rate != target_sr:
                self.logger.info(f"Resampling audio from {audio_segment.frame_rate}Hz to {target_sr}Hz.")
                audio_segment = audio_segment.set_frame_rate(target_sr)
            
            # Convert stereo to mono for VAD if needed, and ensure 16-bit depth
            if audio_segment.channels > 1:
                audio_segment = audio_segment.set_channels(1)
            audio_segment = audio_segment.set_sample_width(2) # 16-bit samples

            raw_audio_np = np.array(audio_segment.get_array_of_samples()).astype(np.float32) / (2**15) # Normalize to -1.0 to 1.0

            # Step 2: Noise Reduction
            noise_strength = self.config.get_setting("processing_parameters.audio_enhancement.noise_reduction_strength", 0.5)
            self.logger.info(f"Applying noise reduction with strength: {noise_strength}")
            self._update_progress(20, 100, "Applying noise reduction...")

            # Use noise gate or simple noise reduction. `nr.reduce_noise` is robust.
            # `y_noise` and `sr_noise` can be estimated from silent segments or full audio.
            # For simplicity and speed, let's assume noise is spread throughout for now.
            # A more advanced version might identify silent parts first.
            reduced_noise_audio = nr.reduce_noise(
                y=raw_audio_np, 
                sr=target_sr, 
                prop_decrease=noise_strength,
                stationary=True # Assumes noise is stationary (like fan hum, etc.)
            )

            # Step 3: Voice Activity Detection (VAD) and Silence Removal (Optional, based on config)
            # This is more for segmenting, but can also help clean by removing long silences.
            # If `remove_silence` is enabled, use it.
            remove_silence = self.config.get_setting("processing_parameters.audio_enhancement.remove_silence", False)
            if remove_silence:
                self.logger.info("Applying Voice Activity Detection (VAD) to remove silence.")
                self._update_progress(50, 100, "Detecting and removing silence...")
                
                # Convert numpy array back to pydub AudioSegment for split_on_silence
                clean_audio_segment = AudioSegment(
                    (reduced_noise_audio * (2**15)).astype(np.int16).tobytes(), 
                    frame_rate=target_sr,
                    sample_width=2,
                    channels=1
                )

                min_silence_len = self.config.get_setting("processing_parameters.audio_enhancement.min_silence_len_ms", 1000)
                silence_thresh_db = self.config.get_setting("processing_parameters.audio_enhancement.silence_thresh_db", -35)

                audio_chunks = split_on_silence(
                    clean_audio_segment,
                    min_silence_len=min_silence_len,
                    silence_thresh=silence_thresh_db,
                    keep_silence=200 # Keep a small amount of silence at chunk edges
                )
                if not audio_chunks:
                    self.logger.warning("No audio chunks detected after silence removal. Output will be empty.")
                    # Create an empty audio segment
                    final_audio_segment = AudioSegment.silent(duration=0, frame_rate=target_sr, sample_width=2)
                else:
                    final_audio_segment = sum(audio_chunks)
                final_audio_np = np.array(final_audio_segment.get_array_of_samples()).astype(np.float32) / (2**15)
            else:
                final_audio_np = reduced_noise_audio # If no silence removal, use noise-reduced audio

            # Step 4: Normalization
            normalize_level_dbfs = self.config.get_setting("processing_parameters.audio_enhancement.normalization_level_dbfs", -3.0)
            self.logger.info(f"Applying normalization to {normalize_level_dbfs} dBFS.")
            self._update_progress(75, 100, "Applying normalization...")

            # Convert numpy array back to pydub AudioSegment for normalization
            # Ensure final_audio_np is not empty before converting
            if final_audio_np.size == 0:
                self.logger.warning("Final audio numpy array is empty after processing. Skipping normalization.")
                final_normalized_audio_segment = AudioSegment.silent(duration=0, frame_rate=target_sr, sample_width=2)
            else:
                audio_for_norm = AudioSegment(
                    (final_audio_np * (2**15)).astype(np.int16).tobytes(), 
                    frame_rate=target_sr,
                    sample_width=2,
                    channels=1
                )
                final_normalized_audio_segment = audio_for_norm.normalize(normalize_level_dbfs)

            # Step 5: Save Result
            self.logger.info(f"Saving processed audio to: {output_filepath}")
            self._update_progress(90, 100, "Saving processed audio...")
            
            # Ensure the output format is compatible with soundfile and the desired extension
            output_format = output_filepath.suffix[1:].lower() # Get extension without dot, e.g., 'flac' or 'wav'
            if output_format not in ['flac', 'wav', 'mp3', 'ogg', 'aac']: # Supported formats by pydub for export
                # Default to FLAC for high quality if unknown or unsupported
                output_format = 'flac'
                output_filepath = output_filepath.with_suffix('.flac')
                self.logger.warning(f"Unsupported output format '{output_filepath.suffix}', defaulting to .flac")

            final_normalized_audio_segment.export(output_filepath, format=output_format)

            self._update_progress(100, 100, "Audio processing complete!")
            self.logger.info(f"Audio processing completed successfully: {output_filepath}")

            if delete_original:
                self.logger.info(f"Attempting to delete original file: {input_filepath}")
                try:
                    os.remove(input_filepath)
                    self.logger.info(f"Original file deleted: {input_filepath}")
                except OSError as e:
                    self.logger.warning(f"Failed to delete original file {input_filepath}: {e}. Skipping deletion.")
            
            self._is_processing = False
            return True, f"Audio processing complete! Saved to: {output_filepath}"

        except AudioProcessingError as e:
            self._is_processing = False
            self.logger.error(f"Audio processing failed: {e}", exc_info=True)
            if output_filepath.exists():
                try:
                    os.remove(output_filepath)
                    self.logger.info(f"Cleaned up partial output file: {output_filepath}")
                except Exception as cleanup_e:
                    self.logger.warning(f"Failed to clean up partial output file {output_filepath}: {cleanup_e}")
            return False, f"Audio processing failed: {e}"
        except Exception as e:
            self._is_processing = False
            self.logger.error(f"An unexpected error occurred during audio processing from '{input_filepath}' to '{output_filepath}': {e}", exc_info=True)
            if output_filepath.exists():
                try:
                    os.remove(output_filepath)
                    self.logger.info(f"Cleaned up partial output file: {output_filepath}")
                except Exception as cleanup_e:
                    self.logger.warning(f"Failed to clean up partial output file {output_filepath}: {cleanup_e}")
            return False, f"Audio processing failed: {e}"
        finally:
            # Ensure any loaded audio resources are released if necessary
            # pydub's AudioSegment manages its own memory, explicit close not usually needed.
            self._external_progress_callback = None # Clear callback to prevent stale references


    def is_processing(self) -> bool:
        """Returns True if an audio processing task is currently in progress, False otherwise."""
        return self._is_processing

# Example Usage (for testing this module independently)
if __name__ == "__main__":
    import time
    # This example requires a dummy audio file. You can create a short .wav or .mp3.
    # For a real test, replace 'test_audio.wav' with an actual audio file path.
    
    # Setup logger for standalone testing
    current_dir = Path(__file__).parent
    logs_dir = current_dir.parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True) # Ensure logs directory exists
    from src.core.logger import AppLogger
    AppLogger(log_dir=str(logs_dir), log_level=logging.DEBUG)
    test_logger = get_application_logger()
    test_logger.info("--- Starting AudioProcessor module test ---")

    test_input_dir = current_dir.parent.parent / "test_media"
    test_input_dir.mkdir(exist_ok=True)
    test_output_dir = current_dir.parent.parent / "test_output"
    test_output_dir.mkdir(exist_ok=True)

    dummy_audio_path = test_input_dir / "test_audio.wav" # Ensure this file exists for testing
    output_audio_path = test_output_dir / "processed_test_audio.flac"

    # Create a dummy audio file if it doesn't exist (for testing purposes)
    if not dummy_audio_path.exists():
        test_logger.info(f"Creating a dummy audio file: {dummy_audio_path}")
        try:
            # Create 5 seconds of silent WAV audio for testing
            audio_segment = AudioSegment.silent(duration=5000, frame_rate=48000, sample_width=2)
            audio_segment.export(dummy_audio_path, format="wav")
            test_logger.info("Dummy audio file created.")
        except Exception as e:
            test_logger.error(f"Could not create dummy audio file: {e}. Please manually create {dummy_audio_path} for testing.", exc_info=True)
            dummy_audio_path = None # Mark as not available for testing

    if dummy_audio_path and dummy_audio_path.exists():
        test_logger.info("\n--- Starting audio processing tests ---")
        processor = AudioProcessor()

        def my_progress_callback(progress_value: int, message: str):
            """Simple progress callback for demonstration."""
            test_logger.info(f"Processing Progress: {progress_value}% - {message}")

        # Test 1: Successful audio processing
        test_logger.info(f"\n--- Test 1: Processing audio ({dummy_audio_path}) ---")
        success, message = processor.process_audio_file(dummy_audio_path, output_audio_path, progress_callback_func=my_progress_callback)
        test_logger.info(f"Result: {message} (Success: {success})")
        assert success and output_audio_path.exists()

        # Test 2: File not found
        test_logger.info(f"\n--- Test 2: Non-existent input file ---")
        non_existent_path = test_input_dir / "non_existent_audio.mp3"
        success, message = processor.process_audio_file(non_existent_path, test_output_dir / "non_existent_output.flac", progress_callback_func=my_progress_callback)
        test_logger.info(f"Result: {message} (Success: {success})")
        assert not success and "Input audio file does not exist" in message

        test_logger.info("\n--- All audio processing tests completed ---")
        test_logger.info("Please check the 'test_output' directory for processed audio files.")
    else:
        test_logger.error("Skipping audio processing tests due to missing dummy audio file or creation failure.")
    test_logger.info("--- AudioProcessor module test completed ---")
