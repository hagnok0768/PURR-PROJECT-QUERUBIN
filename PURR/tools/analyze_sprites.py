import pygame
import sys

pygame.init()

try:
    img = pygame.image.load("assets/environment/grass.png")
except FileNotFoundError:
    try:
        img = pygame.image.load("grass.png")
    except:
        print("Image not found")
        sys.exit()

width, height = img.get_size()
print(f"Image size: {width}x{height}")

# 1. Horizontal Scan to find X-ranges
col_has_pixels = []
for x in range(width):
    has_pixel = False
    for y in range(0, height, 5): # step 5
        if img.get_at((x, y))[3] > 0:
            has_pixel = True
            break
    col_has_pixels.append(has_pixel)

segments_x = []
current_segment = None
for x, has_pixel in enumerate(col_has_pixels):
    if has_pixel:
        if current_segment is None:
            current_segment = [x, x]
        else:
            current_segment[1] = x
    else:
        if current_segment is not None:
            # Filter tiny segments (noise)
            if (current_segment[1] - current_segment[0]) > 10:
                segments_x.append(current_segment)
            current_segment = None
if current_segment is not None:
    if (current_segment[1] - current_segment[0]) > 10:
        segments_x.append(current_segment)

# 2. For each X-segment, find Y-range
crops = []
for i, (x1, x2) in enumerate(segments_x):
    min_y = height
    max_y = 0
    # Scan inside the segment
    for x in range(x1, x2 + 1, 5): 
        for y in range(0, height, 5):
            if img.get_at((x, y))[3] > 0:
                if y < min_y: min_y = y
                if y > max_y: max_y = y
    
    # Fine tune edges if needed, but scanning steps is faster
    if max_y >= min_y:
        w = x2 - x1 + 1
        h = max_y - min_y + 1
        print(f"Sprite {i}: Rect(x={x1}, y={min_y}, w={w}, h={h})")
        
        # Expand slightly to be safe? No, tight crop is better for placement
        crops.append((x1, min_y, w, h))

print("Crops found:", crops)
