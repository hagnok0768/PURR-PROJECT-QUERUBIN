import pygame
import sys

pygame.init()

try:
    img = pygame.image.load("assets/environment/WaterStoped.png")
    print(f"WaterStoped.png size: {img.get_size()}")
    
    # Check for transparency boundaries
    width, height = img.get_size()
    min_x, min_y = width, height
    max_x, max_y = 0, 0
    
    has_pixels = False
    for x in range(width):
        for y in range(height):
            if img.get_at((x, y))[3] > 0: # Alpha > 0
                has_pixels = True
                if x < min_x: min_x = x
                if x > max_x: max_x = x
                if y < min_y: min_y = y
                if y > max_y: max_y = y
                
    if has_pixels:
        print(f"Content Rect: x={min_x}, y={min_y}, w={max_x-min_x+1}, h={max_y-min_y+1}")
    else:
        print("Image is fully transparent")

except Exception as e:
    print(f"Error: {e}")
