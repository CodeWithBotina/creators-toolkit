import os
import io
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
from rembg import remove # Ensure rembg is installed (pip install rembg)
import logging

from src.core.logger import get_application_logger
from src.core.config_manager import get_application_config

class ImageProcessingError(Exception):
    """Custom exception for image processing errors."""
    pass

class ImageBgRemover:
    """
    Handles background removal and optional quality enhancement for images.
    """
    def __init__(self):
        self.logger = get_application_logger()
        self.config = get_application_config()
        self._is_processing = False # Internal state to track if a process is in progress
        self._external_progress_callback = None # Callback for GUI progress updates

        self.logger.info("ImageBgRemover initialized.")

    def _update_progress(self, progress_percentage: int, message: str, level: str = "info"):
        """
        Internal helper to update progress and log messages.
        """
        if self._external_progress_callback:
            self._external_progress_callback(progress_percentage, message)
        self.logger.log(getattr(logging, level.upper()), f"IMAGE_PROGRESS: {message} ({progress_percentage}%)")

    def _enhance_quality(self, image: Image.Image) -> Image.Image:
        """
        Applies quality enhancements to an image (contrast, sharpness, smoothing).
        Ensures the image remains in RGBA mode for transparency.
        """
        self.logger.debug("Applying image quality enhancements.")
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
            
        # Separate RGB and Alpha channels
        rgb = image.convert('RGB')
        alpha = image.getchannel('A')

        # Enhance contrast
        enhancer = ImageEnhance.Contrast(rgb)
        rgb = enhancer.enhance(1.2) # Increased contrast slightly

        # Enhance sharpness
        enhancer = ImageEnhance.Sharpness(rgb)
        rgb = enhancer.enhance(1.3) # Increased sharpness slightly

        # Apply smoothing to reduce noise/pixelation artifacts introduced by processing
        # This is a light smoothing, adjust as needed.
        rgb = rgb.filter(ImageFilter.SMOOTH)

        # Recombine with the original alpha channel
        r, g, b = rgb.split()
        return Image.merge('RGBA', (r, g, b, alpha))

    def remove_background_and_enhance(self, input_filepath: Path, output_filepath: Path, delete_original: bool = False, progress_callback_func=None):
        """
        Removes the background from an image and applies optional quality enhancements.

        Args:
            input_filepath (Path): The path to the input image file.
            output_filepath (Path): The desired path for the output processed image file.
            delete_original (bool): If True, the original image file will be deleted after successful processing.
            progress_callback_func (callable, optional): A function to call with progress updates (0-100 integer, message).
                                                        Signature: `progress_callback_func(progress_int: int, message: str)`
        Returns:
            tuple: (bool, str) - True if successful, False otherwise, and a message.
        """
        if self._is_processing:
            self.logger.warning("Attempted to start image processing while another is in progress.")
            return False, "Another image processing task is already in progress. Please wait."

        self._is_processing = True
        self._external_progress_callback = progress_callback_func
        self.logger.info(f"Attempting to process image from '{input_filepath}' to '{output_filepath}'")
        self._update_progress(0, "Starting image processing...")

        if not input_filepath.exists():
            self._is_processing = False
            self.logger.error(f"Input image file not found: {input_filepath}")
            return False, f"Input image file does not exist: {input_filepath}"
        
        if not input_filepath.is_file():
            self._is_processing = False
            self.logger.error(f"Input path is not a file: {input_filepath}")
            return False, f"Input path is not a file: {input_filepath}"

        # Ensure output directory exists
        output_filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Ensure output file has .png extension for transparency
        if output_filepath.suffix.lower() not in [".png"]:
            self.logger.warning(f"Output file extension changed from '{output_filepath.suffix}' to '.png' for transparency.")
            output_filepath = output_filepath.with_suffix(".png")


        try:
            # Step 1: Load image and remove background
            self.logger.info(f"Loading image and removing background from: {input_filepath}")
            self._update_progress(10, "Removing background...")
            
            with open(input_filepath, 'rb') as f:
                input_bytes = f.read()

            output_bytes = remove(input_bytes) # This is where rembg does its magic
            
            img_processed = Image.open(io.BytesIO(output_bytes)).convert('RGBA')

            # Step 2: Apply quality enhancement if configured
            apply_enhancement = self.config.get_setting("processing_parameters.image_background_removal.image_quality_enhancement", True)
            if apply_enhancement:
                self._update_progress(60, "Enhancing image quality...")
                img_final = self._enhance_quality(img_processed)
            else:
                img_final = img_processed
                self._update_progress(60, "Skipping image quality enhancement.")

            # Step 3: Save Result
            self.logger.info(f"Saving processed image to: {output_filepath}")
            self._update_progress(90, "Saving processed image...")
            
            # Save as PNG to preserve transparency
            img_final.save(output_filepath, "PNG", compress_level=9) # compress_level=9 for max compression

            self._update_progress(100, "Image processing complete!")
            self.logger.info(f"Image processing completed successfully: {output_filepath}")

            if delete_original:
                self.logger.info(f"Attempting to delete original file: {input_filepath}")
                try:
                    os.remove(input_filepath)
                    self.logger.info(f"Original file deleted: {input_filepath}")
                except OSError as e:
                    self.logger.warning(f"Failed to delete original file {input_filepath}: {e}. Skipping deletion.")
            
            self._is_processing = False
            return True, f"Image processing complete! Saved to: {output_filepath}"

        except ImageProcessingError as e:
            self._is_processing = False
            self.logger.error(f"Image processing failed: {e}", exc_info=True)
            if output_filepath.exists():
                try:
                    os.remove(output_filepath)
                    self.logger.info(f"Cleaned up partial output file: {output_filepath}")
                except Exception as cleanup_e:
                    self.logger.warning(f"Failed to clean up partial output file {output_filepath}: {cleanup_e}")
            return False, f"Image processing failed: {e}"
        except Exception as e:
            self._is_processing = False
            self.logger.error(f"An unexpected error occurred during image processing from '{input_filepath}' to '{output_filepath}': {e}", exc_info=True)
            if output_filepath.exists():
                try:
                    os.remove(output_filepath)
                    self.logger.info(f"Cleaned up partial output file: {output_filepath}")
                except Exception as cleanup_e:
                    self.logger.warning(f"Failed to clean up partial output file {output_filepath}: {cleanup_e}")
            return False, f"Image processing failed: {e}"
        finally:
            self._external_progress_callback = None # Clear callback to prevent stale references


    def is_processing(self) -> bool:
        """Returns True if an image processing task is currently in progress, False otherwise."""
        return self._is_processing

# Example Usage (for testing this module independently)
if __name__ == "__main__":
    import time
    # This example requires a dummy image file. You can use a .png or .jpg.
    
    # Setup logger for standalone testing
    current_dir = Path(__file__).parent
    logs_dir = current_dir.parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True) # Ensure logs directory exists
    from src.core.logger import AppLogger
    AppLogger(log_dir=str(logs_dir), log_level=logging.DEBUG)
    test_logger = get_application_logger()
    test_logger.info("--- Starting ImageBgRemover module test ---")

    test_input_dir = current_dir.parent.parent / "test_media"
    test_input_dir.mkdir(exist_ok=True)
    test_output_dir = current_dir.parent.parent / "test_output"
    test_output_dir.mkdir(exist_ok=True)

    dummy_image_path = test_input_dir / "test_image.png" # Ensure this file exists for testing
    output_image_path = test_output_dir / "processed_test_image_nobg.png"

    # Create a dummy image file if it doesn't exist (for testing purposes)
    if not dummy_image_path.exists():
        test_logger.info(f"Creating a dummy image file: {dummy_image_path}")
        try:
            # Create a simple red square image for testing
            img = Image.new('RGB', (100, 100), color = 'red')
            # Add a small black square in the middle to simulate an object on a background
            from PIL import ImageDraw
            draw = ImageDraw.Draw(img)
            draw.rectangle([30, 30, 70, 70], fill='black')
            img.save(dummy_image_path)
            test_logger.info("Dummy image file created.")
        except Exception as e:
            test_logger.error(f"Could not create dummy image file: {e}. Please manually create {dummy_image_path} for testing.", exc_info=True)
            dummy_image_path = None # Mark as not available for testing

    if dummy_image_path and dummy_image_path.exists():
        test_logger.info("\n--- Starting image processing tests ---")
        remover = ImageBgRemover()

        def my_progress_callback(progress_value: int, message: str):
            """Simple progress callback for demonstration."""
            test_logger.info(f"Processing Progress: {progress_value}% - {message}")

        # Test 1: Successful image processing
        test_logger.info(f"\n--- Test 1: Processing image ({dummy_image_path}) ---")
        success, message = remover.remove_background_and_enhance(dummy_image_path, output_image_path, progress_callback_func=my_progress_callback)
        test_logger.info(f"Result: {message} (Success: {success})")
        assert success and output_image_path.exists()

        # Test 2: File not found
        test_logger.info(f"\n--- Test 2: Non-existent input file ---")
        non_existent_path = test_input_dir / "non_existent_image.jpg"
        success, message = remover.remove_background_and_enhance(non_existent_path, test_output_dir / "non_existent_output.png", progress_callback_func=my_progress_callback)
        test_logger.info(f"Result: {message} (Success: {success})")
        assert not success and "Input image file does not exist" in message

        test_logger.info("\n--- All image processing tests completed ---")
        test_logger.info("Please check the 'test_output' directory for processed image files.")
    else:
        test_logger.error("Skipping image processing tests due to missing dummy image file or creation failure.")
    test_logger.info("--- ImageBgRemover module test completed ---")
