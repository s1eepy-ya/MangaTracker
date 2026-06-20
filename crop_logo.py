from PIL import Image

def crop_transparent(image_path):
    print(f"Cropping {image_path}...")
    img = Image.open(image_path)
    
    # Get bounding box of non-transparent pixels
    bbox = img.getbbox()
    
    if bbox:
        cropped_img = img.crop(bbox)
        cropped_img.save(image_path)
        print(f"Successfully cropped {image_path}")
    else:
        print(f"No non-transparent pixels found in {image_path} (or image is fully transparent).")

if __name__ == "__main__":
    crop_transparent(r"c:\Users\lizae\Downloads\MangaTracker\static\img\logo.png")
