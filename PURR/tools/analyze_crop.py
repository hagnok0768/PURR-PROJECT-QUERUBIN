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

# Segment 1 details
x = 866
w = 1089
target_rect = pygame.Rect(x, 0, w, height)

strip = img.subsurface(target_rect)
mask = pygame.mask.from_surface(strip)
rects = mask.get_bounding_rects()

if rects:
    union_rect = rects[0]
    for r in rects[1:]:
        union_rect.union_ip(r)
        
    print(f"Detected Sprite Vertical Bounds inside strip: {union_rect}")
    
    final_x = x + union_rect.x
    final_y = union_rect.y
    final_w = union_rect.width
    final_h = union_rect.height
    
    print(f"FINAL CROP RECT: ({final_x}, {final_y}, {final_w}, {final_h})")
else:
    print("No pixels found in segment 1")
