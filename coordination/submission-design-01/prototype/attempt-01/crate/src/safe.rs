//! All access uses pinned descriptors. No path-component symlink is followed.
use crate::{Error, Result};
use std::ffi::{CStr, CString};
use std::fs::{File, Metadata};
use std::io::{Read, Write};
use std::os::fd::{AsRawFd, FromRawFd};
use std::os::unix::fs::MetadataExt;
use std::path::Path;

pub struct Dir {
    file: File,
    pub label: String,
}
fn c(s: &str) -> Result<CString> {
    CString::new(s).map_err(|_| {
        Error::new(
            "unsafe_path",
            "NUL in path",
            s,
            "Choose an explicit ordinary path.",
        )
    })
}
fn io(e: std::io::Error, path: &str) -> Error {
    let reason = match e.raw_os_error() {
        Some(libc::ENOENT) => "missing",
        Some(libc::ELOOP) | Some(libc::ENOTDIR) => "unsafe_path",
        Some(libc::EEXIST) => "destination_exists",
        _ => "unreadable",
    };
    Error::new(
        reason,
        e.to_string(),
        path,
        "Preserve existing state; inspect the named path and use the supported completion or disposition command.",
    )
}
fn openat(dir: i32, name: &str, flags: i32, mode: libc::mode_t) -> Result<File> {
    let n = c(name)?;
    let fd = unsafe {
        libc::openat(
            dir,
            n.as_ptr(),
            flags | libc::O_CLOEXEC | libc::O_NOFOLLOW,
            mode as libc::c_uint,
        )
    };
    if fd < 0 {
        Err(io(std::io::Error::last_os_error(), name))
    } else {
        Ok(unsafe { File::from_raw_fd(fd) })
    }
}
fn parts(path: &str) -> Result<Vec<&str>> {
    if !Path::new(path).is_absolute() || path.as_bytes().contains(&0) {
        return Err(Error::new(
            "unsafe_path",
            "An absolute path is required",
            path,
            "Supply an absolute path without symlinks or parent traversal.",
        ));
    }
    let mut out = Vec::new();
    for p in path.split('/').skip(1) {
        if p.is_empty() {
            continue;
        }
        if p == "." || p == ".." {
            return Err(Error::new(
                "unsafe_path",
                "Dot components are not allowed",
                path,
                "Supply the explicit absolute path.",
            ));
        }
        out.push(p);
    }
    Ok(out)
}
impl Dir {
    pub fn open(path: &str) -> Result<Self> {
        let mut f = openat(libc::AT_FDCWD, "/", libc::O_RDONLY | libc::O_DIRECTORY, 0)?;
        for p in parts(path)? {
            f = openat(f.as_raw_fd(), p, libc::O_RDONLY | libc::O_DIRECTORY, 0).map_err(
                |mut e| {
                    e.paths = vec![path.into()];
                    e
                },
            )?;
        }
        Ok(Self {
            file: f,
            label: path.into(),
        })
    }
    pub fn lock(&self) -> Result<()> {
        if unsafe { libc::flock(self.file.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) } != 0 {
            return Err(Error::new(
                "busy",
                std::io::Error::last_os_error().to_string(),
                &self.label,
                "Wait for the active mutation to stop, then inspect this same bundle.",
            ));
        }
        Ok(())
    }
    fn member(&self, name: &str) -> Result<()> {
        if name.is_empty() || name.contains('/') || name == "." || name == ".." {
            Err(Error::new(
                "unsafe_path",
                "Bundle member must be one ordinary name",
                name,
                "Do not change retained records.",
            ))
        } else {
            Ok(())
        }
    }
    pub fn read(&self, name: &str, limit: usize) -> Result<Vec<u8>> {
        self.member(name)?;
        let f = openat(
            self.file.as_raw_fd(),
            name,
            libc::O_RDONLY | libc::O_NONBLOCK,
            0,
        )?;
        read_file(f, limit, &format!("{}/{}", self.label, name))
    }
    pub fn exists(&self, name: &str) -> Result<bool> {
        self.member(name)?;
        let n = c(name)?;
        let mut st = std::mem::MaybeUninit::<libc::stat>::uninit();
        let rc = unsafe {
            libc::fstatat(
                self.file.as_raw_fd(),
                n.as_ptr(),
                st.as_mut_ptr(),
                libc::AT_SYMLINK_NOFOLLOW,
            )
        };
        if rc == 0 {
            Ok(true)
        } else {
            let e = std::io::Error::last_os_error();
            if e.raw_os_error() == Some(libc::ENOENT) {
                Ok(false)
            } else {
                Err(io(e, name))
            }
        }
    }
    pub fn names(&self) -> Result<Vec<String>> {
        // Open a fresh descriptor so readdir's position does not affect future inventories.
        let f = openat(
            self.file.as_raw_fd(),
            ".",
            libc::O_RDONLY | libc::O_DIRECTORY,
            0,
        )?;
        let fd = unsafe { libc::dup(f.as_raw_fd()) };
        if fd < 0 {
            return Err(io(std::io::Error::last_os_error(), &self.label));
        }
        let dp = unsafe { libc::fdopendir(fd) };
        if dp.is_null() {
            unsafe { libc::close(fd) };
            return Err(io(std::io::Error::last_os_error(), &self.label));
        }
        let mut out = Vec::new();
        loop {
            clear_errno();
            let ent = unsafe { libc::readdir(dp) };
            if ent.is_null() {
                let error = std::io::Error::last_os_error();
                unsafe { libc::closedir(dp) };
                if error.raw_os_error() != Some(0) {
                    return Err(io(error, &self.label));
                }
                out.sort();
                return Ok(out);
            }
            let raw = unsafe { CStr::from_ptr((*ent).d_name.as_ptr()) };
            let s = match raw.to_str() {
                Ok(s) => s.to_owned(),
                Err(_) => {
                    unsafe { libc::closedir(dp) };
                    return Err(Error::new(
                        "unsafe_path",
                        "Non-UTF-8 bundle member",
                        &self.label,
                        "Keep this directory intact and choose a fresh bundle for new intake.",
                    ));
                }
            };
            if s != "." && s != ".." {
                out.push(s);
            }
            if out.len() > 10000 {
                unsafe { libc::closedir(dp) };
                return Err(Error::new(
                    "limit_exceeded",
                    "Too many bundle directory entries",
                    &self.label,
                    "Preserve this directory; inspect its provenance.",
                ));
            }
        }
    }
    pub fn ensure_location(&self) -> Result<()> {
        let named = Self::open(&self.label)?;
        let held = self.file.metadata().map_err(|e| io(e, &self.label))?;
        let observed = named.file.metadata().map_err(|e| io(e, &self.label))?;
        if held.dev() != observed.dev() || held.ino() != observed.ino() {
            return Err(Error::new(
                "bundle_moved_during_operation",
                "The named destination no longer identifies the pinned directory",
                &self.label,
                "Preserve both locations; inspect the original bundle before treating delivery as confirmed.",
            ));
        }
        Ok(())
    }
    pub fn sync(&self) -> Result<()> {
        self.file.sync_all().map_err(|e| io(e, &self.label))
    }
    pub fn write_exclusive(&self, name: &str, bytes: &[u8]) -> Result<()> {
        self.member(name)?;
        let mut f = openat(
            self.file.as_raw_fd(),
            name,
            libc::O_WRONLY | libc::O_CREAT | libc::O_EXCL,
            0o600,
        )?;
        f.write_all(bytes).map_err(|e| io(e, name))?;
        f.sync_all().map_err(|e| io(e, name))?;
        self.sync()
    }
    /// Exclusive publication of a fully written receipt; staged evidence remains.
    pub fn write_receipt(&self, name: &str, stage: &str, bytes: &[u8]) -> Result<()> {
        self.member(name)?;
        self.member(stage)?;
        self.write_exclusive(stage, bytes)?;
        let a = c(&stage)?;
        let b = c(name)?;
        if unsafe {
            libc::linkat(
                self.file.as_raw_fd(),
                a.as_ptr(),
                self.file.as_raw_fd(),
                b.as_ptr(),
                0,
            )
        } != 0
        {
            return Err(io(std::io::Error::last_os_error(), name));
        }
        self.sync()
    }
    /// Publish a verified complete stage without syncing; caller owns its commit barrier.
    pub fn publish_unsynced(&self, name: &str, stage: &str, expected: &[u8]) -> Result<()> {
        self.member(name)?;
        self.member(stage)?;
        let observed = self.read(stage, 2 * 1024 * 1024)?;
        if observed != expected {
            return Err(Error::new(
                "integrity_error",
                "Staged receipt differs from planned bytes",
                stage,
                "Preserve this attempt; do not overwrite its staging files.",
            ));
        }
        let a = c(stage)?;
        let b = c(name)?;
        if unsafe {
            libc::linkat(
                self.file.as_raw_fd(),
                a.as_ptr(),
                self.file.as_raw_fd(),
                b.as_ptr(),
                0,
            )
        } != 0
        {
            return Err(io(std::io::Error::last_os_error(), name));
        }
        Ok(())
    }
}
fn same(a: &Metadata, b: &Metadata) -> bool {
    a.dev() == b.dev()
        && a.ino() == b.ino()
        && a.len() == b.len()
        && a.mtime() == b.mtime()
        && a.mtime_nsec() == b.mtime_nsec()
        && a.ctime() == b.ctime()
        && a.ctime_nsec() == b.ctime_nsec()
}
fn read_file(mut f: File, limit: usize, path: &str) -> Result<Vec<u8>> {
    let before = f.metadata().map_err(|e| io(e, path))?;
    if !before.is_file() {
        return Err(Error::new(
            "not_regular",
            "Only regular files may be read",
            path,
            "Select regular-file copies; do not follow links or special files.",
        ));
    }
    if before.len() > limit as u64 {
        return Err(Error::new(
            "limit_exceeded",
            "File exceeds the admitted size limit",
            path,
            "Reduce the explicitly selected input population.",
        ));
    }
    let mut bytes = Vec::new();
    std::io::Read::by_ref(&mut f)
        .take(limit as u64 + 1)
        .read_to_end(&mut bytes)
        .map_err(|e| io(e, path))?;
    let after = f.metadata().map_err(|e| io(e, path))?;
    if bytes.len() > limit || !same(&before, &after) || after.len() != bytes.len() as u64 {
        return Err(Error::new(
            "changed_during_read",
            "File changed or exceeded its bound during reading",
            path,
            "Keep the diagnostic; use stable original inputs for explicit completion.",
        ));
    }
    Ok(bytes)
}
pub fn read_absolute(path: &str, limit: usize) -> Result<Vec<u8>> {
    let ps = parts(path)?;
    let (leaf, dirs) = ps.split_last().ok_or_else(|| {
        Error::new(
            "not_regular",
            "Root is not an input file",
            path,
            "Select a regular file.",
        )
    })?;
    let parent = if dirs.is_empty() {
        "/".to_owned()
    } else {
        format!("/{}", dirs.join("/"))
    };
    let d = Dir::open(&parent)?;
    d.read(leaf, limit)
}

#[cfg(target_os = "macos")]
fn clear_errno() {
    unsafe {
        *libc::__error() = 0;
    }
}
#[cfg(target_os = "linux")]
fn clear_errno() {
    unsafe {
        *libc::__errno_location() = 0;
    }
}
