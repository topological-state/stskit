# STSkit and STSdispo

_STSkit_ provides plugins for the [Stellwerksim] railroad traffic controller simulation game.
The main program _STSdispo_ features live and interactive graphical timetable, track allocation and connection matrix modules
that help you to play [Stellwerksim] more efficiently.

The package also provides a plugin client interface in Python that you can use in your own plugin development.

[Stellwerksim]: https://www.stellwerksim.de

# Main Features

The main program _STSdispo_ features the following modules:

- Graphical and textual timetables
- Track allocation diagram
- Entrance/Exit tables
- Connection matrix
- Locomotive shunting schedule
- Event ticker
- Network graph (experimental)

The project sets a focus on analyzing original schedule data, effective run times, dependency tracking and automated configuration to visualize important data for efficient train disposition.

The plugin client interface exposes the complete [Stellwerksim plugin interface] in a Python object structure. 

[Stellwerksim plugin interface]: https://doku.stellwerksim.de/doku.php?id=stellwerksim:plugins:spezifikation

# Requirements and Installation

_STSkit_ requires [Python] 3.12 or higher. 
A virtual Python environment such as [uv] or [conda-forge] is highly recommended.
All required packages are available from [PyPI].

For installation and usage, see the [documentation on GitHub].

[Python]: https://www.python.org/
[uv]: https://docs.astral.sh/uv/
[conda-forge]: https://conda-forge.org/download/
[PyPI]: https://pypi.org/
[documentation on GitHub]: https://topological-state.github.io/stskit/de/installation/
