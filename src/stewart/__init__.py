"""Shared custody for managed audits.

The package owns assignment initialization, preparation of a disposable
detached checkout, evidence collection, collection-bound triage and retention,
paused-session resume, a read-only session view, an optional bounded
experiment wrapper with its comparison ledger, and closing a finished or
abandoned audit. It never launches an agent, runs project tests or commits;
only ``close`` deletes, and only what its closing record or a resource claim
it wrote authorizes.

Importing this package performs no repository, process, network or host work.
The callable surface in ``stewart.api`` resolves lazily, and ``--help``
never touches a session. Experiment children receive the standalone ledger
through the pinned launcher's reserved ``_stewart_ledger_v1`` module.

Canonical command::

    <venv>/bin/stewart --help
    <venv>/bin/python -I -m stewart --help
"""
