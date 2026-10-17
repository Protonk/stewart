"""Exercise an explicitly selected profile through production preparation.

Set STEWART_PROBE_REAL_HARNESS to an absolute profile file to spend a real
harness request. No containing repository's profile population is discovered.
This checks invocation compatibility; separate paired access probes qualify a
scope adapter's actual shell and file-tool boundaries.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil

import pytest

from stewart._json import loads_control
from stewart.launch_profile import PROFILE_NAME, validate_profile
from stewart.prepare import prepare
import stewart_support as support

pytestmark = [pytest.mark.system, pytest.mark.heavy]
OPT_IN = "STEWART_PROBE_REAL_HARNESS"


@pytest.mark.skipif(not os.environ.get(OPT_IN), reason=f"set {OPT_IN} to an explicit profile file; this spends a harness request")
def test_selected_profile_probe_passes_against_the_installed_harness(tmp_path, run_cmd):
    profile_path = Path(os.environ[OPT_IN])
    assert profile_path.is_absolute() and profile_path.is_file(), "select an absolute profile file, not a repository search"
    data = profile_path.read_bytes()
    profile = validate_profile(loads_control(data))
    assert profile["probe"] is not None, "the selected profile must declare a probe"
    assert shutil.which(profile["probe"][0]), "the selected harness executable must exist"
    checkout = support.make_checkout(tmp_path, run_cmd)
    (checkout.repo / support.WS / PROFILE_NAME).write_bytes(data)
    prepared = prepare(checkout.ws, checkout.prompt_commit())
    assert not (Path(prepared["worktree"]) / "tools").exists()
    block = prepared["probe_command"]
    result = run_cmd(["/bin/sh", "-c", block], cwd=tmp_path, env=dict(os.environ), timeout=300)
    assert result.returncode == 0 and "probe exit 0" in result.stdout, (
        f"the installed harness rejected the selected profile\n{block}\n"
        f"stdout:\n{result.stdout[-2000:]}\nstderr:\n{result.stderr[-2000:]}")
