import os
from rembg import remove

def main():
    path = r"c:\Users\lizae\Downloads\MangaTracker\static\img\logo.png"
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
