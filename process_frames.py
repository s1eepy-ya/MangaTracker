import os
from rembg import remove
from PIL import Image, ImageDraw, ImageChops

frames_dir = r"c:\Users\lizae\Downloads\MangaTracker\static\img\frames"
path_fd = os.path.join(frames_dir, "fire_dragon.png")
path_bc = os.path.join(frames_dir, "blue_crystal.png")
path_gc = os.path.join(frames_dir, "golden_crown.png")
path_dr = os.path.join(frames_dir, "dark_rose.png")
path_nc = os.path.join(frames_dir, "neon_cyberpunk.png")

def process_fire_dragon():
    print("Processing fire_dragon.png with rembg...")
    with open(path_fd, "rb") as i:
        input_data = i.read()
    output_data = remove(input_data)
    with open(path_fd, "wb") as o:
        o.write(output_data)
        
    print("Cutting hole in fire_dragon...")
    img = Image.open(path_fd).convert("RGBA")
    w, h = img.size
    mask = Image.new("L", img.size, 255)
    draw = ImageDraw.Draw(mask)
    margin = int(w * 0.16)
    draw.ellipse((margin, margin, w - margin, h - margin), fill=0)
    
    r, g, b, a = img.split()
    # Apply hole mask
    a = ImageChops.multiply(a, mask)
    img = Image.merge("RGBA", (r, g, b, a))
    img.save(path_fd)

def process_golden_crown():
    print("Generating golden_crown.png...")
    img_bc = Image.open(path_bc).convert("RGBA")
    r, g, b, a = img_bc.split()
    r = r.point(lambda i: min(int(i * 1.5), 255))
    g = g.point(lambda i: min(int(i * 1.3), 255))
    b = b.point(lambda i: int(i * 0.3))
    img_gc = Image.merge("RGBA", (r, g, b, a))
    img_gc.save(path_gc)

def process_neon_cyberpunk():
    print("Generating neon_cyberpunk.png...")
    img_dr = Image.open(path_dr).convert("RGBA")
    r, g, b, a = img_dr.split()
    r = r.point(lambda i: min(int(i * 1.8), 255))
    g = g.point(lambda i: int(i * 0.5))
    b = b.point(lambda i: min(int(i * 2.0), 255))
    img_nc = Image.merge("RGBA", (r, g, b, a))
    img_nc.save(path_nc)

if __name__ == "__main__":
    process_fire_dragon()
    process_golden_crown()
    process_neon_cyberpunk()
    print("Done!")
