from PIL import Image
import os

stickers = {
    "public/stickers/hero-ai.png": 512,
    "public/stickers/404.png": 512,
    "public/stickers/hello.png": 256,
    "public/stickers/looks-good.png": 256,
}

for path, max_size in stickers.items():
    img = Image.open(path).convert("RGBA")
    img.thumbnail((max_size, max_size), Image.LANCZOS)
    img.save(path, optimize=True)
    print(f"Resized {path} to {img.size}")
