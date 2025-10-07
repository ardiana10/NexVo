from PIL import Image, ImageDraw

# ukuran kotak 32x32 px
size = 32
img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# koordinat centang (bentuk "V")
points = [(6, 16), (14, 24), (26, 8)]
draw.line(points, fill=(255, 255, 255, 255), width=4)

img.save("check_white.png")
print("check_white.png dibuat")
