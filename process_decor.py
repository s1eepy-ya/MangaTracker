import os
import glob
from rembg import remove
from PIL import Image

def main():
    img_dir = r"c:\Users\lizae\Downloads\MangaTracker\static\img"
    paths = glob.glob(os.path.join(img_dir, "sakura_petals_*.png")) + glob.glob(os.path.join(img_dir, "manga_speedlines_*.png"))
    
    for path in paths:
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
