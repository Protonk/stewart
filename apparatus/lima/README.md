# Stewart development guest

On the Mac, start the guest from the repository root with Lima 2.3.0.

```sh
limactl start --name=stewart apparatus/lima/stewart.yaml
```

The template pins a Debian 13 aarch64 cloud image by SHA-512. VZ supplies
Rosetta for amd64, six vCPUs, 8 GiB RAM and an 80 GiB sparse disk. Keep
space available on both filesystems. The guest stores the checkout, Podman
storage, audit archives and evidence on its disk. Rosetta and Lima's
provisioning media are the only host-supplied mounts it needs.

Use `limactl shell --workdir / stewart` for guest administration. The default
login can use sudo. Start everyday sessions as the unprivileged development
user from the Mac. Use an independent SSH connection for each login.

```sh
ssh -F "$HOME/.lima/stewart/ssh.config" -o ControlMaster=no -o ControlPath=none -l stewart-dev lima-stewart
```

Clone the repository into the development user's home. On an existing
installation, transfer local-only commits with a Git bundle. Set the clone's
origin to the repository's GitHub remote. Use the same guest login for edits,
agents, Cargo, the independent drivers and the container suites.

## Git transport

For HTTPS, the remote for this repository is
`https://github.com/Protonk/stewart.git`. Use a fine-grained GitHub credential
restricted to Stewart with the repository permissions needed to push. The
maintainer unlocks the user's Secret Service collection in the guest and
checks storage with a disposable canary before supplying a real credential.
In the guest's Bash shell, the first unlock creates the login keyring. Choose
a private passphrase and keep it for later logins.

```sh
IFS= read -rsp 'Guest keyring passphrase: ' ringpass; printf '\n'
printf '%s' "$ringpass" | gnome-keyring-daemon --unlock --components=secrets >/dev/null
unset ringpass
```

```sh
printf '%s' stewart-canary | secret-tool store --label='Stewart storage check' project stewart check git-store
test "$(secret-tool lookup project stewart check git-store)" = stewart-canary
secret-tool clear project stewart check git-store
```

From the same private terminal, use hidden entry for the scoped token.

```sh
IFS= read -rsp 'Stewart repository token: ' token; printf '\n'
printf '%s' "$token" | gh auth login --hostname github.com --git-protocol https --with-token
unset token
gh auth status --hostname github.com
```

Inspect the reported location
for keyring storage. Stop if it reports a plaintext file. Run `gh auth setup-git`
and verify push access with `git push --dry-run origin HEAD:main`. Leave secrets
out of shell history, command arguments and evidence.

For SSH, use a separate Mac agent holding exactly the repository's push key.
In that agent's shell, compare `ssh-add -l -E sha256` to the expected single
public fingerprint. Add `-A` to the development login above and repeat the
fingerprint check inside the guest before using the SSH remote. Agent forwarding
is off for ordinary logins. Keep the release signing key on the Mac. Compare both
release binaries to the qualification record before signing the reviewed
`SHA256SUMS`, then return the signature and public key to the guest.

## Guest checks and accounts

Run these commands from the development login. The source and workspaces
should resolve to ext4, the filename fixture to vfat, and the emulator
registration to Lima's Rosetta interpreter.

```sh
findmnt --target "$HOME"
findmnt --target /var/lib/stewart/dev-tmp
findmnt --target /var/lib/stewart/fixtures/names
lsattr -d /var/lib/stewart/fixtures/fold/work
cat /proc/sys/fs/binfmt_misc/rosetta
podman info --format json | jq '.host | {rootless: .security.rootless, cgroupVersion, cgroupControllers}'
export STEWART_IT_TMP=/var/lib/stewart/dev-tmp
```

After preloading the pinned Python image, run `sh apparatus/lima/check-limits.sh IMAGE@sha256:DIGEST`
as each account. It checks CPU throttling and compares a small allocation with
one killed at the memory limit.

The development and launcher accounts have distinct Podman stores and
subordinate UID/GID ranges. The maintainer installs reviewed code and writers
for the launcher. The queue accepts authorized requests from the development
user. Launches use the launcher's private Linux keyring. See the
[C10 instructions](../c10/README.md) for loading a provider connection and
the [queue guide](../c10/HOST-QUEUE.md) for placing requests. Enter the
dedicated harness login with the pinned Linux executable as its intended
user. Follow the [harness guide](../claude-code/README.md) for its separate
configuration directory and commissioning procedure.

See [Building and testing](../../development/DEVELOPMENT.md) for the
offline Cargo matrix, two-architecture suites and evidence retention.
