# stskit

_stskit_ provides a Python interface and visualization plug-ins for Stellwerksim.
[Stellwerksim](https://www.stellwerksim.de) is a collaborative online railroad traffic controller simulation game.
The stskit project implements a plugin client interface in the Python language providing access to game data for visualization and analysis.
The project includes the client code that you can use in your own developments as well as the _sts-charts_ program that may help you to play Stellwerksim more efficiently.

# Main features

The plugin client interface exposes the complete Stellwerksim plugin interface in a Python object structure. All client-server communication is asynchronous, based on the [trio](https://trio.readthedocs.io/en/stable/index.html) library.

_sts-charts_ is a graphical demo program with the following components:

- Detailed track occupancy diagram. Possible conflicts and coupling maneuvers are highlighted. Delays are estimated based on original data and adjusted at long stops.
- Arrival and departure diagrams
- Event ticker
- Network graph (experimental)

The project lays a focus on analyzing original schedule data, effective run times and (as low as possible) user configuration to visualize important data for efficient train disposition.

# Requirements and Installation

stskit requires [Python](https://www.python.org/) 3.8 or higher. The [Miniconda](https://docs.conda.io/en/latest/miniconda.html) distribution is recommended. All required packages are readily available from Conda or [PyPI](https://pypi.org/).

For installation, see the [Installation](https://github.com/topological-state/stskit/wiki/Installation) page.

# License

Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0) <http://creativecommons.org/licenses/by-nc-sa/4.0/>

# Contributing

Contributions are welcome in all aspects of the project, most urgently in the development of the Qt-based user interface.
