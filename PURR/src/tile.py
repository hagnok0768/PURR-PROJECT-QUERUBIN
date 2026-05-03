class Tile:
    def __init__(self, ground_type):
        self.ground_type = ground_type  # 'G', 'W', 'S' (Floor)
        self.piles = [] # Lista de dicionários: {'structure': str, 'amount': int, 'base_amount': int}
        
    @property
    def structure(self):
        if not self.piles: return None
        return self.piles[0]['structure']
    
    @structure.setter
    def structure(self, value):
        if value is None:
            self.piles = []
        else:
            if not self.piles:
                self.piles.append({'structure': value, 'amount': 1, 'base_amount': 0})
            else:
                self.piles[0]['structure'] = value

    @property
    def amount(self):
        if not self.piles: return 0
        return self.piles[0]['amount']
    
    @amount.setter
    def amount(self, value):
        if not self.piles:
            if value > 0:
                self.piles.append({'structure': 'Wall', 'amount': value, 'base_amount': 0})
        else:
            self.piles[0]['amount'] = value

    @property
    def base_amount(self):
        if not self.piles: return 0
        return self.piles[0]['base_amount']
    
    @base_amount.setter
    def base_amount(self, value):
        if not self.piles:
            self.piles.append({'structure': 'Wall', 'amount': 1, 'base_amount': value})
        else:
            self.piles[0]['base_amount'] = value

    def is_walkable(self):
        if self.ground_type == 'W':
            return False
        for p in self.piles:
            if p['structure'] in ['Clay', 'Wall', 'Tree', 'Log'] and p['base_amount'] == 0:
                return False
        return True

    def add_structure(self, structure, amount=1, base_amount=0):
        if amount <= 0: return False
        
        # 1. Check for collisions with DIFFERENT structures
        # (Não permite ocupar o mesmo espaço físico de outro tipo de objeto)
        for p in self.piles:
            if p['structure'] != structure:
                p_top = p['base_amount'] + p['amount']
                new_top = base_amount + amount
                # Se os intervalos de altura se sobrepõem
                if not (new_top <= p['base_amount'] or base_amount >= p_top):
                    return False # Colisão!
        
        # 2. Adiciona o novo segmento
        self.piles.append({'structure': structure, 'amount': amount, 'base_amount': base_amount})
        self.piles.sort(key=lambda x: x['base_amount'])
        
        # 3. Consolidação (Merging)
        # Junta segmentos do mesmo tipo que se tocam ou sobrepõem
        if not self.piles: return
        
        merged = []
        current = self.piles[0].copy()
        
        for i in range(1, len(self.piles)):
            nxt = self.piles[i]
            # Se tocam/sobrepõem e são do mesmo tipo
            if (nxt['structure'] == current['structure'] and 
                nxt['base_amount'] <= current['base_amount'] + current['amount']):
                
                new_top = max(current['base_amount'] + current['amount'], 
                              nxt['base_amount'] + nxt['amount'])
                current['amount'] = new_top - current['base_amount']
            else:
                merged.append(current)
                current = nxt.copy()
        
        merged.append(current)
        self.piles = merged
