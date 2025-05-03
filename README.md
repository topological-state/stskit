# STSkit and STSdispo

_STSkit_ provides plugins for the [Stellwerksim](https://www.stellwerksim.de) railroad traffic controller simulation game.
The main program _STSdispo_ features live and interactive graphical timetable, track allocation and connection matrix modules
that help you to play [Stellwerksim](https://www.stellwerksim.de) more efficiently.

The package also provides a plugin client interface in Python that you can use in your own plugin development.

# Main Features

The main program _STSdispo_ features the following modules:

- Graphical and textual timetables
- Track allocation diagram
- Entrance/Exit tables
- Connection matrix
- Locomotive shunting schedule
- Event ticker
- Network graph (experimental)

The project lays a focus on analyzing original schedule data, effective run times, dependency tracking and automated configuration to visualize important data for efficient train disposition.

The plugin client interface exposes the complete [Stellwerksim plugin interface](https://doku.stellwerksim.de/doku.php?id=stellwerksim:plugins:spezifikation) in a Python object structure. All client-server communication is asynchronous, based on the [trio](https://trio.readthedocs.io/en/stable/index.html) library.

# Requirements and Installation

_STSkit_ requires [Python](https://www.python.org/) 3.8 or higher, the recommended version is 3.12. 
A virtual Python environment such as [uv](https://docs.astral.sh/uv/)
or [conda-forge](https://conda-forge.org/download/) is recommended.
All required packages are available from [PyPI](https://pypi.org/).

For installation and usage, see the [Wiki](https://github.com/topological-state/stskit/wiki) pages on GitHub.
