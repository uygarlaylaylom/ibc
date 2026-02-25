import pytesseract
from PIL import Image
import io

def extract_text_from_image_bytes(image_bytes: bytes) -> str:
    """
    Takes image bytes (from a Streamlit upload), opens it with PIL,
    and runs it through local Tesseract OCR.
    Ensure 'tesseract' is installed on the system (e.g. brew install tesseract).
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        
        # We can optionally convert to grayscale to improve Tesseract accuracy
        # but for business cards, standard is often fine. 
        # For better accuracy: image = image.convert('L')
        
        # Run OCR
        extracted_text = pytesseract.image_to_string(image)
        return extracted_text.strip()
    except Exception as e:
        print(f"OCR Error: {e}")
        return f"OCR Okuma Hatası: {e}\n(Tesseract'ın sistemde kurulu olduğundan emin olun: brew install tesseract)"
