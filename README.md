# Stewart

>Make it *just* so

Stewart bounds inquiries over files you choose for examination by an auditor,
currently implemented as calls to Anthropic's Messages API. Supply a question,
materials, an answer form and limits. Stewart preserves the inputs, gives the
auditor tools to investigate them, and delivers its recorded answer as structured
data and readable Markdown.

## Question forms

The `family` field in `question.md` selects the auditor's task and its tools for
recording an answer.

| Form | What the auditor does |
| --- | --- |
| `open-inquiry` | Answers your question as written, drawing on observations from the supplied files. |
| `inquiry-framing` | Starts from a concern you describe, formulates a working question the files can help answer, and investigates it. |
| `comparison` | Examines the alternatives you name side by side and records how they differ or agree on a stated criterion. |

Each form has a [worked submission and walkthrough](examples/questions/README.md). Run
`stewart help forms` for the instructions and material roles.

## Install and verify a Linux release

Download the binary for your architecture (`stewart-linux-aarch64` or
`stewart-linux-x86_64`), `SHA256SUMS` and `SHA256SUMS.sig` from the same
[release](https://github.com/Protonk/stewart/releases). Before replacing an installed
binary, keep a copy if it created any open audits. Only that exact binary can continue
or close them.

Set `SIGNERS` to the path of the [allowed signers file](allowed_signers) from a trusted checkout
and confirm the signer's fingerprint through an independent channel. From the download
directory on Linux, verify the signature and checksum before installing.

```sh
binary="stewart-linux-$(uname -m)"
ssh-keygen -Y verify -f "$SIGNERS" -I stewart-release -n file -s SHA256SUMS.sig < SHA256SUMS &&
  sha256sum --check --ignore-missing SHA256SUMS &&
  install -Dm755 "$binary" "$HOME/.local/bin/stewart"
```

Add `$HOME/.local/bin` to your `PATH` and run `stewart help` to check the installation.
The signed checksums also cover the source archive, which includes the dependencies for
an [offline build](development/DEVELOPMENT.md#build-from-a-release-source-archive).

## Run an inquiry

### Prepare and commission

Choose an archive on local ext4, XFS or Btrfs. `new` prints an audit reference and
creates the submission folder if needed.

```sh
stewart new "$HOME/inquiry" --archive "$HOME/stewart-archive"
```

Put the UTF-8 text files to examine under `materials/`. In `question.md`, write your
question and set the form, model, turn and token limits, and an existing directory for
the answer. Use absolute paths for the submission folder, archive and answer
destination. Keep all three separate, with none inside another.
[Question file format](docs/INTERFACE.md#32-front-matter-question2)

Use the reference from `new` in place of `REF`. Review the selection, instructions and
limits shown by `prepare`. It prints the `HANDLE` that identifies what you reviewed.
Commissioning copies and verifies the inputs, fixing the question and materials for the audit.

```sh
stewart prepare REF
stewart commission REF HANDLE --i-am-finished
```

### Run and read the answer

Only `run` contacts the provider. Supply the API key through `ANTHROPIC_API_KEY` or an
open file descriptor with `--key-fd FD`. The auditor reads and searches the captured
text and can cite passages in its entries. If a run is interrupted, another `run` on the
same reference continues with the recorded entries and remaining allowance.

```sh
stewart run REF
stewart status REF
```

On submission, Stewart seals the answer, copies it to the destination and reads it back.
`status` reports whether delivery succeeded. In the return package, `answer.md` is the
readable answer and `answer.json` contains the same entries as structured data. The
package also includes the original question body, a manifest and any submitted
artifacts.

Finish with `stewart close REF`. If you close after launch with the answer still open,
Stewart preserves the entries and records that the manager sealed them. If `close` asks
for confirmation, inspect the delivered copy and follow the command it prints. The
archive keeps the accepted inputs, exchanges and recorded work after closure.

The [CLI walkthrough](examples/manager/FILE-ONLY.md) shows the commands and their
output. The optional [manager MCP server](docs/MANAGER-PREPARATION.md) can assemble the
submission folder before you prepare it.

## Status

Stewart 0.0.2 is experimental. In live audits through the Messages API, Haiku 5.5 and
Opus 5.5 each submitted answers in all three forms, and Stewart verified delivery. The
optional Claude Code adapter, available in source builds, has completed one live open
inquiry. [Live audit records](apparatus/qualified.md)

Both release binaries passed the acceptance suite on the same Linux guest kernel. The
aarch64 binary ran natively and the x86_64 binary ran under Rosetta.
[Release qualification](apparatus/qualified.md#framing-effort-acceptance-01)

## Development

The [design](DESIGN.md) explains the responsibilities of the manager, auditor and
service. The [crate guide](service/README.md) maps those responsibilities to the Rust
code. For changes to Stewart, see the [behavioral contracts](CONTRACTS.md),
[acceptance requirements](ACCEPTANCE.md) and
[build and test guide](development/DEVELOPMENT.md).

## License

[MIT](LICENSE).
