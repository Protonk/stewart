# Manager walkthroughs

Two walkthroughs follow one manager through an audit of the
[open-inquiry worked example](../questions/open/WALKTHROUGH.md):

- [Files only](FILE-ONLY.md): create a reference, write the submission folder,
  prepare, commission, run, check status and close, using the CLI alone.
- [With the preparation MCP](WITH-MCP.md): discover and explain the family,
  then assemble the same submission folder through `stewart manager-mcp`, and
  continue with the CLI from `prepare`.

The two routes give the same question body, materials, settings and
arrangement, and deliver the same return. Only the CLI prepares, accepts, runs
and closes an audit.

## What the outputs show

The outputs are those of the release binary. The audit's run used a scripted
stand-in for the provider, selected with `STEWART_PROVIDER_URL`; no model was
involved and the auditor's calls are the hand-written ones of the
[auditor walkthrough](../questions/open/WALKTHROUGH.md). The stand-in behaves as
follows:

- In the first run it answers every request with HTTP 529 (`overloaded_error`,
  message `Overloaded`) and `retry-after: 0`, so the run ends interrupted after
  four attempts.
- In the second run its four responses carry, in order: `list` and a `read` of
  each material; `record_observation`, `record_account` and `record_limit`;
  `prepare`; then a `read` of the prepared rendering and the confirmed
  `submit`, with the inputs shown in the auditor walkthrough. Each response
  reports 3,000 input and 400 output tokens.

A real run talks to the provider named by the commission's model and spends its
usage; its replies depend on the model.

## Reading the examples

The manager is Ana. Her submission folder is `/home/ana/reminders`, her archive
`/home/ana/stewart-archive`, her return destination `/home/ana/returns` and her
candidate workspace `/home/ana/candidates`. `stewart` is installed as
`/usr/local/bin/stewart`. Commands start with `$`. `REF` stands for the
reference `new` prints and `HANDLE` for the handle `prepare` prints.

Each walkthrough starts from a home holding only the repository's worked
example. A command's block shows its standard output. A `…` stands for a value
that differs between runs, such as a time, a digest, a path-dependent size or
an identifier, and a line holding only `…` stands for lines left out. An MCP
reply shows some members of its `structuredContent`: each member shown equals
the reply's, and an object may leave members out.

The release acceptance driver runs these walkthroughs against the release
binary and compares each output shown with the binary's.
