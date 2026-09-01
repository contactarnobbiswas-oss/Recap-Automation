import os
import requests
from PIL import Image, ImageEnhance
from io import BytesIO

def process_thumbnail(
    thumbnail_url: str,
    output_filepath: str,
    flip_horizontal: bool = True,
    enhance_contrast: float = 1.08,
    enhance_brightness: float = 1.03,
    enhance_color: float = 1.10
) -> str:
    """
    Downloads original YouTube thumbnail and processes it (horizontal flip, subtle contrast/color enhancement)
    to generate an attractive, edited, copyright-safe thumbnail image.
    """
    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
    
    res = requests.get(thumbnail_url, timeout=15)
    res.raise_for_status()
    
    img = Image.open(BytesIO(res.content)).convert("RGB")
    
    # Mirror/Flip horizontally
    if flip_horizontal:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
        
    # Contrast enhancement
    if enhance_contrast != 1.0:
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(enhance_contrast)
        
    # Brightness enhancement
    if enhance_brightness != 1.0:
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(enhance_brightness)

    # Color saturation enhancement
    if enhance_color != 1.0:
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(enhance_color)
        
    img.save(output_filepath, "JPEG", quality=95)
    return output_filepath
