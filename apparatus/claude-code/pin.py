"""Fetch and authenticate the approved Claude executable pin; never launch it."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


VERSION = "2.1.322"
PLATFORM = "darwin-arm64"
FINGERPRINT = "31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE"
BASE = "https://downloads.claude.ai"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def manifest_checksum(data):
    obj = json.loads(data)
    if obj.get("version") != VERSION:
        raise ValueError("manifest version does not match the approved pin")
    checksum = obj["platforms"][PLATFORM]["checksum"]
    if not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-f]{64}", checksum):
        raise ValueError("manifest has no valid darwin-arm64 SHA-256")
    return checksum


def signed_by_release_key(status):
    for line in status.splitlines():
        fields = line.split()
        if len(fields) >= 11 and fields[:2] == ["[GNUPG:]", "VALIDSIG"]:
            if fields[2] == FINGERPRINT or (len(fields) == 12 and fields[11] == FINGERPRINT):
                return True
    return False


def run_logged(out, name, argv):
    result = subprocess.run(argv, capture_output=True, timeout=90)
    (out / (name + ".stdout")).write_bytes(result.stdout)
    (out / (name + ".stderr")).write_bytes(result.stderr)
    (out / (name + ".exit")).write_text(str(result.returncode) + "\n")
    if result.returncode:
        raise RuntimeError("%s failed (exit %s); inspect %s" % (name, result.returncode, out / (name + ".stderr")))
    return result.stdout


def fetch(out, source, destination):
    if os.uname().machine != "arm64":
        raise RuntimeError("this approved pin is for native macOS ARM64")
    out.mkdir(mode=0o700, parents=False, exist_ok=False)
    for name, url in [
        ("claude-code.asc", BASE + "/keys/claude-code.asc"),
        ("manifest.json", BASE + "/claude-code-releases/" + VERSION + "/manifest.json"),
        ("manifest.json.sig", BASE + "/claude-code-releases/" + VERSION + "/manifest.json.sig"),
    ]:
        print("Fetching " + url, flush=True)
        run_logged(out, "fetch-" + name, ["/usr/bin/curl", "--fail", "--silent", "--show-error", "--location",
                   "--proto", "=https", "--proto-redir", "=https", "--max-time", "60", "--output", str(out / name), url])
    verify(out, source, destination)


def verify(out, source, destination):
    gpg, gpgv = shutil.which("gpg"), shutil.which("gpgv")
    if not gpg or not gpgv:
        raise RuntimeError("gpg and gpgv are required; no Claude executable has been launched")
    attempt = Path(tempfile.mkdtemp(prefix="verify-", dir=out))
    # Public-key-only operations: no agent, user keyring or trust configuration.
    keyring = attempt / "release-key.gpg"
    run_logged(attempt, "dearmor", [gpg, "--no-options", "--homedir", str(attempt), "--batch",
                                   "--dearmor", "--output", str(keyring), str(out / "claude-code.asc")])
    status = run_logged(attempt, "signature", [gpgv, "--homedir", str(attempt), "--keyring", str(keyring),
                        "--status-fd", "1", str(out / "manifest.json.sig"), str(out / "manifest.json")])
    if not signed_by_release_key(status.decode("utf-8")):
        raise RuntimeError("signature does not identify the pinned Anthropic release key")
    checksum = manifest_checksum((out / "manifest.json").read_bytes())
    source = source.resolve(strict=True)
    if digest(source) != checksum:
        raise RuntimeError("installed binary does not match the authenticated manifest")
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if destination.exists():
        if destination.is_symlink() or digest(destination) != checksum:
            raise RuntimeError("refusing to replace an existing, different pin: " + str(destination))
    else:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".pin-", delete=False) as stream:
            tmp = Path(stream.name)
            try:
                with source.open("rb") as original:
                    shutil.copyfileobj(original, stream)
                stream.flush()
                os.fsync(stream.fileno())
                if digest(tmp) != checksum:
                    raise RuntimeError("binary changed while being copied")
                tmp.chmod(0o500)
                os.link(tmp, destination)  # Exclusive publication; never overwrite a pin.
            finally:
                tmp.unlink(missing_ok=True)
    run_logged(attempt, "codesign", ["/usr/bin/codesign", "--verify", "--verbose", str(destination)])
    receipt = {"version": VERSION, "platform": PLATFORM, "binary": str(destination), "sha256": checksum,
               "manifest_sha256": digest(out / "manifest.json"), "signer": FINGERPRINT,
               "verification": str(attempt)}
    with (out / "pin.json").open("x") as record:
        record.write(json.dumps(receipt, indent=2) + "\n")
    print("Verified pin: " + str(destination))
    print("SHA-256: " + checksum)
    print("Receipt: " + str(out / "pin.json"))
    print("No Claude process was started.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="new evidence directory under .scratch")
    parser.add_argument("--verify-only", action="store_true", help="verify already downloaded files; retain a new verification attempt")
    args = parser.parse_args()
    home = Path.home()
    try:
        action = verify if args.verify_only else fetch
        action(args.output.resolve(), home / ".local/share/claude/versions" / VERSION,
               home / ".local/share/stewart-claude-code" / VERSION / "claude")
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.exit(1, "pin refused: %s\n" % exc)


if __name__ == "__main__":
    main()
