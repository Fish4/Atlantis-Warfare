#!/usr/bin/python

import math, copy, random, sys
from collections import deque
import direct.directbase.DirectStart
from panda3d.core import Fog, TextureStage
from direct.showbase.DirectObject import DirectObject
from direct.interval.IntervalGlobal import *
from pandac.PandaModules import BitMask32, GeomNode, VBase4, NodePath, Point2, Point3, CardMaker, TransparencyAttrib, CompassEffect
#Imports for rain
import uuid
from pandac.PandaModules import LineSegs
from panda3d.core import Vec4
from pandac.PandaModules import CollisionNode, CollisionSphere, CollisionHandler

##################################################
#                                                #
#      global variables                          #
#                                                #
##################################################

TURNS_TO_WIN = 2
HEX_DIAM = 10
BOARD_X = 11
BOARD_Y = 11
SQRT_3 = math.sqrt(3)
RAD_TO_DEG = 180.0 / math.pi
DEG_TO_RAD = 1.0 / RAD_TO_DEG
# tan(INTERIOR_ANGLE / 2) * sin(IDEAL_AZIMUTH) == 1
IDEAL_AZIMUTH = math.asin(1.0 / math.tan(60.0 * DEG_TO_RAD)) * RAD_TO_DEG

###################################################
#                                                 #
#     Utility function to calculate objects       #
#                                                 #
###################################################


# giving x,y,z return the board'x and board'y and z
def board_coordinates(x, y, z):
    board_x = 0.75 * HEX_DIAM * x
    board_y = HEX_DIAM * SQRT_3 / 2 * y + (x % 2 * 0.5 * HEX_DIAM * SQRT_3 / 2)
    return (board_x, board_y, z)


# return all adjacent tiles?
def get_adjacent(terrain, x, y):
    if x % 2 == 0:
        coords = [(x - 1, y), (x, y + 1), (x + 1, y), (x + 1, y - 1), (x, y - 1), (x - 1, y - 1)]
    else:
        coords = [(x - 1, y + 1), (x, y + 1), (x + 1, y + 1), (x + 1, y), (x, y - 1), (x - 1, y)]
    adjacent = []
    for coord in coords:
        if coord[0] < 0 or coord[1] < 0:
            continue
        elif coord[0] >= terrain.size_x or coord[1] >= terrain.size_y:
            continue
        else:
            adjacent.append(terrain.rows[coord[0]][coord[1]])
    return adjacent


# get distance between tile1 and tile 2
def tile_distance_squared(tile1, tile2):
    (x1, y1, z1) = board_coordinates(tile1.x, tile1.y, 0)
    (x2, y2, z2) = board_coordinates(tile2.x, tile2.y, 0)
    vector = Point2(x1, y1) - Point2(x2, y2)
    return vector.lengthSquared()


def find_nearby(terrain, x, y, distance):
    # using bfs to search within movement range and non obstacles
    dist = 0
    # this is basically close list
    nearby = []
    openlist = deque([])
    currentTile = terrain.getTile(x, y)
    currentTile.dist = dist
    openlist.append(currentTile)
    nearby.append(currentTile)
    while openlist:
        currentTile = openlist.popleft()
        if currentTile.dist >= distance:
            break
        else:
            neighbors = get_adjacent(terrain, currentTile.x, currentTile.y)
            for n in neighbors:
                if n.material == 'obstacle':
                    continue
                if n in nearby:
                    continue
                else:
                    n.dist = currentTile.dist + 1
                    openlist.append(n)
                    nearby.append(n)
    for tile in openlist:
        tile.dist = 0
    return nearby


def find_vision(terrain, x, y, distance):
    # using bfs to search within movement range and non obstacles
    dist = 0
    # this is basically close list
    nearby = []
    openlist = deque([])
    currentTile = terrain.getTile(x, y)
    currentTile.dist = dist
    openlist.append(currentTile)
    nearby.append(currentTile)
    while openlist:
        currentTile = openlist.popleft()
        if currentTile.dist >= distance:
            break
        else:
            neighbors = get_adjacent(terrain, currentTile.x, currentTile.y)
            for n in neighbors:
                if n.material == 'obstacle':
                    continue
                if n in nearby:
                    continue
                if n.height > currentTile.height:
                    n.dist = currentTile.dist + 2
                    if n.dist <= distance:
                        openlist.append(n)
                        nearby.append(n)
                    else:
                        continue
                else:
                    n.dist = currentTile.dist + 1
                    openlist.append(n)
                    nearby.append(n)
    for tile in openlist:
        tile.dist = 0
    return nearby


def HexPathFinding(terrain, start, end):
    dist = 0
    openlist = deque([])
    closelist = deque([])
    path = deque([])
    currentTile = terrain.getTile(end.x, end.y)
    currentTile.dist = dist
    openlist.append(currentTile)
    closelist.append(currentTile)
    while openlist:
        currentTile = openlist.popleft()
        if currentTile == terrain.getTile(start.x, start.y):
            break
        else:
            neighbors = get_adjacent(terrain, currentTile.x, currentTile.y)
            for n in neighbors:
                if n.material == 'obstacle':
                    continue
                elif n in closelist:
                    continue
                else:
                    n.dist = currentTile.dist + 1
                    openlist.append(n)
                    closelist.append(n)
    path.append(currentTile)
    while currentTile != end:
        neighbors = get_adjacent(terrain, currentTile.x, currentTile.y)
        for neighbor in neighbors:
            if neighbor.dist == currentTile.dist - 1 and neighbor in closelist:
                path.append(neighbor)
                currentTile = neighbor
                break
    path.append(end)
    return path


###################################################
#                                                 #
#     Mouse Class                                 #
#                                                 #
###################################################


# a Mouse class handles all mouse input
class Mouse(DirectObject):
    def __init__(self, app):
        # local variables for mouse class
        self.app = app
        self.init_collide()
        self.has_mouse = None
        self.prev_pos = None
        self.pos = None
        self.drag_start = None
        self.hovered_object = None
        self.button2 = False
        self.mouseTask = taskMgr.add(self.mouse_task, 'mouseTask')
        self.task = None
        # set up event and response to this event
        self.accept('mouse1', self.mouse1)
        self.accept('mouse1-up', self.mouse1_up)
        # change the mouse to accept 'right-click' to rotate camera
        self.accept('mouse3', self.rotateCamera)
        self.accept('mouse3-up', self.stopCamera)
        self.accept('wheel_up', self.zoomIn)
        self.accept('wheel_down', self.zoomOut)

    # set up the collision for object
    def init_collide(self):
        # why the heck he import within method
        from pandac.PandaModules import CollisionTraverser, CollisionNode
        from pandac.PandaModules import CollisionHandlerQueue, CollisionRay
        # init and import collision for object
        self.cTrav = CollisionTraverser('MousePointer')
        self.cQueue = CollisionHandlerQueue()
        self.cNode = CollisionNode('MousePointer')
        self.cNodePath = base.camera.attachNewNode(self.cNode)
        self.cNode.setFromCollideMask(GeomNode.getDefaultCollideMask())
        self.cRay = CollisionRay()
        self.cNode.addSolid(self.cRay)
        self.cTrav.addCollider(self.cNodePath, self.cQueue)

    # by the collision methods mouse is able to find out which tile mouse is at
    def find_object(self):
        if self.app.world.nodePath:
            self.cRay.setFromLens(base.camNode, self.pos.getX(), self.pos.getY())
            self.cTrav.traverse(self.app.world.terrain.nodePath)
            if self.cQueue.getNumEntries() > 0:
                self.cQueue.sortEntries()
                return self.cQueue.getEntry(0).getIntoNodePath()
        return None

    # setting task for mouse
    def mouse_task(self, task):
        action = task.cont
        # if the current tile has a mouse point to this
        self.has_mouse = base.mouseWatcherNode.hasMouse()
        if self.has_mouse:
            self.pos = base.mouseWatcherNode.getMouse()
            if self.prev_pos:
                self.delta = self.pos - self.prev_pos
            else:
                self.delta = None
            if self.task:
                action = self.task(task)
        else:
            self.pos = None
        if self.pos:
            self.prev_pos = Point2(self.pos.getX(), self.pos.getY())
        return action

    # when mouse hover over this hexagon
    def hover(self, task):
        if self.hovered_object:
            self.hovered_object.unhover()
            self.hovered_object = None
        if self.button2:
            self.camera_drag()
        hovered_nodePath = self.find_object()
        if hovered_nodePath:
            tile = hovered_nodePath.findNetTag('tile')
            if not tile.isEmpty():
                tag = tile.getTag('tile')
                coords = tag.split(',')
                (x, y) = [int(n) for n in coords]
                # set the hovered target to be the corresponding hexagon on terrain
                self.hovered_object = self.app.world.terrain.rows[x][y]
                self.hovered_object.hover()
            character = hovered_nodePath.findNetTag('char')
            if not character.isEmpty():
                tag = character.getTag('char')
                (team_index, char_id) = [int(n) for n in tag.split(',')]
                self.hovered_object = self.app.world.teams[team_index].characters_dict[char_id]
                self.hovered_object.hover()
            ghost = hovered_nodePath.findNetTag('ghost')
            if not ghost.isEmpty():
                tag = ghost.getTag('ghost')
                (team_index, char_id) = [int(n) for n in tag.split(',')]
                for ghostInstance in self.app.ghosts:
                    if (ghostInstance.team.index == team_index) and (ghostInstance.id == char_id):
                        self.hovered_object = ghostInstance
                self.hovered_object.hover()
        return task.cont

    def mouse1(self):
        self.app.state.request('mouse1')

    def mouse1_up(self):
        self.app.state.request('mouse1-up')

    def camera_drag(self):
        if self.delta:
            old_heading = base.camera.getH()
            new_heading = old_heading - self.delta.getX() * 180
            base.camera.setH(new_heading % 360)
            old_pitch = base.camera.getP()
            new_pitch = old_pitch + self.delta.getY() * 90
            new_pitch = max(-90, min(-10, new_pitch))
            base.camera.setP(new_pitch)

    def rotateCamera(self):
        self.button2 = True

    def stopCamera(self):
        self.button2 = False

    def zoomIn(self):
        lens = base.cam.node().getLens()
        size = lens.getFilmSize()
        if size.length() >= 75:
            lens.setFilmSize(size / 1.2)

    def zoomOut(self):
        lens = base.cam.node().getLens()
        size = lens.getFilmSize()
        if size.length() <= 250:
            lens.setFilmSize(size * 1.2)

###################################################
#                                                 #
#     Team class                                  #
#                                                 #
###################################################


# Team class same as player class
class Team(DirectObject):
    def __init__(self, world, index, name, color):
        # local variables
        self.world = world
        self.index = index
        self.name = name
        self.color = color
        self.characters = []
        self.characters_dict = {}
        # teammatesDone is to be used in turnManager to check if the entire team is done with its turn
        self.teammatesDone = 0
        self.TurnsToWin = TURNS_TO_WIN
        self.completing_objective = False

        #resets the turns of the characters in the team allow for their next turn
    def reset_turns(self):
        for character in self.characters:
            character.turn = True

    def check_completing_objective(self):
        counter = 0
        for character in self.characters:
            # if there is somebody on the objective tile who has not been hit, and sombody from the same team was on the tile last, then decrement turns left
            if character.terrain.getTile(character.x, character.y).material == 'objective' and not character.attacked and self.completing_objective:
                self.TurnsToWin -= 1
                counter += 1
                character.terrain.getTile(character.x, character.y).nodePath.setColor(VBase4(1, 0, 0, 1))
            elif character.terrain.getTile(character.x, character.y).material == 'objective':
                character.terrain.getTile(character.x, character.y).nodePath.setColor(VBase4(0, 0, 1, 1))
                self.completing_objective = True
                self.TurnsToWin = TURNS_TO_WIN
                counter += 1
        # if code has arrived here, then nobody is on the ohjective tile
        if counter <= 0:
            self.TurnsToWin = TURNS_TO_WIN
            self.completing_objective = False

    # add a character to this team and increment teamSize
    def add_character(self, x, y):
        # define character id as random integer
        character_id = random.randint(0, 15)
        # if character id is already defined before, then randomly find another another integer
        # TODO: fix this random integer only check within the team
        while self.characters_dict.has_key(character_id):
            character_id = random.randint(0, 15)
        char = Character(self.world.terrain, self, character_id, x, y)
        print char.id
        self.characters.append(char)
        self.characters_dict[character_id] = char
        return char

    # using character id to remove a character from this team and decrement teamSize
    def delete_character(self, character_id):
        for i, char in enumerate(self.characters):
            if char == self.characters_dict[character_id]:
                char.nodePath.removeNode()
                del self.characters[i]
        del self.characters_dict[character_id]

###################################################
#                                                 #
#     Character class                             #
#                                                 #
###################################################


# character class
class Character(DirectObject):
    def __init__(self, terrain, team, id, x, y, ghost=False):
        self.terrain = terrain
        self.team = team
        self.id = id
        self.x = x
        self.y = y
        self.hp = 1.0
        self.is_dead = False
        self.tile = self.terrain.rows[x][y]
        self.height = self.tile.height
        self.color = self.team.color
        self.pending_action = None
        self.nodePath = None
        self.turn = True
        self.rotated = False
        self.ghost = ghost
        self.frontTile = None
        self.attacked = False
        self.path = None
        self.simulatedTile = None

    #sets the model, raparents, sets position, and sets tag
    def init_nodepath(self):
        self.nodePath = loader.loadModel('models/character')  # load model to this class
        self.nodePath.reparentTo(self.terrain.nodePath)       # parent to terrain
        self.nodePath.setColor(VBase4(*self.color))           # set color to same as team color
        (pos_x, pos_y, pos_z) = board_coordinates(self.x, self.y, self.height)
        self.nodePath.setPos(pos_x, pos_y, pos_z)
        self.nodePath.setScale(5, 5, 5)
        # self.frontTile = app.world.terrain.getTile(pos_x + 1, pos_y)
        # self.rotate()
        if self.ghost:
            self.nodePath.setTransparency(1)
            self.nodePath.setAlphaScale(0.5)
            self.nodePath.setTag('ghost', '%u,%u' % (self.team.index, self.id))
        else:
            self.nodePath.setTag('char', '%u,%u' % (self.team.index, self.id))

    def init_healthBar(self):
        self.bar = Bar()
        self.bar.reparentTo(self.nodePath)
        self.bar.setPos(0, 0, 1.8)
        self.bar.setBillboardPointEye()

    # move the character to the tile
    def move_to(self, tile):
        self.tile = tile
        (self.x, self.y, self.height) = (tile.x, tile.y, tile.height)
        (pos_x, pos_y, pos_z) = board_coordinates(self.x, self.y, self.height)
        self.nodePath.setPos(pos_x, pos_y, pos_z)

    # when character got a mouse over on him, change it's color
    def hover(self):
        color = self.nodePath.getColor() * 1.5
        self.nodePath.setColor(color)

    # returns character to original color
    def unhover(self):
        color = self.nodePath.getColor() / 1.5
        self.nodePath.setColor(color)

    def set_action(self, action):
        self.pending_action = action

        #moves the character and rotates them as well
    def do_action(self):
        if(self.pending_action is not None):
            self.pending_action.do()
        self.pending_action = None
        self.turn = False
        self.team.teammatesDone = self.team.teammatesDone + 1

    # reduce hp when get hit
    def damage(self, damage):
        self.hp -= damage
        self.bar.setValue(self.hp)

    # check hp is less 0
    def should_die(self):
        return bool(self.hp <= 0.01)

    def die(self):
        self.is_dead = True
        self.nodePath.removeNode()

        #rotates this character
    def rotate(self):
        self.nodePath.lookAt(self.frontTile.nodePath)
        self.nodePath.setP(0)

    #sets the front tile and sets rotated to true
    def setRotation(self, tile):
        self.rotated = True
        self.frontTile = tile

    # possibly a unimplement method for FSM
    def __getstate__(self):
        safe_dict = self.__dict__.copy()
        safe_dict['nodePath'] = None
        return safe_dict

    def __setstate__(self, safe_dict):
        self.__dict__.update(safe_dict)


#########################
#                       #
#       Bar class       #
#                       #
#########################

class Bar(NodePath):
                            #change scale to change health bar size
        def __init__(self, scale=1.2):
                NodePath.__init__(self, 'healthbar')

                self.scale = scale
                cmfg = CardMaker('fg')
                cmfg.setFrame(- scale,  scale, -0.1 * scale, 0.1 * scale)
                self.fg = self.attachNewNode(cmfg.generate())

                cmbg = CardMaker('bg')
                cmbg.setFrame(- scale, scale, -0.1 * scale, 0.1 * scale)
                self.bg = self.attachNewNode(cmbg.generate())

                #cmbd = CardMaker('bd')
                #cmbd.setFrame(- scale * 1.3, scale * 1.3, -.2 * scale, .2 * scale)
                #self.bd = self.attachNewNode(cmbd.generate())

                self.fg.setColor(1, 0, 0, 1)
                self.bg.setColor(0.2, 0.2, 0.2, 1)

                self.setValue(1)

                        # set a value between 0 and 1 to indicate the health
        def setValue(self, value):
                value = min(max(0, value), 1)
                self.health = value
                self.fg.setScale(value * self.scale, 0.001, self.scale)
                self.bg.setScale(self.scale * (1.001 - value), 0.001, self.scale)
#                self.bd.setScale(self.scale * (1.1 - value), 0.001, self.scale)
                self.fg.setX((value - .999) * self.scale * self.scale)
                self.bg.setX(value * self.scale * self.scale)

###################################################
#                                                 #
#     Tile class                                  #
#                                                 #
###################################################


# tile class
class Tile(DirectObject):
    def __init__(self, terrain, material, x, y, height):
        # local variable
        self.terrain = terrain
        self.material = material
        self.x = x
        self.y = y
        self.height = height
        self.adjacent = []
        self.nodePath = None
        self.dist = 0
        self.reached = False

    def init_nodepath(self):
        self.nodePath = self.terrain.nodePath.attachNewNode('tile')
        cyl = loader.loadModel('models/tile-cyl')
        cyl.reparentTo(self.nodePath)    # side view of tile
        cap = loader.loadModel('models/tile-side')
        cap.reparentTo(self.nodePath)    # top view of tile
        cap2 = loader.loadModel('models/tile-cap')
        cap2.reparentTo(self.nodePath)    # top view of tile
        # for each different material print it as different color
        if self.material == 'grass':
            new_color = VBase4(0, .7, 0, 1.0)
        elif self.material == 'stone':
            new_color = VBase4(.9, .9, .9, 1.0)
        if self.material == 'objective':
            new_color = VBase4(0.7, 0.7, 0.7, 1.0)
        if self.material == 'obstacle':
            new_color = VBase4(0.7, 0.7, 0.3, 1.0)
        self.nodePath.setColor(new_color)
        (pos_x, pos_y, pos_z) = board_coordinates(self.x, self.y, 0)
        self.nodePath.setPos(pos_x, pos_y, pos_z)
        self.set_height(self.height)
        self.nodePath.setTag('tile', '%u,%u' % (self.x, self.y))

    # when mouse over this tile, change the color to be lighter
    def hover(self):
        self.terrain.hoveredTile = self
        color = self.nodePath.getColor() * 1.5
        self.nodePath.setColor(color)

    # when mouse move away, change the color back
    def unhover(self):
        self.terrain.hoveredTile = None
        color = self.nodePath.getColor() / 1.5
        self.nodePath.setColor(color)

    # draw the tile according to the height
    def set_height(self, new_height):
        self.height = round(new_height / 2.0) * 2
        self.nodePath.find('**/tile-cyl.egg').setSz(self.height)
        self.nodePath.find('**/tile-side.egg').setZ(self.height - 1.0)
        self.nodePath.find('**/tile-cap.egg').setZ(self.height - 1.0)

    # when this tile get selected, mark it at terrain
    def select(self):
        self.terrain.selectedTile = self

    # when not selected, remove the mark
    def unselect(self):
        self.terrain.selectedTile = None

    # a method to change meterail, for the edit.py
    def change_material(self, new_material):
        self.material = new_material
        if self.material == 'grass':
            new_color = VBase4(0, .7, 0, 1.0)
        elif self.material == 'stone':
            new_color = VBase4(.5, .5, .5, 1.0)
        if self.material == 'objective':
            new_color = VBase4(0.7, 0.7, 0.7, 1.0)
        if self.material == 'obstacle':
            new_color = VBase4(0.7, 0.7, 0.3, 1.0)
        if self.terrain.hoveredTile == self:
            new_color *= 1.5
        self.nodePath.setColor(new_color)

    # calculate all the characters that is on the tile
    def get_inhabitants(self):
        characters = []
        for team in self.terrain.world.teams:
            for character in team.characters:
                if character.is_dead:
                    continue
                    #how many characters can even be in a tile?
                if (character.x, character.y) == (self.x, self.y):
                    characters.append(character)
        return characters

    # unimplement for FSM
    def __getstate__(self):
        safe_dict = self.__dict__.copy()
        safe_dict['nodePath'] = None
        safe_dict['adjacent'] = []
        return safe_dict

    def __setstate__(self, safe_dict):
        self.__dict__.update(safe_dict)

###################################################
#                                                 #
#     Terrain class                               #
#                                                 #
###################################################


# terrain class (map class)
class Terrain(DirectObject):
    def __init__(self, world):
        self.world = world
        self.rows = []
        self.hoveredTile = None
        self.selectedTile = None
        self.size_x = BOARD_X
        self.size_y = BOARD_Y
        self.nodePath = None

    def init_nodepath(self):
        # attach the terrain under world
        self.nodePath = self.world.nodePath.attachNewNode('Terrain')
        for row in self.rows:
            for tile in row:
                tile.init_nodepath()

    # generate the entire new map
    def generate(self):
        for x in range(self.size_x):
            row = []
            for y in range(self.size_y):
                material = 'grass'
                height = 2
                tile = Tile(self, material, x, y, height)
                row.append(tile)
            self.rows.append(row)
        for x in range(self.size_x):
            for y in range(self.size_y):
                self.rows[x][y].adjacent = get_adjacent(self, x, y)

    def getTile(self, x, y):
        return self.rows[x][y]

    # unimplement method for FSM
    def __getstate__(self):
        safe_dict = self.__dict__.copy()
        safe_dict['hoveredTile'] = None
        safe_dict['selectedTile'] = None
        safe_dict['nodePath'] = None
        return safe_dict

    def __setstate__(self, safe_dict):
        self.__dict__.update(safe_dict)
        for x in range(self.size_x):
            for y in range(self.size_y):
                self.rows[x][y].adjacent = get_adjacent(self, x, y)

###################################################
#                                                 #
#     World class                                 #
#                                                 #
###################################################


# world class
class World(DirectObject):
    def __init__(self):
        # base.setBackgroundColor(0.2, 0.2, 0.6)

        # create all the tiles on map
        self.init_terrain()
        # create all the players in team
        self.init_teams()
        self.position_camera()
        self.nodePath = None

    def init_nodepath(self):


        # Load the environment model.
        self.environ = loader.loadModel("models/env03")

        # water
        self.water = loader.loadModel('models/square')
        self.water.setSx(400*2)
        self.water.setSy(400*2)
        self.water.setPos(0, 80, -1)  # sea level
        self.water.setTransparency(TransparencyAttrib.MAlpha)
        newTS = TextureStage('1')
        self.water.setTexture(newTS, loader.loadTexture('models/water.png'))
        self.water.setTexScale(newTS, 4)
        self.water.reparentTo(render)
        LerpTexOffsetInterval(self.water, 50, (1, 0), (0, 0), textureStage=newTS).loop()

        # Our sky
        self.skysphere = loader.loadModel('models/blue-sky-sphere')
        self.skysphere.setEffect(CompassEffect.make(render))
        self.skysphere.setScale(0.05)

        # NOT render or you'll fly through the sky!:
        self.skysphere.reparentTo(base.camera)

        # Reparent the model to render.
        self.environ.reparentTo(render)

        # Apply scale and position transforms on the model.
        self.environ.setScale(1, 1, 1)
        self.environ.setPos(37, 48, 0)
        self.environ.setHpr(270, 0, 0)
        self.environ.setTwoSided(True)

        # fog
        colour = (0.1, 0.1, 0.1)
        expfog = Fog("scene-wide-fog")
        expfog.setColor(*colour)
        expfog.setExpDensity(0.01)
        render.setFog(expfog)

        # Set Rain Boundaries
        mapCollision = CollisionNode('mapcnode')
        mapCollision.setTag('INTO', 'map')

        self.pt1, self.pt2 = self.environ.getTightBounds()
        self.deltaX = self.pt2.x - self.pt1.x
        self.deltaY = self.pt2.y - self.pt1.y
        self.deltaZ = 1000

        # Set up rain effect initialization
        self.spawnEveryXSeconds = .001
        self.spawnXDrops = 4
        self.dropDuration = .2
        self.percentChanceOfImpactCircle = .8
        self.percentChanceOfImpactFog = .5
        self.percentChanceOfDoubleDrop = .8
        self.percentChanceOfTripleDrop = .2

        # base.setBackgroundColor(*colour)

        self.nodePath = render.attachNewNode('World')
        self.init_lights()
        self.init_camera()
        self.terrain.init_nodepath()
        for team in self.teams:
            for character in team.characters:
                character.init_nodepath()

        # create rain
        taskMgr.doMethodLater(0, self.makeItRain, 'make-it-rain')

    def makeItRain(self, task=None):
        task.delayTime = self.spawnEveryXSeconds
        for i in range(0, self.spawnXDrops, 1):
            self.x = random.uniform(self.pt1.x, self.pt2.x)
            self.y = random.uniform(self.pt1.y, self.pt2.y)
            self.doubleDrop = False
            self.tripleDrop = False
            if (1-self.percentChanceOfDoubleDrop) <= random.random():
                self.doubleDrop = True
                if (1-self.percentChanceOfTripleDrop) <= random.random():
                    self.tripleDrop = True
            self.createRainDrop(self.x, self.y, self.doubleDrop, self.tripleDrop)
        return task.again

    def createRainDrop(self, x=0, y=0, doubleDrop=False, tripleDrop=False):
        # Set up line geometry for rain.
        id = str(uuid.uuid4())
        dummy = NodePath('dummy'+id)
        lineSegs = LineSegs('line'+id)
        if self.tripleDrop:
            lineSegs.setThickness(3.0)
        elif self.doubleDrop:
            lineSegs.setThickness(2.0)
        else:
            lineSegs.setThickness(1.0)
        lineSegs.moveTo(0, 0, 0)
        lineSegs.drawTo(0, 0, self.deltaZ*.1)
        lineGeomNode = lineSegs.create()
        # True: gray; False: white and red.
        if True:
            lineSegs.setVertexColor(0, Vec4(1, 1, 1, .4))
            lineSegs.setVertexColor(1, Vec4(.3, .3, .3, 0))
            pass
        else:
            lineSegs.setVertexColor(0, Vec4(1, 1, 1, .4))
            lineSegs.setVertexColor(1, Vec4(1, 0, 0, 1))
        linePath = dummy.attachNewNode(lineGeomNode)
        linePath.setTransparency(True)
        linePath.reparentTo(render)
        # Add collision node with 'FROM' tag = 'rain'
        pickerNode = CollisionNode('linecnode'+id)
        pickerNode.setTag('FROM', 'rain')
        rayCollider = linePath.attachNewNode(pickerNode)
        # A small collision sphere is attached to the bottom of each rain drop.
        rayCollider.node().addSolid(CollisionSphere(0, 0, 0, .25))
        #base.cTrav.addCollider(rayCollider, collisionHandler)
        # Sequence rain
        Sequence(
            LerpPosInterval(linePath, self.dropDuration, Point3(x, y, self.pt1.z), Point3(x, y, self.pt2.z), blendType='easeIn', fluid=1),
            Parallel(Func(dummy.removeNode), Func(linePath.removeNode))
        ).start()

    def makeArc(angleDegrees=360, numSteps=16, color=Vec4(1, 1, 1, 1)):
        ls = LineSegs()
        angleRadians = deg2Rad(angleDegrees)
        for i in range(numSteps + 1):
            a = angleRadians * i / numSteps
            y = math.sin(a)
            x = math.cos(a)
            ls.drawTo(x, y, 0)
        node = ls.create()
        if color != Vec4(1, 1, 1, 1):
            for i in range(numSteps + 1):
                ls.setVertexColor(i, color)
            pass
        return NodePath(node)

    def clear(self):
        if self.nodePath:
            self.nodePath.removeNode()
            self.environ.removeNode()

    def generate(self):
        self.terrain.generate()
        self.teams = [
                Team(self, 0, 'Team 1', (0.1, 0.1, 0.1, 1.0)),
                Team(self, 1, 'Team 2', (0.9, 0.9, 0.9, 1.0)),
        ]
        self.teams[0].add_character(0, 0)
        self.teams[1].add_character(self.terrain.size_x - 1, self.terrain.size_y - 1)

    # init a light module to make model looks better by using shader
    def init_lights(self):
        from pandac.PandaModules import AmbientLight, DirectionalLight
        from pandac.PandaModules import ShadeModelAttrib
        # Set flat shading
        flatShade = ShadeModelAttrib.make(ShadeModelAttrib.MFlat)
        self.nodePath.setAttrib(flatShade)
        # Create directional light
        dlight1 = DirectionalLight('dlight1')
        dlight1.setColor(VBase4(1.0, 1.0, 1.0, 1.0))
        dlnp1 = self.nodePath.attachNewNode(dlight1)
        dlnp1.setHpr(-10, -30, 0)
        self.nodePath.setLight(dlnp1)
        # Create second directional light
        dlight2 = DirectionalLight('dlight2')
        dlight2.setColor(VBase4(0.0, 0.1, 0.2, 1.0))
        dlnp2 = self.nodePath.attachNewNode(dlight2)
        dlnp2.setHpr(170, 0, 0)
        self.nodePath.setLight(dlnp2)
        # Create ambient light
        alight = AmbientLight('alight')
        alight.setColor(VBase4(0.3, 0.3, 0.3, 1.0))
        alnp = self.nodePath.attachNewNode(alight)
        self.nodePath.setLight(alnp)

    # preset the camera position
    def init_camera(self):
        from pandac.PandaModules import OrthographicLens
        lens = OrthographicLens()
        lens.setAspectRatio(4.0 / 3.0)
        lens.setNear(-1000)
        base.cam.node().setLens(lens)
        base.camera.setHpr(60, 0 - IDEAL_AZIMUTH, 0)

    def position_camera(self):
        width = math.sqrt((0.75 * HEX_DIAM * self.terrain.size_x) ** 2 + (HEX_DIAM * SQRT_3 / 2 * self.terrain.size_y) ** 2)
        base.cam.node().getLens().setFilmSize(width)
        (pos_x, pos_y, pos_z) = board_coordinates(self.terrain.size_x * 0.5, self.terrain.size_y * 0.5, 0)
        base.camera.setPos(pos_x, pos_y, 10)

    def init_terrain(self):
        self.terrain = Terrain(self)

    def init_teams(self):
        self.teams = []

    def __getstate__(self):
        safe_dict = self.__dict__.copy()
        safe_dict['nodePath'] = None
        return safe_dict

    def __setstate__(self, safe_dict):
        self.__dict__.update(safe_dict)
        self.init_nodepath()
