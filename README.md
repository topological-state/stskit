# stskit

_stskit_ provides graphical data analysis tools such as graphical timetable, track allocation and connection matrix
that help you to play [Stellwerksim](https://www.stellwerksim.de) more efficiently.
[Stellwerksim](https://www.stellwerksim.de) is a collaborative online railroad traffic controller simulation game.

_stskit_ also implements a plugin client interface in Python that you can use in your own plugin development.

# Main Features

The main program _sts-charts_ features the following visual components:

- Graphical and textual timetables
- Track allocation diagram
- Entrance/Exit tables
- Connection matrix
- Event ticker
- Network graph (experimental)

The project lays a focus on analyzing original schedule data, effective run times and (as low as possible) user configuration to visualize important data for efficient train disposition.

The plugin client interface exposes the complete Stellwerksim plugin interface in a Python object structure. All client-server communication is asynchronous, based on the [trio](https://trio.readthedocs.io/en/stable/index.html) library.

# Requirements and Installation

stskit requires [Python](https://www.python.org/) 3.8 or higher. The [Miniconda](https://docs.conda.io/en/latest/miniconda.html) distribution is recommended. All required packages are available from Conda or [PyPI](https://pypi.org/).

For installation and usage, see the [Wiki](https://github.com/topological-state/stskit/wiki) pages on GitHub.
