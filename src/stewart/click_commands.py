"""Click-backed command leaves: the arguments, options and help of delegated commands.

``stewart.cli`` keeps the only command registry. Its root parser lists every
command, owns the global options and resolves the repository, reference and
request-key context. For a delegated command it hands over the remaining
tokens unparsed. This module parses them with Click and calls the existing
operation; ``stewart.cli.main`` renders the result and chooses the exit code.

Click is entered through ``make_context`` and ``invoke`` only. ``Command.main``
would also answer a ``_STEWART_COMPLETE`` completion request found in the
environment, turn an interrupt into ``Abort`` and exit 1 on a broken pipe, even
outside standalone mode, so it is never called. This is the only module that
imports Click; ``stewart.cli`` imports it only when a delegated command runs.
"""
from __future__ import annotations

import click

from stewart._bootstrap import EXIT_OK, StewartError
from stewart.docs import DOCUMENTS

#: argparse offers ``-h`` beside ``--help``; delegated commands keep both.
_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.command("docs", context_settings=_SETTINGS)
# A named metavar keeps Click from wrapping the usage line inside a document name.
@click.argument("document", metavar="DOCUMENT", type=click.Choice(sorted(DOCUMENTS)),
                help="One of: " + ", ".join(sorted(DOCUMENTS)) + ".")
def docs(document: str) -> tuple[dict, int]:
    """Print a bundled document or role template.

    No repository is read or written.
    """
    from stewart.docs import document as bundled
    return bundled(document), EXIT_OK


@click.command("request", context_settings=_SETTINGS)
@click.option("--key", required=True, metavar="KEY", help="The request key to inspect, as given to --request-key.")
@click.pass_obj
def request(resolved: dict, key: str) -> tuple[dict, int]:
    """Show a request key's binding, its attempts with their planned outputs, and its outcome.

    The outcome is completed, refused, in_progress, reserved, partial or
    unverifiable, with each output available, retired or missing now.
    Inspection never executes or resumes anything.
    """
    from stewart.request_keys import show
    result = show(resolved["repo"], key)
    return result, result["exit_code"]


#: Every delegated command by name; ``stewart.cli.build_parser`` lists each under that name.
COMMANDS = {command.name: command for command in (docs, request)}


def parse(name: str, tokens: list[str]) -> click.Context:
    """Parse a delegated command's own tokens.

    Help is printed to stdout and ends the process with ``SystemExit(0)``, as
    argparse's does. A usage error becomes the CLI's structured ``usage``
    refusal; Click's own message is kept as the refusal's message.
    """
    command = COMMANDS[name]
    try:
        return command.make_context(f"stewart {name}", list(tokens))
    except click.exceptions.Exit as shown:
        raise SystemExit(shown.exit_code) from None
    except click.UsageError as exc:
        raise StewartError(exc.format_message(), reason="usage",
                           next_steps=["consult --help for the complete command"]) from exc


def invoke(context: click.Context, **resolved) -> tuple[dict, int]:
    """Run a parsed command's operation with the context the root resolved; return (result, exit code)."""
    context.obj = resolved
    with context:
        return context.command.invoke(context)
