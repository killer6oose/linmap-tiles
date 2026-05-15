"""
GZW Map Tile Generator
Generates tiles from a high-res map image for upload to Cloudflare R2.

Output format: v2/{z}/{x}/{y}.jpg
Tile size: 256x256px
Zoom levels: 1-6

Canvas sizes per zoom level:
  Zoom 1:  512 x 512   (2x2 tiles)
  Zoom 2:  1024 x 1024 (4x4 tiles)
  Zoom 3:  2048 x 2048 (8x8 tiles)
  Zoom 4:  4096 x 4096 (16x16 tiles)
  Zoom 5:  8192 x 8192 (32x32 tiles)
  Zoom 6:  16384 x 16384 (64x64 tiles)

Usage:
  python generate_tiles.py --input map.jpg --output tiles_output
  python generate_tiles.py --input map.png --output tiles_output --quality 90
"""

import os
import sys
import argparse
import math
from PIL import Image

TILE_SIZE = 256
MIN_ZOOM = 1
MAX_ZOOM = 6


def canvas_size(zoom):
    return TILE_SIZE * (2 ** zoom)


def generate_tiles(input_path, output_dir, min_zoom=MIN_ZOOM, max_zoom=MAX_ZOOM, quality=85):
    print(f"Opening {input_path}...")
    img = Image.open(input_path).convert("RGB")
    orig_w, orig_h = img.size
    print(f"Input image: {orig_w} x {orig_h} px")

    # Scale the image to fit within the zoom 6 canvas (16384x16384),
    # preserving aspect ratio, centred on a black square canvas.
    max_canvas = canvas_size(max_zoom)
    scale = min(max_canvas / orig_w, max_canvas / orig_h)
    scaled_w = int(orig_w * scale)
    scaled_h = int(orig_h * scale)

    print(f"Scaling to {scaled_w} x {scaled_h} and centring on {max_canvas} x {max_canvas} canvas...")
    scaled = img.resize((scaled_w, scaled_h), Image.LANCZOS)

    base_canvas = Image.new("RGB", (max_canvas, max_canvas), (0, 0, 0))
    paste_x = (max_canvas - scaled_w) // 2
    paste_y = (max_canvas - scaled_h) // 2
    base_canvas.paste(scaled, (paste_x, paste_y))

    total_tiles = sum((2 ** z) ** 2 for z in range(min_zoom, max_zoom + 1))
    done = 0

    for zoom in range(min_zoom, max_zoom + 1):
        num_tiles = 2 ** zoom
        size = canvas_size(zoom)

        print(f"\nZoom {zoom}: {num_tiles}x{num_tiles} tiles ({size}x{size}px canvas)...")

        # Downsample base canvas to this zoom level
        if size == max_canvas:
            zoom_img = base_canvas
        else:
            zoom_img = base_canvas.resize((size, size), Image.LANCZOS)

        for x in range(num_tiles):
            for y in range(num_tiles):
                left  = x * TILE_SIZE
                upper = y * TILE_SIZE
                right = left  + TILE_SIZE
                lower = upper + TILE_SIZE

                tile = zoom_img.crop((left, upper, right, lower))

                tile_path = os.path.join(output_dir, "v2", str(zoom), str(x), f"{y}.jpg")
                os.makedirs(os.path.dirname(tile_path), exist_ok=True)
                tile.save(tile_path, "JPEG", quality=quality, optimize=True)

                done += 1
                if done % 100 == 0 or done == total_tiles:
                    pct = done / total_tiles * 100
                    print(f"  [{done}/{total_tiles}] {pct:.1f}%", end="\r", flush=True)

    print(f"\n\nDone! {done} tiles written to: {output_dir}/v2/")
    print("\nNext step - upload to R2:")
    print("  rclone copy tiles_output/v2 r2:linmap-tiles/v2 --progress")
    print("\nOr via Wrangler (slow - one file at a time):")
    print("  See upload_to_r2.ps1 for a PowerShell batch upload script.")


def main():
    parser = argparse.ArgumentParser(description="Generate map tiles from a high-res image.")
    parser.add_argument("--input",   required=True, help="Path to input image (PNG, JPG, etc.)")
    parser.add_argument("--output",  default="tiles_output", help="Output directory (default: tiles_output)")
    parser.add_argument("--quality", type=int, default=85, help="JPEG quality 1-95 (default: 85)")
    parser.add_argument("--min-zoom", type=int, default=MIN_ZOOM, help=f"Min zoom level (default: {MIN_ZOOM})")
    parser.add_argument("--max-zoom", type=int, default=MAX_ZOOM, help=f"Max zoom level (default: {MAX_ZOOM})")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: Input file not found: {args.input}")
        sys.exit(1)

    if args.quality < 1 or args.quality > 95:
        print("ERROR: Quality must be between 1 and 95.")
        sys.exit(1)

    os.makedirs(args.output, exist_ok=True)
    generate_tiles(args.input, args.output, args.min_zoom, args.max_zoom, args.quality)


if __name__ == "__main__":
    main()
