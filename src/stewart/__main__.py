"""Select this installation, then enter the shared isolated manager bootstrap.

Use ``<venv-python> -I -m stewart``. Python loads the selected installation's
__init__/__main__ before this handoff; those files and interpreter site hooks
are startup trust roots. The console launcher isolates before any package import.
Importing this module for discovery performs no operations.
"""

if __name__ == "__main__":
    import os
    from pathlib import Path
    import sys

    bootstrap = str(Path(__file__).with_name("_bootstrap.py"))
    os.execv(sys.executable, [sys.executable, "-I", "-B", bootstrap, "source", "--", *sys.argv[1:]])
