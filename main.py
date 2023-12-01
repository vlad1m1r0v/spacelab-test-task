import logging
import os
import random
import json
import sys
from collections import deque
from typing import Deque

# setup logger
logging.basicConfig(level=logging.DEBUG,
                    filemode='w',
                    format='%(asctime)s %(levelname)s %(message)s',
                    datefmt='%d %b %Y')
# health constants
INITIAL_HEALTH = 5
HEAL_POINTS = 3
# map
INITIAL_PLAIN = [
    ['X', 'X', 'X', 'X', 'H', ' ', ' ', 'F'],
    ['X', 'X', 'K', 'X', 'X', ' ', 'X', 'X'],
    ['X', ' ', ' ', ' ', 'X', ' ', 'H', 'X'],
    [' ', ' ', 'X', ' ', ' ', ' ', 'X', 'X']
]
SPAWN_POINT = [3, 0]
# cell variables
BLOCKED = 'X'
FREE = ' '
KEY = 'K'
HEALTH = 'H'
FINISH = 'F'
# 'D' stands for Damage
FIRE = 'D'


def white_cells(plain):
    cells = []
    for row in range(len(plain)):
        for col in range(len(plain[row])):
            if plain[row][col] == FREE:
                cells.append((row, col))
    return cells


# for putting fire on them randomly
WHITE_CELLS = white_cells(INITIAL_PLAIN)
FIRE_AMOUNT = 4
# actions keys
YES = 'y'
NO = 'n'
SAVE = 's'
UP = 'u'
DOWN = 'd'
LEFT = 'l'
RIGHT = 'r'
HEAL = 'h'
TAKE = 't'
FIGHT = 'f'
# direction is key, vector is value
move: dict[str, list] = {
    UP: [-1, 0],
    DOWN: [1, 0],
    LEFT: [0, -1],
    RIGHT: [0, 1]
}


class Player:
    def __init__(self, name: str,
                 health: int = None,
                 has_key: bool = None,
                 cur: list = None,
                 prev: list = None,
                 hp: int = None):
        self.__name: str = name
        self.__health: int = health if health is not None else INITIAL_HEALTH
        self.__has_key: bool = has_key if has_key is not None else False
        self.__cur: list = cur if cur is not None else SPAWN_POINT
        self.__prev: list = prev
        self.__hp: int = hp if hp is not None else HEAL_POINTS

    @property
    def name(self):
        return self.__name

    @property
    def health(self):
        return self.__health

    @property
    def has_key(self):
        return self.__has_key

    @property
    def cur(self):
        return self.__cur.copy()

    @property
    def prev(self):
        if isinstance(self.__prev, list):
            return self.__prev.copy()
        return None

    @property
    def hp(self):
        return self.__hp

    @property
    def can_heal(self):
        return self.__hp > 0 and self.__health < INITIAL_HEALTH

    @property
    def is_alive(self):
        return self.__health > 0

    def assign_key(self):
        self.__has_key = True

    def drop_key(self):
        self.__has_key = False

    def receive_damage(self):
        self.__health -= 1

    def restore_health(self):
        self.__health = INITIAL_HEALTH

    def heal(self):
        self.__health += 1
        self.__hp -= 1

    def is_step_back(self, dydx: list):
        py, px = self.cur
        dy, dx = dydx
        return self.prev == [py + dy, px + dx]

    def move(self, dydx: list):
        self.__prev = self.cur
        py, px = self.cur
        dy, dx = dydx
        self.__cur = [py + dy, px + dx]


class GameMap:
    def __init__(self, plain: list[list] = None):
        self.__plain = plain if plain is not None else INITIAL_PLAIN

    @property
    def plain(self):
        return self.__plain

    # for fire and key
    def __mark_cell(self, pos: list, cell: str):
        self.__plain[pos[0]][pos[1]] = cell

    # many for fire, once for key
    def __clear_cell(self, cell: str, many: bool = False):
        for row in range(len(self.__plain)):
            for col in range(len(self.__plain[row])):
                if self.__plain[row][col] == cell:
                    self.__plain[row][col] = FREE
                    if not many:
                        return

    def spawn_fire(self):
        fire_cells = random.sample(WHITE_CELLS, FIRE_AMOUNT)
        for cell in fire_cells:
            self.__mark_cell(cell, FIRE)
        logging.info(f'Fire spawned at cells {", ".join(map(str, fire_cells))}')

    def clear_fire(self):
        self.__clear_cell(cell=FIRE, many=True)

    def spawn_key(self, pos: list):
        self.__mark_cell(pos, KEY)

    def clear_key(self):
        self.__clear_cell(KEY)

    def is_fire(self, pos: list) -> bool:
        return self.__plain[pos[0]][pos[1]] == FIRE

    def is_heal(self, pos: list) -> bool:
        return self.__plain[pos[0]][pos[1]] == HEALTH

    def is_key(self, pos: list) -> bool:
        return self.__plain[pos[0]][pos[1]] == KEY

    def is_heal_or_key(self, pos: list) -> bool:
        return self.__plain[pos[0]][pos[1]] in [KEY, HEAL]

    def is_finish(self, pos: list):
        return self.__plain[pos[0]][pos[1]] == FINISH

    def is_valid_move(self, dydx: list, p: Player):
        dy, dx = dydx
        py, px = p.cur
        pos_y, pos_x = py + dy, px + dx
        is_inside_map = 0 <= pos_y < len(self.__plain) and 0 <= pos_x < len(self.plain[0])
        if not is_inside_map:
            return is_inside_map
        return self.__plain[pos_y][pos_x] != BLOCKED


class SaveManager:
    @staticmethod
    def save_exists():
        return os.path.exists('save.json')

    @staticmethod
    def save(q: Deque[Player], gm: GameMap):
        data = {
            'queue': [{
                'name': p.name,
                'health': p.health,
                'has_key': p.has_key,
                'cur': p.cur,
                'prev': p.prev,
                'hp': p.hp
            } for p in q],
            'map': gm.plain
        }
        try:
            with open('save.json', 'w') as f:
                json.dump(data, f, indent=4)
        except IOError:
            # If the file doesn't exist, create it and write the save
            with open('save.json', 'w+') as f:
                json.dump(data, f, indent=4)

    @staticmethod
    def load():
        with open('save.json', 'r') as f:
            data = json.load(f)
        return {
            'map': GameMap(plain=data['map']),
            'queue': deque(Player(**p) for p in data['queue'])
        }


class Game:
    def __init__(self):
        self.__queue = deque()
        self.__map = GameMap()

    def __load(self):
        data = SaveManager.load()
        self.__queue = data['queue']
        self.__map = data['map']

    def __handle_save(self, p: Player):
        # save is not counted as action, push player back
        # to the start of the queue and let him repeat action
        self.__queue.append(p)
        SaveManager.save(self.__queue, self.__map)
        logging.info(f'{p.name} saved a game')
        self.__action()

    def __drop_key_and_kick_after_death(self, p: Player):
        if p.has_key:
            p.drop_key()
            self.__map.spawn_key(p.cur)
        if p in self.__queue:
            self.__queue.remove(p)
        logging.info(f'{p.name} died: kicked from the game')

    def __check_hit_wall(self, dydx: list, p: Player):
        if self.__map.is_valid_move(dydx=dydx, p=p):
            return
        p.receive_damage()
        logging.info(f'{p.name} hit the wall: {p.health} health')
        if not p.is_alive:
            self.__drop_key_and_kick_after_death(p)
            self.__action()
        self.__queue.appendleft(p)
        self.__action()

    def __check_step_back(self, dydx: list, p: Player):
        if p.is_step_back(dydx) and not self.__map.is_heal_or_key(p.cur):
            logging.info(f'{p.name} stepped back: kicked from the game')
            self.__action()

    def __check_other_players_on_cell(self, p: Player):
        present_names = [other.name for other in self.__queue if other.cur == p.cur]
        if len(present_names):
            logging.info('Other players present on cell: {p}'.format(p=', '.join(present_names)))

    def __check_step_on_fire(self, p: Player):
        if self.__map.is_fire(p.cur):
            p.receive_damage()
            logging.info(f'{p.name} stepped on fire: {p.health} health')
            if not p.is_alive:
                self.__drop_key_and_kick_after_death(p)
                self.__action()
            self.__queue.appendleft(p)
            self.__action()

    def __check_cell_has_key(self, p: Player):
        if self.__map.is_key(p.cur):
            logging.info(f'Cell {p.cur} has key')
            self.__queue.appendleft(p)
            self.__action()

    def __check_cell_is_heal(self, p: Player):
        if self.__map.is_heal(p.cur):
            p.restore_health()
            logging.info(f'{p.name} restored health: {p.health} health')
            self.__queue.appendleft(p)
            self.__action()

    def __check_finish(self, p: Player):
        if self.__map.is_finish(p.cur):
            if p.has_key:
                logging.info(f'{p.name} won')
                sys.exit()
            else:
                logging.info(f'{p.name} came to the finish without key')
                self.__drop_key_and_kick_after_death(p)
                self.__action()

    def __handle_move(self, key: str, p: Player):
        dydx = move[key]
        self.__check_hit_wall(dydx=dydx, p=p)
        self.__check_step_back(dydx=dydx, p=p)
        p.move(dydx)
        logging.info(f'{p.name} new position: {str(p.cur)}')
        self.__check_other_players_on_cell(p)
        self.__check_step_on_fire(p)
        self.__check_cell_has_key(p)
        self.__check_cell_is_heal(p)
        self.__check_finish(p)
        self.__queue.appendleft(p)
        self.__action()

    def __handle_heal(self, p: Player):
        if p.can_heal:
            p.heal()
            logging.info(f'{p.name} healed himself: {p.health} health')
            self.__queue.appendleft(p)
            self.__action()
        else:
            logging.info(f'{p.name} should either have max health or have no HP')
            self.__queue.append(p)
            self.__action()

    def __handle_key(self, p: Player):
        if self.__map.is_key(p.cur):
            p.assign_key()
            self.__map.clear_key()
            logging.info(f'{p.name} took key')
            self.__queue.appendleft(p)
            self.__action()
        else:
            logging.info(f'There is no key in current position')
            self.__queue.append(p)
            self.__action()

    def __handle_fight(self, p: Player):
        # can't delete elements in queue while iterate through it,
        # so we store killed players in array and kick them after loop
        killed = []
        for player in self.__queue:
            if player.cur == p.cur:
                player.receive_damage()
                logging.info(f'{player.name} received damage from {p.name}: {player.health} health left')
                if not player.is_alive:
                    killed.append(player)
        for k in killed:
            self.__drop_key_and_kick_after_death(k)
        self.__queue.appendleft(p)
        self.__action()

    def __action(self):
        # if no players left
        if len(self.__queue) == 0:
            logging.info('No players left: game is over')
            sys.exit()
        # clear previously generated fire cells
        self.__map.clear_fire()
        # before each action spawn fire
        self.__map.spawn_fire()
        # pop player from queue
        player = self.__queue.pop()
        key = input(f'\n{player.name} turn: ')
        if key == SAVE:
            self.__handle_save(player)
        elif key in [UP, DOWN, LEFT, RIGHT]:
            self.__handle_move(key=key, p=player)
        elif key == HEAL:
            self.__handle_heal(player)
        elif key == TAKE:
            self.__handle_key(player)
        elif key == FIGHT:
            self.__handle_fight(player)
        else:
            logging.info('Invalid key: try again')
            self.__queue.append(player)
            self.__action()

    def __start(self):
        num = int(input('Enter amount of players: '))
        for n in range(num):
            name = input(f'Enter {n + 1} players\'s name: ')
            player = Player(name=name)
            self.__queue.appendleft(player)
        self.__action()

    def run(self):
        if SaveManager.save_exists():
            answer = input('You have a safe file. Do you want to load it? (y/n)')
            if answer == YES:
                self.__load()
                self.__action()
        self.__start()


game = Game()
game.run()
