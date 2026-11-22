# Release plan

This plan owns the remaining work for the first release and the order of the
tracked plans. The [qualification index](apparatus/qualified.md) owns the
results the release ships on, [DEVELOPMENT](development/DEVELOPMENT.md#prepare-release-artifacts)
the packaging and signing procedure, and the
[README](README.md#install-and-verify-a-linux-release) what users verify.

## Work order

| Order | Remaining work | Owner |
| --- | --- | --- |
| Now | Decide whether the Mac's migration records need a backup | [Migration records](#migration-records) |
| Now | Decide whether releases are signed | [Signing](#signing) |
| After the signing decision | Package and publish the release | [Release](#release) |
| After the release | Shorten test and suite wall-clock time | [Test wall-clock](development/TEST-WALL-CLOCK-PLAN.md) |

## Migration records

`.scratch/linux-move-mac-private-01` on the Mac holds five records from the move
to the Linux guest: the custody disposition, the launcher successor check, the
native inventory and status, and the qualification pin review. The disposition
record, also kept as `migration/historical-custody-disposition.json` in the
launcher account, asks that the Mac originals be kept until an independent
backup exists, because the guest disk shares the Mac's physical storage. The
private selection it names (`launcher-selected` on the Mac and
`migration/selected-01` in the launcher account, manifest SHA-256
`4a1262fc86e0c8e8877d0938a93b6725dc54e0c4decc083b9787e8d0ff736c06`) is no longer
present in either place.

- [ ] The maintainer decides what of this material is still needed. Copy what
  is needed to authorized storage on a separate device and verify the copy,
  recovering the selection from a machine backup if it is needed and one
  exists. Then delete the Mac folder and the launcher's copy of the
  disposition record.

## Signing

The documented procedure has the maintainer sign `SHA256SUMS` on the Mac with
an SSH key under the principal `stewart-release`, which users check against
`allowed_signers` at the repository root
([guest guide](apparatus/lima/README.md#release-signing)). Neither the key nor
`allowed_signers` exists yet.

The publishing token lets the maintainer upload to GitHub; it gives a
downloader nothing to check. A signature lets a downloader confirm that the
files came from the maintainer without trusting GitHub, the account or the
token. The token lives in the guest's keyring and the signing key would stay on
the Mac, so a compromised guest could not issue a release that verifies. The
check helps users who get the public key from outside the repository or keep
the key they trusted for an earlier release. Neither CONTRACTS nor ACCEPTANCE
requires a signature.

- [ ] The maintainer decides:
  - **Sign:** create a dedicated Ed25519 key on the Mac, add its public key to
    `allowed_signers` with the principal `stewart-release`, and publish its
    fingerprint somewhere other than the repository.
  - **Do not sign:** remove the signature from the README's installation steps,
    DEVELOPMENT's release procedure and its packaging check row, and the guest
    guide's signing section. Users then rely on HTTPS from GitHub and on
    rebuilding from the source archive.

## Release

The release ships the binaries qualified by
[`framing-effort-acceptance-01`](apparatus/qualified.md#framing-effort-acceptance-01),
with the vendor inputs of
[`linux-move-toolchain-02`](apparatus/qualified.md#linux-move-toolchain-02).
The same binaries wrote the Messages alignment records the release names.

1. Commit the release candidate in the guest checkout. Add `allowed_signers` if
   signing, and delete this plan so that the source archive carries no release
   plan. The remaining steps continue from this plan's last revision; name
   them in the commit message.
2. Stage and check the artifacts as
   [DEVELOPMENT](development/DEVELOPMENT.md#prepare-release-artifacts)
   describes, with `--qualification framing-effort-acceptance-01` and
   `--toolchain linux-move-toolchain-02`, and run the packaging script's
   [check row](development/DEVELOPMENT.md#what-to-run-for-what-you-changed).
   The script refuses any change under `service/` since the qualified source
   commit apart from `service/README.md`; such a change needs a new release
   suite run first.
3. If signing, the maintainer signs and verifies `SHA256SUMS` on the Mac.
4. Push `main` and a tag on the release commit named `v` followed by the crate
   version. The maintainer decides when to publish the GitHub release with both
   binaries, the source archive, `SHA256SUMS` and, if signing,
   `SHA256SUMS.sig`.
5. After publication, remove the launcher account's holdings for the eight
   closed alignment audits: their containers and volumes, the six alignment
   queues under `/var/lib/stewart`, their campaign folders and host evidence in
   the launcher's home, and the per-campaign checkouts `stewart-framing-01` and
   `stewart-compaction-01`. The qualification index checks the alignment
   records against the development account's copies, which stay while the
   records are current.
