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