import pygame
import sys
import traceback
import json
import os
import math
import time
import random
import ctypes

# --- Configuração de AppUserModelID (Fix para ícone na Taskbar do Windows) ---
try:
    # Usar um ID único e garantir que o Windows trate como um App separado do Python
    myappid = u'pichau.purr.game.v1' 
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

# --- Tenta esconder o Console no Windows se não estiver no debugger ---
# Isso resolve o problema da "janela do python" aparecendo
try:
    if os.name == 'nt':
        # Só esconde se não estiver rodando via terminal/console explicitamente
        # ou se o usuário reclamou da janela
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd != 0:
             # SW_HIDE = 0
             ctypes.windll.user32.ShowWindow(hwnd, 0)
except Exception:
    pass

try:
    from tile import Tile
except ImportError:
    from src.tile import Tile

# --- Configurações ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
TILE_SIZE = 30  # Tamanho do bloco
BG_COLOR = (30, 144, 255) # Azul Oceano

# Cores para representar os terrenos e estruturas
COLORS = {
    'W': (30, 144, 255),  # Water
    'S': (240, 230, 140), # Sand
    'G': (34, 139, 34),   # Grass
    'F': (0, 100, 0),     # Forest (Tree)
    'R': (105, 105, 105), # Rock
    'C': (180, 110, 80),  # Clay (Ground)
    'WALL': (139, 69, 19) # Wall (Brown)
}

# --- O MAPA (A Ilha de Gato) ---
# Width: 20 chars
base_map = [
    "WWWWWWWWWWWWWWWWWWWW",
    "WWWWWWWWWWWWWWWWWWWW",
    "WWWWSSSWWWWWWSSSWWWW",
    "WWWSSGSSWWWWSSGSSWWW",
    "WWSSGGGSSWWSSGGGSSWW",
    "WWSGGGGGSSSSGGGGGSWW",
    "WSGGGGGGGGGGGGGGGGSW",
    "WSGGFFGGGGGGGGFFGGSW",
    "WSGGFFGGGGGGGGFFGGSW",
    "WSGGGGGGGGGGGGGGGGSW",
    "WSGGGGGGGRRGGGGGGGSW",
    "WWSGGGGGRRRRGGGGGSWW", # Fixed Nose Symmetry
    "WWWSGGGGGGGGGGGGSWWW", # Fixed Width/Sym
    "WWWWSGGGGGGGGGGSWWWW", # Fixed Width/Sym
    "WWWWWSGGGGGGGGSWWWWW", # Fixed Width/Sym
    "WWWWWWSSSSSSSWWWWWWW", # Base of chin
    "WWWWWWWWWWWWWWWWWWWW",
]

def double_map_size(original_map):
    new_map = []
    for row in original_map:
        doubled_row = "".join([char * 2 for char in row])
        new_map.append(doubled_row)
        new_map.append(doubled_row)
    return new_map

# 1. Expand strings first
string_map = double_map_size(base_map)

# 2. Convert to Tile Objects
level_map = []
for row_str in string_map:
    row_tiles = []
    for char in row_str:
        if char == 'F':
            t = Tile('G')
            t.structure = 'Tree'
        elif char == 'R':
            t = Tile('G')
            t.structure = 'Clay'
        else:
            t = Tile(char)
        row_tiles.append(t)
    level_map.append(row_tiles)

def cart_to_iso(x, y):
    iso_x = (x - y) * TILE_SIZE
    iso_y = (x + y) * (TILE_SIZE / 2)
    return iso_x, iso_y

def iso_to_cart(iso_x, iso_y):
    # Inverso de cart_to_iso
    # iso_x = (x - y) * TILE_SIZE
    # iso_y = (x + y) * (TILE_SIZE / 2)
    
    # iso_x / TILE_SIZE = x - y
    # iso_y / (TILE_SIZE / 2) = x + y
    
    # A = x - y
    # B = x + y
    # 2x = A + B -> x = (A + B) / 2
    # 2y = B - A -> y = (B - A) / 2
    
    A = iso_x / TILE_SIZE
    B = iso_y / (TILE_SIZE / 2)
    
    x = (A + B) / 2
    y = (B - A) / 2
    return math.floor(x), math.floor(y)

def get_tile_height(tile):
    max_h = 0
    for p in tile.piles:
        h = 0
        if p['structure'] == 'Clay':
            h = (p['base_amount'] * 5) + (p['amount'] * 5)
        elif p['structure'] == 'Wall':
            h = (p['base_amount'] * 30) + (p['amount'] * 30)
        elif p['structure'] == 'Tree':
            h = (p['base_amount'] * 30) + 60
        if h > max_h: max_h = h
    return max_h

# --- Inventory Helpers ---
def inv_count(inventory, name):
    return sum(item['count'] for item in inventory if item['name'] == name)

def inv_add(inventory, name, qty, box_w=200, box_h=200):
    # Try to stack first
    for item in inventory:
        if item['name'] == name:
            item['count'] += qty
            return
    # Else add new at random pos
    import random
    # Keep within box margins (approx)
    x = random.randint(20, box_w - 60)
    y = random.randint(20, box_h - 60)
    inventory.append({'name': name, 'count': qty, 'x': x, 'y': y})

def inv_remove(inventory, name, qty):
    remaining = qty
    # Iterate backwards to safely remove/modify
    for i in range(len(inventory) - 1, -1, -1):
        item = inventory[i]
        if item['name'] == name:
            if item['count'] > remaining:
                item['count'] -= remaining
                remaining = 0
                break
            else:
                remaining -= item['count']
                inventory.pop(i)
        if remaining <= 0:
            break

def main():
    global SCREEN_WIDTH, SCREEN_HEIGHT
    pygame.init()
    pygame.font.init()
    
    # --- Configurações Iniciais ---
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    icon_path = os.path.join(base_dir, 'assets', 'sprites', 'tiger_gray_cat', 'ICON.png')

    # No modo editor, queremos ver o mouse, mas no modo play pode ser que o usuário queira esconder
    # Vamos garantir que ele comece visível
    pygame.mouse.set_visible(True)

    # 1. Tenta carregar o ícone ANTES do set_mode (ajuda em alguns drivers)
    try:
        if os.path.exists(icon_path):
            temp_icon = pygame.image.load(icon_path)
            # Redimensiona para 256x256 que é o padrão de alta qualidade para Taskbar
            icon_256 = pygame.transform.smoothscale(temp_icon, (256, 256))
            pygame.display.set_icon(icon_256)
    except Exception:
        pass

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("Purr Project Querubin")
    clock = pygame.time.Clock()

    # 2. Reforça o ícone DEPOIS do set_mode (garante na maioria dos sistemas)
    try:
        if os.path.exists(icon_path):
            icon_surf = pygame.image.load(icon_path).convert_alpha()
            # Ícone de 32x32 para o canto da janela
            icon_32 = pygame.transform.smoothscale(icon_surf, (32, 32))
            pygame.display.set_icon(icon_32)
            # Ícone de 256x256 de novo para a Taskbar
            icon_large = pygame.transform.smoothscale(icon_surf, (256, 256))
            pygame.display.set_icon(icon_large)
    except Exception as e:
        print(f"Erro final ao carregar ícone: {e}")
    
    # --- Menu de Seleção de Modo (Preload) ---
    load_bg = None
    try:
        load_path = os.path.join(base_dir, 'assets', 'LOAD.png')
        if os.path.exists(load_path):
            load_bg = pygame.image.load(load_path).convert()
            load_bg = pygame.transform.scale(load_bg, (SCREEN_WIDTH, SCREEN_HEIGHT))
    except Exception as e:
        print(f"Erro ao carregar LOAD.png: {e}")

    font_menu = pygame.font.SysFont('Arial', 32, bold=True)
    font_sub = pygame.font.SysFont('Arial', 24)
    
    selected_mode = None
    while selected_mode is None:
        if load_bg:
            screen.blit(load_bg, (0, 0))
        else:
            screen.fill(BG_COLOR)
        
        # Botões Lado a Lado na parte de baixo
        btn_w, btn_h = 200, 60
        spacing = 40
        start_x = (SCREEN_WIDTH - (btn_w * 2 + spacing)) // 2
        btn_y = SCREEN_HEIGHT - 120

        play_rect = pygame.Rect(start_x, btn_y, btn_w, btn_h)
        edit_rect = pygame.Rect(start_x + btn_w + spacing, btn_y, btn_w, btn_h)
        
        mx, my = pygame.mouse.get_pos()
        
        # Render Play Button
        p_color = (100, 255, 100) if play_rect.collidepoint(mx, my) else (50, 180, 50)
        pygame.draw.rect(screen, (0, 0, 0), play_rect.inflate(4, 4), border_radius=12) # Borda
        pygame.draw.rect(screen, p_color, play_rect, border_radius=10)
        p_text = font_menu.render("PLAY", True, (255, 255, 255))
        screen.blit(p_text, (play_rect.centerx - p_text.get_width()//2, play_rect.centery - p_text.get_height()//2))
        
        # Render Editor Button
        e_color = (100, 100, 255) if edit_rect.collidepoint(mx, my) else (50, 50, 180)
        pygame.draw.rect(screen, (0, 0, 0), edit_rect.inflate(4, 4), border_radius=12) # Borda
        pygame.draw.rect(screen, e_color, edit_rect, border_radius=10)
        e_text = font_menu.render("EDITOR", True, (255, 255, 255))
        screen.blit(e_text, (edit_rect.centerx - e_text.get_width()//2, edit_rect.centery - e_text.get_height()//2))
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.VIDEORESIZE:
                SCREEN_WIDTH, SCREEN_HEIGHT = event.size
                screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
                if load_bg:
                    # Reload or rescale background to fit new size
                    try:
                        load_path = os.path.join(base_dir, 'assets', 'LOAD.png')
                        if os.path.exists(load_path):
                            load_bg = pygame.image.load(load_path).convert()
                            load_bg = pygame.transform.scale(load_bg, (SCREEN_WIDTH, SCREEN_HEIGHT))
                    except:
                        pass
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if play_rect.collidepoint(mx, my):
                    selected_mode = "PLAY"
                if edit_rect.collidepoint(mx, my):
                    selected_mode = "EDITOR"
        
        pygame.display.flip()
        clock.tick(60)

    game_mode = selected_mode
    print(f"Modo selecionado: {game_mode}")

    offset_x = SCREEN_WIDTH // 2
    offset_y = 50

    # --- Sprites do Gato ---
    try:
        def load_cat_sprite(name):
            path = os.path.join(base_dir, 'assets', 'sprites', 'tiger_gray_cat', name)
            return pygame.image.load(path).convert_alpha()

        cat_sitting = load_cat_sprite('Gray Cat FRONT.png')
        cat_sitting = pygame.transform.scale(cat_sitting, (50, 50))

        # Ícone para o Minimapa
        try:
            cat_minimap_icon = load_cat_sprite('ICON.png')
            cat_minimap_icon = pygame.transform.scale(cat_minimap_icon, (16, 16))
        except Exception:
            cat_minimap_icon = None
        
        # Default fallback idle is now FrontStanding
        try:
            cat_idle = load_cat_sprite('FrontStanding.png')
            cat_idle = pygame.transform.scale(cat_idle, (50, 50))
        except:
            cat_idle = cat_sitting # Fallback
        
        try:
            cat_move = load_cat_sprite('Right Stand.png')
            cat_move = pygame.transform.scale(cat_move, (50, 50))
            
            cat_left = load_cat_sprite('Left Stand.png')
            cat_left = pygame.transform.scale(cat_left, (50, 50))

            # Novo: Sprite de Frente (Walk)
            try:
                cat_front_s = load_cat_sprite('FrontStanding.png')
                cat_front_s = pygame.transform.scale(cat_front_s, (50, 50))
                
                cat_front_w = load_cat_sprite('FrontWalk.png')
                cat_front_w = pygame.transform.scale(cat_front_w, (50, 50))
            except Exception as e:
                print(f"Erro ao carregar front sprites: {e}")
                cat_front_s = cat_idle
                cat_front_w = cat_idle # Fallback

            # Carregar animações de andar
            try:
                cat_walk_right = load_cat_sprite('Right Walk.png')
                cat_walk_right = pygame.transform.scale(cat_walk_right, (50, 50))
            except Exception as e:
                print(f"Erro ao carregar right walk: {e}")
                cat_walk_right = cat_move # Fallback

            try:
                cat_walk_left = load_cat_sprite('Left Walk.png')
                cat_walk_left = pygame.transform.scale(cat_walk_left, (50, 50))
            except Exception as e:
                print(f"Erro ao carregar left walk: {e}")
                cat_walk_left = cat_left # Fallback
            
            try:
                cat_back_s = load_cat_sprite('BackStanding.png')
                cat_back_s = pygame.transform.scale(cat_back_s, (50, 50))
                
                cat_back_w1 = load_cat_sprite('BackWalk.png')
                cat_back_w1 = pygame.transform.scale(cat_back_w1, (50, 50))
                
                cat_back_w2 = load_cat_sprite('BackWalk2.png')
                cat_back_w2 = pygame.transform.scale(cat_back_w2, (50, 50))
            except Exception as e:
                print(f"Erro ao carregar back sprites: {e}")
                cat_back_s = cat_idle
                cat_back_w1 = cat_idle
                cat_back_w2 = cat_idle

            try:
                cat_uplw = load_cat_sprite('UPLW.png')
                cat_uplw = pygame.transform.scale(cat_uplw, (50, 50))
            except Exception as e:
                print(f"Erro ao carregar UPLW: {e}")
                cat_uplw = cat_idle

            try:
                cat_uprw = load_cat_sprite('UPRW.png')
                cat_uprw = pygame.transform.scale(cat_uprw, (50, 50))
            except Exception as e:
                print(f"Erro ao carregar UPRW: {e}")
                cat_uprw = cat_idle

            # Listas de frames para animação
            frames_right = [cat_move, cat_walk_right]
            frames_left = [cat_left, cat_walk_left]
            frames_up_left = [cat_uplw, cat_uplw]
            frames_up_right = [cat_uprw, cat_uprw]
            frames_front = [cat_front_s, cat_front_w]
            frames_back = [cat_back_s, cat_back_w1, cat_back_w2]
            
            # Action Sprites (Atk)
            try:
                cat_atk1 = load_cat_sprite('AtkStanding1.png')
                cat_atk1 = pygame.transform.scale(cat_atk1, (50, 50))
                
                cat_atk2 = load_cat_sprite('AtkStanding2.png')
                cat_atk2 = pygame.transform.scale(cat_atk2, (50, 50))
                
                frames_action = [cat_atk1, cat_atk2]
            except Exception as e:
                print(f"Erro ao carregar action sprites: {e}")
                frames_action = [cat_idle, cat_idle]

            print("Sprites de animação carregados com sucesso!")
            
        except Exception as e:
            print(f"Erro geral no carregamento de sprites do gato: {e}")
            cat_move = cat_idle
            cat_left = cat_idle
            cat_uplw = cat_idle
            cat_uprw = cat_idle
            frames_right = [cat_move, cat_move]
            frames_left = [cat_left, cat_left]
            frames_up_left = [cat_uplw, cat_uplw]
            frames_up_right = [cat_uprw, cat_uprw]
            frames_front = [cat_idle, cat_idle]
            frames_back = [cat_idle, cat_idle, cat_idle]

    except (pygame.error, FileNotFoundError) as e:
        print(f"Aviso: Sprites do gato não encontrados: {e}")
        s = pygame.Surface((30, 30))
        s.fill((255, 0, 0))
        cat_idle = s
        cat_move = s
        cat_left = s
        cat_minimap_icon = pygame.transform.scale(s, (10, 10))
        frames_right = [s, s]
        frames_left = [s, s]
        frames_up_left = [s, s]
        frames_up_right = [s, s]
        frames_front = [s, s]
        frames_back = [s, s, s]
    
    # --- Sprites Ambiente (Grama e Água) ---
    grass_variants = []
    water_img = None
    clay_img = None
    tree_img = None
    sand_img = None
    clay_wall_img = None
    clay_ground_img = None
    caixa_img = None
    
    try:
        def load_env_sprite(path_parts):
            full_path = os.path.join(base_dir, *path_parts)
            return pygame.image.load(full_path).convert_alpha()

        # Carregar Grama
        try:
            grass_full = load_env_sprite(['assets', 'environment', 'grass.png'])
            # Usando apenas a grama do meio conforme solicitado
            crops_data = [(866, 425, 1089, 656)]
            for rect in crops_data:
                grass_single = grass_full.subsurface(rect)
                grass_resized = pygame.transform.smoothscale(grass_single, (60, 30))
                grass_variants.append(grass_resized)
            print(f"grass.png carregado. {len(grass_variants)} variações criadas.")
        except Exception as e:
            print(f"Erro ao carregar grass.png: {e}")

        # Carregar Água
        try:
            water_full = load_env_sprite(['assets', 'environment', 'WaterStoped.png'])
            cx = water_full.get_width() // 2
            cy = water_full.get_height() // 2
            crop_rect = pygame.Rect(cx - 60, cy - 30, 120, 60)
            water_single = water_full.subsurface(crop_rect)
            water_rect_surf = pygame.transform.smoothscale(water_single, (60, 30))
            mask = pygame.Surface((60, 30), pygame.SRCALPHA)
            pygame.draw.polygon(mask, (255, 255, 255, 255), [(30, 0), (60, 15), (30, 30), (0, 15)])
            water_rect_surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            water_img = water_rect_surf
            print("WaterStoped.png carregado.")
        except Exception as e:
            print(f"Aviso: WaterStoped.png erro: {e}")

        # Carregar Argila
        try:
            clay_full = load_env_sprite(['assets', 'environment', 'Ore1.png'])
            clay_img = pygame.transform.scale(clay_full, (40, 40)) 
            print("Ore1.png carregado.")
        except Exception as e:
            print(f"Erro ao carregar argila: {e}")

        # Carregar Wall
        try:
            clay_wall_full = load_env_sprite(['assets', 'environment', 'ClayWall.png'])
            clay_wall_img = pygame.transform.scale(clay_wall_full, (60, 60))
            print("ClayWall.png carregado.")
        except Exception as e:
            print(f"Erro ao carregar clay wall: {e}")

        # Carregar Árvore e Estágios de Crescimento
        tree_growth_imgs = []
        try:
            # tree1.png é a árvore padrão madura
            tree_full = load_env_sprite(['assets', 'environment', 'tree4.png'])
            tree_img = pygame.transform.scale(tree_full, (60, 80))
            
            for i in range(5):
                t_path = os.path.join(base_dir, 'assets', 'environment', f'tree{i}.png')
                if os.path.exists(t_path):
                    img = pygame.image.load(t_path).convert_alpha()
                    img = pygame.transform.scale(img, (60, 80))
                    tree_growth_imgs.append(img)
                else:
                    tree_growth_imgs.append(tree_img)
            print("Estágios de crescimento da árvore carregados.")
        except Exception as e:
            print(f"Erro ao carregar árvore/estágios: {e}")
            tree_img = None

        # Carregar Log
        try:
            log_full = load_env_sprite(['assets', 'environment', 'Log.png'])
            log_img = pygame.transform.scale(log_full, (45, 30))
            print("Log.png carregado.")
            
            log_stack_full = load_env_sprite(['assets', 'environment', 'LogStack.png'])
            log_stack_img = pygame.transform.scale(log_stack_full, (50, 40))
            print("LogStack.png carregado.")
        except Exception as e:
            print(f"Erro ao carregar Log/LogStack: {e}")
            log_img = None
            log_stack_img = None

        # Carregar Areia
        try:
            sand_full = load_env_sprite(['assets', 'environment', 'sandy.png'])
            sand_img = pygame.transform.smoothscale(sand_full, (60, 30))
            mask_s = pygame.Surface((60, 30), pygame.SRCALPHA)
            pygame.draw.polygon(mask_s, (255, 255, 255, 255), [(30, 0), (60, 15), (30, 30), (0, 15)])
            sand_img.blit(mask_s, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            
            # Criar Clay Ground (Tint de Sand)
            clay_ground_img = sand_img.copy()
            # Tint avermelhado/marrom
            clay_ground_img.fill((200, 150, 120), special_flags=pygame.BLEND_RGBA_MULT)
            
            print("sandy.png carregado e clay_ground_img gerado.")
        except Exception as e:
            print(f"Erro ao carregar areia/clay_ground: {e}")
            
        # Carregar Inventário UI (Caixa)
        try:
            caixa_full = load_env_sprite(['assets', 'environment', 'Caixa.png'])
            caixa_img = pygame.transform.scale(caixa_full, (200, 200))
            print("Caixa.png carregado.")
        except Exception as e:
            print(f"Erro ao carregar Caixa.png: {e}") 
            caixa_img = None

        # Carregar Inventário Mini
        try:
            caixa_mini_full = load_env_sprite(['assets', 'environment', 'CaixaMini.png'])
            caixa_mini_img = pygame.transform.scale(caixa_mini_full, (50, 50))
            print("CaixaMini.png carregado.")
        except Exception as e:
            print(f"Erro ao carregar CaixaMini.png: {e}")
            caixa_mini_img = None
        
    except Exception as e:
        print(f"Aviso: Erro crítico nos sprites de ambiente ({e}).")

    # --- Sprite Pulo ---
    cat_jump_frames = []
    try:
        jump_sheet = load_env_sprite(['assets', 'sprites', 'tiger_gray_cat', 'JUMP.png'])
        sheet_w, sheet_h = jump_sheet.get_size()
        cols, rows = 3, 4
        frame_width, frame_height = sheet_w // cols, sheet_h // rows
        target_row = 1 
        for i in range(cols):
            rect = (i * frame_width, target_row * frame_height, frame_width, frame_height)
            frame = jump_sheet.subsurface(rect)
            frame = pygame.transform.scale(frame, (50, 50))
            cat_jump_frames.append(frame)
    except Exception as e:
        print(f"Aviso: JUMP.png erro ({e}).")
        cat_jump_frames = [cat_move]

    # --- Constantes de Controle ---
    last_click_time = 0
    double_click_threshold = 300 # ms
    
    # --- Variáveis de Jogo ---
    anim_frame = 0
    anim_timer = 0
    ANIM_SPEED = 50 
    
    # Action State
    is_acting = False
    action_timer = 0
    action_frame = 0
    ACTION_DURATION = 400 # ms
    ACTION_ANIM_SPEED = 100 # ms per frame
    
    # Rest State
    is_resting = False
    
    
    # Drag and Drop State
    dragging_item = None # Name of the item being dragged (e.g., 'Wood', 'Clay')
    dragging_source_tile = None # New: (x, y) tuple if dragged from map, None if from inventory
    dragging_source_inv_item = None 
    dragging_amount = 0 # How many we are dragging
    dragging_max_amount = 0
    dragging_base_amount = 0 # Preserva a altura original se vier do mapa
    dragging_offset = (0, 0) # Offset from mouse to item center

    # Editor Painting State
    editor_is_painting = False
    editor_last_painted_tile = None # (gx, gy)
    
    # --- Minimap State ---
    minimap_minimized = False
    minimap_last_click_time = 0
    DOUBLE_CLICK_TIME = 300 # ms
    minimap_ui_rect = pygame.Rect(0, 0, 0, 0) # Will be updated in draw

    # --- Inventory UI State ---
    inventory_minimized = False
    inventory_last_click_time = 0
    inventory_box_rect = pygame.Rect(0, 0, 0, 0)

    # --- Editor Selection State ---
    editor_categories = ["STRUCTURE", "TERRAIN", "SPAWNER"]
    editor_category_idx = 0
    # Categorias e seus itens
    editor_options = {
        "STRUCTURE": [None, "Wall"], # Agora só Wall e None. Arvores/Ores vêm de Spawners.
        "TERRAIN": ["G", "W", "S", "C"],
        "SPAWNER": [None, "Tree", "Clay"]
    }
    editor_selected_idx = 0
    editor_spawner_delay = 120 # Padrão 120s para novos spawners
    
    # Dashboard state
    show_dashboard = True # Sempre visível no editor? Sim.
    dashboard_rects = [] # Para colisões de clique
    
    def get_editor_selection():
        cat = editor_categories[editor_category_idx]
        return editor_options[cat][editor_selected_idx]

    def apply_editor_tool(gx, gy, is_continuous=False):
        nonlocal respawning_resources
        if not (0 <= gy < len(level_map) and 0 <= gx < len(level_map[0])):
            return
            
        tile = level_map[gy][gx]
        selection = get_editor_selection()
        cat = editor_categories[editor_category_idx]
        
        if cat == "STRUCTURE":
            if selection == "Wall":
                # No editor, sempre coloca na base ou aumenta a pilha existente na base
                found_base_wall = False
                for p in tile.piles:
                    if p['structure'] == 'Wall' and p['base_amount'] == 0:
                        if not is_continuous:
                            p['amount'] += 1
                        found_base_wall = True
                        break
                if not found_base_wall:
                    tile.add_structure("Wall", 1, 0)
            elif selection == "Clay":
                tile.add_structure("Clay", 10, 0)
            else:
                if selection is not None:
                    tile.add_structure(selection, 1, 0)
                else:
                    tile.piles = [] # Clear
        elif cat == "TERRAIN":
            tile.ground_type = selection
        elif cat == "SPAWNER":
             # Verifica se já existe um spawner no local
             existing = next((r for r in respawning_resources if r['x'] == gx and r['y'] == gy), None)
             
             # Se clicar em um spawner existente com a mesma ferramenta, incrementa o tempo (30s em 30s)
             if existing and existing['structure'] == selection and not is_continuous:
                 existing['respawn_delay'] += 30
                 if existing['respawn_delay'] > 600: # Limite de 10 minutos para o ciclo
                     existing['respawn_delay'] = 30
                 show_message(f"Spawner {selection} Delay: {existing['respawn_delay']}s")
                 return # Não precisa refazer o resto

             # Caso contrário, remove e cria um novo (com o delay padrão do editor)
             respawning_resources = [r for r in respawning_resources if not (r['x'] == gx and r['y'] == gy)]
             if selection is not None:
                 respawning_resources.append({
                     'x': gx, 
                     'y': gy, 
                     'structure': selection, 
                     'respawn_time': time.time(),
                     'respawn_delay': editor_spawner_delay
                 })
                 tile.structure = selection 
                 if selection == "Clay": tile.amount = 10
             else:
                 tile.structure = None 
        
        show_message(f"Editor: Applied {selection}")

    # Animação de Andar
    walk_frame = 0
    walk_timer = 0
    WALK_SPEED = 200 # Sincronizado com o delay de movimento ou um pouco mais rápido

    player_x = 20
    player_y = 17
    inventory = []

    # --- STATUS DO GATINHO ---
    stats = {
        'str': 10,
        'dex': 20,
        'int': 10
    }
    
    # Valores atuais e máximos
    max_hp = stats['str'] * 2
    current_hp = max_hp
    
    max_stamina = stats['dex'] * 2
    current_stamina = max_stamina
    
    max_mana = stats['int'] * 2
    current_mana = max_mana

    stamina_timer = 0 # Para controlar o gasto por segundo

    # --- RESPAWN CONFIG ---
    respawning_resources = [] # List of dicts: {'x': x, 'y': y, 'structure': str, 'respawn_time': timestamp}
    RESPAWN_DELAY_CLAY = 120 # 2 minutes
    RESPAWN_DELAY_TREE = 300 # 5 minutes (example) or keep it consistent. User said "resources". I'll do 2 min for Clay. 

    # --- SAVE / LOAD ---
    SAVE_FILE = "savegame.json"
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, 'r') as f:
                data = json.load(f)
                player_x = data.get('player_x', 20)
                player_y = data.get('player_y', 17)
                
                loaded_inv = data.get('inventory', [])
                if isinstance(loaded_inv, dict):
                     # Migration from old save
                     inventory = []
                     for k, v in loaded_inv.items():
                         if v > 0:
                             inv_add(inventory, k, v)
                else:
                     inventory = loaded_inv

                # Load Map State
                map_piles = data.get('map_piles', [])
                map_ground = data.get('map_ground', [])
                if map_piles:
                    for r, row in enumerate(map_piles):
                         if r < len(level_map):
                             for c, pile_data in enumerate(row):
                                 if c < len(level_map[r]):
                                     level_map[r][c].piles = pile_data
                else:
                    # Legacy Fallback
                    map_structures = data.get('map_structures', [])
                    map_amounts = data.get('map_amounts', [])
                    map_bases = data.get('map_bases', [])
                    if map_structures:
                        for r, row in enumerate(map_structures):
                            if r < len(level_map):
                                for c, struct in enumerate(row):
                                    if c < len(level_map[r]) and struct:
                                        amt = map_amounts[r][c] if (r < len(map_amounts) and c < len(map_amounts[r])) else 1
                                        base = map_bases[r][c] if (r < len(map_bases) and c < len(map_bases[r])) else 0
                                        level_map[r][c].add_structure(struct, amt, base)

                if map_ground:
                     for r, row in enumerate(map_ground):
                         if r < len(level_map):
                             for c, gr in enumerate(row):
                                 if c < len(level_map[r]):
                                     level_map[r][c].ground_type = gr
                else: 
                     # Initial default for loaded Clay that didn't have amount saved
                     for row in level_map:
                         for tile in row:
                             if tile.structure == 'Clay':
                                 tile.amount = 1
                
                # Load Respawn Queue
                respawning_resources = data.get('respawning_resources', [])

                # Migration: Stone -> Clay
                stone_count = inv_count(inventory, 'Stone')
                if stone_count > 0:
                     inv_add(inventory, 'Clay', stone_count)
                     inv_remove(inventory, 'Stone', stone_count)

                # Migration: Wood -> Log (Inventory) - REMOVIDO POR PEDIDO DO USUÁRIO
                # O usuário quer deletar as logs da bag que estão crashando
                inventory = [item for item in inventory if item['name'] not in ['Log', 'Wood']]
                
                # Cleanup Malformed Piles (Map)
                for r_idx, row in enumerate(level_map):
                    for c_idx, tile in enumerate(row):
                        valid_piles = []
                        for p in tile.piles:
                            if isinstance(p, dict) and 'structure' in p:
                                # Garante que campos básicos existem
                                p['amount'] = p.get('amount', 1)
                                p['base_amount'] = p.get('base_amount', 0)
                                valid_piles.append(p)
                        tile.piles = valid_piles

                print(f"Jogo carregado! Posição: {player_x}, {player_y}")
        except Exception as e:
            print(f"Erro ao carregar save: {e}")
    
    # Delay de movimento
    last_move_time = 0
    MOVE_DELAY = 200

    # Física de Pulo
    z_offset = 0   
    z_velocity = 0 
    GRAVITY = 1.5  
    is_jumping = False
    jump_count = 0
    MAX_JUMPS = 2
    
    # Estado de Direção
    facing_direction = 'RIGHT' # Padrão
    # 'RIGHT' usa cat_move (P1)
    # 'LEFT' usa cat_left
    # 'FRONT' usa cat_idle (quando parado)

    # --- Chat / Sistema de Mensagens ---
    chat_message = ""
    chat_timer = 0
    CHAT_DURATION = 2000 # 2 segundos

    def show_message(text):
        nonlocal chat_message, chat_timer
        chat_message = text
        chat_timer = pygame.time.get_ticks()

    # --- Inventário ---
    # inventory init moved up
    font = pygame.font.SysFont('Arial', 18)
    chat_font = pygame.font.SysFont('Arial', 16, bold=True)

    running = True
    while running:
        current_time = pygame.time.get_ticks()
        
        # --- Resource Respawn Check ---
        now = time.time()
        for res in respawning_resources:
            rx, ry = res['x'], res['y']
            if 0 <= ry < len(level_map) and 0 <= rx < len(level_map[0]):
                tile = level_map[ry][rx]
                
                # Se for Tree, ela cresce visualmente antes de se tornar colhível
                if res['structure'] == 'Tree':
                    if tile.structure is None:
                        # Se já passou do tempo de respawn, vira árvore colhível (Stage 4)
                        if now >= res.get('respawn_time', 0):
                            tile.add_structure('Tree', 1, 0)
                else:
                    # Outros recursos (Clay) spawnão instantaneamente no final do timer
                    if now >= res.get('respawn_time', 0):
                        if tile.structure is None:
                            tile.structure = res['structure']
                            if tile.structure == 'Clay': tile.amount = 10

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                # SAVE GAME
                # Serialize Map
                map_piles = []
                map_ground = []
                for row in level_map:
                    piles_row = []
                    gr_row = []
                    for tile in row:
                        piles_row.append(tile.piles)
                        gr_row.append(tile.ground_type)
                    map_piles.append(piles_row)
                    map_ground.append(gr_row)

                save_data = {
                    'player_x': player_x, 
                    'player_y': player_y,
                    'inventory': inventory,
                    'map_piles': map_piles,
                    'map_ground': map_ground,
                    'respawning_resources': respawning_resources
                }
                try:
                    with open(SAVE_FILE, 'w') as f:
                        json.dump(save_data, f)
                    print("Jogo Salvo!")
                except Exception as e:
                    print(f"Erro ao salvar: {e}")
                running = False
            
            if event.type == pygame.VIDEORESIZE:
                SCREEN_WIDTH, SCREEN_HEIGHT = event.size
                screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11: # Toggle Fullscreen
                     pygame.display.toggle_fullscreen()

            # --- Interação e Construção ---
            if event.type == pygame.KEYDOWN:
                if game_mode == "EDITOR":
                    # Atalhos do Editor
                    if event.key == pygame.K_TAB:
                        # Troca de categoria (Estrutura vs Terreno)
                        editor_category_idx = (editor_category_idx + 1) % len(editor_categories)
                        editor_selected_idx = 0 # Reseta seleção ao trocar categoria
                        show_message(f"Editor: Category {editor_categories[editor_category_idx]}")
                    
                    if event.key == pygame.K_1: editor_selected_idx = 0
                    if event.key == pygame.K_2: editor_selected_idx = 1
                    if event.key == pygame.K_3: editor_selected_idx = 2
                    if event.key == pygame.K_4: editor_selected_idx = 3
                    
                    # Garantir que o index é válido para a nova categoria
                    cat = editor_categories[editor_category_idx]
                    editor_selected_idx = editor_selected_idx % len(editor_options[cat])
                    show_message(f"Selected: {editor_options[cat][editor_selected_idx]}")

                if game_mode == "EDITOR":
                    if event.key == pygame.K_KP_PLUS or event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                        editor_spawner_delay += 10
                        show_message(f"Spawner Delay: {editor_spawner_delay}s")
                    if event.key == pygame.K_KP_MINUS or event.key == pygame.K_MINUS:
                        editor_spawner_delay = max(10, editor_spawner_delay - 10)
                        show_message(f"Spawner Delay: {editor_spawner_delay}s")

                if event.key == pygame.K_e: # Interact / Gather
                    is_acting = True
                    action_timer = current_time
                    action_frame = 0
                    
                    ix, iy = 0, 0
                    # Define offset baseado na direção atual
                    if facing_direction == 'RIGHT': ix, iy = 1, -1
                    elif facing_direction == 'LEFT': ix, iy = -1, 1
                    elif facing_direction == 'UP': ix, iy = -1, -1
                    elif facing_direction == 'DOWN': ix, iy = 1, 1
                    elif facing_direction == 'UP_LEFT': ix, iy = -1, 0
                    elif facing_direction == 'UP_RIGHT': ix, iy = 0, -1
                    elif facing_direction == 'DOWN_LEFT': ix, iy = 0, 1
                    elif facing_direction == 'DOWN_RIGHT': ix, iy = 1, 0
                    
                    target_x, target_y = player_x + ix, player_y + iy
                    
                    if 0 <= target_y < len(level_map) and 0 <= target_x < len(level_map[0]):
                        target_tile = level_map[target_y][target_x]
                        # New Pile-based Gather Logic
                        harvested = False
                        target_idx = -1
                        for i, p in enumerate(target_tile.piles):
                            if p['structure'] in ['Tree', 'Clay']:
                                target_idx = i
                                break
                        
                        if target_idx != -1:
                            pile = target_tile.piles.pop(target_idx)
                            p_type = pile['structure']
                            p_amt = pile['amount']
                            
                            # Aciona Spawner
                            spw = next((r for r in respawning_resources if r['x'] == target_x and r['y'] == target_y), None)
                            if spw and spw['structure'] == p_type:
                                spw['respawn_time'] = time.time() + spw.get('respawn_delay', 120)
                            
                            if p_type == 'Tree':
                                # Drop Log on ground
                                drop_x, drop_y = target_x, target_y
                                # Tenta vizinho se o atual estiver cheio (embora acabe de esvaziar a árvore)
                                neighbors = [(target_x+1, target_y), (target_x-1, target_y), (target_x, target_y+1), (target_x, target_y-1)]
                                random.shuffle(neighbors)
                                for nx, ny in neighbors:
                                    if 0 <= ny < len(level_map) and 0 <= nx < len(level_map[0]):
                                        if level_map[ny][nx].is_walkable():
                                            drop_x, drop_y = nx, ny
                                            break
                                level_map[drop_y][drop_x].add_structure('Log', 1, 0)
                                show_message("Tree harvested! Log dropped.")
                            elif p_type == 'Clay':
                                inv_add(inventory, 'Clay', p_amt)
                                show_message(f"Clay +{p_amt}")
                            
                            harvested = True
                            target_tile.piles.sort(key=lambda x: x['base_amount'])
                            
                        else:
                            show_message("Nothing here...")

                if event.key == pygame.K_b: # Build Wall
                     wood_available = inv_count(inventory, 'Wood')
                     if wood_available >= 2:
                        target_x, target_y = player_x, player_y
                        
                        # Use facing direction to determine target tile
                        # Use facing direction to determine target tile (8-way)
                        if facing_direction == 'RIGHT':
                            target_x += 1; target_y -= 1
                        elif facing_direction == 'LEFT':
                            target_x -= 1; target_y += 1
                        elif facing_direction == 'UP':
                            target_x -= 1; target_y -= 1
                        elif facing_direction == 'DOWN':
                            target_x += 1; target_y += 1
                        elif facing_direction == 'UP_LEFT':
                            target_x -= 1
                        elif facing_direction == 'UP_RIGHT':
                            target_y -= 1
                        elif facing_direction == 'DOWN_LEFT':
                            target_y += 1
                        elif facing_direction == 'DOWN_RIGHT':
                            target_x += 1
                        
                        # Safety: Never build on your own tile
                        if target_x == player_x and target_y == player_y:
                            # Default to 'Front' (DOWN in iso)
                            target_x += 1; target_y += 1
                        
                        if 0 <= target_y < len(level_map) and 0 <= target_x < len(level_map[0]):
                             target_tile = level_map[target_y][target_x]
                             if target_tile.ground_type == 'G':
                                 if target_tile.structure is None:
                                     # Smart Snap: Tenta acoplar à altura de blocos vizinhos
                                     desired_base = int(z_offset // 30)
                                     
                                     # Verifica vizinhos para ver se tem algo no alto para "grudar"
                                     neighbors = [
                                         (target_x+1, target_y), (target_x-1, target_y),
                                         (target_x, target_y+1), (target_x, target_y-1)
                                     ]
                                     for nx, ny in neighbors:
                                         if 0 <= ny < len(level_map) and 0 <= nx < len(level_map[0]):
                                             ntile = level_map[ny][nx]
                                             if ntile.structure == 'Wall':
                                                 # Se encontrarmos um vizinho, usamos a base dele para "acoplar"
                                                 desired_base = ntile.base_amount
                                                 break
                                     
                                     target_tile.structure = 'Wall'
                                     target_tile.base_amount = desired_base
                                     target_tile.amount = 1
                                     inv_remove(inventory, 'Wood', 2)
                                     show_message(f"Wall built at H{desired_base}")
                                 elif target_tile.structure == 'Wall':
                                     # Empilhamento vertical com a tecla B
                                     target_tile.amount += 1
                                     inv_remove(inventory, 'Wood', 2)
                                     show_message(f"Wall height increased! (H{target_tile.base_amount}+{target_tile.amount})")
                                 else:
                                     show_message("Spot Occupied")
                             else:
                                 show_message("Invalid Ground")
                        else:
                             show_message("Out of bounds!")
                     else:
                        show_message("Need 2 Wood!")


            if event.type == pygame.MOUSEWHEEL:
                if dragging_item:
                    if dragging_item == 'Wall':
                        # Ajustar o ANDAR (Altura de Base)
                        dragging_base_amount += event.y
                        if dragging_base_amount < 0: dragging_base_amount = 0
                        show_message(f"Floor Adjusted: H{dragging_base_amount}")
                    else:
                        # Adjust dragging amount (Clay, etc)
                        step = 1
                        # Support for fast adjusting with modifiers
                        mods = pygame.key.get_mods()
                        if mods & pygame.KMOD_SHIFT:
                            step = 10
                        if mods & pygame.KMOD_CTRL:
                            step = 100
                            
                        dragging_amount += event.y * step
                        
                        # Clamp between 1 and the maximum available from source
                        if dragging_amount < 1: 
                            dragging_amount = 1
                        if dragging_amount > dragging_max_amount:
                            dragging_amount = dragging_max_amount
                        
                        show_message(f"Amount: {dragging_amount} / {dragging_max_amount}")

            if event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = pygame.mouse.get_pos()
                is_double_click = (pygame.time.get_ticks() - last_click_time < double_click_threshold)
                last_click_time = pygame.time.get_ticks()
                
                # --- Lógica do Editor ---
                if game_mode == "EDITOR":
                    # Check Dashboard Clicks (Sempre no botão 1)
                    dash_w, dash_h = 550, 140
                    dash_x = (SCREEN_WIDTH - dash_w) // 2
                    dash_y = SCREEN_HEIGHT - dash_h - 20
                    dash_rect = pygame.Rect(dash_x, dash_y - 25, dash_w, dash_h + 25)
                    
                    if event.button == 1 and dash_rect.collidepoint(mx, my):
                        editor_is_painting = False # Para não pintar enquanto clica no painel
                        # Clicou nas abas?
                        tab_w = dash_w // len(editor_categories)
                        for i in range(len(editor_categories)):
                            tab_r = pygame.Rect(dash_x + i * tab_w, dash_y - 25, tab_w, 25)
                            if tab_r.collidepoint(mx, my):
                                editor_category_idx = i
                                editor_selected_idx = 0
                                continue
                        
                        # Clicou nos slots de item?
                        curr_cat = editor_categories[editor_category_idx]
                        items = editor_options[curr_cat]
                        margin = 20
                        slot_size = 60
                        for i in range(len(items)):
                            slot_r = pygame.Rect(dash_x + margin + i * (slot_size + 20), dash_y + 45, slot_size, slot_size)
                            if slot_r.collidepoint(mx, my):
                                editor_selected_idx = i
                                continue
                        continue 

                    adj_mx = mx - offset_x
                    adj_my = my - offset_y
                    grid_x, grid_y = iso_to_cart(adj_mx, adj_my)
                    
                    if 0 <= grid_y < len(level_map) and 0 <= grid_x < len(level_map[0]):
                        tile = level_map[grid_y][grid_x]
                        
                        if event.button == 3: # Botão Direito: REMOVER TUDO
                            tile.structure = None
                            respawning_resources = [r for r in respawning_resources if not (r['x'] == grid_x and r['y'] == grid_y)]
                            show_message("Removed structure and spawner")
                            continue

                        if event.button == 1: # Botão Esquerdo: ADICIONAR
                            editor_is_painting = True
                            editor_last_painted_tile = (grid_x, grid_y)
                            apply_editor_tool(grid_x, grid_y, is_continuous=False)
                    continue 

                if event.button == 1: # Clique Esquerdo no modo PLAY
                    # --- Minimap Double Click Check ---
                    if minimap_ui_rect.collidepoint(mx, my):
                        now = pygame.time.get_ticks()
                        if now - minimap_last_click_time < DOUBLE_CLICK_TIME:
                            minimap_minimized = not minimap_minimized
                            show_message("Minimap " + ("minimized" if minimap_minimized else "expanded"))
                            minimap_last_click_time = 0 # reset
                        else:
                            minimap_last_click_time = now
                        # Absorve clique no minimapa
                        continue

                    # --- Inventory Double Click Check ---
                    if inventory_box_rect.collidepoint(mx, my):
                        now = pygame.time.get_ticks()
                        if now - inventory_last_click_time < DOUBLE_CLICK_TIME:
                            inventory_minimized = not inventory_minimized
                            show_message("Bag " + ("minimized" if inventory_minimized else "expanded"))
                            inventory_last_click_time = 0
                        else:
                            inventory_last_click_time = now
                        
                        # Se estiver minimizada, absorve o clique para não andar/pegar itens
                        if inventory_minimized:
                            continue
                        # Se não estiver minimizada, continua para ver se clicou em um item
                    
                    # --- Lógica de PLAY ---
                    # Check Inventory Collisions first (UI Layer)
                    if not inventory_minimized:
                        inv_box_w = 200
                        inv_box_h = 200
                        inv_box_x = 10
                        inv_box_y = SCREEN_HEIGHT - inv_box_h - 10
                        
                        # Check actual items
                        clicked_slot = False
                        # Iterate copy to avoid issues if we modify, but we won't modify on click
                        for item in reversed(inventory):
                            ix = inv_box_x + item.get('x', 0)
                            iy = inv_box_y + item.get('y', 0)
                            i_rect = pygame.Rect(ix, iy, 40, 40) # Assume 40x40 icons
                            
                            if i_rect.collidepoint(mx, my):
                                clicked_slot = True
                                dragging_item = item['name'] # Keep name for consistency with rest of code
                                # We need to track the SOURCE item to deduct later
                                dragging_source_inv_item = item 
                                dragging_source_tile = None
                                
                                # Default to full stack UNLESS Shift is held (start with 1?)
                                # Or just always full and use wheel as requested.
                                dragging_amount = item['count'] 
                                dragging_max_amount = item['count'] # New tracker
                                dragging_offset = (ix - mx, iy - my)
                                show_message(f"Pegou {item['name']}, use o Mouse Wheel para ajustar quant.")
                                break
                    else:
                        clicked_slot = False
                
                # Check Map Click for Dragging Clay
                if not clicked_slot:
                    adj_mx = mx - offset_x
                    adj_my = my - offset_y
                    grid_x, grid_y = iso_to_cart(adj_mx, adj_my)
                    
                    if 0 <= grid_y < len(level_map) and 0 <= grid_x < len(level_map[0]):
                        tile = level_map[grid_y][grid_x]
                        dist_x = abs(grid_x - player_x)
                        dist_y = abs(grid_y - player_y)
                        
                        if dist_x <= 5 and dist_y <= 5: # Aumentado para 5 para alcançar construções distantes
                            # --- Height-Aware Picking for Selecting Items ---
                            best_p = -1
                            found_pick = False
                            
                            for ry in range(max(0, player_y-6), min(len(level_map), player_y+7)):
                                for rx in range(max(0, player_x-6), min(len(level_map[0]), player_x+7)):
                                    t = level_map[ry][rx]
                                    for pile_idx, p in enumerate(t.piles):
                                        ix, iy = cart_to_iso(rx, ry)
                                        dx, dy = ix + offset_x, iy + offset_y
                                        
                                        h_unit = 30 if p['structure'] == 'Wall' else (5 if p['structure'] == 'Clay' else 60)
                                        h_val = p['amount'] * h_unit
                                        b_val = p['base_amount'] * h_unit
                                        
                                        # Caixa de colisão visual (3D)
                                        box_rect = pygame.Rect(dx - 30, dy - 30 - b_val - (h_val-30), 60, h_val)
                                        if box_rect.collidepoint(mx, my):
                                            priority = ry + rx + (b_val * 0.001)
                                            if priority > best_p:
                                                best_p = priority
                                                grid_x, grid_y = rx, ry
                                                target_pile_idx = pile_idx
                                                # Determina qual bloco específico foi clicado
                                                clicked_h = (dy + 15 - my) / h_unit
                                                target_block_in_pile = int(clicked_h - p['base_amount'])
                                                found_pick = True

                            if found_pick:
                                tile = level_map[grid_y][grid_x]
                                # Usa a pilha específica identificada no clique
                                pile = tile.piles[target_pile_idx]
                                
                                dragging_item = pile['structure']
                                dragging_source_tile = (grid_x, grid_y)
                                dragging_source_inv_item = None
                                dragging_amount = 1
                                dragging_max_amount = pile['amount']
                                # Altura absoluta do bloco no mundo
                                dragging_base_amount = pile['base_amount'] + target_block_in_pile
                                
                                # Lógica de Divisão (Mantém os outros blocos)
                                old_pile = tile.piles.pop(target_pile_idx)
                                
                                # Parte de baixo (se houver)
                                if target_block_in_pile > 0:
                                    tile.piles.append({
                                        'structure': old_pile['structure'],
                                        'amount': target_block_in_pile,
                                        'base_amount': old_pile['base_amount']
                                    })
                                # Parte de cima (se houver)
                                if target_block_in_pile < old_pile['amount'] - 1:
                                    tile.piles.append({
                                        'structure': old_pile['structure'],
                                        'amount': old_pile['amount'] - target_block_in_pile - 1,
                                        'base_amount': old_pile['base_amount'] + target_block_in_pile + 1
                                    })
                                
                                tile.piles.sort(key=lambda x: x['base_amount'])
                                
                                # Aciona o Spawner para renascer (Regrowth) se houver um spawner aqui
                                spawner = next((r for r in respawning_resources if r['x'] == grid_x and r['y'] == grid_y), None)
                                if spawner and dragging_item == spawner['structure']:
                                    spawner['respawn_time'] = time.time() + spawner['respawn_delay']

                                # Se for Double Click, vai direto para a bag
                                if is_double_click:
                                    item_to_add = dragging_item
                                    if dragging_item == 'Tree': item_to_add = 'Log'
                                    inv_add(inventory, item_to_add, dragging_amount)
                                    show_message(f"Collected {item_to_add}")
                                    dragging_item = None
                                    dragging_amount = 0
                                    found_pick = False 
                                    break
                                
                                if dragging_item == 'Tree':
                                    # No lugar de ir para a mão, "pula" no chão como Log
                                    # Encontra um vizinho vazio ou o próprio tile se couber
                                    target_x, target_y = grid_x, grid_y
                                    neighbors = [(grid_x+1, grid_y), (grid_x-1, grid_y), (grid_x, grid_y+1), (grid_x, grid_y-1)]
                                    random.shuffle(neighbors)
                                    for nx, ny in neighbors:
                                        if 0 <= ny < len(level_map) and 0 <= nx < len(level_map[0]):
                                            ntile = level_map[ny][nx]
                                            if ntile.is_walkable(): # Vizinho vazio/caminhável
                                                target_x, target_y = nx, ny
                                                break
                                    
                                    level_map[target_y][target_x].add_structure('Log', 1, 0)
                                    show_message("Tree harvested! Log spawned on ground.")
                                    
                                    # Reseta o dragging pois o item "pulou"
                                    dragging_item = None
                                    dragging_amount = 0
                                    dragging_source_tile = None
                                else:
                                    dragging_offset = (-22, -15) # Center Log on mouse
                                    show_message(f"Picked up {dragging_item}")


            if event.type == pygame.MOUSEBUTTONUP and event.button == 1: # Left Release
                if game_mode == "EDITOR":
                    editor_is_painting = False
                    editor_last_painted_tile = None
                
                if dragging_item:
                    mx, my = pygame.mouse.get_pos()
                    
                    # Check Drop on Inventory
                    inv_box_w = 200
                    inv_box_h = 200
                    inv_box_x = 10
                    inv_box_y = SCREEN_HEIGHT - inv_box_h - 10
                    inv_rect = pygame.Rect(inv_box_x, inv_box_y, inv_box_w, inv_box_h)
                    
                    if inv_rect.collidepoint(mx, my):
                        if dragging_item == 'Wall' and dragging_source_tile:
                            show_message("Cannot store Wall blocks in the bag!")
                            # Cancel movement and restore to source tile later
                        else:
                            # Dropped on Inventory
                            # Determine relative X, Y using offset to avoid jumping
                            rel_x = mx + dragging_offset[0] - inv_box_x
                            rel_y = my + dragging_offset[1] - inv_box_y
                            
                            # Clamp to bag bounds (keeping icon size approx 40x40 in mind)
                            rel_x = max(5, min(inv_box_w - 40, rel_x))
                            rel_y = max(5, min(inv_box_h - 40, rel_y))

                            # Handle split logic
                            final_qty = dragging_amount
                            
                            # Check for merging if dropped on another item of same type
                            merged = False
                            target_merge_item = None
                            for other_item in inventory:
                                if other_item == dragging_source_inv_item: continue
                                if other_item['name'] == dragging_item:
                                    # Hitbox for merge (approx 35x35)
                                    o_ix = inv_box_x + other_item['x']
                                    o_iy = inv_box_y + other_item['y']
                                    o_rect = pygame.Rect(o_ix, o_iy, 35, 35)
                                    if o_rect.collidepoint(mx, my):
                                        target_merge_item = other_item
                                        merged = True
                                        break
                            
                            if merged and target_merge_item:
                                target_merge_item['count'] += final_qty
                                # If from inventory, deduct from source
                                if dragging_source_inv_item:
                                    dragging_source_inv_item['count'] -= final_qty
                                    if dragging_source_inv_item['count'] <= 0:
                                        if dragging_source_inv_item in inventory:
                                            inventory.remove(dragging_source_inv_item)
                            
                            if not merged:
                                # If from inventory, we are moving or splitting
                                if dragging_source_inv_item:
                                    if final_qty < dragging_max_amount:
                                        # SPLIT: Leave remainder in source
                                        dragging_source_inv_item['count'] -= final_qty
                                        # Add NEW item at new pos
                                        inventory.append({'name': dragging_item, 'count': final_qty, 'x': rel_x, 'y': rel_y})
                                    else:
                                        # MOVE: Move original item
                                        dragging_source_inv_item['x'] = rel_x
                                        dragging_source_inv_item['y'] = rel_y
                                else:
                                    # From Map: Add new item
                                    inventory.append({'name': dragging_item, 'count': final_qty, 'x': rel_x, 'y': rel_y})
                                    
                                    # If we split from map (took less than max), we need to put remainder back on map?
                                    if dragging_source_tile and final_qty < dragging_max_amount:
                                        leftover = dragging_max_amount - final_qty
                                        sx, sy = dragging_source_tile
                                        t = level_map[sy][sx]
                                        t.structure = dragging_item 
                                        t.amount = leftover

                            show_message(f"Moved {final_qty} {dragging_item}")
                            
                            dragging_item = None
                            dragging_source_tile = None
                            dragging_source_inv_item = None
                            dragging_amount = 0
                            continue 

                    # Try to place item on Map
                    adj_mx = mx - offset_x
                    adj_my = my - offset_y
                    
                    # --- Plane-Based Picking for Placement ---
                    # Determine target Z context for picking
                    # If we have a neighbor or a specific base we're aiming for, we use that plane.
                    # As a first pass, let's try picking at the player's current floor level.
                    picking_z = (z_offset // 30) * 30
                    if dragging_item == 'Wall' and dragging_base_amount > 0:
                        picking_z = dragging_base_amount * 30
                    
                    grid_x, grid_y = iso_to_cart(adj_mx, adj_my + picking_z)
                    
                    # Logic to place
                    placed = False
                    
                    # Distance Check
                    dist_x = abs(grid_x - player_x)
                    dist_y = abs(grid_y - player_y)
                    
                    valid_dist = (dist_x <= 4 and dist_y <= 4)
                    valid_map = (0 <= grid_y < len(level_map) and 0 <= grid_x < len(level_map[0]))
                    
                    if valid_dist and valid_map:
                        target_tile = level_map[grid_y][grid_x]
                        
                        if dragging_item == 'Wall':
                            # Determina a altura desejada
                            desired_base = dragging_base_amount
                            if dragging_source_tile is None:
                                desired_base = int(z_offset // 30)
                            
                            # Tenta colocar (add_structure agora retorna False se houver colisão de tipos)
                            if target_tile.add_structure('Wall', 1, desired_base):
                                if dragging_source_inv_item:
                                     dragging_source_inv_item['count'] -= 1
                                     if dragging_source_inv_item['count'] <= 0:
                                          if dragging_source_inv_item in inventory:
                                               inventory.remove(dragging_source_inv_item)
                                
                                show_message(f"Wall placed at H{desired_base}")
                                placed = True
                            else:
                                show_message("Spot Occupied!")
                        else:
                            # Unified Placement using add_structure with collision check
                            target_structure = dragging_item
                            if dragging_item == 'Wood': target_structure = 'Tree'
                            
                            h_level = dragging_base_amount
                            if dragging_source_tile is None:
                                h_level = int(z_offset // 30)
                            
                            if target_tile.add_structure(target_structure, dragging_amount, h_level):
                                if dragging_source_inv_item:
                                     dragging_source_inv_item['count'] -= dragging_amount
                                     if dragging_source_inv_item['count'] <= 0:
                                          if dragging_source_inv_item in inventory:
                                               inventory.remove(dragging_source_inv_item)
                                show_message(f"{target_structure} placed at H{h_level}")
                                placed = True
                            else:
                                show_message("Spot Occupied!")

                    if not placed:
                        if dragging_source_tile:
                            # Map -> Map (Cancel)
                            sx, sy = dragging_source_tile
                            tile_to_restore = level_map[sy][sx]
                            # Restaura o bloco na sua altura original
                            tile_to_restore.add_structure(dragging_item, 1, dragging_base_amount)
                            show_message("Cancelled")
                        elif dragging_source_inv_item:
                            # Inventory -> Inventory (Cancel)
                            pass
                    
                    dragging_item = None
                    dragging_source_tile = None
                    dragging_source_inv_item = None
                    dragging_amount = 0

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if dragging_item:
                        if dragging_source_tile:
                            sx, sy = dragging_source_tile
                            tile_to_restore = level_map[sy][sx]
                            tile_to_restore.structure = dragging_item
                            tile_to_restore.amount = dragging_max_amount
                        
                        dragging_item = None
                        dragging_source_tile = None
                        dragging_source_inv_item = None
                        dragging_amount = 0
                        show_message("Drag Cancelled")

                if event.key == pygame.K_c: # Toggle Rest
                    is_resting = not is_resting
                    if is_resting:
                        show_message("Resting...")
                    else:
                        show_message("Awake!")
                
                if event.key == pygame.K_SPACE and jump_count < MAX_JUMPS:
                    if current_stamina >= 1:
                        current_stamina -= 1
                        jump_count += 1
                        is_jumping = True
                        z_velocity = 15
                        anim_frame = 0
                        print(f"Boing! {jump_count}")
                    else:
                        show_message("Too tired to jump!")

        # --- Input ---
        keys = pygame.key.get_pressed()
        mouse_buttons = pygame.mouse.get_pressed()
        dx, dy = 0, 0
        
        move_left = move_right = move_up = move_down = False
        
        # Free cam for Editor
        if game_mode == "EDITOR":
             cam_speed = 10
             if keys[pygame.K_LEFT] or keys[pygame.K_a]: offset_x += cam_speed
             if keys[pygame.K_RIGHT] or keys[pygame.K_d]: offset_x -= cam_speed
             if keys[pygame.K_UP] or keys[pygame.K_w]: offset_y += cam_speed
             if keys[pygame.K_DOWN] or keys[pygame.K_s]: offset_y -= cam_speed
             
             # Continuous Painting logic
             if editor_is_painting and mouse_buttons[0]:
                 mx, my = pygame.mouse.get_pos()
                 
                 # Ignorar se estiver sobre o Dashboard
                 dash_w, dash_h = 550, 140
                 dash_x = (SCREEN_WIDTH - dash_w) // 2
                 dash_y = SCREEN_HEIGHT - dash_h - 20
                 dash_rect = pygame.Rect(dash_x, dash_y - 25, dash_w, dash_h + 25)
                 
                 if not dash_rect.collidepoint(mx, my):
                     gx, gy = iso_to_cart(mx - offset_x, my - offset_y)
                     if (gx, gy) != editor_last_painted_tile:
                         apply_editor_tool(gx, gy, is_continuous=True)
                         editor_last_painted_tile = (gx, gy)
        
        if game_mode == "PLAY":
            move_left = keys[pygame.K_LEFT] or keys[pygame.K_a]
            move_right = keys[pygame.K_RIGHT] or keys[pygame.K_d]
            move_up = keys[pygame.K_UP] or keys[pygame.K_w]
            move_down = keys[pygame.K_DOWN] or keys[pygame.K_s]

            # --- Mouse Movement (Ultima Online Style) ---
            if mouse_buttons[2]: # Right Click Hold
                mx, my = pygame.mouse.get_pos()
                
                # Use Character Screen Position as Center
                # Note: We need accurate screen position of the player
                p_iso_x, p_iso_y = cart_to_iso(player_x, player_y)
                cx = p_iso_x + offset_x + TILE_SIZE//2 # Approximate center
                cy = p_iso_y + offset_y + TILE_SIZE//2
                
                # Vector from center to mouse (Screen Space)
                scr_dx = mx - cx
                scr_dy = my - cy
                
                # Convert to Grid Space Delta to linearize angles
                A = scr_dx / TILE_SIZE
                B = scr_dy / (TILE_SIZE / 2)
                
                grid_dx = (A + B) / 2
                grid_dy = (B - A) / 2
                
                # Calculate angle in Grid Space (Degrees)
                angle = math.degrees(math.atan2(grid_dy, grid_dx))
                if angle < 0: angle += 360
                
                # Sectoring (centered on 0, 45, 90...)
                angle_idx = int((angle + 22.5) % 360 / 45)
                
                # Map sectors directly to combinators
                if angle_idx == 0:   # 0 deg: +X (Grid East) -> Down + Right logic
                    move_down = True; move_right = True
                elif angle_idx == 1: # 45 deg: +X, +Y (Grid South-East) -> Down
                    move_down = True
                elif angle_idx == 2: # 90 deg: +Y (Grid South) -> Down + Left
                    move_down = True; move_left = True
                elif angle_idx == 3: # 135 deg: -X, +Y (Grid South-West) -> Left
                    move_left = True
                elif angle_idx == 4: # 180 deg: -X (Grid West) -> Up + Left
                    move_up = True; move_left = True
                elif angle_idx == 5: # 225 deg: -X, -Y (Grid North-West) -> Up
                    move_up = True
                elif angle_idx == 6: # 270 deg: -Y (Grid North) -> Up + Right
                    move_up = True; move_right = True
                elif angle_idx == 7: # 315 deg: +X, -Y (Grid North-East) -> Right
                    move_right = True

        # Prioridade para movimentos diagonais ou novos
        if move_left:
            dx -= 1; dy += 1
        if move_right:
            dx += 1; dy -= 1
        if move_up:
            dx -= 1; dy -= 1
        if move_down:
            dx += 1; dy += 1

        # Lógica de Facing Direction combinada
        if move_up and move_left:
            facing_direction = 'UP_LEFT'
        elif move_up and move_right:
            facing_direction = 'UP_RIGHT'
        elif move_down and move_left:
            facing_direction = 'DOWN_LEFT'
        elif move_down and move_right:
            facing_direction = 'DOWN_RIGHT'
        elif move_left:
            facing_direction = 'LEFT'
        elif move_right:
            facing_direction = 'RIGHT'
        elif move_up:
            facing_direction = 'UP'
        elif move_down:
            facing_direction = 'DOWN'

        dx = max(-1, min(1, dx))
        dy = max(-1, min(1, dy))

        # Determinar velocidade (Delay) com Shift para correr e cansaço
        current_move_delay = MOVE_DELAY # Padrão
        is_running = False
        
        if (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) and current_stamina > 0:
            current_move_delay = MOVE_DELAY // 2 # Corre (metade do delay = dobro da velocidade)
            is_running = True
        elif current_stamina <= 0:
            current_move_delay = MOVE_DELAY * 3 # Realmente lento com 0 stamina
        elif current_stamina < 10:
            current_move_delay = int(MOVE_DELAY * 1.5) # Mais devagar abaixo de 10
        else:
            current_move_delay = MOVE_DELAY # Anda (delay normal)

        img_to_draw = cat_idle
        is_moving_keys = (dx != 0 or dy != 0)
        
        if is_moving_keys:
            is_resting = False # Stop resting if moving

        if is_resting:
             img_to_draw = cat_sitting
        elif is_acting:
             # Animation logic for action
             if current_time - action_timer > ACTION_DURATION:
                 is_acting = False
             else:
                 # Alternate frames
                 action_frame = (int((current_time - action_timer) / ACTION_ANIM_SPEED)) % 2
                 img_to_draw = frames_action[action_frame]
                 
                 # Flip if facing left
                 if facing_direction in ['LEFT', 'UP_LEFT', 'DOWN_LEFT']:
                     img_to_draw = pygame.transform.flip(img_to_draw, True, False)

        elif is_jumping:
             if len(cat_jump_frames) > 0:
                 if current_time - anim_timer > ANIM_SPEED:
                     anim_frame = (anim_frame + 1) % len(cat_jump_frames)
                     anim_timer = current_time
                 img_to_draw = cat_jump_frames[anim_frame]
                 
                 if facing_direction == 'LEFT' or facing_direction == 'UP_LEFT' or facing_direction == 'DOWN_LEFT':
                     img_to_draw = pygame.transform.flip(img_to_draw, True, False)
                     
             else:
                 img_to_draw = cat_move
        elif is_moving_keys:
             # Sincroniza animação com o delay de movimento (quanto menor o delay, mais rápido o frame)
             if current_time - walk_timer > current_move_delay:
                 walk_frame = (walk_frame + 1) % 2
                 walk_timer = current_time
                 
             if facing_direction == 'LEFT' or facing_direction == 'DOWN_LEFT':
                 img_to_draw = frames_left[walk_frame]
             elif facing_direction == 'RIGHT' or facing_direction == 'DOWN_RIGHT':
                 img_to_draw = frames_right[walk_frame]
             elif facing_direction == 'UP_LEFT':
                 img_to_draw = frames_up_left[walk_frame]
             elif facing_direction == 'UP_RIGHT':
                 img_to_draw = frames_up_right[walk_frame]
             elif facing_direction == 'UP':
                 # UP usa BackWalk e BackWalk2 (índices 1 e 2)
                 img_to_draw = frames_back[1 + walk_frame]
             elif facing_direction == 'DOWN':
                 img_to_draw = frames_front[walk_frame]
             else:
                 # Caso padrão (frontal ou indefinido)
                 img_to_draw = cat_move

        else:
             # Quando parado, usar o frame 0 (Stand) da direção atual
             if facing_direction == 'LEFT' or facing_direction == 'DOWN_LEFT':
                 img_to_draw = frames_left[0]
             elif facing_direction == 'RIGHT' or facing_direction == 'DOWN_RIGHT':
                 img_to_draw = frames_right[0]
             elif facing_direction == 'UP_LEFT':
                 img_to_draw = frames_up_left[0]
             elif facing_direction == 'UP_RIGHT':
                 img_to_draw = frames_up_right[0]
             elif facing_direction == 'UP':
                 img_to_draw = frames_back[0]
             elif facing_direction == 'DOWN':
                 img_to_draw = frames_front[0]
             else:
                 img_to_draw = cat_idle


        # Gasta stamina quando corre (1 por segundo)
        if is_running and (dx != 0 or dy != 0):
            if current_time - stamina_timer > 1000:
                current_stamina = max(0, current_stamina - 1)
                stamina_timer = current_time
        elif is_resting:
            # Recupera stamina rapidamente ao descansar
            if current_time - stamina_timer > 500:
                current_stamina = min(max_stamina, current_stamina + 1)
                stamina_timer = current_time
        elif not is_running:
            # Recupera stamina lentamente
            if current_time - stamina_timer > 2000:
                current_stamina = min(max_stamina, current_stamina + 0.5)
                stamina_timer = current_time

        if not is_resting and (dx != 0 or dy != 0) and (current_time - last_move_time > current_move_delay):
            target_x = player_x + dx
            target_y = player_y + dy
            if (0 <= target_y < len(level_map)) and (0 <= target_x < len(level_map[0])):
                target_tile = level_map[target_y][target_x]
                
                # Checagem de Colisão 3D (Posição + Altura em múltiplas pilhas)
                char_h = 25
                is_blocked_3d = False
                
                for p in target_tile.piles:
                    if p['structure'] == 'Wall':
                        w_bot = p['base_amount'] * 30
                        w_top = (p['base_amount'] + p['amount']) * 30
                        if (z_offset < w_top) and (z_offset + char_h > w_bot):
                            is_blocked_3d = True
                            break
                    elif p['structure'] == 'Tree':
                        t_bot = p['base_amount'] * 30
                        if (z_offset < t_bot + 60) and (z_offset + char_h > t_bot):
                            is_blocked_3d = True
                            break
                    elif p['structure'] == 'Clay':
                        c_bot = p['base_amount'] * 5
                        c_top = (p['base_amount'] + p['amount']) * 5
                        if (z_offset < c_top) and (z_offset + char_h > c_bot):
                            is_blocked_3d = True
                            break
                
                # Permite entrar se não estiver bloqueado 3D e o terreno for válido
                can_move = not is_blocked_3d
                if target_tile.ground_type == 'W' and z_offset <= 0:
                    can_move = False # Água ainda bloqueia no nível do chão
                
                if can_move:
                    # --- Kicking Logic (Chutar Log) ---
                    # Encontra logs na base que podem ser chutados
                    log_pile = next((p for p in target_tile.piles if p['structure'] == 'Log' and p['base_amount'] == 0), None)
                    if log_pile:
                        # Tenta empurrar na mesma direção do movimento
                        kx, ky = target_x + dx, target_y + dy
                        if 0 <= ky < len(level_map) and 0 <= kx < len(level_map[0]):
                            k_tile = level_map[ky][kx]
                            if k_tile.is_walkable():
                                k_tile.add_structure('Log', log_pile['amount'], 0)
                                target_tile.piles.remove(log_pile)
                                # Agora o tile está livre para caminhar?
                                can_move = target_tile.is_walkable()
                            else:
                                can_move = False # Bloqueado pelo log que não pode ser chutado
                        else:
                            can_move = False # Borda do mapa

                if can_move:
                    player_x, player_y = target_x, target_y
                    last_move_time = current_time

            # --- Física de Pulo e Gravidade (Executada APÓS o movimento para evitar lag de 1 frame) ---
        if game_mode == "PLAY":
            current_tile_obj = level_map[player_y][player_x]
            
            # Identifica superfícies de apoio (chão e plataformas)
            possible_floors = [0]
            ceilings = []
            
            if current_tile_obj.structure == 'Wall':
                possible_floors.append((current_tile_obj.base_amount + current_tile_obj.amount) * 30)
                ceilings.append(current_tile_obj.base_amount * 30)
            elif current_tile_obj.structure == 'Clay':
                possible_floors.append((current_tile_obj.base_amount + current_tile_obj.amount) * 5)

            # Ground level: maior suporte abaixo ou no nível atual
            ground_level = 0
            for f in possible_floors:
                if f <= z_offset + 5: # Margem de 5px para aceitar degraus e evitar quedas
                    if f > ground_level:
                        ground_level = f
            
            # Teto: menor obstrução acima
            current_ceiling = 9999
            for c in ceilings:
                if c > z_offset:
                    if c < current_ceiling:
                        current_ceiling = c

            if is_jumping or z_offset > ground_level:
                z_offset += z_velocity
                z_velocity -= GRAVITY
                
                if z_offset <= ground_level:
                    z_offset = ground_level
                    z_velocity = 0
                    jump_count = 0
                    is_jumping = False
                
                # Bater a cabeça
                if z_offset + 25 >= current_ceiling:
                    z_offset = current_ceiling - 26
                    z_velocity = 0
            elif z_offset < ground_level:
                # Subida instantânea de degraus (plataformas)
                z_offset = ground_level

        # --- Calcular Target Tile (Highlight) ---
        tix, tiy = 0, 0
        if facing_direction == 'RIGHT': tix, tiy = 1, -1
        elif facing_direction == 'LEFT': tix, tiy = -1, 1
        elif facing_direction == 'UP': tix, tiy = -1, -1
        elif facing_direction == 'DOWN': tix, tiy = 1, 1
        elif facing_direction == 'UP_LEFT': tix, tiy = -1, 0
        elif facing_direction == 'UP_RIGHT': tix, tiy = 0, -1
        elif facing_direction == 'DOWN_LEFT': tix, tiy = 0, 1
        elif facing_direction == 'DOWN_RIGHT': tix, tiy = 1, 0
        
        highlight_tx = player_x + tix
        highlight_ty = player_y + tiy

        # --- Câmera ---
        if game_mode == "PLAY":
            cat_iso_x, cat_iso_y = cart_to_iso(player_x, player_y)
            target_offset_x = (SCREEN_WIDTH // 2) - cat_iso_x
            target_offset_y = (SCREEN_HEIGHT // 2) - cat_iso_y
            DEADZONE = 90
            
            diff_x = target_offset_x - offset_x
            diff_y = target_offset_y - offset_y
            
            if abs(diff_x) > DEADZONE:
                offset_x += diff_x - DEADZONE if diff_x > 0 else diff_x + DEADZONE
            
            if abs(diff_y) > DEADZONE:
                offset_y += diff_y - DEADZONE if diff_y > 0 else diff_y + DEADZONE
        
        # Determine mouse grid pos for highlighting
        mx, my = pygame.mouse.get_pos()
        hover_grid_x, hover_grid_y = iso_to_cart(mx - offset_x, my - offset_y)

        screen.fill(BG_COLOR)

        # --- Desenho do Mapa ---
        for row_index, row in enumerate(level_map):
            for col_index, tile in enumerate(row):
                iso_x, iso_y = cart_to_iso(col_index, row_index)
                draw_x = iso_x + offset_x
                draw_y = iso_y + offset_y

                points = [
                    (draw_x, draw_y),
                    (draw_x + TILE_SIZE, draw_y + TILE_SIZE/2),
                    (draw_x, draw_y + TILE_SIZE),
                    (draw_x - TILE_SIZE, draw_y + TILE_SIZE/2)
                ]
                
                # --- Destacar Alvo da Interação / Editor ---
                if (game_mode == "PLAY" and col_index == highlight_tx and row_index == highlight_ty) or \
                   (game_mode == "EDITOR" and col_index == hover_grid_x and row_index == hover_grid_y):
                     # Desenha um chão amarelo semi-transparente ou borda
                     select_surf = pygame.Surface((TILE_SIZE*2, TILE_SIZE), pygame.SRCALPHA)
                     # Desenhar losango
                     color_sel = (255, 255, 0, 100) if game_mode == "PLAY" else (0, 255, 255, 100)
                     pygame.draw.polygon(select_surf, color_sel, [
                         (TILE_SIZE, 0), (TILE_SIZE*2, TILE_SIZE/2), (TILE_SIZE, TILE_SIZE), (0, TILE_SIZE/2)
                     ])
                     screen.blit(select_surf, (draw_x - TILE_SIZE, draw_y))
                     # Borda extra
                     pygame.draw.polygon(screen, color_sel[:3], points, 2)
                
                # Draw Ground
                g_type = tile.ground_type
                if g_type == 'G' and grass_variants:
                     # Hash determinístico para variação
                     variant_idx = (col_index * 3 + row_index * 7) % len(grass_variants)
                     selected_grass = grass_variants[variant_idx]
                     
                     pygame.draw.polygon(screen, COLORS['G'], points)
                     screen.blit(selected_grass, (draw_x - TILE_SIZE, draw_y))
                elif g_type == 'G':
                    pygame.draw.polygon(screen, COLORS['G'], points)
                elif g_type == 'W' and water_img:
                    # Renderiza o sprite de água
                    screen.blit(water_img, (draw_x - TILE_SIZE, draw_y))
                elif g_type == 'S' and sand_img:
                    # Desenhar fundo amarelo primeiro (caso o sprite tenha transparência)
                    pygame.draw.polygon(screen, COLORS['S'], points)
                    screen.blit(sand_img, (draw_x - TILE_SIZE, draw_y))
                elif g_type == 'C' and clay_ground_img:
                    # Desenhar fundo marrom primeiro
                    pygame.draw.polygon(screen, COLORS['C'], points)
                    screen.blit(clay_ground_img, (draw_x - TILE_SIZE, draw_y))
                else:
                    color = COLORS.get(g_type, (0,0,0))
                    pygame.draw.polygon(screen, color, points)

                # --- Draw Growth Stages for Tree Spawners ---
                if tile.structure is None:
                    spawner = next((r for r in respawning_resources if r['x'] == col_index and r['y'] == row_index), None)
                    if spawner and spawner['structure'] == 'Tree' and tree_growth_imgs:
                        # Calcula o estágio atual baseado no tempo restante
                        # elapsed = delay - (target - now)
                        delay = spawner['respawn_delay']
                        target = spawner['respawn_time']
                        elapsed = max(0, delay - (target - now))
                        # 5 estágios: 0, 1, 2, 3, 4
                        stage = int(min(4, (elapsed / delay) * 5))
                        if stage < len(tree_growth_imgs):
                            screen.blit(tree_growth_imgs[stage], (draw_x - 30, draw_y - 60))

                # Draw Structures (Iterate over all piles in tile)
                for p in tile.piles:
                    p_type = p.get('structure')
                    p_amt = p.get('amount', 1)
                    p_base = p.get('base_amount', 0)
                    
                    if p_type == 'Tree':
                        if tree_img:
                            screen.blit(tree_img, (draw_x - 30, draw_y - 60 - (p_base * 30)))
                        else:
                             pygame.draw.rect(screen, (101, 67, 33), (draw_x - 5, draw_y - 10 - (p_base * 30), 10, 25)) 
                             pygame.draw.circle(screen, COLORS['F'], (int(draw_x), int(draw_y - 15 - (p_base * 30))), 20)
                    elif p_type == 'Clay':
                        if clay_img:
                            visual_limit = 5
                            iters = min(p_amt, visual_limit)
                            base_x = draw_x - 20
                            base_y = draw_y - 5 - (p_base * 5)
                            offset_per_item = 5
                            for i in range(iters):
                                draw_pos_y = base_y - (i * offset_per_item)
                                screen.blit(clay_img, (base_x, draw_pos_y))
                            if p_amt > visual_limit:
                                txt_amt = font.render(f"+{p_amt - visual_limit}", True, (255, 255, 255))
                                screen.blit(txt_amt, (draw_x, base_y - (visual_limit * offset_per_item) - 15))
                        else:
                            pygame.draw.circle(screen, COLORS['R'], (int(draw_x), int(draw_y + 10 - (p_base * 5))), 12)
                    elif p_type == 'Log':
                        if log_img:
                            # Centraliza perfeitamente no tile (60x30)
                            # Log (45x30)
                            base_x = draw_x - 22
                            base_y = draw_y + 2 - (p_base * 8)
                            
                            if p_amt > 1 and log_stack_img:
                                # Pilha (50x40)
                                screen.blit(log_stack_img, (draw_x - 25, draw_y - 10 - (p_base * 8)))
                                if p_amt > 2:
                                    txt_amt = font.render(f"x{p_amt}", True, (255, 255, 255))
                                    screen.blit(txt_amt, (draw_x, draw_y - 25 - (p_base * 8)))
                            else:
                                screen.blit(log_img, (base_x, base_y))
                        else:
                            pygame.draw.rect(screen, (139, 69, 19), (draw_x - 10, draw_y - 5 - (p_base * 10), 20, 10))
                    elif p_type == 'Wall':
                        if clay_wall_img:
                            base_x = draw_x - 30
                            base_y = draw_y - 30 
                            stack_offset_y = 30
                            for i in range(p_base, p_base + p_amt):
                                screen.blit(clay_wall_img, (base_x, base_y - (i * stack_offset_y)))
                        else:
                            wall_color = COLORS['Wall']
                            # Simple fallback for floating walls
                            pygame.draw.rect(screen, wall_color, (draw_x - 15, draw_y - 15 - (p_base * 30), 30, 30))

                # --- DESENHO DO GATO (DENTRO DO LOOP PARA SORTING) ---
                if game_mode == "PLAY" and col_index == player_x and row_index == player_y:
                    cat_draw_x = draw_x - (img_to_draw.get_width() // 2)
                    cat_draw_y = draw_y - img_to_draw.get_height() + (TILE_SIZE // 2) - z_offset
                    screen.blit(img_to_draw, (cat_draw_x, cat_draw_y))

                    # --- Balão de Fala do Gato ---
                    if chat_message and (current_time - chat_timer < CHAT_DURATION):
                        # Renderiza Texto
                        text_s = chat_font.render(chat_message, True, (0, 0, 0))
                        # Fundo branco
                        bubble_rect = text_s.get_rect(center=(cat_draw_x + 25, cat_draw_y - 20))
                        bg_rect = bubble_rect.inflate(10, 10)
                        pygame.draw.rect(screen, (255, 255, 255), bg_rect, border_radius=5)
                        pygame.draw.rect(screen, (0, 0, 0), bg_rect, 2, border_radius=5) # Borda
                        screen.blit(text_s, bubble_rect)
                    elif current_time - chat_timer >= CHAT_DURATION:
                        chat_message = "" # Limpa mensagem antiga


        if game_mode == "EDITOR":
            # Desenha ícones flutuantes sobre os spawners para o editor ver
            for spawner in respawning_resources:
                sx, sy = spawner['x'], spawner['y']
                s_iso_x, s_iso_y = cart_to_iso(sx, sy)
                s_draw_x = s_iso_x + offset_x
                s_draw_y = s_iso_y + offset_y
                
                # Pequeno indicador de spawner (Sírculo verde com a inicial)
                pygame.draw.circle(screen, (0, 255, 0), (int(s_draw_x), int(s_draw_y)), 10)
                spw_txt = font.render("S", True, (0, 0, 0))
                screen.blit(spw_txt, (s_draw_x - 5, s_draw_y - 10))

        # --- UI Overlay ---
        try:
             ui_y_base = 10
             
             if game_mode == "PLAY":
                 # Status Bars (Top Left)
                 bar_x = 10
                 bar_y = 10
                 bar_w = 150
                 bar_h = 12
                 spacing = 18
                 
                 # Backgrounds
                 for i in range(3):
                     pygame.draw.rect(screen, (50, 50, 50), (bar_x, bar_y + i * spacing, bar_w, bar_h), border_radius=3)
                 
                 # HP (Red)
                 hp_percent = current_hp / max_hp if max_hp > 0 else 0
                 pygame.draw.rect(screen, (200, 50, 50), (bar_x, bar_y, int(bar_w * hp_percent), bar_h), border_radius=3)
                 hp_txt = font.render(f"HP: {int(current_hp)}/{int(max_hp)}", True, (255, 255, 255))
                 screen.blit(hp_txt, (bar_x + bar_w + 5, bar_y - 2))
                 
                 # STAMINA (Yellow/Orange)
                 st_percent = current_stamina / max_stamina if max_stamina > 0 else 0
                 pygame.draw.rect(screen, (255, 200, 50), (bar_x, bar_y + spacing, int(bar_w * st_percent), bar_h), border_radius=3)
                 st_txt = font.render(f"ST: {int(current_stamina)}/{int(max_stamina)}", True, (255, 255, 255))
                 screen.blit(st_txt, (bar_x + bar_w + 5, bar_y + spacing - 2))
                 
                 # MANA (Blue)
                 mn_percent = current_mana / max_mana if max_mana > 0 else 0
                 pygame.draw.rect(screen, (50, 100, 255), (bar_x, bar_y + spacing * 2, int(bar_w * mn_percent), bar_h), border_radius=3)
                 mn_txt = font.render(f"MN: {int(current_mana)}/{int(max_mana)}", True, (255, 255, 255))
                 screen.blit(mn_txt, (bar_x + bar_w + 5, bar_y + spacing * 2 - 2))
                 
                 # Stats Display (Optional, small)
                 stats_txt = font.render(f"STR {stats['str']} DEX {stats['dex']} INT {stats['int']}", True, (200, 200, 200))
                 screen.blit(stats_txt, (bar_x, bar_y + spacing * 3))
             else:
                 # Background box for Editor UI (if needed)
                 # --- NEW EDITOR DASHBOARD UI ---
                 dash_w, dash_h = 550, 140
                 dash_x = (SCREEN_WIDTH - dash_w) // 2
                 dash_y = SCREEN_HEIGHT - dash_h - 20
                 
                 # Background surface with transparency
                 dash_surf = pygame.Surface((dash_w, dash_h), pygame.SRCALPHA)
                 dash_surf.fill((0, 0, 0, 180))
                 pygame.draw.rect(dash_surf, (100, 100, 100), (0, 0, dash_w, dash_h), 3, border_radius=10)
                 screen.blit(dash_surf, (dash_x, dash_y))

                 # Draw Categories (Tabs)
                 tab_w = dash_w // len(editor_categories)
                 for i, cat in enumerate(editor_categories):
                     tab_rect = pygame.Rect(dash_x + i * tab_w, dash_y - 25, tab_w, 25)
                     is_active = (i == editor_category_idx)
                     
                     t_col = (40, 40, 40, 220) if not is_active else (70, 70, 180, 220)
                     t_surf = pygame.Surface((tab_w, 25), pygame.SRCALPHA)
                     t_surf.fill(t_col)
                     pygame.draw.rect(t_surf, (150, 150, 150), (0, 0, tab_w, 25), 2 if is_active else 1)
                     screen.blit(t_surf, (tab_rect.x, tab_rect.y))
                     
                     cat_name_txt = font.render(cat, True, (255, 255, 255) if is_active else (180, 180, 180))
                     screen.blit(cat_name_txt, (tab_rect.centerx - cat_name_txt.get_width()//2, tab_rect.y + 3))

                 # Draw Items for current category
                 curr_cat = editor_categories[editor_category_idx]
                 items = editor_options[curr_cat]
                 
                 margin = 20
                 slot_size = 60
                 for i, item in enumerate(items):
                     slot_rect = pygame.Rect(dash_x + margin + i * (slot_size + 20), dash_y + 45, slot_size, slot_size)
                     is_sel = (i == editor_selected_idx)
                     
                     pygame.draw.rect(screen, (30, 30, 30), slot_rect, border_radius=5)
                     if is_sel:
                         pygame.draw.rect(screen, (0, 255, 0), slot_rect, 3, border_radius=5)
                     else:
                         pygame.draw.rect(screen, (80, 80, 80), slot_rect, 1, border_radius=5)

                     preview_img = None
                     if item == "Tree": preview_img = tree_img
                     elif item == "Clay": preview_img = clay_img
                     elif item == "G": preview_img = grass_variants[0] if grass_variants else None
                     elif item == "W": preview_img = water_img
                     elif item == "S": preview_img = sand_img
                     
                     if preview_img:
                         p_scaled = pygame.transform.scale(preview_img, (slot_size - 10, slot_size - 10))
                         screen.blit(p_scaled, (slot_rect.x + 5, slot_rect.y + 5))
                         if curr_cat == "SPAWNER":
                             pygame.draw.rect(screen, (0, 255, 0), slot_rect, 2, border_radius=5)
                     elif item == "Wall":
                         pygame.draw.rect(screen, (101, 67, 33), (slot_rect.x + 10, slot_rect.y + 10, slot_size - 20, slot_size - 20))
                     elif item is None:
                         rem_txt = font.render("X", True, (255, 0, 0))
                         screen.blit(rem_txt, (slot_rect.centerx - 5, slot_rect.centery - 10))
                     
                     label = str(item) if item else "Remove"
                     label_txt = font.render(label, True, (255, 255, 255))
                     screen.blit(label_txt, (slot_rect.centerx - label_txt.get_width()//2, slot_rect.bottom + 2))

                 inst_txt = font.render("[TAB] Cat | [<- ->] Item | [M1] Paint", True, (150, 150, 150))
                 screen.blit(inst_txt, (dash_x + 10, dash_y + 10))
                 
                 delay_txt = font.render(f"Spawner Delay: {editor_spawner_delay}s [+/-]", True, (200, 200, 255))
                 screen.blit(delay_txt, (dash_x + dash_w - delay_txt.get_width() - 10, dash_y + 10))

             # --- Inventory Box (SÓ NO MODO PLAY) ---
             if game_mode == "PLAY":
                 if not inventory_minimized:
                     inv_box_w, inv_box_h = 200, 200
                     inv_box_x = 10
                     inv_box_y = SCREEN_HEIGHT - inv_box_h - 10
                     inventory_box_rect = pygame.Rect(inv_box_x, inv_box_y, inv_box_w, inv_box_h)
                     
                     if caixa_img:
                         screen.blit(caixa_img, (inv_box_x, inv_box_y))
                     else:
                         inv_bg = pygame.Surface((inv_box_w, inv_box_h), pygame.SRCALPHA)
                         inv_bg.fill((0, 0, 0, 150))
                         screen.blit(inv_bg, (inv_box_x, inv_box_y))
                         pygame.draw.rect(screen, (150, 150, 150), (inv_box_x, inv_box_y, inv_box_w, inv_box_h), 2)
                     
                     for item in inventory:
                         # Logic to handle dragging visualization
                         draw_count = item['count']
                         if dragging_source_inv_item == item:
                             # Calculate visual remainder
                             draw_count = item['count'] - dragging_amount
                             if draw_count <= 0:
                                 continue # Fully picked up

                         ix = inv_box_x + item.get('x', 0)
                         iy = inv_box_y + item.get('y', 0)
                         item_name = item['name']

                         if item_name == 'Log' and log_img:
                             icon = pygame.transform.scale(log_img, (40, 28))
                             screen.blit(icon, (ix, iy))
                         elif item_name == 'Wood' and tree_img:
                             icon = pygame.transform.scale(tree_img, (30, 45))
                             screen.blit(icon, (ix, iy))
                         elif item_name == 'Clay' and clay_img:
                             icon = pygame.transform.scale(clay_img, (35, 35))
                             screen.blit(icon, (ix, iy))
                         else:
                             pygame.draw.rect(screen, (200, 200, 200), (ix, iy, 30, 30))

                         if draw_count > 1:
                             cnt_surf = font.render(str(draw_count), True, (255, 255, 255))
                             shadow = font.render(str(draw_count), True, (0, 0, 0))
                             screen.blit(shadow, (ix + 16, iy + 17))
                             screen.blit(cnt_surf, (ix + 15, iy + 16))
                 else:
                     # Mini Box logic
                     inv_box_w, inv_box_h = 50, 50
                     inv_box_x = 10
                     inv_box_y = SCREEN_HEIGHT - inv_box_h - 10
                     inventory_box_rect = pygame.Rect(inv_box_x, inv_box_y, inv_box_w, inv_box_h)
                     
                     if caixa_mini_img:
                         screen.blit(caixa_mini_img, (inv_box_x, inv_box_y))
                     else:
                         pygame.draw.rect(screen, (100, 100, 100), inventory_box_rect)
                         mini_txt = font.render("INV", True, (255, 255, 255))
                         screen.blit(mini_txt, (inv_box_x + 5, inv_box_y + 15))

             # --- Minimap ---
             if not minimap_minimized:
                 minimap_tile_size = 5
                 map_width_tiles = len(level_map[0])
                 map_height_tiles = len(level_map)
                 minimap_w = map_width_tiles * minimap_tile_size
                 minimap_h = map_height_tiles * minimap_tile_size
                 
                 minimap_x = SCREEN_WIDTH - minimap_w - 10
                 minimap_y = 10
                 
                 # Update hit rect
                 minimap_ui_rect = pygame.Rect(minimap_x - 2, minimap_y - 2, minimap_w + 4, minimap_h + 4)

                 # Background + Border for minimap
                 pygame.draw.rect(screen, (0, 0, 0), minimap_ui_rect)
                 
                 for r, row in enumerate(level_map):
                     for c, tile in enumerate(row):
                         color = COLORS.get(tile.ground_type, (0,0,0))
                         # Overwrite color for structures to make them visible on minimap
                         if tile.structure == 'Clay': 
                             color = COLORS['R']
                         elif tile.structure == 'Tree': 
                             color = COLORS['F']
                         elif tile.structure == 'Wall': 
                             color = COLORS['WALL']
                         elif tile.structure == 'Log':
                             color = (139, 69, 19) # Brown
                             
                         pygame.draw.rect(screen, color, 
                                          (minimap_x + c * minimap_tile_size, 
                                           minimap_y + r * minimap_tile_size, 
                                           minimap_tile_size, minimap_tile_size))

                 # Player on Minimap
                 if game_mode == "PLAY":
                     # player_x, player_y are grid coordinates
                     mp_player_x = minimap_x + (player_x * minimap_tile_size)
                     mp_player_y = minimap_y + (player_y * minimap_tile_size)
                     if cat_minimap_icon:
                         screen.blit(cat_minimap_icon, 
                                     (int(mp_player_x) - cat_minimap_icon.get_width() // 2, 
                                      int(mp_player_y) - cat_minimap_icon.get_height() // 2))
                     else:
                         pygame.draw.circle(screen, (255, 0, 0), (int(mp_player_x), int(mp_player_y)), 3)
             else:
                 # Minimap is minimized -> Draw the Icon
                 icon_size = 64
                 minimap_x = SCREEN_WIDTH - icon_size - 10
                 minimap_y = 10
                 minimap_ui_rect = pygame.Rect(minimap_x, minimap_y, icon_size, icon_size)
                 
                 # Tenta carregar o ícone específico do minimapa
                 try:
                     icon_path_min = os.path.join(base_dir, 'assets', 'MiniMapIcon.png')
                     if os.path.exists(icon_path_min):
                         m_icon = pygame.image.load(icon_path_min).convert_alpha()
                         m_icon = pygame.transform.smoothscale(m_icon, (icon_size, icon_size))
                         screen.blit(m_icon, (minimap_x, minimap_y))
                     else:
                         # Fallback para o ICON.png original caso o MiniMapIcon suma
                         alt_path = os.path.join(base_dir, 'assets', 'sprites', 'tiger_gray_cat', 'ICON.png')
                         if os.path.exists(alt_path):
                             m_icon = pygame.image.load(alt_path).convert_alpha()
                             m_icon = pygame.transform.smoothscale(m_icon, (icon_size, icon_size))
                             screen.blit(m_icon, (minimap_x, minimap_y))
                         else:
                             pygame.draw.rect(screen, (0, 100, 255), minimap_ui_rect)
                 except:
                     pygame.draw.rect(screen, (0, 100, 255), minimap_ui_rect)
                 
                 # Borda branca removida conforme pedido do usuário

        except Exception as e:
             # print(f"UI Error: {e}")
             pass

        # --- GHOST of Dragging Item ---
        # Draw this LAST so it stays on top of the UI (Inventory box)
        if dragging_item:
            dmx, dmy = pygame.mouse.get_pos()
            icon_to_draw = None
            if dragging_item == 'Clay' and clay_img:
                icon_to_draw = clay_img
            elif dragging_item == 'Wood' and tree_img:
                icon_to_draw = tree_img
            elif dragging_item == 'Log' and log_img:
                icon_to_draw = log_img
            elif dragging_item == 'Wall' and clay_wall_img:
                icon_to_draw = clay_wall_img
                
            if icon_to_draw:
                # Ghost on mouse (Drawn over UI)
                draw_size = (40, 40)
                if dragging_item == 'Wall':
                    draw_size = (60, 60)
                
                ghost_icon = pygame.transform.scale(icon_to_draw, draw_size)
                # Se dragging_offset for (0,0), centralizamos no mouse
                if dragging_offset == (0, 0):
                    gi_x = dmx - draw_size[0] // 2
                    gi_y = dmy - draw_size[1] // 2
                else:
                    gi_x = dmx + dragging_offset[0]
                    gi_y = dmy + dragging_offset[1]

                screen.blit(ghost_icon, (gi_x, gi_y))
                
                # Show amount being dragged
                if dragging_amount > 1:
                    amt_txt = font.render(str(dragging_amount), True, (255, 255, 255))
                    sh_txt = font.render(str(dragging_amount), True, (0, 0, 0))
                    screen.blit(sh_txt, (gi_x + 1, gi_y - 19))
                    screen.blit(amt_txt, (gi_x, gi_y - 20))
                
            # --- Plane-Based Ghost Picking ---
            adj_mx = dmx - offset_x
            adj_my = dmy - offset_y
            
            # Predict picking Z for ghost
            picking_z = (z_offset // 30) * 30
            if dragging_item == 'Wall' and dragging_base_amount > 0:
                picking_z = dragging_base_amount * 30
            
            g_gx, g_gy = iso_to_cart(adj_mx, adj_my + picking_z)
            
            dist_x = abs(g_gx - player_x)
            dist_y = abs(g_gy - player_y)
            valid_range = 4 if dragging_item == 'Wall' else 2
            valid_pos = (dist_x <= valid_range and dist_y <= valid_range) and (0 <= g_gy < len(level_map) and 0 <= g_gx < len(level_map[0]))
            
            if valid_pos:
                 target_t = level_map[g_gy][g_gx]
                 if dragging_item == 'Wall':
                     if target_t.structure not in [None, 'Wall']:
                         valid_pos = False
                 elif target_t.structure is not None:
                     valid_pos = False

            if icon_to_draw and valid_pos:
                # Recalculate screen pos for map ghost
                gh_iso_x, gh_iso_y = cart_to_iso(g_gx, g_gy)
                gh_draw_x = gh_iso_x + offset_x
                gh_draw_y = gh_iso_y + offset_y
                
                ghost_surf = icon_to_draw.copy()
                ghost_z_offset = 0 # Default (ground)
                
                if dragging_item == 'Wood':
                     ghost_surf = pygame.transform.scale(ghost_surf, (60, 80))
                     offset_ghost_y = 65
                elif dragging_item == 'Wall':
                     ghost_surf = pygame.transform.scale(ghost_surf, (60, 60))
                     offset_ghost_y = 30
                     # Preview Height
                     p_base = dragging_base_amount
                     if dragging_source_tile is None:
                         p_base = int(z_offset // 30)
                     
                     # Ajuste visual: se já existir uma parede nessa altura, o preview sobe (stacking simulado)
                     # add_structure faz isso internamente, então o preview deve mostrar o resultado final.
                     temp_base = p_base
                     for p in target_t.piles:
                         if p['structure'] == 'Wall':
                             # Se o novo bloco encosta no topo desta pilha, ele vai para cima
                             if p['base_amount'] <= temp_base < p['base_amount'] + p['amount']:
                                 temp_base = p['base_amount'] + p['amount']
                     preview_base = temp_base
                     ghost_z_offset = preview_base * 30
                else: # Clay
                     ghost_surf = pygame.transform.scale(ghost_surf, (40, 40))
                     offset_ghost_y = 5 
                
                ghost_surf.fill((100, 255, 100, 150), special_flags=pygame.BLEND_RGBA_MULT)
                # Apply ghost_z_offset to the drawing position
                screen.blit(ghost_surf, (gh_draw_x - (ghost_surf.get_width()//2), gh_draw_y - offset_ghost_y - ghost_z_offset))
                
                # Exibir indicador de andar (H0, H1, H2...) para facilitar o posicionamento
                if dragging_item == 'Wall':
                    h_label = font.render(f"H{preview_base}", True, (255, 255, 255))
                    # Desenhar com uma pequena sombra para legibilidade
                    sh_label = font.render(f"H{preview_base}", True, (0, 0, 0))
                    lx = gh_draw_x + 15
                    ly = gh_draw_y - offset_ghost_y - ghost_z_offset - 20
                    screen.blit(sh_label, (lx + 1, ly + 1))
                    screen.blit(h_label, (lx, ly))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        input("Pressione Enter para sair...")
