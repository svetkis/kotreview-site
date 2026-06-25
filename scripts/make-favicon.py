from PIL import Image
import os

src = "public/stickers/hero-friends.png"
out_dir = "public"

img = Image.open(src).convert("RGBA")

# Find bounding box and crop to content
bbox = img.getbbox()
cropped = img.crop(bbox)

# Make square with transparent background and a little padding
padding_ratio = 0.08
content_size = max(cropped.size)
padding = int(content_size * padding_ratio)
size = content_size + padding * 2
square = Image.new("RGBA", (size, size), (0, 0, 0, 0))
x = (size - cropped.width) // 2
y = (size - cropped.height) // 2
square.paste(cropped, (x, y), cropped)

# Generate sizes
sizes = {
    "favicon-32x32.png": 32,
    "favicon-16x16.png": 16,
    "apple-touch-icon.png": 180,
    "icon-192.png": 192,
}

for name, s in sizes.items():
    resized = square.resize((s, s), Image.LANCZOS)
    resized.save(os.path.join(out_dir, name))

print("Favicons generated")
