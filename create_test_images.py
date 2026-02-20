"""
Generate test images for vision model testing
"""
from PIL import Image, ImageDraw, ImageFont
import os

def create_test_image(filename, color, text, size=(400, 400)):
    """Create a simple test image with color and text"""
    # Create image with solid color
    img = Image.new('RGB', size, color=color)
    
    # Add text
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except:
        font = ImageFont.load_default()
    
    # Calculate text position (center)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    position = ((size[0] - text_width) / 2, (size[1] - text_height) / 2)
    
    # Draw text
    draw.text(position, text, font=font, fill=(255, 255, 255) if sum(color) < 400 else (0, 0, 0))
    
    # Save
    img.save(filename)
    print(f"Created: {filename}")

if __name__ == "__main__":
    # Create test directory
    os.makedirs("test_images", exist_ok=True)
    
    # Create test images
    create_test_image("test_images/red_inflamed.jpg", (255, 50, 50), "Red Inflamed")
    create_test_image("test_images/healthy_pink.jpg", (255, 200, 200), "Healthy Pink")
    create_test_image("test_images/dark_brown.jpg", (139, 69, 19), "Dark Brown")
    create_test_image("test_images/yellow_discharge.jpg", (255, 255, 100), "Yellow")
    create_test_image("test_images/white_normal.jpg", (255, 255, 255), "Normal")
    
    print("\n✅ Test images created in 'test_images/' folder")
    print("Use these images to test the vision API!")
