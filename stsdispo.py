# nuitka-project: --enable-plugin=pyside6
# nuitka-project: --static-libpython=no
# nuitka-project: --include-data-files=stskit/mplstyle/*.mplstyle=stskit/mplstyle/
# nuitka-project: --include-data-files=stskit/qt/*.css=stskit/qt/
# nuitka-project: --include-data-files=stskit/qt/*.ui=stskit/qt/
# nuitka-project: --include-data-files=stskit/config/*.json=stskit/config/

# Compilation mode, standalone everywhere, except on macOS there app bundle
# nuitka-project: --mode=app
#
# Debugging options, controlled via environment variable at compile time.
# nuitka-project-if: {OS} == "Windows" and os.getenv("DEBUG_COMPILATION", "no") == "yes"
#     nuitka-project: --windows-console-mode=hide
# nuitka-project-else:
#     nuitka-project: --windows-console-mode=disabled

# to compile with nuitka:
# uv run python -m nuitka --standalone stsdispo.py
# or:
# uv run python -m nuitka --onefile stsdispo.py


from stskit.__main__ import main

if __name__ == '__main__':
    main()
