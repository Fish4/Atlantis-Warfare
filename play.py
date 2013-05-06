#!usr/bin/python

# python import
import cPickle
import sys
import socket
from sets import Set

# panda 3d import
from direct.showbase.DirectObject import DirectObject
from pandac.PandaModules import Point2, Point3
from direct.fsm import FSM
from direct.interval.IntervalGlobal import *
from direct.gui.DirectGui import *

# network import
from network.Server import *
from network.Client import *

# hexabots import
from hexabots import World, Mouse, Tile, Character
from hexabots import board_coordinates, find_nearby, tile_distance_squared, HexPathFinding, get_adjacent, find_vision

VISION_DISTANCE = 4
COLLISION_DAMAGE = 0.1
ATTACK_DAMAGE = 0.2
MOVE_DISTANCE = 3


"""

Tasks:
        Display ranged attack
        set damage for ranged attack
        make sure ranged attack occurs

Changes:

problems:


NOTE:
        character, tile will only get initiated when new map is made.

"""

###################################################
#                                                 #
#     Utility functions                           #
#                                                 #
###################################################


# turn timer
def turnTimerTask(task):
    # when task starts, start the timer
    secondsTime = int(task.time)
    timeleft = 30 - secondsTime % 60
    # change it to timeleft
    app.turnTimer.setText("Turn Timer " + str(timeleft))
    # change the text
    if timeleft > 5:
        # before 5s second
        return Task.cont
    elif timeleft == 5:
        # right when timeleft == 5, yell comonethen
        if not app.playedReminder:
            mySound = loader.loadSfx("sounds/comeonthen.mp3")
            mySound.play()
            app.playedReminder = True
            return Task.cont
        return Task.cont
    # else keep counting time
    elif timeleft > 0:
        return Task.cont
    # when the timer is 0
    elif timeleft <= 0:
        if app.singlePlayer:
            app.state.demand('AITeam')
        else:
        # force state to be playmove
            app.state.demand('PlayMove')
        return Task.done


# this is a task to calculate the vision
def setVisions(task):
    vision = Set()
    vision.add(app.world.terrain.getTile(5, 5))
    if app.singlePlayer:
        for character in app.world.teams[0].characters:
            visionList = find_vision(app.world.terrain, character.x, character.y, VISION_DISTANCE)
            visionSet = Set(visionList)
            vision = vision | visionSet
        for character in app.world.teams[1].characters:
            if character.tile in vision:
                if character.nodePath.getSa() == 0:
                    character.nodePath.setTransparency(1)
                    character.nodePath.setAlphaScale(1)
            else:
                if character.nodePath.getSa() == 1:
                    character.nodePath.setTransparency(1)
                    character.nodePath.setAlphaScale(0)
        for row in app.world.terrain.rows:
            for tile in row:
                if tile.material == 'obstacle':
                    pass
                elif tile in vision:
                    if tile.nodePath.getColor() * 1.5 <= VBase4(0, .7, 0, 1.0)*1.5:
                        tile.nodePath.setColor(tile.nodePath.getColor() * 1.5)
                else:
                    if tile.nodePath.getColor() >= VBase4(0, 0, 0, 0):
                        tile.nodePath.setColor(tile.nodePath.getColor() / 1.5)
    elif app.player == 'server':
        for character in app.world.teams[0].characters:
            visionList = find_vision(app.world.terrain, character.x, character.y, VISION_DISTANCE)
            visionSet = Set(visionList)
            vision = vision | visionSet
        for character in app.world.teams[1].characters:
            if character.tile in vision:
                if character.nodePath.getSa() == 0:
                    character.nodePath.setTransparency(1)
                    character.nodePath.setAlphaScale(1)
            else:
                if character.nodePath.getSa() == 1:
                    character.nodePath.setTransparency(1)
                    character.nodePath.setAlphaScale(0)
        for row in app.world.terrain.rows:
            for tile in row:
                if tile.material == 'obstacle':
                    pass
                elif tile in vision:
                    if tile.nodePath.getColor() * 1.5 <= VBase4(0, .7, 0, 1.0)*1.5:
                        tile.nodePath.setColor(tile.nodePath.getColor() * 1.5)
                else:
                    if tile.nodePath.getColor() >= VBase4(0, 0, 0, 0):
                        tile.nodePath.setColor(tile.nodePath.getColor() / 1.5)
    else:
        for character in app.world.teams[1].characters:
            visionList = find_vision(app.world.terrain, character.x, character.y, VISION_DISTANCE)
            visionSet = Set(visionList)
            vision = vision | visionSet
        for character in app.world.teams[0].characters:
            if character.tile in vision:
                if character.nodePath.getSa() == 0:
                    character.nodePath.setTransparency(1)
                    character.nodePath.setAlphaScale(1)
            else:
                if character.nodePath.getSa() == 1:
                    character.nodePath.setTransparency(1)
                    character.nodePath.setAlphaScale(0)
        for row in app.world.terrain.rows:
            for tile in row:
                if tile.material == 'obstacle':
                    pass
                elif tile in vision:
                    if tile.nodePath.getColor() * 1.5 <= VBase4(0, .7, 0, 1.0)*1.5:
                        tile.nodePath.setColor(tile.nodePath.getColor() * 1.5)
                else:
                    if tile.nodePath.getColor() >= VBase4(0, 0, 0, 0):
                        tile.nodePath.setColor(tile.nodePath.getColor() / 1.5)
    return Task.cont


# a task to check objective and update the gui
def checkObjective(task):
    for team in app.world.teams:
        team.check_completing_objective()
        if team.name == 'Team 1':
            app.objectiveTeam1.setText('Team 1: ' + str(team.TurnsToWin))
        else:
            app.objectiveTeam2.setText('Team 2: ' + str(team.TurnsToWin))
    if not app.world.terrain.getTile(5, 5).get_inhabitants():
        app.world.terrain.getTile(5, 5).nodePath.setColor(VBase4(0.7, 0.7, 0.7, 1.0))
    app.state.request('TurnManager')
    return Task.done


####################################################
#  method performing all the moves and collision:  #
#####################################################################################################
#                                                                                                   #
#   1   calculte the next moves                                                                     #
#   2   calculate and resolve all the collision                                                     #
#      2.1  resolve 'both moving collision'                                                         #
#         2.1.1  resolve multiple character moving to the same tile                                 #
#         2.1.2  resolve 'swap' situation                                                           #
#      2.2  resolve moving onto non-moving character case                                           #
#   3.  resolve all the normal moves                                                                #
#      note: if the move is onto someone else on the same team, the simulatedTile will not get      #
#            updated in order to track the previous correct position                                #
#            then, if it is the last move, just move to the simulatedTile                           #
#                                                                                                   #
#####################################################################################################
def ExecuteMoves(task):
    # collision damage
    def attack(target):
        target.damage(COLLISION_DAMAGE)

    # move method
    def move(mover, target):
        mover.move_to(target)

    # rotation action
    def rotate(mover):
        mover.rotate()
        mover.rotated = False

    # request attack state
    def requestAttack():
        for team in app.world.teams:
            for character in team.characters:
                character.path = None
        app.state.request('PlayAttack')

    MoveEvents = Sequence()

    # is 5 because it also contains move to the self.tile
    for timeToken in range(5):
        # create a parallel to execute all the move simultaneously
        thisMove = Parallel()
        # dict to store all the event happened at this time token
        nextEvents = dict([])
        ###########################################################################################
        # 1. Calculate next tile                                                                  #
        # purose of this pre-calculation is to store all the next move to detect the collision    #
        # store all the character's next move to the nextEvents                                   #
        ###########################################################################################
        for team in app.world.teams:
            for character in team.characters:
                # if character being attacked (at this case, being collided), then dont move character anymore
                if not character.attacked:
                    if character.path:
                        # find the character's next tile
                        next = character.path.popleft()
                        # if someone else is also moving to this tile
                        if next in nextEvents:
                            otherCharacter = nextEvents[next]
                            if isinstance(otherCharacter, Character):
                                nextEvents[next] = []
                                nextEvents[next].append(character)
                                nextEvents[next].append(otherCharacter)
                            else:
                                nextEvents[next].append(character)
                        # else perform the normal move
                        else:
                            nextEvents[next] = character
        ##################################################################################################################
        # 2. Resolve collision                                                                                           #
        # this is where it actually brings out the collision                                                             #
        # check all the list, purpose of this lise is: maybe there is more than one that is moving onto this tile        #
        ##################################################################################################################

        ####################################################################
        #
        # 2.1.1 situation multiple character moves onto the same tile
        #
        for nextTile in nextEvents.keys():
            if isinstance(nextEvents[nextTile], list):
                movers = nextEvents[nextTile]
                team = movers[0].team
                collided = False
                # check the collision case
                # when multiple character move to the same tile
                for mover in movers:
                    if mover.team != team:
                        collided = True
                # calculate the number for each team
                team1 = 0
                team2 = 0
                if collided:
                    for mover in movers:
                        if mover.team.name == 'Team 1':
                            team1 += 1
                        else:
                            team2 += 1
                # collided case, attack each other and mark them being attacked
                if collided:
                    # if even, both team take damage
                    if team1 == team2:
                        for mover in movers:
                            i_sequence = Sequence()

                            from_coords = Point3(mover.simulatedTile.nodePath.getPos())
                            to_coords = Point3(board_coordinates(nextTile.x, nextTile.y, nextTile.height))
                            i_move_to = LerpPosInterval(mover.nodePath, 0.5, to_coords, blendType='easeIn')
                            i_move_from = LerpPosInterval(mover.nodePath, 0.5, from_coords, blendType='easeOut')
                            i_autoAttack = Func(attack, mover)
                            i_sequence.append(i_move_to)
                            i_sequence.append(i_move_from)
                            i_sequence.append(i_autoAttack)
                            # music here
                            mySound = loader.loadSfx("sounds/ouch.mp3")
                            ouch = SoundInterval(mySound, 0)
                            i_sequence.append(ouch)
                            i_moveAction = Func(move, mover, mover.simulatedTile)
                            i_sequence.append(i_moveAction)
                            thisMove.append(i_sequence)
                            mover.rotated = False
                            mover.attacked = True
                    # if team 1 has advantabe, then team 2 take damage
                    elif team1 > team2:
                        for mover in movers:
                            if mover.team.name == 'Team 1':
                                i_sequence = Sequence()

                                from_coords = Point3(mover.simulatedTile.nodePath.getPos())
                                to_coords = Point3(board_coordinates(nextTile.x, nextTile.y, nextTile.height))
                                i_move_to = LerpPosInterval(mover.nodePath, 0.5, to_coords, blendType='easeIn')
                                i_move_from = LerpPosInterval(mover.nodePath, 0.5, from_coords, blendType='easeOut')
                                i_sequence.append(i_move_to)
                                i_sequence.append(i_move_from)
                                # music here
                                i_moveAction = Func(move, mover, mover.simulatedTile)
                                i_sequence.append(i_moveAction)
                                thisMove.append(i_sequence)
                                mover.rotated = False
                                mover.attacked = True
                            elif mover.team.name == 'Team 2':
                                i_sequence = Sequence()

                                from_coords = Point3(mover.simulatedTile.nodePath.getPos())
                                to_coords = Point3(board_coordinates(nextTile.x, nextTile.y, nextTile.height))
                                i_move_to = LerpPosInterval(mover.nodePath, 0.5, to_coords, blendType='easeIn')
                                i_move_from = LerpPosInterval(mover.nodePath, 0.5, from_coords, blendType='easeOut')
                                i_autoAttack = Func(attack, mover)
                                i_sequence.append(i_move_to)
                                i_sequence.append(i_move_from)
                                i_sequence.append(i_autoAttack)
                                # music here
                                mySound = loader.loadSfx("sounds/ouch.mp3")
                                ouch = SoundInterval(mySound, 0)
                                i_sequence.append(ouch)
                                i_moveAction = Func(move, mover, mover.simulatedTile)
                                i_sequence.append(i_moveAction)
                                thisMove.append(i_sequence)
                                mover.rotated = False
                                mover.attacked = True
                    # else if team 2 has advantage, then team 1 take damage
                    else:
                        for mover in movers:
                            if mover.team.name == 'Team 1':
                                i_sequence = Sequence()

                                from_coords = Point3(mover.simulatedTile.nodePath.getPos())
                                to_coords = Point3(board_coordinates(nextTile.x, nextTile.y, nextTile.height))
                                i_move_to = LerpPosInterval(mover.nodePath, 0.5, to_coords, blendType='easeIn')
                                i_move_from = LerpPosInterval(mover.nodePath, 0.5, from_coords, blendType='easeOut')
                                i_autoAttack = Func(attack, mover)
                                i_sequence.append(i_move_to)
                                i_sequence.append(i_move_from)
                                i_sequence.append(i_autoAttack)
                                # music here
                                mySound = loader.loadSfx("sounds/ouch.mp3")
                                ouch = SoundInterval(mySound, 0)
                                i_sequence.append(ouch)
                                i_moveAction = Func(move, mover, mover.simulatedTile)
                                i_sequence.append(i_moveAction)
                                thisMove.append(i_sequence)
                                mover.rotated = False
                                mover.attacked = True
                            elif mover.team.name == 'Team 2':
                                i_sequence = Sequence()

                                from_coords = Point3(mover.simulatedTile.nodePath.getPos())
                                to_coords = Point3(board_coordinates(nextTile.x, nextTile.y, nextTile.height))
                                i_move_to = LerpPosInterval(mover.nodePath, 0.5, to_coords, blendType='easeIn')
                                i_move_from = LerpPosInterval(mover.nodePath, 0.5, from_coords, blendType='easeOut')
                                i_sequence.append(i_move_to)
                                i_sequence.append(i_move_from)
                                # music here
                                i_moveAction = Func(move, mover, mover.simulatedTile)
                                i_sequence.append(i_moveAction)
                                thisMove.append(i_sequence)
                                mover.rotated = False
                                mover.attacked = True
            ############################################################################
            #
            # 2.1.1 situation, swap position
            #

            # if only one move to this tile, then just perform a normal move
            elif isinstance(nextEvents[nextTile], Character):
                mover = nextEvents[nextTile]
                if not mover.attacked:
                    # check the collision case
                    for team in app.world.teams:
                        # only collide with enemy character
                        if team != mover.team:
                            for character in team.characters:
                                if character.simulatedTile == nextTile:
                                    if character.path:
                                        #######################################################
                                        # swap position
                                        # when two idiots walk toward each other
                                        for nextTile2 in nextEvents.keys():
                                            if character.simulatedTile in get_adjacent(app.world.terrain, nextTile2.x, nextTile2.y) and nextEvents[nextTile2] == character:
                                                i_sequence = Sequence()

                                                from_coords = Point3(character.simulatedTile.nodePath.getPos())
                                                to_coords = Point3(board_coordinates(mover.simulatedTile.x, mover.simulatedTile.y, mover.simulatedTile.height))
                                                i_move_to = LerpPosInterval(character.nodePath, 0.5, to_coords, blendType='easeIn')
                                                i_move_from = LerpPosInterval(character.nodePath, 0.5, from_coords, blendType='easeOut')
                                                i_autoAttack = Func(attack, mover)
                                                i_sequence.append(i_move_to)
                                                i_sequence.append(i_move_from)
                                                i_sequence.append(i_autoAttack)
                                                # music here
                                                mySound = loader.loadSfx("sounds/ouch.mp3")
                                                ouch = SoundInterval(mySound, 0)
                                                i_sequence.append(ouch)
                                                i_moveAction = Func(move, character, character.simulatedTile)
                                                i_sequence.append(i_moveAction)
                                                thisMove.append(i_sequence)
                                                mover.rotated = False
                                                mover.attacked = True

                                                i_sequence2 = Sequence()
                                                # if there is an enemy within range
                                                from_coords2 = Point3(mover.simulatedTile.nodePath.getPos())
                                                to_coords2 = Point3(board_coordinates(character.simulatedTile.x, character.simulatedTile.y, character.simulatedTile.height))
                                                i_move_to2 = LerpPosInterval(mover.nodePath, 0.5, to_coords2, blendType='easeIn')
                                                i_move_from2 = LerpPosInterval(mover.nodePath, 0.5, from_coords2, blendType='easeOut')
                                                i_autoAttack2 = Func(attack, character)
                                                i_sequence2.append(i_move_to2)
                                                i_sequence2.append(i_move_from2)
                                                i_sequence2.append(i_autoAttack2)
                                                # music here
                                                mySound2 = loader.loadSfx("sounds/ouch.mp3")
                                                ouch2 = SoundInterval(mySound2, 0)
                                                i_sequence2.append(ouch2)
                                                i_moveAction2 = Func(move, mover, mover.simulatedTile)
                                                i_sequence2.append(i_moveAction2)
                                                thisMove.append(i_sequence2)
                                                character.rotated = False
                                                character.attacked = True
        ##################################################################################################
        #
        # 2.2 situation, move onto someone that is not moving
        #
        for nextTile in nextEvents.keys():
            if isinstance(nextEvents[nextTile], Character):
                mover = nextEvents[nextTile]
                if not mover.attacked:
                    # check the collision case
                    for team in app.world.teams:
                        # only collide with enemy character
                        if team != mover.team:
                            for character in team.characters:
                                if character.tile == nextTile:
                                    if not character.path:
                                        mover.rotated = False
                                        mover.attacked = True

                                        i_sequence2 = Sequence()

                                        # this lazy dude got attacked by you without countering back
                                        from_coords2 = Point3(mover.simulatedTile.nodePath.getPos())
                                        to_coords2 = Point3(board_coordinates(character.simulatedTile.x,
                                                                              character.simulatedTile.y,
                                                                              character.simulatedTile.height))
                                        i_move_to2 = LerpPosInterval(mover.nodePath, 0.5, to_coords2, blendType='easeIn')
                                        i_move_from2 = LerpPosInterval(mover.nodePath, 0.5, from_coords2, blendType='easeOut')
                                        i_autoAttack2 = Func(attack, character)
                                        i_sequence2.append(i_move_to2)
                                        i_sequence2.append(i_move_from2)
                                        i_sequence2.append(i_autoAttack2)
                                        # music here
                                        mySound2 = loader.loadSfx("sounds/ouch.mp3")
                                        ouch2 = SoundInterval(mySound2, 0)
                                        i_sequence2.append(ouch2)
                                        i_moveAction2 = Func(move, mover, mover.simulatedTile)
                                        i_sequence2.append(i_moveAction2)
                                        thisMove.append(i_sequence2)
                                        character.rotated = False
                                        character.attacked = True
                                    elif character.path and character.attacked:
                                        mover.rotated = False
                                        mover.attacked = True

                                        i_sequence2 = Sequence()

                                        # this lazy dude got attacked by you without countering back
                                        from_coords2 = Point3(mover.simulatedTile.nodePath.getPos())
                                        to_coords2 = Point3(board_coordinates(character.simulatedTile.x,
                                                                              character.simulatedTile.y,
                                                                              character.simulatedTile.height))
                                        i_move_to2 = LerpPosInterval(mover.nodePath, 0.5, to_coords2, blendType='easeIn')
                                        i_move_from2 = LerpPosInterval(mover.nodePath, 0.5, from_coords2, blendType='easeOut')
                                        i_autoAttack2 = Func(attack, character)
                                        i_sequence2.append(i_move_to2)
                                        i_sequence2.append(i_move_from2)
                                        i_sequence2.append(i_autoAttack2)
                                        # music here
                                        mySound2 = loader.loadSfx("sounds/ouch.mp3")
                                        ouch2 = SoundInterval(mySound2, 0)
                                        i_sequence2.append(ouch2)
                                        i_moveAction2 = Func(move, mover, mover.simulatedTile)
                                        i_sequence2.append(i_moveAction2)
                                        thisMove.append(i_sequence2)
                                        character.rotated = False
                                        character.attacked = True

                                elif character.simulatedTile == nextTile:
                                    ####################################################################
                                    # Move onto someone that is not moving
                                    # when the character just hanging out there and got jumped by you
                                    if character.attacked:
                                        mover.rotated = False
                                        mover.attacked = True

                                        i_sequence2 = Sequence()

                                        # this lazy dude got attacked by you without countering back
                                        from_coords2 = Point3(mover.simulatedTile.nodePath.getPos())
                                        to_coords2 = Point3(board_coordinates(character.simulatedTile.x,
                                                                              character.simulatedTile.y,
                                                                              character.simulatedTile.height))
                                        i_move_to2 = LerpPosInterval(mover.nodePath, 0.5, to_coords2, blendType='easeIn')
                                        i_move_from2 = LerpPosInterval(mover.nodePath, 0.5, from_coords2, blendType='easeOut')
                                        i_autoAttack2 = Func(attack, character)
                                        i_sequence2.append(i_move_to2)
                                        i_sequence2.append(i_move_from2)
                                        i_sequence2.append(i_autoAttack2)
                                        # music here
                                        mySound2 = loader.loadSfx("sounds/ouch.mp3")
                                        ouch2 = SoundInterval(mySound2, 0)
                                        i_sequence2.append(ouch2)
                                        i_moveAction2 = Func(move, mover, mover.simulatedTile)
                                        i_sequence2.append(i_moveAction2)
                                        thisMove.append(i_sequence2)
                                        character.rotated = False
                                        character.attacked = True

        ######################################################################################################################
        #
        # 3. Resolve the rest normal moves
        #
        for nextTile in nextEvents.keys():
            # if only one move to this tile, then just perform a normal move
            if isinstance(nextEvents[nextTile], Character):
                mover = nextEvents[nextTile]

                # if no collision happened at next tile, then do the normal move
                if not mover.attacked:
                    teamBeingAttackAndStayed = False
                    for team in app.world.teams:
                        if team == mover.team:
                            for character in team.characters:
                                if character.simulatedTile == nextTile and character.attacked:
                                    teamBeingAttackAndStayed = True
                                elif character.tile == nextTile and character.attacked:
                                    teamBeingAttackAndStayed = True

                    if teamBeingAttackAndStayed:
                        if len(mover.path) <= 1:
                            pass
                        else:
                            i_sequence = Sequence()
                            to_coords = Point3(*board_coordinates(nextTile.x, nextTile.y, nextTile.height))
                            i_move = LerpPosInterval(mover.nodePath, 1, to_coords)
                            i_sequence.append(i_move)
                            thisMove.append(i_sequence)
                    elif nextTile.get_inhabitants() and not nextTile.get_inhabitants()[0].team == character and not character.path:
                        if len(mover.path) <= 1:
                            pass
                        else:
                            i_sequence = Sequence()
                            to_coords = Point3(*board_coordinates(nextTile.x, nextTile.y, nextTile.height))
                            i_move = LerpPosInterval(mover.nodePath, 1, to_coords)
                            i_sequence.append(i_move)
                            thisMove.append(i_sequence)
                    else:
                        mover.simulatedTile = nextTile
                        i_sequence = Sequence()
                        to_coords = Point3(*board_coordinates(nextTile.x, nextTile.y, nextTile.height))
                        i_move = LerpPosInterval(mover.nodePath, 1, to_coords)
                        i_sequence.append(i_move)
                        i_moveAction = Func(move, mover, nextTile)
                        i_sequence.append(i_moveAction)
                        thisMove.append(i_sequence)
            # else if multiple character moving to the same tile, then check they are on the same team or not
            elif isinstance(nextEvents[nextTile], list):
                movers = nextEvents[nextTile]

                # else it is the same team, just move as usual
                for mover in movers:

                    if len(mover.path) <= 1:
                        pass
                    else:

                        i_sequence = Sequence()
                        to_coords = Point3(*board_coordinates(nextTile.x, nextTile.y, nextTile.height))
                        i_move = LerpPosInterval(mover.nodePath, 1, to_coords)
                        i_sequence.append(i_move)

                        thisMove.append(i_sequence)

        MoveEvents.append(thisMove)

    # rotate event here
    RotateEvents = Parallel()
    for team in app.world.teams:
        for character in team.characters:
            # whoever gets collided does not perform the rotate
            if not character.attacked:
                if character.frontTile:
                    i_sequence = Sequence()
                    i_rotate = Func(rotate, character)
                    i_sequence.append(i_rotate)
                    RotateEvents.append(i_sequence)

    MoveEvents.append(RotateEvents)
    i_finish = Func(requestAttack)
    MoveEvents.append(i_finish)
    MoveEvents.start()

    return Task.done


# method performing all the attacks:
def ExecuteAttacks(task):
    # attacking post_action
    def attack(target, damage):
        target.damage(damage)
        target.attacked = True

    def postAttack():
        app.state.request('CheckObjectives')

    AttackSequence = Sequence()
    Attacks = Parallel()

    # Execute all character's attack
    for team in app.world.teams:
        for character in team.characters:
            if not character.attacked:
                if character.frontTile:
                    if character.frontTile != character.tile:
                        i_sequence = Sequence()
                        # TODO: CHECK
                        # if enemy is in front then attack
                        potentialEnemy = 0
                        damage = 0

                        attackRange = find_line_of_sight(character.tile, character.frontTile, 3)

                        AttackRangeCount = 1

                        for attackTile in attackRange:
                            if attackTile.get_inhabitants():
                                potentialEnemy = attackTile.get_inhabitants()
                                damage = 0.1 * (4 - AttackRangeCount)
                                break
                            else:
                                AttackRangeCount += 1

                        # TODO: ADD TO POTENTIAL ENEMY
                        if potentialEnemy:
                            # if there is an enemy within range
                            from_coords = Point3(character.nodePath.getPos())
                            to_coords = Point3(board_coordinates(potentialEnemy[0].x, potentialEnemy[0].y, potentialEnemy[0].height))
                            i_move_to = LerpPosInterval(character.nodePath, 0.3, to_coords, blendType='easeIn')
                            i_move_from = LerpPosInterval(character.nodePath, 0.3, from_coords, blendType='easeOut')
                            i_autoAttack = Func(attack, potentialEnemy[0], damage)
                            i_sequence.append(i_move_to)
                            i_sequence.append(i_move_from)
                            i_sequence.append(i_autoAttack)
                            # music here
                            mySound = loader.loadSfx("sounds/ouch.mp3")
                            ouch = SoundInterval(mySound, 0)
                            i_sequence.append(ouch)
                        Attacks.append(i_sequence)

    AttackSequence.append(Attacks)
    i_finish = Func(postAttack)
    AttackSequence.append(i_finish)
    AttackSequence.start()

    return Task.done


# check all character having actions or not, if all have then ask for playMove
def actionChecker(task):
    # dummy way to check all characters having actions, and still working YEAH
    count = 0
    for team in app.world.teams:
        for character in team.characters:
            if character.path and character.rotated:
                count = count + 1
    if app.singlePlayer:
        if count == len(app.world.teams[0].characters):
            app.state.demand('AITeam')
            return Task.done
        else:
            return Task.cont
    if count == app.characterCount:
        # if all characters have actions, Execute them
        app.state.demand('PlayMove')
        return Task.done
    else:
        return Task.cont


def find_line_of_sight(current, front, distance):
    counter = 1
    LOS = []
    LOS.append(front)
    currentTile = current
    currentFront = front
    while counter < distance:
        counter += 1
        nextFront = get_next_tile(currentTile, currentFront)
        if nextFront and nextFront.material != 'obstacle':
            LOS.append(nextFront)
            currentTile = currentFront
            currentFront = nextFront
    return LOS


# pass two tiles. the current position tile and the front tile. from there, method creates the next tile's coordinates in a line
def get_next_tile(current, front):
    if isinstance(front, Tile) and isinstance(current, Tile):
      # pass two tiles. the current position tile and the front tile. from there, method creates the next tile's coordinates in a line

        x = current.x
        y = current.y
        newX = front.x
        newY = front.y
        dx = newX - x
        dy = newY - y

        if x % 2 == 0:
            coords = [(-1, 0), (0, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]
        else:
            coords = [(-1, 1), (0, 1), (1, 1), (1, 0), (0, -1), (-1, 0)]
        if (dx, dy) in coords:
            index = coords.index((dx, dy))
        else:
            return None

        if newX % 2 == 0:
            newCoords = [(newX - 1, newY), (newX, newY + 1), (newX + 1, newY), (newX + 1, newY - 1), (newX, newY - 1), (newX - 1, newY - 1)]
        else:
            newCoords = [(newX - 1, newY + 1), (newX, newY + 1), (newX + 1, newY + 1), (newX + 1, newY), (newX, newY - 1), (newX - 1, newY)]

        (nextX, nextY) = newCoords[index]

        if nextX < 0 or nextY < 0:
            return None
        elif nextX >= 11 or nextY >= 11:
            return None
        else:

            nextTile = app.world.terrain.getTile(nextX, nextY)

            return nextTile


# control the background music
def MuteUnmute():
    if app.muted:
        app.backgroundMusic.setVolume(1.0)
        app.muted = False
    else:
        app.backgroundMusic.setVolume(0)
        app.muted = True


# kills off players who should be dead
def cleanup():
    for team in app.world.teams:
        for character in team.characters:
            # if character is not a dead body, and character should be dead ... Eric recoomend ... KILL HIM
            if not character.is_dead and character.should_die():
                # this guy does not only die, but also vanish completely from the world and his team
                app.world.teams[character.team.index].delete_character(character.id)
                # update the count of the total characters
                app.characterCount = app.characterCount - 1


# game over screen is displayed if teams alive is one
def game_over():
    # loser it is
    loser = []
    # goes through all the teams and its characters
    for team in app.world.teams:
        if team.TurnsToWin == 0:
            if app.winner:
                app.winner.destroy()
            if team.name == 'Team 1':
                if app.singlePlayer:
                    app.state.demand('Winner')
                elif app.player == 'server':
                    app.state.demand('Winner')
                else:
                    app.state.demand('Loser')
            else:
                if app.singlePlayer:
                    app.state.demand('Loser')
                elif app.player == 'client':
                    app.state.demand('Winner')
                else:
                    app.state.demand('Loser')
            return True
        if len(team.characters) == 0:
            # if this team doesnt have any warrior to yell this is sparta anymore, he is a definitely loser
            loser.append(team)
    if loser:
        # meaning both teams lose/ draw
        if len(loser) == 2:
            if app.winner:
                app.winner.destroy()
            app.state.demand('Loser')
            return True
        for team in app.world.teams:
            if team not in loser:
                if app.winner:
                    app.winner.destroy()
                if team.name == 'Team 1':
                    if app.singlePlayer:
                        app.state.demand('Winner')
                    elif app.player == 'server':
                        app.state.demand('Winner')
                    else:
                        app.state.demand('Loser')
                else:
                    if app.singlePlayer:
                        app.state.demand('Loser')
                    elif app.player == 'client':
                        app.state.demand('Winner')
                    else:
                        app.state.demand('Loser')
                return True
    return False


# simple protocol method
def encodeInfo(character, action, target):
    if action == 'Move':
        return str(character.id) + ' ' + action + ' ' + str(target.x) + ' ' + str(target.y)
    elif action == 'Attack':
        return str(character.id) + ' ' + action + ' ' + str(target.id)
    elif action == 'Rotate':
        return str(character.id) + ' ' + action + ' ' + str(target.x) + ' ' + str(target.y)


def decodeInfo(information):
    return information.split()

########################################################################
#                                                                      #
#  Upadate world will receive the information and                      #
#  decode the information and save it to character's action            #
#  Without running the action of course                                #
#                                                                      #
########################################################################


def updateWorld(Info):
    decodedInfo = decodeInfo(Info)
    # decoded data will be a list
    # get the second word of the list, indicating what kind of action this actor is doing
    if decodedInfo[1] == 'Move':
        character = findCharacterByID(decodedInfo[0])
        target = findTileByXY(decodedInfo[2], decodedInfo[3])
        character.path = HexPathFinding(app.world.terrain, character, target)
    elif decodedInfo[1] == 'Rotate':
        character = findCharacterByID(decodedInfo[0])
        target = findTileByXY(decodedInfo[2], decodedInfo[3])
        character.setRotation(target)


def findCharacterByID(characterID):
    for team in app.world.teams:
        for character in team.characters:
            if character.id == int(characterID):
                return character


def findTileByXY(x, y):
    return app.world.terrain.getTile(int(x), int(y))

###################################################
#                                                 #
#     Turn Manager Task                           #
#                                                 #
###################################################


# kill all the zombies and determine gameover screen
def TurnCleanUp(task):
    cleanup()
    # takes user back to loading screen
    if game_over():
        # TODO: or maybe implement winner loser here to Horse
        return task.done
    # repeats this process until the game is over
    return task.cont

###################################################
#                                                 #
#     Network Managers                            #
#                                                 #
###################################################


def ServerStarter(task):
    def load():
        # clean up the previous world
        app.delete_world()
        # load the preset map
        F = open('debug.hm', 'rb')
        app.world = cPickle.load(F)
        F.close()
        # end loading map
        app.world.position_camera()
        # init the total number of the characters
        app.characterCount = len(app.world.teams[0].characters) + len(app.world.teams[1].characters)
        # init the health bar and parent to the character
        for team in app.world.teams:
            for character in team.characters:
                character.init_healthBar()
        # change into game state
        app.state.request('TurnManager')
        # start the turn counter
        app.turnCounter = 1
        app.turnText = OnscreenText(text="Turn " + str(app.turnCounter),
                                    style=1, fg=(1, 1, 1, 1),
                                    pos=(0, -0.95),
                                    align=TextNode.ACenter,
                                    scale = .07,
                                    mayChange = True)
        app.objectiveTeam1 = OnscreenText(text="Team 1: " + str(app.world.teams[0].TurnsToWin),
                                          style=1, fg=(1, 1, 1, 1),
                                          pos=(-0.3, -0.95),
                                          align=TextNode.ACenter,
                                          scale = .07,
                                          mayChange = True)
        app.objectiveTeam2 = OnscreenText(text="Team 2: " + str(app.world.teams[1].TurnsToWin),
                                          style=1, fg=(1, 1, 1, 1),
                                          pos=(0.3, -0.95),
                                          align=TextNode.ACenter,
                                          scale = .07,
                                          mayChange = True)
    if app.server.getClients():
        # stop the title music
        app.backgroundMusic.stop()
        load()
        app.player = 'server'
        app.playerStats['server'] = app.world.teams[0]
        app.playerStats['client'] = app.world.teams[1]
        taskMgr.add(ServerManager, 'ServerManager')
        # start the turn timer after start the game
        app.turnTimer = OnscreenText(text="Turn Timer ",
                                     style=1, fg=(1, 1, 1, 1),
                                     pos=(0, 0.9),
                                     align=TextNode.ACenter,
                                     scale = .07,
                                     mayChange = True)
        taskMgr.add(turnTimerTask, 'turnTimerTask')
        return task.done
    else:
        return task.cont


def ClientStarter(task):
    def load():
        # clean up the previous world
        app.delete_world()
        F = open('debug.hm', 'rb')  # load the preset map
        app.world = cPickle.load(F)
        F.close()
        # end loading map
        app.world.position_camera()
        # init the total number of the characters
        app.characterCount = len(app.world.teams[0].characters) + len(app.world.teams[1].characters)
        # init the health bar and parent to the character
        for team in app.world.teams:
            for character in team.characters:
                character.init_healthBar()
        # change into game state
        app.state.request('TurnManager')
        # start the turn counter
        app.turnCounter = 1
        app.turnText = OnscreenText(text="Turn " + str(app.turnCounter),
                                    style=1, fg=(1, 1, 1, 1),
                                    pos=(0, -0.95),
                                    align=TextNode.ACenter,
                                    scale = .07,
                                    mayChange = True)
        app.objectiveTeam1 = OnscreenText(text="Team 1: " + str(app.world.teams[0].TurnsToWin),
                                          style=1, fg=(1, 1, 1, 1),
                                          pos=(-0.3, -0.95),
                                          align=TextNode.ACenter,
                                          scale = .07,
                                          mayChange = True)
        app.objectiveTeam2 = OnscreenText(text="Team 2: " + str(app.world.teams[1].TurnsToWin),
                                          style=1, fg=(1, 1, 1, 1),
                                          pos=(0.3, -0.95),
                                          align=TextNode.ACenter,
                                          scale = .07,
                                          mayChange = True)
    if app.client.getConnected():
        # stop the title music
        app.backgroundMusic.stop()
        load()
        app.player = 'client'
        app.playerStats['server'] = app.world.teams[0]
        app.playerStats['client'] = app.world.teams[1]
        taskMgr.add(ClientManager, 'ClientManager')
        # start the turn timer
        app.turnTimer = OnscreenText(text="Turn Timer ",
                                     style=1, fg=(1, 1, 1, 1),
                                     pos=(0, 0.9),
                                     align=TextNode.ACenter,
                                     scale = .07,
                                     mayChange = True)
        taskMgr.add(turnTimerTask, 'turnTimerTask')
        return task.done
    else:
        return task.cont


def ServerManager(task):
    if app.server.cReader.dataAvailable():
        data = app.server.getData()
        updateWorld(data[0])
    return task.again


def ClientManager(task):
    if app.client.cReader.dataAvailable():
        data = app.client.getData()
        updateWorld(data[0])
    return task.again

###################################################
#                                                 #
#     AI methods                                  #
#                                                 #
###################################################


# returns closest opponent
def find_opponent(teams, character):
    least_distance = 999999999
    closest_opponent = None
    for team in teams:
        # skips character's team.
        if team == character.team:
            continue
        for other_character in team.characters:
            # skips dead characters
            if other_character.is_dead:
                continue
            # checks between all opponents and returns the closest opponent
            distance = tile_distance_squared(other_character.tile, character.tile)
            if distance < least_distance:
                least_distance = distance
                closest_opponent = other_character
    return closest_opponent

###################################################
#                                                 #
#     Finite State Machine                        #
#                                                 #
###################################################


class PlayState(FSM.FSM):
    def __init__(self, name):
        # sends the init function of FSM the argument name which was given to PlayState
        FSM.FSM.__init__(self, name)
        self.character = None
        self.attackTiles = []
        self.movement_candidates = []
        self.font = loader.loadFont('images/consola.ttf')

    ########################################################################################################################
    #                                                                                                                      #
    #                    Network handling states:                                                                          #
    #                                                                                                                      #
    #   Await:           handle the connection for the server                                                              #
    #   Connecting:      handle the connection for the client                                                              #
    ########################################################################################################################

    # Await is for server to wait for client connection
    def enterAwait(self):
        localIP = socket.gethostbyname(socket.gethostname())
        app.messageWindow = OnscreenText(text='Waiting for opponent\n' + str(localIP),
                                         fg=(1, 1, 1, 1),
                                         font=self.font,
                                         pos=(0, 0, 0),
                                         scale=0.07,
                                         mayChange=True)
        base.setBackgroundColor(0, 0, 0)
        app.exitButton = DirectButton(text=("Cancel", "Cancel", "Cancel", "disabled"),
                                      text_fg=(0, 0, 1, 1),
                                      text_scale=.5,
                                      text_font=self.font,
                                      frameColor=(0, 0, 0, 0),
                                      scale=.20,
                                      pos=(0, 0, -0.6),
                                      command=app.cancelServer)

        app.serverStart()

    def exitAwait(self):
        app.messageWindow.destroy()
        app.exitButton.destroy()

    # connecting state is for client to connect
    def enterConnecting(self):
        localIP = socket.gethostbyname(socket.gethostname())
        app.exitButton = DirectButton(text=("Cancel", "Cancel", "Cancel", "disabled"),
                                      text_fg=(0, 0, 1, 1),
                                      text_scale=.5,
                                      text_font=self.font,
                                      frameColor=(0, 0, 0, 0),
                                      scale=.20,
                                      pos=(0, 0, -0.6),
                                      command=app.cancelClient)
        app.ipInput = DirectEntry(text="",
                                  initialText=localIP,
                                  text_font=self.font,
                                  scale=.05,
                                  focus=1,
                                  command=app.connectClient)
        base.setBackgroundColor(0, 0, 0)

    def exitConnecting(self):
        app.ipInput.destroy()
        app.exitButton.destroy()

    def enterTitle(self):         # displays the "menu" of the game when initiated
        if app.instruction:
            app.instruction.destroy()
        app.singleButton = DirectButton(text=("Single Player", "Single Player", "Single Player", "disabled"),
                                        text_fg=(1, 1, 1, 1),
                                        text_scale=.5,
                                        text_font=self.font,
                                        frameColor=(0, 0, 0, 0),
                                        scale=.20,
                                        pos=(0, 0, 0.3),
                                        command=app.single)
        app.createButton = DirectButton(text=("Create Room", "Create Room", "Create Room", "disabled"),
                                        text_fg=(1, 1, 1, 1),
                                        text_scale=.5,
                                        text_font=self.font,
                                        frameColor=(0, 0, 0, 0),
                                        scale=.20,
                                        pos=(0, 0, 0),
                                        command=app.await)
        app.joinButton = DirectButton(text=("Join Room", "Join Room", "Join Room", "disabled"),
                                      text_fg=(1, 1, 1, 1),
                                      text_scale=.5,
                                      text_font=self.font,
                                      frameColor=(0, 0, 0, 0),
                                      scale=.20,
                                      pos=(0, 0, -0.3),
                                      command=app.connect)
        app.exitButton = DirectButton(text=("Exit", "Exit", "Exit", "disabled"),
                                      text_fg=(1, 1, 1, 1),
                                      text_scale=.5,
                                      text_font=self.font,
                                      frameColor=(0, 0, 0, 0),
                                      scale=.20,
                                      pos=(0, 0, -0.6),
                                      command=sys.exit)
        app.background = OnscreenImage(parent=render2d, image="images/title1.png")
        base.cam2dp.node().getDisplayRegion(0).setSort(-20)
        # when back to title, it disconnect the internet
        if app.player == 'client':
            app.clientEnd()
        elif app.player == 'server':
            app.serverEnd()
        # reinit the player status
        app.player = None
        # music here
        if app.backgroundMusic:
            # if the background music is still playing, aka right after the game ends and back to the title
            if app.backgroundMusic.status() == app.backgroundMusic.PLAYING and app.backgroundMusic.getName() == "Five Armies.mp3":
                # start title music
                app.backgroundMusic.stop()
                app.backgroundMusic = loader.loadSfx("sounds/Darkest Child.mp3")
                app.backgroundMusic.setLoop(True)
                app.backgroundMusic.play()
        else:
            # init the title music
            app.backgroundMusic = loader.loadSfx("sounds/Darkest Child.mp3")
            app.backgroundMusic.setLoop(True)
            app.backgroundMusic.play()

    def exitTitle(self):
        # destroy has something to do with DirectGUI
        app.singleButton.destroy()
        app.createButton.destroy()
        app.joinButton.destroy()
        app.exitButton.destroy()
        app.background.destroy()
        if app.winner:
            app.winner.destroy()

    # this is the Winner's screen
    def enterWinner(self):
        if app.backgroundMusic.status() == app.backgroundMusic.PLAYING and app.backgroundMusic.getName() == "Five Armies.mp3":
                # start title music
                app.backgroundMusic.stop()
                app.backgroundMusic = loader.loadSfx("sounds/Heroic Age.mp3")
                app.backgroundMusic.setLoop(True)
                app.backgroundMusic.play()
        app.ggButton = DirectButton(text=("GG", "GG", "GG", ""),
                                    text_fg=(0, 0, 1, 1),
                                    text_scale=.5,
                                    text_font=self.font,
                                    frameColor=(0, 0, 0, 0),
                                    scale=.20,
                                    pos=(0, 0, -0.2),
                                    command=app.GG)
        app.singleButton = DirectButton(text=("Victory", "Victory", "Victory", "disabled"),
                                        text_fg=(0, 0, 1, 1),
                                        text_scale=.5,
                                        text_font=self.font,
                                        frameColor=(0, 0, 0, 0),
                                        scale=.20,
                                        pos=(0, 0, 0.2),
                                        command=app.BackToTitle)

    def exitWinner(self):
        app.turnText.destroy()
        app.objectiveTeam1.destroy()
        app.objectiveTeam2.destroy()
        app.turnTimer.destroy()
        app.ggButton.destroy()
        app.singleButton.destroy()

    # this is the loser's screen
    def enterLoser(self):
        app.singleButton = DirectButton(text=("Defeat", "Defeat", "Defeat", "disabled"),
                                        text_fg=(0, 0, 1, 1),
                                        text_scale=.5,
                                        text_font=self.font,
                                        frameColor=(0, 0, 0, 0),
                                        scale=.20,
                                        pos=(0, 0, 0.2),
                                        command=app.BackToTitle)

    def exitLoser(self):
        app.turnText.destroy()
        app.objectiveTeam1.destroy()
        app.objectiveTeam2.destroy()
        app.turnTimer.destroy()
        app.singleButton.destroy()

    ########################################################################################################################
    #                                                                                                                      #
    #                    In-Game handling states:                                                                          #
    #                                                                                                                      #
    #   TurnManager:    handles assigning to Plan state for both players along with PlayMove state and back to Title state #
    #   Plan:           handles movement UI, sends out information to other player and goes back to TurnManager            #
    #   RotationPlan:   handels rotation ui, sends out information to other player and goes back to TurnManager            #
    #   PlayMove:       handles executing movement of characters.                                                          #
    #   PlayAttack:     handles auto-attack of characters.                                                                 #
    ########################################################################################################################

    def enterTurnManager(self):
        if not app.instruction:
            app.instruction = OnscreenText(text='Click a Character(little star with horn) to control a character.\nYou can control the camera with the right mouse button\nand zoom with the mouse wheel.',
                                           fg=(0.7, 0.7, 0.9, 1),
                                           font=self.font,
                                           align=TextNode.ALeft,
                                           pos=(-1, -0.7, 0),
                                           scale=0.055,
                                           mayChange=True)
        else:
            app.instruction.setText('Try to capture the objective (center grey tile) or eliminate the enemy to win!\nYou can control the camera with the right mouse button\nand zoom with the mouse wheel.')
        taskMgr.add(setVisions, 'setVisions')
        # play laugn sound when turn starts
        if app.backgroundMusic.status() == app.backgroundMusic.READY:
            app.backgroundMusic = loader.loadSfx("sounds/Five Armies.mp3")
            app.backgroundMusic.setLoop(True)
            app.backgroundMusic.play()
        if app.turnStart:
            mySound = loader.loadSfx("sounds/laugh.mp3")
            laugh = SoundInterval(mySound, 0)
            laugh.start()
            app.turnStart = False
            taskMgr.add(turnTimerTask, 'turnTimerTask')
        # initiate the mouse task(aka giving player mouse control)
        app.mouse.task = app.mouse.hover
        taskMgr.add(TurnCleanUp, 'TurnCleanUp')
        taskMgr.add(actionChecker, 'actionChecker')

    def exitTurnManager(self):
        taskMgr.remove('setVisions')
        app.mouse.task = None
        if app.mouse.hovered_object:
            app.mouse.hovered_object.unhover()
            app.mouse.hovered_object = None
        taskMgr.remove('TurnCleanUp')
        taskMgr.remove('actionChecker')

    def filterTurnManager(self, request, args):
        # when mouse left click case
        if request != 'Title' and request == 'mouse1':
            # find the object that mouse is on
            selected = app.mouse.hovered_object
            # if user clicks on a character
            if isinstance(selected, Character):
                # and the character doesn't have an action yet
                if not selected.rotated and not selected.ghost:
                #if not selected.isGhost:
                    if not app.singlePlayer:
                        # and this character is from player's team or is being Mind Controlled
                        if selected.team == app.playerStats[app.player]:
                            app.state.request('Plan', selected)
                    else:
                        if selected.team.name == 'Team 1':
                            # to SOTO: this is for single player mode, of course player only control team 1
                            app.state.request('Plan', selected)
        # for some weird reason this is still useful, maybe find out why?
        if request in ['Plan', 'RotationPlanning', 'PlayMove', 'AITeam']:
            return request
        if request in ['Winner', 'Loser']:
            taskMgr.remove('turnTimerTask')
            return request
        if request == 'Title':
            taskMgr.remove('turnTimerTask')
            app.turnText.destroy()
            app.objectiveTeam1.destroy()
            app.objectiveTeam2.destroy()
            app.turnTimer.destroy()
            return request

    # Plan phase; think big, think deep hmmm...
    def enterPlan(self, character):
        app.instruction.setText('Planning your move: Click on blue tile to command your character to move.')
        app.mouse.task = app.mouse.hover
        self.character = character
        self.movement_candidates = find_nearby(app.world.terrain, character.x, character.y, MOVE_DISTANCE)
        app.cancelButton = DirectButton(text=("Cancel", "Cancel", "Cancel", "Cancel"),
                                        text_fg=(0, 0, 1, 1),
                                        text_scale=.5,
                                        text_font=self.font,
                                        frameColor=(0, 0, 0, 0),
                                        scale=.20,
                                        pos=(0, -0.8, 0.8),
                                        command=app.cancelPlan,
                                        clickSound=loader.loadSfx("sounds/boring.mp3"))
        for tile in self.movement_candidates:
            if app.getImageInhibants(tile):
                self.movement_candidates.remove(tile)
        for tile in self.movement_candidates:
            if tile.material != 'objective':
                tile.nodePath.setColor(0.5, 0.6, 1.0)  # sets color of potential movement locations
                if app.world.terrain.hoveredTile == tile:
                    tile.nodePath.setColor(0.75, 0.9, 1.5)

    # After decided a move, unhighlight all the hightlighted tiles
    def exitPlan(self):
        app.mouse.task = None
        if app.mouse.hovered_object:
            app.mouse.hovered_object.unhover()
            app.mouse.hovered_object = None
        for tile in self.movement_candidates:
            if tile.material != 'objective':
                tile.change_material(tile.material)
        app.cancelButton.destroy()
        self.movement_candidates = None
        self.character = None

    # moves character/attacks enemy or returns "Title" or none
    def filterPlan(self, request, args):
        if request == 'Title':
            return 'Title'
        if request in ['PlayMove', 'AITeam', 'TurnManager']:
            return request
        # when user left-click
        if request == 'mouse1':
            # find the tile that mouse is on
            selected = app.mouse.hovered_object
            # if user did not click anything on tile nor character, nothing happen
            if not selected:
                return None
            if isinstance(selected, Tile):
                #if the selected tile is a move candidate, and does not have a ghost nor another person in  that tile then move to that tile
                if selected in self.movement_candidates and not app.getImageInhibants(selected):
                    self.character.path = HexPathFinding(app.world.terrain, self.character, selected)
                    # create a ghost on selected tile
                    self.ghost = Character(app.world.terrain, self.character.team, self.character.id, selected.x, selected.y, True)
                    self.ghost.init_nodepath()
                    app.ghosts.append(self.ghost)
                    if not app.singlePlayer:
                        if app.player == 'server':
                            app.server.broadcastData(encodeInfo(self.character, 'Move', selected))
                        elif app.player == 'client':
                            app.client.sendData(encodeInfo(self.character, 'Move', selected))
                    return ('RotationPlanning', self.character)
            elif isinstance(selected, Character):
                #if the selected tile is a move candidate, and does not have a ghost nor another person in  that tile then move to that tile
                if selected.tile in self.movement_candidates and not selected.ghost:
                    self.character.path = HexPathFinding(app.world.terrain, self.character, selected.tile)
                    # create a ghost on selected tile
                    self.ghost = Character(app.world.terrain, self.character.team, self.character.id, selected.x, selected.y, True)
                    self.ghost.init_nodepath()
                    app.ghosts.append(self.ghost)
                    if not app.singlePlayer:
                        if app.player == 'server':
                            app.server.broadcastData(encodeInfo(self.character, 'Move', selected.tile))
                        elif app.player == 'client':
                            app.client.sendData(encodeInfo(self.character, 'Move', selected.tile))
                    return ('RotationPlanning', self.character)
        return None

    def enterRotationPlanning(self, character):
        app.instruction.setText('Planning your attack:\nClick on the red tile to aim your character.')
        app.mouse.task = app.mouse.hover
        # find the ghost by given character id
        for ghost in app.ghosts:
            if ghost.id == character.id:
                self.ghost = ghost
        self.rotation_candidates = find_nearby(app.world.terrain, self.ghost.x, self.ghost.y, 1)
        # highlights positions to rotate to
        for tile in self.rotation_candidates:
            if tile.material != 'objective':
                tile.nodePath.setColor(1.0, 0.6, 0.5)
                if app.world.terrain.hoveredTile == tile:
                    tile.nodePath.setColor(1.5, 0.9, 0.75)
        app.cancelButton = DirectButton(text=("Cancel", "Cancel", "Cancel", "Cancel"),
                                        text_fg=(0, 0, 1, 1),
                                        text_scale=.5,
                                        text_font=self.font,
                                        frameColor=(0, 0, 0, 0),
                                        scale=.20,
                                        pos=(0, -0.8, 0.8),
                                        command=app.cancelMove,
                                        extraArgs=[character],
                                        clickSound=loader.loadSfx("sounds/boring.mp3"))

    def exitRotationPlanning(self):
        app.mouse.task = None
        if app.mouse.hovered_object:
            app.mouse.hovered_object.unhover()
            app.mouse.hovered_object = None
        for tile in self.rotation_candidates:
            if tile.material != 'objective' and tile not in self.attackTiles:
                tile.change_material(tile.material)
        self.rotation_candidates = None
        self.ghost = None
        app.cancelButton.destroy()

    # allows ghost ghost to rotate
    def filterRotationPlanning(self, request, args):
        if request == 'Title':
            return 'Title'
        if request in ['PlayMove', 'AITeam', 'TurnManager']:
            return request
        if request == 'mouse1':
            # find the tile that mouse is on
            selected = app.mouse.hovered_object
            if not selected:
                return None
            if isinstance(selected, Tile):
                if selected in self.rotation_candidates:
                    self.ghost.setRotation(selected)
                    self.ghost.rotate()

                    if selected != self.ghost.tile:
                        # highlight the front 3 tiles
                        self.attackTiles.extend(find_line_of_sight(self.ghost.tile, selected, 3))

                        for attackTile in self.attackTiles:
                            if attackTile.material != 'objective':
                                attackTile.nodePath.setColor(VBase4(0.7, 0, 0, 1))

                        # update the character rotation tile without moving actual character
                        app.world.teams[self.ghost.team.index].characters_dict[self.ghost.id].setRotation(selected)
                        if not app.singlePlayer:
                            if app.player == 'server':
                                app.server.broadcastData(encodeInfo(self.ghost, 'Rotate', selected))
                            elif app.player == 'client':
                                app.client.sendData(encodeInfo(self.ghost, 'Rotate', selected))
                        # what about single player mode!!!!!!
                        return 'TurnManager'
            elif isinstance(selected, Character):
                if selected.tile in self.rotation_candidates:
                    self.ghost.setRotation(selected.tile)
                    self.ghost.rotate()

                    if selected.tile != self.ghost.tile:
                        # highlight the front 3 tiles
                        self.attackRange = find_line_of_sight(self.ghost.tile, selected.tile, 3)

                        for attackTile in self.attackRange:
                            if attackTile.material != 'objective':
                                attackTile.nodePath.setColor(VBase4(0.7, 0, 0, 1))

                        # update the character rotation tile without moving actual character
                        app.world.teams[self.ghost.team.index].characters_dict[self.ghost.id].setRotation(selected.tile)
                        if not app.singlePlayer:
                            if app.player == 'server':
                                app.server.broadcastData(encodeInfo(self.ghost, 'Rotate', selected.tile))
                            elif app.player == 'client':
                                app.client.sendData(encodeInfo(self.ghost, 'Rotate', selected.tile))
                        # what about single player mode!!!!!!
                        return 'TurnManager'
        return None

    def enterPlayMove(self):
        for tile in self.attackTiles:
            tile.change_material(tile.material)
        self.attackTiles = []
        app.instruction.setText('Move Execution: Characters will now move in accordance with your commands.\nCaution! Characters can collide with the enemy!')
        taskMgr.add(setVisions, 'setVisions')
        taskMgr.remove('turnTimerTask')
        for ghost in app.ghosts:
            ghost.nodePath.setTransparency(0)
        #kills off ghosts
        for ghost in app.ghosts:
            ghost.die()
        app.ghosts = []
        taskMgr.add(ExecuteMoves, 'ExecuteMoves')

    def exitPlayMove(self):
        taskMgr.remove('ExecuteMoves')

    def enterPlayAttack(self):
        app.instruction.setText('Attack Execution: Charge and attack for glory!')
        taskMgr.add(ExecuteAttacks, 'ExecuteAttacks')

    def exitPlayAttack(self):
        taskMgr.remove('ExecuteAttacks')

    def enterCheckObjectives(self):
        taskMgr.add(checkObjective, 'checkObjective')

    def exitCheckObjectives(self):
        # where turn actually ends
        # init all the turn stuff here
        # increment the turn counter by one and change the turn text
        taskMgr.remove('setVisions')
        app.turnCounter += 1
        app.turnText.setText("Turn " + str(app.turnCounter))
        app.turnStart = True
        app.playedReminder = False
        for team in app.world.teams:
            for character in team.characters:
                character.attacked = False
        taskMgr.remove('checkObjective')

    # AI
    def enterAITeam(self):
        movedTiles = []
        for character in app.world.teams[1].characters:
            player = find_opponent(app.world.teams, character)
            self.movement_candidates = find_nearby(app.world.terrain, character.x, character.y, MOVE_DISTANCE)
            self.attack_candidates = find_nearby(app.world.terrain, character.x, character.y, 1)
            # sets AI to attack if enemy is near
            if player.tile in self.attack_candidates:
                character.setRotation(player.tile)
            else:
                shortest_distance = 10000000
                closest_tile = None
                for tile in self.movement_candidates:
                    vector = Point2(tile.x, tile.y) - Point2(player.x, player.y)
                    distance = vector.lengthSquared()
                    if distance < shortest_distance and distance > 0 and tile not in movedTiles:
                        shortest_distance = distance
                        closest_tile = tile
                character.path = HexPathFinding(app.world.terrain, character, closest_tile)
                movedTiles.append(closest_tile)
                if player.tile in find_nearby(app.world.terrain, closest_tile.x, closest_tile.y, 1):
                    character.setRotation(player.tile)
        self.demand('PlayMove')

    def exitAITeam(self):
        # unhighlight tiles
        for tile in self.movement_candidates:
            if tile.material != 'objective':
                tile.change_material(tile.material)
        self.movement_candidates = None
        self.attack_candidates = None
        self.character = None


class PlayMouse(Mouse):
    pass

###################################################
#                                                 #
#     PlayApp                                     #
#                                                 #
###################################################


class PlayApp(DirectObject):               # step1
    def __init__(self):
        base.disableMouse()                # disables mousebased camera function. must be disabled in order to  position for the camera via code.
        self.world = World()               # step2a World() class located in init__.py
        self.mouse = PlayMouse(self)       # step2b PlayMouse() located in play.py
        self.state = PlayState('state')    # step2c Playstate has __init__(self, Name)
        self.accept("escape", sys.exit)            # Escape quits
        self.accept("m", MuteUnmute)            # Escape quits
        # networking setting
        self.port = 9099
        self.server = None
        self.client = None
        # gui components
        self.winner = None
        self.createButton = None
        self.joinButton = None
        self.singleButton = None
        self.ipAddress = None
        self.background = None
        self.messageWindow = None
        self.exitButton = None
        self.turnText = None
        # using for networking stats
        self.playerStats = {}
        self.player = None
        self.singlePlayer = False
        # image character to determine where character is moving
        self.ghosts = []
        # number of characters on field
        self.characterCount = 0
        self.turnCounter = 10000000
        # music variable
        self.backgroundMusic = None
        self.muted = False
        self.turnStart = True
        # timer
        self.turnTimer = None
        self.playedReminder = False
        # objective text
        self.objectiveTeam1 = None
        self.objectiveTeam2 = None
        # cancel button
        self.cancelButton = None
        # instruction
        self.instruction = None

        # TODO: testing purpose: showing FPS method
        base.setFrameRateMeter(True)

    def getImageInhibants(self, tile):
        characters = []
        for character in self.ghosts:
            if character.is_dead:
                continue
                # how many characters can even be in a tile? MORE THAN 1 SO FAR
            if (character.x, character.y) == (tile.x, tile.y):
                characters.append(character)
        return characters

    def single(self):
        def load():
            # clean up the previous world
            app.delete_world()
            F = open('debug.hm', 'rb')  # load the preset map
            app.world = cPickle.load(F)
            F.close()
            app.world.position_camera()
            app.singlePlayer = True
            # init the health bar and parent to the character
            for team in app.world.teams:
                for character in team.characters:
                    character.init_healthBar()
            app.state.request('TurnManager')
            app.characterCount = len(app.world.teams[0].characters) + len(app.world.teams[1].characters)
            # start the turn counter
            app.turnCounter = 1
            app.turnText = OnscreenText(text="Turn " + str(app.turnCounter),
                                        style=1, fg=(1, 1, 1, 1),
                                        pos=(0, -0.95),
                                        align=TextNode.ACenter,
                                        scale = .07,
                                        mayChange = True)
            app.objectiveTeam1 = OnscreenText(text="Team 1: " + str(app.world.teams[0].TurnsToWin),
                                              style=1, fg=(1, 1, 1, 1),
                                              pos=(-0.3, -0.95),
                                              align=TextNode.ACenter,
                                              scale = .07,
                                              mayChange = True)
            app.objectiveTeam2 = OnscreenText(text="Team 2: " + str(app.world.teams[1].TurnsToWin),
                                              style=1, fg=(1, 1, 1, 1),
                                              pos=(0.3, -0.95),
                                              align=TextNode.ACenter,
                                              scale = .07,
                                              mayChange = True)
        app.backgroundMusic.stop()
        load()
        app.turnTimer = OnscreenText(text="Turn Timer ",
                                     style=1, fg=(1, 1, 1, 1),
                                     pos=(0, 0.9),
                                     align=TextNode.ACenter,
                                     scale = .07,
                                     mayChange = True)
        taskMgr.add(turnTimerTask, 'turnTimerTask')

    # Networking functions
    def await(self):
        self.state.request('Await')

    def connect(self):
        self.state.request('Connecting')

    def cancelServer(self):
        app.serverEnd()
        self.state.request('Title')

    def cancelClient(self):
        app.clientEnd()
        self.state.request('Title')

    def serverStart(self):
        # Start our server up
        self.server = Server(self.port, compress=True)
        # Create a task to handle any incoming data
        taskMgr.add(ServerStarter, "ServerStarter")

    # disconnect server
    def serverEnd(self):
        self.server.disconnect(self.port)
        taskMgr.remove("ServerStarter")
        taskMgr.remove("ServerManager")

    def connectClient(self, ipAddress):
        self.ipInput.destroy()
        self.client = Client(ipAddress, self.port, compress=True)
        taskMgr.add(ClientStarter, "ClientStarter")

    # client disconnect
    def clientEnd(self):
        taskMgr.remove("ClientStarter")
        taskMgr.remove("ClientManager")

    # clears world
    def delete_world(self):
        self.world.clear()

    def cancelPlan(self):
        app.state.demand('TurnManager')

    def cancelMove(self, character):
        # find the ghost by given character id
        for ghost in app.ghosts:
            if ghost.id == character.id:
                self.ghosts.remove(ghost)
                ghost.die()
        character.path = None
        app.state.demand('TurnManager')

    def BackToTitle(self):
        self.state.demand('Title')

    def GG(self):
        mySound = loader.loadSfx("sounds/GG.mp3")
        GG = SoundInterval(mySound, 0)
        GG.start()
        self.ggButton["state"] = DGG.DISABLED


app = PlayApp()         # start PlayApp() located in play.py
app.state.request('Title')  # app starts state with Title
run()
