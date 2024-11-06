import cairosvg
from PIL import Image

# Load the original SVG file
input_svg_path = "tidal.svg"  # Change to your actual path
intermediate_png_path = "tidal_temp.png"  # Intermediate PNG file
output_bmp_path = "tidal.bmp"  # Final BMP output

# Convert SVG to PNG first using CairoSVG
try:
    cairosvg.svg2png(url=input_svg_path, write_to=intermediate_png_path, output_width=32, output_height=32)
    print(f"SVG successfully converted to PNG at: {intermediate_png_path}")
except Exception as e:
    print(f"Error converting SVG to PNG: {e}")
    exit()

# Convert PNG to BMP (Monochrome) using Pillow
try:
    img = Image.open(intermediate_png_path).convert("1")  # Convert to monochrome (black & white)
    img.save(output_bmp_path, "BMP")
    print(f"PNG successfully converted to BMP at: {output_bmp_path}")
except IOError:
    print("Error loading or converting the PNG to BMP.")

