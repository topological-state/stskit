# stskit
python-interface and visualization plug-ins for stellwerksim

stellwerksim (https://www.stellwerksim.de) is a collaborative online railroad traffic controller simulation game.
the stskit project implements a plugin client interface in the python language providing access to game data for visualization and analysis.
the project includes the client code that you can use in your own developments as well as a number of demo programs.

# main components

- stsplugin.py and stsobj.py: plugin client. provides the stellwerksim data interface to plugins.
- ticker.py: terminal-based event ticker demo program.
- main.py (and other modules): graphical demo program providing track occupancy diagrams and more.

# requirements

stskit requires python 3.8 or higher. the anaconda or miniconda distribution is recommended. for some requirements, pypi is needed.

# license
Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0) http://creativecommons.org/licenses/by-nc-sa/4.0/
