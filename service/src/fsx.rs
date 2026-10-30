//! Descriptor-relative filesystem access.
//!
//! Every access below the opened roots uses `*at` calls on pinned directory
//! descriptors with `O_NOFOLLOW`, so no path component is ever re-resolved and
//! no link is followed. Regular files are opened with `O_NONBLOCK` and their
//! type is rechecked on the open descriptor, so a FIFO, socket or device is
//! never read. Files Stewart creates are exclusive (`O_CREAT | O_EXCL`), mode
//! 0600; directories are 0700.

use crate::platform;
use std::ffi::{CStr, CString};
use std::fs::File;
use std::io::{self, Read, Write};
use std::os::fd::{AsRawFd, FromRawFd};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Kind {
    Dir,
    File,
    Symlink,
    Fifo,
    Socket,
    CharDevice,
    BlockDevice,
    Other,
}

impl Kind {
    pub fn from_mode(mode: u32) -> Kind {
        match mode & (libc::S_IFMT as u32) {
            m if m == libc::S_IFDIR as u32 => Kind::Dir,
            m if m == libc::S_IFREG as u32 => Kind::File,
            m if m == libc::S_IFLNK as u32 => Kind::Symlink,
            m if m == libc::S_IFIFO as u32 => Kind::Fifo,
            m if m == libc::S_IFSOCK as u32 => Kind::Socket,
            m if m == libc::S_IFCHR as u32 => Kind::CharDevice,
            m if m == libc::S_IFBLK as u32 => Kind::BlockDevice,
            _ => Kind::Other,
        }
    }
    pub fn name(self) -> &'static str {
        match self {
            Kind::Dir => "directory",
            Kind::File => "regular file",
            Kind::Symlink => "symbolic link",
            Kind::Fifo => "FIFO",
            Kind::Socket => "socket",
            Kind::CharDevice => "character device",
            Kind::BlockDevice => "block device",
            Kind::Other => "special file",
        }
    }
}

/// The parts of `stat` Stewart compares. No ctime: a permission change alone
/// is never a content change (INTERFACE 3.3).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Stat {
    pub dev: u64,
    pub ino: u64,
    pub kind: Kind,
    pub size: u64,
    pub mtime_s: i64,
    pub mtime_ns: i64,
}

impl Stat {
    // The stat field types differ between platforms; the casts are kept.
    #[allow(clippy::unnecessary_cast)]
    fn from(st: &libc::stat) -> Stat {
        Stat {
            dev: st.st_dev as u64,
            ino: st.st_ino as u64,
            kind: Kind::from_mode(st.st_mode as u32),
            size: st.st_size as u64,
            mtime_s: st.st_mtime as i64,
            mtime_ns: st.st_mtime_nsec as i64,
        }
    }
    pub fn mtime(&self) -> String {
        format!("{}.{:09}", self.mtime_s, self.mtime_ns)
    }
    pub fn id(&self) -> (u64, u64) {
        (self.dev, self.ino)
    }
}

pub fn cstr(name: &str) -> io::Result<CString> {
    CString::new(name).map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "NUL in name"))
}

fn cbytes(name: &[u8]) -> io::Result<CString> {
    CString::new(name.to_vec())
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "NUL in name"))
}

pub fn fstat(f: &File) -> io::Result<Stat> {
    let mut st: libc::stat = unsafe { std::mem::zeroed() };
    if unsafe { libc::fstat(f.as_raw_fd(), &mut st) } != 0 {
        return Err(io::Error::last_os_error());
    }
    Ok(Stat::from(&st))
}

/// An open directory descriptor with the absolute path it was opened as
/// (for messages and retained-location lists only; never re-resolved).
pub struct Dir {
    pub file: File,
    pub path: String,
}

/// Why a path walk stopped.
#[derive(Debug)]
pub enum WalkError {
    /// The component at this prefix path is a symbolic link.
    Symlink(String),
    /// The component at this prefix path does not exist.
    Missing(String),
    /// The component at this prefix path is not a directory.
    NotDir(String),
    Io(String, io::Error),
}

impl WalkError {
    pub fn path(&self) -> &str {
        match self {
            WalkError::Symlink(p)
            | WalkError::Missing(p)
            | WalkError::NotDir(p)
            | WalkError::Io(p, _) => p,
        }
    }
}

pub fn join(base: &str, name: &str) -> String {
    if base == "/" {
        format!("/{name}")
    } else {
        format!("{base}/{name}")
    }
}

impl Dir {
    /// Open an absolute path, following symbolic links as the kernel does.
    /// Used for manager-owned locations (folder, destination).
    pub fn open_follow(path: &str) -> io::Result<Dir> {
        let c = cstr(path)?;
        let fd = unsafe {
            libc::open(
                c.as_ptr(),
                libc::O_RDONLY | libc::O_DIRECTORY | libc::O_CLOEXEC,
            )
        };
        if fd < 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(Dir {
            file: unsafe { File::from_raw_fd(fd) },
            path: path.to_string(),
        })
    }

    /// Open an absolute path by walking its components from `/` with
    /// `O_NOFOLLOW`, so a symbolic link anywhere in the path is detected.
    pub fn open_nofollow(path: &str) -> Result<Dir, WalkError> {
        let root = Dir::open_follow("/").map_err(|e| WalkError::Io("/".into(), e))?;
        let mut cur = root;
        if path == "/" {
            return Ok(cur);
        }
        let mut prefix = String::new();
        for comp in path[1..].split('/') {
            prefix.push('/');
            prefix.push_str(comp);
            match cur.open_dir(comp) {
                Ok(d) => {
                    cur = Dir {
                        file: d.file,
                        path: prefix.clone(),
                    }
                }
                Err(e) => {
                    let kind = cur.stat_at(comp).ok().map(|s| s.kind);
                    return Err(match (e.raw_os_error(), kind) {
                        (_, Some(Kind::Symlink)) => WalkError::Symlink(prefix),
                        (Some(libc::ENOENT), _) => WalkError::Missing(prefix),
                        (_, Some(k)) if k != Kind::Dir => WalkError::NotDir(prefix),
                        _ => WalkError::Io(prefix, e),
                    });
                }
            }
        }
        Ok(cur)
    }

    pub fn stat(&self) -> io::Result<Stat> {
        fstat(&self.file)
    }

    /// Open a child directory without following a link.
    pub fn open_dir(&self, name: &str) -> io::Result<Dir> {
        self.open_dir_bytes(name.as_bytes(), true)
    }

    pub fn open_dir_bytes(&self, name: &[u8], nofollow: bool) -> io::Result<Dir> {
        let c = cbytes(name)?;
        let flags = libc::O_RDONLY
            | libc::O_DIRECTORY
            | libc::O_CLOEXEC
            | if nofollow { libc::O_NOFOLLOW } else { 0 };
        let fd = unsafe { libc::openat(self.file.as_raw_fd(), c.as_ptr(), flags) };
        if fd < 0 {
            return Err(io::Error::last_os_error());
        }
        let p = join(&self.path, &String::from_utf8_lossy(name));
        Ok(Dir {
            file: unsafe { File::from_raw_fd(fd) },
            path: p,
        })
    }

    /// `..` of this directory, for ancestry walks.
    pub fn parent(&self) -> io::Result<Dir> {
        let fd = unsafe {
            libc::openat(
                self.file.as_raw_fd(),
                c"..".as_ptr(),
                libc::O_RDONLY | libc::O_DIRECTORY | libc::O_CLOEXEC,
            )
        };
        if fd < 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(Dir {
            file: unsafe { File::from_raw_fd(fd) },
            path: format!("{}/..", self.path),
        })
    }

    /// `fstatat(AT_SYMLINK_NOFOLLOW)`: classify an entry without following it.
    pub fn stat_at(&self, name: &str) -> io::Result<Stat> {
        self.stat_at_bytes(name.as_bytes(), true)
    }

    pub fn stat_at_bytes(&self, name: &[u8], nofollow: bool) -> io::Result<Stat> {
        let c = cbytes(name)?;
        let mut st: libc::stat = unsafe { std::mem::zeroed() };
        let flags = if nofollow {
            libc::AT_SYMLINK_NOFOLLOW
        } else {
            0
        };
        if unsafe { libc::fstatat(self.file.as_raw_fd(), c.as_ptr(), &mut st, flags) } != 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(Stat::from(&st))
    }

    pub fn exists(&self, name: &str) -> io::Result<bool> {
        match self.stat_at(name) {
            Ok(_) => Ok(true),
            Err(e) if e.raw_os_error() == Some(libc::ENOENT) => Ok(false),
            Err(e) => Err(e),
        }
    }

    /// `mkdirat` with mode 0700. `EEXIST` is returned to the caller: a
    /// numbered directory is claimed, never assumed free.
    pub fn mkdir(&self, name: &str) -> io::Result<()> {
        let c = cstr(name)?;
        if unsafe { libc::mkdirat(self.file.as_raw_fd(), c.as_ptr(), 0o700) } != 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(())
    }

    /// Create a directory if absent; an existing directory is accepted.
    pub fn ensure_dir(&self, name: &str) -> io::Result<Dir> {
        match self.mkdir(name) {
            Ok(()) => {}
            Err(e) if e.raw_os_error() == Some(libc::EEXIST) => {}
            Err(e) => return Err(e),
        }
        self.open_dir(name)
    }

    /// Open a regular file for reading without following a link, rechecking
    /// the type on the open descriptor. FIFOs are opened with `O_NONBLOCK`
    /// so the open itself cannot block; they are then refused unread.
    pub fn open_regular(&self, name: &str) -> Result<(File, Stat), ReadError> {
        self.open_regular_bytes(name.as_bytes(), true)
    }

    pub fn open_regular_bytes(
        &self,
        name: &[u8],
        nofollow: bool,
    ) -> Result<(File, Stat), ReadError> {
        let c = cbytes(name).map_err(ReadError::Io)?;
        let flags = libc::O_RDONLY
            | libc::O_NONBLOCK
            | libc::O_CLOEXEC
            | if nofollow { libc::O_NOFOLLOW } else { 0 };
        let fd = unsafe { libc::openat(self.file.as_raw_fd(), c.as_ptr(), flags) };
        if fd < 0 {
            let e = io::Error::last_os_error();
            return Err(match e.raw_os_error() {
                Some(libc::ENOENT) => ReadError::Missing,
                Some(libc::ELOOP) => ReadError::NotRegular(Kind::Symlink),
                _ => match self.stat_at_bytes(name, true).map(|s| s.kind) {
                    Ok(Kind::Symlink) => ReadError::NotRegular(Kind::Symlink),
                    _ => ReadError::Io(e),
                },
            });
        }
        let f = unsafe { File::from_raw_fd(fd) };
        let st = fstat(&f).map_err(ReadError::Io)?;
        if st.kind != Kind::File {
            return Err(ReadError::NotRegular(st.kind));
        }
        Ok((f, st))
    }

    /// Read a whole regular file of at most `limit` bytes, verifying that its
    /// identity, size and mtime did not change during the read.
    pub fn read_regular(&self, name: &str, limit: u64) -> Result<(Vec<u8>, Stat), ReadError> {
        let (f, st) = self.open_regular(name)?;
        let bytes = read_bounded(f, &st, limit)?;
        Ok((bytes, st))
    }

    /// Create a new file exclusively (`O_CREAT | O_EXCL | O_NOFOLLOW`, 0600).
    pub fn create_excl(&self, name: &str) -> io::Result<File> {
        let c = cstr(name)?;
        let fd = unsafe {
            libc::openat(
                self.file.as_raw_fd(),
                c.as_ptr(),
                libc::O_WRONLY | libc::O_CREAT | libc::O_EXCL | libc::O_NOFOLLOW | libc::O_CLOEXEC,
                0o600 as libc::c_uint,
            )
        };
        if fd < 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(unsafe { File::from_raw_fd(fd) })
    }

    /// Exclusive file publication: create, write, `fsync` the file, then
    /// `fsync` this directory. On failure the step that failed is reported;
    /// a created file stays in place as evidence.
    pub fn write_excl(&self, name: &str, bytes: &[u8]) -> Result<(), WriteError> {
        let mut f = self.create_excl(name).map_err(|e| WriteError {
            step: Step::Create,
            err: e,
        })?;
        f.write_all(bytes).map_err(|e| WriteError {
            step: Step::Write,
            err: e,
        })?;
        f.sync_all().map_err(|e| WriteError {
            step: Step::SyncFile,
            err: e,
        })?;
        self.sync().map_err(|e| WriteError {
            step: Step::SyncDir,
            err: e,
        })?;
        Ok(())
    }

    pub fn sync(&self) -> io::Result<()> {
        self.file.sync_all()
    }

    /// `linkat(self/from, to_dir/to)`. `EEXIST` means the name is taken.
    pub fn link_to(&self, from: &str, to_dir: &Dir, to: &str) -> io::Result<()> {
        let a = cstr(from)?;
        let b = cstr(to)?;
        if unsafe {
            libc::linkat(
                self.file.as_raw_fd(),
                a.as_ptr(),
                to_dir.file.as_raw_fd(),
                b.as_ptr(),
                0,
            )
        } != 0
        {
            return Err(io::Error::last_os_error());
        }
        Ok(())
    }

    /// Entry names of this directory (excluding `.` and `..`), as raw bytes,
    /// read from a fresh open file description. At most `max` names are
    /// returned; `Ok((names, true))` means the directory held more.
    pub fn names_bounded(&self, max: usize) -> io::Result<(Vec<Vec<u8>>, bool)> {
        let fd = unsafe {
            libc::openat(
                self.file.as_raw_fd(),
                c".".as_ptr(),
                libc::O_RDONLY | libc::O_DIRECTORY | libc::O_CLOEXEC,
            )
        };
        if fd < 0 {
            return Err(io::Error::last_os_error());
        }
        let dp = unsafe { libc::fdopendir(fd) };
        if dp.is_null() {
            let e = io::Error::last_os_error();
            unsafe { libc::close(fd) };
            return Err(e);
        }
        let mut out = Vec::new();
        let mut more = false;
        loop {
            platform::clear_errno();
            let ent = unsafe { libc::readdir(dp) };
            if ent.is_null() {
                let e = io::Error::last_os_error();
                unsafe { libc::closedir(dp) };
                if e.raw_os_error().unwrap_or(0) != 0 {
                    return Err(e);
                }
                break;
            }
            let raw = unsafe { CStr::from_ptr((*ent).d_name.as_ptr()) }.to_bytes();
            if raw == b"." || raw == b".." {
                continue;
            }
            if out.len() == max {
                more = true;
                unsafe { libc::closedir(dp) };
                break;
            }
            out.push(raw.to_vec());
        }
        Ok((out, more))
    }

    /// All entry names, which must be UTF-8 (Stewart's own directories).
    pub fn names(&self) -> io::Result<Vec<String>> {
        let (raw, _) = self.names_bounded(usize::MAX)?;
        let mut out = Vec::with_capacity(raw.len());
        for r in raw {
            out.push(
                String::from_utf8(r)
                    .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "a non-UTF-8 name"))?,
            );
        }
        out.sort();
        Ok(out)
    }

    /// `(dev, ino)` of this directory and each ancestor up to `/`, found by
    /// walking `..` from the opened descriptor (INTERFACE 4.1).
    pub fn ancestry(&self) -> io::Result<Vec<(u64, u64)>> {
        let mut chain = vec![self.stat()?.id()];
        let mut cur = self.parent()?;
        for _ in 0..4096 {
            let id = cur.stat()?.id();
            if *chain.last().expect("non-empty") == id {
                return Ok(chain);
            }
            chain.push(id);
            cur = cur.parent()?;
        }
        Err(io::Error::other(
            "the directory ancestry is deeper than 4096 levels",
        ))
    }

    /// Flip one bit of a file Stewart just wrote (test builds' `corrupt`).
    #[cfg(feature = "fault-injection")]
    pub fn corrupt_file(&self, name: &str) -> io::Result<()> {
        use std::io::{Seek, SeekFrom};
        let c = cstr(name)?;
        let fd = unsafe {
            libc::openat(
                self.file.as_raw_fd(),
                c.as_ptr(),
                libc::O_RDWR | libc::O_NOFOLLOW | libc::O_CLOEXEC,
            )
        };
        if fd < 0 {
            return Err(io::Error::last_os_error());
        }
        let mut f = unsafe { File::from_raw_fd(fd) };
        let mut first = [0u8; 1];
        let n = f.read(&mut first)?;
        f.seek(SeekFrom::Start(0))?;
        if n == 0 {
            // An empty file has no bit to flip; one byte is appended instead.
            f.write_all(&[1])?;
        } else {
            f.write_all(&[first[0] ^ 1])?;
        }
        f.sync_all()
    }

    /// Remove every file in this directory (the `remove_partial_on_retry`
    /// sabotage control only; the product never removes anything).
    #[cfg(feature = "sabotage")]
    pub fn sabotage_remove_files(&self) {
        if let Ok(names) = self.names() {
            for n in names {
                if let Ok(c) = cstr(&n) {
                    unsafe { libc::unlinkat(self.file.as_raw_fd(), c.as_ptr(), 0) };
                }
            }
        }
    }

    /// `renameat` over an existing name (the `rewrite_record_in_place`
    /// sabotage control only).
    #[cfg(feature = "sabotage")]
    pub fn sabotage_rename_over(&self, from: &str, to_dir: &Dir, to: &str) -> io::Result<()> {
        let a = cstr(from)?;
        let b = cstr(to)?;
        if unsafe {
            libc::renameat(
                self.file.as_raw_fd(),
                a.as_ptr(),
                to_dir.file.as_raw_fd(),
                b.as_ptr(),
            )
        } != 0
        {
            return Err(io::Error::last_os_error());
        }
        Ok(())
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Step {
    Create,
    Write,
    SyncFile,
    SyncDir,
}

impl Step {
    pub fn name(self) -> &'static str {
        match self {
            Step::Create => "create",
            Step::Write => "write",
            Step::SyncFile => "fsync file",
            Step::SyncDir => "fsync directory",
        }
    }
}

#[derive(Debug)]
pub struct WriteError {
    pub step: Step,
    pub err: io::Error,
}

#[derive(Debug)]
pub enum ReadError {
    Missing,
    NotRegular(Kind),
    TooLarge {
        size: u64,
        limit: u64,
    },
    /// Identity, size or mtime changed while reading.
    Changed,
    Io(io::Error),
}

impl ReadError {
    pub fn describe(&self) -> String {
        match self {
            ReadError::Missing => "missing".into(),
            ReadError::NotRegular(k) => format!("not a regular file ({})", k.name()),
            ReadError::TooLarge { size, limit } => {
                format!("{size} bytes exceeds the bound of {limit}")
            }
            ReadError::Changed => "changed while it was being read".into(),
            ReadError::Io(e) => crate::util::describe(e),
        }
    }
}

/// Read `f` (whose pre-read stat is `before`) completely, refusing more than
/// `limit` bytes and any change of identity, size or mtime during the read.
pub fn read_bounded(mut f: File, before: &Stat, limit: u64) -> Result<Vec<u8>, ReadError> {
    if before.size > limit {
        return Err(ReadError::TooLarge {
            size: before.size,
            limit,
        });
    }
    let mut bytes = Vec::with_capacity(before.size as usize);
    (&mut f)
        .take(limit + 1)
        .read_to_end(&mut bytes)
        .map_err(ReadError::Io)?;
    if bytes.len() as u64 > limit {
        return Err(ReadError::TooLarge {
            size: bytes.len() as u64,
            limit,
        });
    }
    let after = fstat(&f).map_err(ReadError::Io)?;
    if after != *before || after.size != bytes.len() as u64 {
        return Err(ReadError::Changed);
    }
    Ok(bytes)
}
