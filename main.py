import json
import random
import os.path
from enum import Enum
from collections import deque
import logging
from typing import List

# setup logger
logging.basicConfig(level=logging.INFO, filename='game.log', filemode='w',
                    format='%(asctime)s %(levelname)s %(message)s')
# health constants
INITIAL_HEALTH = 5
HEAL_POINTS = 3
# map constants
INITIAL_PLAIN = [
    ['X', 'X', 'X', 'X', 'H', ' ', ' ', 'F'],
    ['X', 'X', 'K', 'X', 'X', ' ', 'X', 'X'],
    ['X', ' ', ' ', ' ', 'X', ' ', 'H', 'X'],
    [' ', ' ', 'X', ' ', ' ', ' ', 'X', 'X']
]


class Mark(Enum):
    BLOCKED = 'X'
    FREE = ' '
    PLAYER = 'P'
    KEY = 'K'
    HEAL = 'H'
    FINISH = 'F'
    # fire cell
    DANGER = 'D'


# for putting random fire on them
def find_white_cells(plain):
    cells = []
    for row in range(len(plain)):
        for col in range(len(plain[row])):
            if plain[row][col] == Mark.FREE.value:
                cells.append((row, col))
    return cells


WHITE_CELLS = find_white_cells(INITIAL_PLAIN)
FIRE_CELLS = 4
SPAWN_POINT = [3, 0]


# utility function that checks save file
def save_exists():
    return os.path.exists('save.json')


class Direction(Enum):
    w = [-1, 0]
    s = [1, 0]
    a = [0, -1]
    d = [0, 1]


class Key(Enum):
    YES = 'y'
    NO = 'n'
    UP = 'u'
    DOWN = 'd'
    LEFT = 'l'
    RIGHT = 'r'
    ATTACK = 'a'
    HEAL = 'h'
    SAVE = 's'


class Player:
    def __init__(self, name: str,
                 health: int = None,
                 has_key: bool = None,
                 current_pos: list = None,
                 previous_pos: list = None,
                 heal_points: int = None):
        self.name: str = name
        self.health: int = health if health is not None else INITIAL_HEALTH
        self.has_key: bool = has_key if has_key is not None else False
        self.current_pos: list = current_pos if current_pos is not None else SPAWN_POINT
        self.previous_pos: list = previous_pos if previous_pos is not None else None
        self.heal_points: int = heal_points if heal_points is not None else HEAL_POINTS

    @property
    def can_heal(self):
        return self.health < INITIAL_HEALTH and self.heal_points > 0

    def heal(self):
        self.health += 1
        self.heal_points -= 1

    def attack(self):
        self.health -= 1

    def restore_health(self):
        self.health = INITIAL_HEALTH

    def assign_key(self):
        self.has_key = True

    def drop_key(self):
        self.has_key = False

    def move(self, move):
        # assign value, not reference
        self.previous_pos = self.current_pos.copy()
        player_y, player_x = self.current_pos
        dy, dx = move
        self.current_pos = [player_y + dy, player_x + dx]


class Game:
    def __init__(self):
        self.queue = deque()
        self.plain = INITIAL_PLAIN

    def save(self):
        progress = {'plain': self.plain,
                    'queue': [p.__dict__ for p in self.queue]}
        try:
            with open('save.json', 'w') as f:
                json.dump(progress, f, indent=4)
        except IOError:
            # If the file doesn't exist, create it and write the save
            with open('save.json', 'w+') as f:
                json.dump(progress, f, indent=4)

    def load(self):
        with open('save.json', 'r') as f:
            progress = json.load(f)
        self.plain = progress['plain']
        self.queue = deque(Player(**player) for player in progress['queue'])

    def mark(self, mark: Mark, pos: list):
        self.plain[pos[0]][pos[1]] = mark.value

    def clear_mark(self, mark: Mark, each: bool = False):
        for row in range(len(self.plain)):
            for col in range(len(self.plain[row])):
                if self.plain[row][col] == mark.value:
                    self.plain[row][col] = Mark.FREE.value
                    if not each:
                        return

    def render(self):
        rows = [''.join(row) for row in self.plain]
        print('\n'.join(rows))

    def spawn_fire(self) -> List:
        fire_cells = random.sample(WHITE_CELLS, FIRE_CELLS)
        for cell in fire_cells:
            self.mark(Mark.DANGER, cell)
        return fire_cells

    def hit_wall(self, player: Player):
        p_y, p_x = player.current_pos
        if 0 <= p_y < len(self.plain) \
                and 0 <= p_x < len(self.plain[0]) \
                and self.plain[p_y][p_x] != Mark.BLOCKED:
            return
        player.attack()
        logging.info(f'{player.name} hit on the wall, - 1 HP')

    def step_on_fire(self, player: Player):
        p_y, p_x = player.current_pos
        if self.plain[p_y][p_x] == Mark.DANGER.value:
            player.attack()
            logging.info(f'{player.name} stepped on fire, - 1 HP')

    def step_on_heal_cell(self, player: Player):
        p_y, p_x = player.current_pos
        if self.plain[p_y][p_x] == Mark.HEAL.value:
            player.restore_health()
            logging.info(f'{player.name} health is restored, 5 HP / 5 HP')

    def is_step_back(self, player: Player, move: List):
        p_y, p_x = player.current_pos
        m_y, m_x = move
        next_pos = [p_y + m_y, p_x + m_x]
        if next_pos == player.previous_pos \
                and self.plain[p_y][p_x] not in [Mark.HEAL.value, Mark.KEY.value]:
            logging.info(f'{player.name} stepped back, kicked from the game')
            return True
        return False

    def step_on_key_cell(self, player: Player):
        p_y, p_x = player.current_pos
        if self.plain[p_y][p_x] == Mark.KEY.value:
            player.assign_key()
            self.clear_mark(Mark.KEY)
            logging.info(f'{player.name} picked a key')

    def start(self):
        num = int(input('Enter amount of players: '))
        for n in range(num):
            name = input(f'Enter {n + 1} players\'s name: ')
            player = Player(name=name)
            self.queue.append(player)
        self.next()

    def next(self):
        # spawn fire
        fire_cells = self.spawn_fire()
        logging.info(f'Fire spawned at coordinates: {", ".join(map(str, fire_cells))}')
        # take player from queue
        player = self.queue.popleft()
        # render map
        self.render()
        key = input(f'{player.name} turn: ')
        if key == Key.SAVE.value:
            # save is not counted as action, take player back to the queue
            self.queue.appendleft(player)
            self.save()
            logging.info(f'{player.name} saved game')
            self.next()
        # handle movement buttons
        elif key in [Key.UP.value, Key.DOWN.value, Key.LEFT.value, Key.RIGHT.value]:
            move = Direction[key].value
            if self.is_step_back(player, move):
                self.next()
            player.move(move)
            # check all cases
            self.hit_wall(player)
            self.step_on_fire(player)
            self.step_on_heal_cell(player)
            self.step_on_key_cell(player)

    def run(self):
        if save_exists():
            response = input('You have a safe file. Do you want to load it? (y/n)')
            if response == Key.YES.value:
                self.load()
                self.next()
        else:
            self.start()


game = Game()
game.run()
