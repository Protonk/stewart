"""Stage unsigned Linux release binaries and a reproducible offline source archive."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def vendor_files(listing, root):
    files = {}
    for line in listing.decode("utf-8").splitlines():
        match = re.fullmatch(r"([a-f0-9]{64})  (vendor/.+)", line)
        require(match, "invalid vendor listing row")
        expected, name = match.groups()
        rel = Path(name)
        require(str(rel) == name and ".." not in rel.parts and name not in files, "invalid or duplicate vendor path")
        files[name] = expected
    entries = list((root / "vendor").rglob("*"))
    require(not any(p.is_symlink() or not (p.is_dir() or p.is_file()) for p in entries), "unsupported vendor entry")
    require(set(files) == {p.relative_to(root).as_posix() for p in entries if p.is_file()},
            "vendor listing and source tree membership differ")
    return files


def add_bytes(archive, name, raw, mtime):
    member = tarfile.TarInfo(name)
    member.size, member.mtime, member.mode = len(raw), mtime, 0o644
    archive.addfile(member, io.BytesIO(raw))


def source_archive(path, commit, version, listing, files):
    prefix = "stewart-" + version + "/"
    epoch = int(git("show", "-s", "--format=%ct", commit).strip())
    tracked = git("archive", "--format=tar", "--prefix=" + prefix, commit)
    with path.open("xb") as output, gzip.GzipFile(filename="", fileobj=output, mode="wb", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w|", pax_headers={"comment": commit}) as dest:
            with tarfile.open(fileobj=io.BytesIO(tracked)) as src:
                for member in src:
                    dest.addfile(member, src.extractfile(member) if member.isfile() else None)
            add_bytes(dest, prefix + "service/VENDOR-SHA256SUMS", listing, epoch)
            for name, expected in sorted(files.items()):
                raw = (ROOT / "service" / name).read_bytes()
                require(hashlib.sha256(raw).hexdigest() == expected, "changed vendor file: " + name)
                add_bytes(dest, prefix + "service/" + name, raw, epoch)


def stage(args):
    require(not args.output.exists(), "choose a new output directory")
    require(not git("status", "--porcelain"), "commit the candidate checkout before packaging")
    commit = git("rev-parse", "HEAD").decode().strip()
    version = tomllib.loads(git("show", commit + ":service/Cargo.toml").decode())["package"]["version"]
    require(re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z.+-]*", version), "invalid crate version")
    subprocess.run([sys.executable, "-I", "-B", str(ROOT / "apparatus/qualified.py"), "check"],
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    index = json.loads(git("show", commit + ":apparatus/qualified.json"))
    records = {r["id"]: r for r in index["entries"]}
    release, toolchain = records[args.qualification], records[args.toolchain]
    for record, suite in [(release, "acceptance"), (toolchain, "toolchain")]:
        require(record.get("suite") == suite and record["outcome"] == "qualified", "expected a qualified " + suite)
    changes = git("diff", "--name-only", release["source_commit"], commit, "--", "service", ":(exclude)service/README.md")
    require(not changes, "crate inputs differ from qualification: " + changes.decode().strip())
    evidence = ROOT / release["evidence"]["path"]
    listing = (ROOT / toolchain["evidence"]["path"] / "host/vendor.sha256").read_bytes()
    require(hashlib.sha256(listing).hexdigest() == toolchain["vendor"]["listing_sha256"] and
            listing == (evidence / "host/vendor.sha256").read_bytes(), "vendor provenance differs")
    files = vendor_files(listing, ROOT / "service")
    require(len(files) == toolchain["vendor"]["files"], "vendor count differs")
    with tempfile.TemporaryDirectory(prefix=".stewart-package-", dir=args.output.parent) as temp:
        work = Path(temp) / "artifacts"
        work.mkdir()
        for arch, label in [("arm64", "aarch64"), ("amd64", "x86_64")]:
            platform = release["platforms"]["linux-" + label]
            dest = work / ("stewart-linux-" + label)
            shutil.copyfile(evidence / ("bin-" + arch) / "stewart", dest)
            require(platform["outcome"] == "qualified" and digest(dest) == platform["release_sha256"],
                    "shipping binary differs from qualification: " + label)
            dest.chmod(0o755)
        source_archive(work / ("stewart-" + version + "-source.tar.gz"), commit, version, listing, files)
        sums = "".join(digest(p) + "  " + p.name + "\n" for p in sorted(work.iterdir()))
        (work / "SHA256SUMS").write_text(sums, encoding="ascii")
        work.rename(args.output)
    print("Staged", version, "from", commit, "with", len(files), "verified vendor files.")
    print(sums, end="")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qualification", required=True, help="Retained two-platform acceptance suite ID")
    parser.add_argument("--toolchain", required=True, help="Retained toolchain suite ID for the vendor inputs")
    parser.add_argument("--output", required=True, type=Path, help="New directory for the unsigned artifacts")
    try:
        stage(parser.parse_args())
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError, tarfile.TarError) as error:
        parser.exit(1, "Release packaging failed: " + str(error) + "\n")
