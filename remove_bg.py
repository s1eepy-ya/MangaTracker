import os
import glob
from rembg import remove
from PIL import Image

def main():
    icons_dir = r"c:\Users\lizae\Downloads\MangaTracker\static\img\icons"
    icon_paths = glob.glob(os.path.join(icons_dir, "*.png"))
    
    for path in icon_paths:
        print(f"Processing {path}...")
        try:
            with open(path, "rb") as i:
                input_data = i.read()
            output_data = remove(input_data)
            
            with open(path, "wb") as o:
                o.write(output_data)
            print(f"Successfully removed background from {os.path.basename(path)}")
        except Exception as e:
            print(f"Failed to process {path}: {e}")

if __name__ == "__main__":
    main()
