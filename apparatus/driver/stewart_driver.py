#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent black-box acceptance driver for Stewart (entrypoint).

    python3 -I -B apparatus/driver/stewart_driver.py --list
    python3 -I -B apparatus/driver/stewart_driver.py --self-test
    python3 -I -B apparatus/driver/stewart_driver.py \\
        --binary /abs/stewart --test-binary /abs/stewart-test \\
        --evidence /abs/new-evidence-folder [--case PATTERN]... [--exclude PATTERN]...

The driver is several modules in this directory: driver_core (framework),
rawjson, answer_witness, fake_provider, reacting_auditor, procedure and run_support
(run support), and the case modules cases_*.py, imported here in name order. A new
group of cases is a new cases_<name>.py file; nothing here needs editing.
See apparatus/README.md for the cases, their controls and the evidence.
"""
import os
import sys

# `python3 -I` does not put the script's directory on sys.path, so the driver's
# own modules would not be importable. Add exactly this directory, first, and
# nothing else: no PYTHONPATH, no current directory, no site packages.
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import driver_core  # noqa: E402

# Support modules register their self-tests on import.
import rawjson  # noqa: E402,F401
import answer_witness  # noqa: E402,F401
import fake_provider  # noqa: E402,F401
import reacting_auditor  # noqa: E402,F401
import run_support  # noqa: E402,F401
import procedure  # noqa: E402,F401


def load_case_modules():
    """Import every cases_*.py beside this file, in name order; each registers its cases."""
    import importlib
    names = sorted(n[:-3] for n in os.listdir(HERE)
                   if n.startswith("cases_") and n.endswith(".py") and n[:-3].isidentifier())
    for name in names:
        importlib.import_module(name)
    return names


if __name__ == "__main__":
    load_case_modules()
    sys.exit(driver_core.main())
