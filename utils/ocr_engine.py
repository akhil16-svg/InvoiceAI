import cv2
import pytesseract
import numpy as np
import tempfile

def preprocess_image(image_path):
    # ✅ Read the image using OpenCV
    image_cv = cv2.imread(image_path)

    if image_cv is None:
        raise ValueError(f"Failed to load image from {image_path}")

    # Convert to grayscale
    gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)

    # Denoise and threshold if needed
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return thresh

def extract_text(image_path):
    processed = preprocess_image(image_path)
    text = pytesseract.image_to_string(processed)
    return text

def save_temp_file(uploaded_file):
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.write(uploaded_file.read())
    return temp_file.name
