# Manager alignment

Settle what the manager supplies, sees and receives before further studies lean
on it. This is a sketch, not a schedule.

- [ ] Walk the manager's path (scaffold, prepare, receipt, status, close and
  return) against [CONTRACTS](CONTRACTS.md#manager-readback-status-and-close)
  and the [interaction findings](apparatus/studies/interaction/RESULTS.md).
  List the mismatches.
- [ ] Implement the [returned question](CONTRACTS.md#returned-question-and-answer):
  specification and service by one author, driver by another.
- [ ] Bring the remaining choices to the principal with evidence. Nothing
  further is selected beyond the design goal below.

## Design goal: an optional preparation server

A small synchronous MCP server, in the shipped binary, that helps a manager
build a submission before commissioning. It presents the question types in a
useful structure and serves pre-written, approved information on request. It
guides and does not gather: collecting material stays with the manager's own
tools. The CLI remains the only way to run an audit, and a folder built by hand
is in every respect as good as one built with the server.

Supplying this interface replaces shipping a version-stamped user guide: the
text comes from the binary that will pin it.

**Anti-goals**

- Intelligence of any kind beyond that structured presentation and on-demand
  approved text. The server calls no model and infers nothing.
- Inspection-style validation of contents. Manager and auditor are cooperative;
  the server does not look for hostile or manipulative material.
- Specialized connectors to the CLI. The server wraps no command, takes no audit
  reference and opens no archive, so that it stays optional in substance.

**Idea to weigh:** a startup option, working name `--newbie`, for an agent that
has not read the documentation. By default the server offers little. With the
option it leads: the question types first, then the materials suggested for the
type chosen. A server only answers calls, so the lead comes from its startup
instructions and from what each reply offers next.

- [ ] Draft the manager-facing text for each question type and settle its owner
  beside [the form specification](docs/QUESTION-FORMS.md). The principal
  approves the text before a server carries it.
- [ ] Propose the server's surface and its place in CONTRACTS, INTERFACE and
  ACCEPTANCE. It is a new product surface; independent driver cases follow the
  specification. Write it without new dependencies.
