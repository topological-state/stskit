# nuitka-project: --enable-plugin=pyside6
# nuitka-project: --static-libpython=no
# nuitka-project: --include-data-files=stskit/mplstyle/*.mplstyle=stskit/mplstyle/
# nuitka-project: --include-data-files=stskit/qt/*.css=stskit/qt/
# nuitka-project: --include-data-files=stskit/qt/*.ui=stskit/qt/
# nuitka-project: --include-data-files=stskit/config/*.json=stskit/config/

# to compile with nuitka:
# uv run python -m nuitka --standalone stsdispo.py
# or:
# uv run python -m nuitka --onefile stsdispo.py


from stskit.__main__ import main

if __name__ == '__main__':
    main()
