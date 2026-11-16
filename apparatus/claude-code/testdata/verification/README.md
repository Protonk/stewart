# Local verification output

These files preserve complete stdout, stderr and exit records from local public
release verification for Claude Code `2.1.322`, macOS ARM64. They contain no
credentials. `test_pin.py` and `test_profile.py` replay the results without
executing GPG, `codesign` or Claude. Paths in diagnostics are opaque text and
are never opened by the tests.

The successful records come from
`.scratch/claude-code-pin-01/verify-q0507wi4/`; their original file timestamps are
2026-11-10 23:33:44–45 UTC. `codesign-refused.*` comes from the earlier
`.scratch/claude-code-pin-01/verify-sj71kzuz/codesign.*`, timestamped
2026-11-10 23:26:57 UTC. These are two historical observations, not a controlled
comparison of executable contents. The records do not identify the GPG or OS
tool versions. The successful pin receipt binds executable SHA-256
`a9d237949db816a0b7afd88a9a8e1df36b3a597a30f5a41d1c0539eb180a3450`
and manifest SHA-256
`05d2eff648bb528c1479c719bb8eca9a759657631e285d03aaf37fe779173f1c`.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `dearmor.stdout`, `dearmor.stderr`, `codesign.stdout`, `codesign-refused.stdout` | 0 each | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `dearmor.exit`, `signature.exit`, `codesign.exit` | 2 each | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |
| [signature.stdout](signature.stdout) | 382 | `92fb6272050944cb16ef49d2693fa0ab29c869e5e19107bdf197352e474ef5a6` |
| [signature.stderr](signature.stderr) | 217 | `ea2578fb0a6dd908573d0c6b848a0112b7ac1271805165adcf6159fc319ccd7b` |
| [codesign.stderr](codesign.stderr) | 179 | `dbb465ef6079213b7e02121c6f60bda6e4f175dd705fcda236028f6ad5497e35` |
| [codesign-refused.stderr](codesign-refused.stderr) | 144 | `d064cf2ee794341db368137bd2b3db5ef061e8395272920ea20d112d87f52ce8` |
| [codesign-refused.exit](codesign-refused.exit) | 2 | `4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865` |

The signature parser consumes the full captured status stream. A negative
variant replaces the selected fingerprint, another removes only `VALIDSIG`,
and a subkey variant changes only that line's signing-key field while preserving
the selected primary key. Changing line endings to CRLF preserves the result.
These exercise identity parsing; they cannot prove cryptographic verification.

The logging comparison supplies each captured process result and checks exact
retention of both channels and exit code. A differing case changes only the
successful `codesign` exit to 1, retaining its successful diagnostic text; the
wrapper must still refuse. The original failure also refuses with its diagnostic
intact. Profile preparation must stop before publishing launch or preparation
records when supplied that failure.

Profile tests use the captured successful verifier output with synthetic public
inputs and a canary executable, so the output does not authenticate those inputs.
The existing canary firing control, launch-byte whitespace invariance and
wrong-signer/refusal controls remain. No test launches the captured executable,
rechecks its signature or claims a fresh installation verification.
