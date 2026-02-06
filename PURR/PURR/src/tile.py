class Tile:
    def __init__(self, ground_type):
        self.ground_type = ground_type  # 'G', 'W', 'S' (Floor)
        self.structure = None           # None, 'Tree', 'Clay', 'Wall'
        self.amount = 1                 # Quantity of the structure (for stacking Clay)
        
    def is_walkable(self):
        # Water is not walkable
        if self.ground_type == 'W':
            return False
        # Structures that block movement
        if self.structure in ['Clay', 'Wall', 'Tree']:
            return False
        return True
