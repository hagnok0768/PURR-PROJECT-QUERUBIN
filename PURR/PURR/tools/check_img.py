import pygame
import sys

# Configuration
IMAGE_FILE = 'JUMP.png'
ROWS = 4
COLS = 3

pygame.init()

try:
    img = pygame.image.load(IMAGE_FILE)
except pygame.error as e:
    print(f"Could not load image: {e}")
    sys.exit(1)

img_w, img_h = img.get_size()
print(f"Image loaded: {IMAGE_FILE} ({img_w}x{img_h})")
print(f"Configured Grid: {ROWS} Rows x {COLS} Cols")

frame_w = img_w // COLS
frame_h = img_h // ROWS
print(f"Calculated Frame Size: {frame_w}x{frame_h}")

screen = pygame.display.set_mode((img_w, img_h))
pygame.display.set_caption("Check Img - Grid Viewer")

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            
    screen.fill((50, 50, 50))
    screen.blit(img, (0, 0))
    
    # Draw Grid Lines
    # Vertical lines (Columns)
    for c in range(COLS + 1):
        x = c * frame_w
        pygame.draw.line(screen, (255, 0, 0), (x, 0), (x, img_h), 2)
        
    # Horizontal lines (Rows)
    for r in range(ROWS + 1):
        y = r * frame_h
        pygame.draw.line(screen, (255, 0, 0), (0, y), (img_w, y), 2)
        
    pygame.display.flip()

pygame.quit()
