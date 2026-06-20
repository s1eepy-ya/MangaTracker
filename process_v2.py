import os
from PIL import Image, ImageDraw

frames_dir = r"c:\Users\lizae\Downloads\MangaTracker\static\img\frames"

def clear_bg(img_path, out_path, is_dragon=False):
    if not os.path.exists(img_path): return
    img = Image.open(img_path).convert("RGBA")
    data = img.getdata()
    new_data = []
    
    # 1. Remove black background
    for item in data:
        if item[0] < 20 and item[1] < 20 and item[2] < 20:
            new_data.append((255, 255, 255, 0))
        else:
            new_data.append(item)
    img.putdata(new_data)
    
    # 2. Cut hole in the middle
    w, h = img.size
    mask = Image.new("L", img.size, 255)
    draw = ImageDraw.Draw(mask)
    margin = int(w * 0.18) if not is_dragon else int(w * 0.15)
    draw.ellipse((margin, margin, w - margin, h - margin), fill=0)
    
    r, g, b, a = img.split()
    # multiply alpha with mask
    from PIL import ImageChops
    a = ImageChops.multiply(a, mask)
    img = Image.merge("RGBA", (r, g, b, a))
    
    img.save(out_path)
    print(f"Saved {out_path}")

# Source paths
src_fd = os.path.join(frames_dir, "fire_dragon.png")
src_bc = os.path.join(frames_dir, "blue_crystal.png")
src_dr = os.path.join(frames_dir, "dark_rose.png")

# Target paths
tgt_fd = os.path.join(frames_dir, "fire_dragon_v2.png")
tgt_gc = os.path.join(frames_dir, "golden_crown_v2.png")
tgt_nc = os.path.join(frames_dir, "neon_cyberpunk_v2.png")

# 1. Process fire dragon
clear_bg(src_fd, tgt_fd, True)

# 2. Process golden crown
img_bc = Image.open(src_bc).convert("RGBA")
r, g, b, a = img_bc.split()
r = r.point(lambda i: min(int(i * 1.5), 255))
g = g.point(lambda i: min(int(i * 1.3), 255))
b = b.point(lambda i: int(i * 0.3))
img_gc = Image.merge("RGBA", (r, g, b, a))
img_gc.save(tgt_gc)
clear_bg(tgt_gc, tgt_gc)

# 3. Process neon cyberpunk
img_dr = Image.open(src_dr).convert("RGBA")
r, g, b, a = img_dr.split()
r = r.point(lambda i: min(int(i * 1.8), 255))
g = g.point(lambda i: int(i * 0.5))
b = b.point(lambda i: min(int(i * 2.0), 255))
img_nc = Image.merge("RGBA", (r, g, b, a))
img_nc.save(tgt_nc)
clear_bg(tgt_nc, tgt_nc)
