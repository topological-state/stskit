
# STSkit / STSdispo

_STSkit_ provides graphical data analysis tools such as graphical timetable, track allocation and connection matrix
that help you to play [Stellwerksim](https://www.stellwerksim.de) more efficiently.
[Stellwerksim](https://www.stellwerksim.de) is a collaborative online railroad traffic controller simulation game.

_STSkit_ also implements a plugin client interface in Python that you can use in your own plugin development.

### Main features

The main program _STSdispo_ features the following graphical modules:

- Graphical and textual timetables
- Track allocation diagram
- Entrance/Exit tables
- Connection matrix
- Shunting table
- Event ticker
- Network graph (experimental)

The project lays a focus on analyzing original schedule data, effective run times and (as low as possible) user configuration to visualize important data for efficient train disposition.

The plugin client interface exposes the complete [Stellwerksim plugin interface](https://doku.stellwerksim.de/doku.php?id=stellwerksim:plugins:spezifikation) in a Python object structure. All client-server communication is asynchronous, based on the [trio](https://trio.readthedocs.io/en/stable/index.html) library.

Like Stellwerksim, the user interface and documentation are in German.

