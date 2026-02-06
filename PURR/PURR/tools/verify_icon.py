import pygame
import os

pygame.display.init()
path = 'assets/sprites/tiger_gray_cat/ICON.png'
if os.path.exists(path):
    icon = pygame.image.load(path)
    print(f'Size: {icon.get_size()}')
    print(f'Format: {icon.get_bytesize()}')
    print(f'Alpha: {icon.get_flags() & pygame.SRCALPHA != 0}')
else:
    print('File not found')
pygame.quit()
