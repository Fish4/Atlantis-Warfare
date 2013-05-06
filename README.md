Project Atlantis Warfare
========================
### by Fish 4 Entertainment

1v1 __Simultaneous__ Turn-Based Strategy Game made with Panda3D

Announcement
------------

The first release version is out. Please take your time and enjoy it!
We welcome any feedback to improve our next iteration.

Game Instruction
----------------

Game goal:

	1. Kill the other team
	2. Capture the objective

Game controls:
	
	1. Mouse left-click to select
	2. Mouse right-click to rotate camera
	3. Mouse wheel to zoom-in and out
	4. M to mute/unmute music
	5. ESC to quit game

Game States:

	Select a character to start the __Planning__ sequence:

	1. Move Planning
		* Plan your move ahead of time
	2. Attack Planning
		* Predict where enemy is going to be located
	
	After all character already have actions or timeup, game system will execute all the move from the planning phase simultaneously.  
	The result might differ from player's expectation because of the unit collision

	The __Execution__ sequence is as following:

	1. Execute all the moves with collisions
	2. If character has not been collided(interrupted), execute character's attack

	After the __Execution__ sequence, comes the __objective__ sequence:

	* If character is standing on the objective and not being attacked; the character captured the objective successfully for 1 turn

Networking:

	So far the network option may only be used for lan internet connection.
	In order to connect to others, you have to type in the other computer's ip address, which may be shown on his screen, and click 'enter'
	And, if the connection has been established, the network game starts.

---

#### Current schedule: :scream_cat:

First release is released at 3/20/2013  
Here is the [download link](https://mega.co.nz/#!WhBHEBLC!H_6OkxCyX57_aJEAHfznKAeQsvBurIC4hM9zb3gp2iU)

#### Reference page:

[hexabots](http://code.google.com/p/hexabots/)

#### File Structure:

Documents/
> store all documents files (images for presentations as well)

hexabots/
> hexagon, tile, player, team, mouse, and world methods
> in short, mostly game methods

models/
> all models goes here

sounds/
> all the sounds

images/
> all the used images

network/
> all the network methods

edit.py
> map editor
> commands: l to load, s to save, d to delete, c to create

play.py
> game play

README.md
 > README file

debug.hm
> map information