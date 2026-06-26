import cv2
import numpy as np
from PIL import Image

def preprocess_image_for_ocr(pil_image: Image.Image) -> Image.Image:
    """
    Applies advanced OpenCV preprocessing to a PIL Image to maximize Tesseract OCR accuracy.
    This includes grayscale conversion, adaptive thresholding, and noise removal.
    """
    # 1. Convert PIL Image to OpenCV format (numpy array)
    img_array = np.array(pil_image)
    
    # Check if the image has an alpha channel or is already grayscale
    if len(img_array.shape) == 3 and img_array.shape[2] == 4:
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2GRAY)
    elif len(img_array.shape) == 3 and img_array.shape[2] == 3:
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        
    # 2. Deskewing
    # Try to find the angle of text to straighten the image
    _, binarized = cv2.threshold(img_array, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(binarized > 0))
    if len(coords) > 0:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        
        # Only deskew if the angle is significant (e.g., > 0.5 degrees)
        if abs(angle) > 0.5:
            (h, w) = img_array.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            img_array = cv2.warpAffine(img_array, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=255)
            
    # 3. Adaptive Thresholding (Binarization)
    # This removes shadows and gradients, keeping the text dark and background white.
    img_array = cv2.adaptiveThreshold(
        img_array, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 71, 15
    )
    
    # 4. Noise Removal (Morphological Operations)
    img_array = cv2.medianBlur(img_array, 3)
    
    return Image.fromarray(img_array)
