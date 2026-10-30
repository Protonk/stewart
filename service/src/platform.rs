//! The Linux-only calls Stewart depends on, in one place.
//!
//! Linux is the only supported platform (CONTRACTS, "Platform and auditor
//! access"). Each function has a Linux implementation, which is what ships,
//! and a macOS implementation that exists only so the service can be iterated
//! on natively on the development Mac. The macOS branches are development
//! fallbacks, not supported behavior:
//!
//! | Purpose | Linux (shipped) | macOS (development only) |
//! | --- | --- | --- |
//! | Active lock | `F_OFD_SETLK` / `F_OFD_GETLK` write lock | `flock` (probe briefly takes a shared lock) |
//! | Root birth time | `statx(STATX_BTIME)` | `fstat` `st_birthtime` |
//! | Writer identity | `/proc/self/exe` | `std::env::current_exe` |
//! | Filesystem allowlist | `fstatfs` `f_type` magic: ext4, xfs, btrfs | `fstatfs` `f_fstypename` "apfs" |
//! | Random bytes | `getrandom(2)` | `getentropy(3)` |
//! | errno reset | `__errno_location` | `__error` |
//! | Process start time | `/proc/self/stat` field 22 | none (recorded as null) |

use std::ffi::CString;
use std::fs::File;
use std::io::{self, Read};
use std::os::fd::{AsRawFd, FromRawFd};

/// Fill `buf` with random bytes from the kernel.
pub fn random_fill(buf: &mut [u8]) -> io::Result<()> {
    #[cfg(target_os = "linux")]
    {
        // The raw syscall, not musl's getrandom() wrapper. In the fat-LTO
        // static release build the post-LTO IR declared getrandom extern_weak,
        // so the linker never took musl's definition from libc.a and the call
        // had no definition: it returned without writing (all-zero
        // identifiers) on aarch64 and crashed on x86_64. Thin-LTO and non-LTO
        // builds linked it and worked. Where the weak linkage comes from is
        // not established; the syscall needs no library symbol.
        let mut off = 0;
        while off < buf.len() {
            let rc = unsafe {
                libc::syscall(
                    libc::SYS_getrandom,
                    buf[off..].as_mut_ptr(),
                    (buf.len() - off) as libc::c_long,
                    0 as libc::c_long,
                )
            };
            if rc < 0 {
                let e = io::Error::last_os_error();
                if e.raw_os_error() == Some(libc::EINTR) {
                    continue;
                }
                return Err(e);
            }
            off += rc as usize;
        }
        Ok(())
    }
    #[cfg(target_os = "macos")]
    {
        // Development only: getentropy serves at most 256 bytes per call.
        for chunk in buf.chunks_mut(256) {
            if unsafe { libc::getentropy(chunk.as_mut_ptr().cast(), chunk.len()) } != 0 {
                return Err(io::Error::last_os_error());
            }
        }
        Ok(())
    }
}

pub fn clear_errno() {
    #[cfg(target_os = "linux")]
    unsafe {
        *libc::__errno_location() = 0;
    }
    #[cfg(target_os = "macos")]
    unsafe {
        *libc::__error() = 0;
    }
}

// ---------------------------------------------------------------------------
// The active lock (INTERFACE 4.6).

/// Open file description lock commands from the kernel's asm-generic
/// fcntl.h. They are the same on every Linux architecture; the libc crate
/// defines them for musl but not for every libc, so they are spelled here.
#[cfg(target_os = "linux")]
const F_OFD_GETLK: libc::c_int = 36;
#[cfg(target_os = "linux")]
const F_OFD_SETLK: libc::c_int = 37;

/// Try to take the whole-file write lock on `f` without waiting.
/// `Ok(false)` means another holder has it.
pub fn lock_try(f: &File) -> io::Result<bool> {
    #[cfg(target_os = "linux")]
    {
        // Open file description lock: owned by this open file description and
        // released by the kernel when its last descriptor closes, including on
        // kill. l_pid must be 0 for OFD requests.
        let mut fl: libc::flock = unsafe { std::mem::zeroed() };
        fl.l_type = libc::F_WRLCK as libc::c_short;
        fl.l_whence = libc::SEEK_SET as libc::c_short;
        fl.l_start = 0;
        fl.l_len = 0;
        fl.l_pid = 0;
        let rc = unsafe { libc::fcntl(f.as_raw_fd(), F_OFD_SETLK, &mut fl as *mut libc::flock) };
        if rc == 0 {
            return Ok(true);
        }
        let e = io::Error::last_os_error();
        match e.raw_os_error() {
            Some(libc::EAGAIN) | Some(libc::EACCES) => Ok(false),
            _ => Err(e),
        }
    }
    #[cfg(target_os = "macos")]
    {
        // Development only: flock locks also belong to the open file description.
        let rc = unsafe { libc::flock(f.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) };
        if rc == 0 {
            return Ok(true);
        }
        let e = io::Error::last_os_error();
        match e.raw_os_error() {
            Some(libc::EWOULDBLOCK) => Ok(false),
            _ => Err(e),
        }
    }
}

/// Test whether some holder has the lock, acquiring nothing (Linux).
/// `Ok(true)` means held.
pub fn lock_held(f: &File) -> io::Result<bool> {
    #[cfg(target_os = "linux")]
    {
        let mut fl: libc::flock = unsafe { std::mem::zeroed() };
        fl.l_type = libc::F_WRLCK as libc::c_short;
        fl.l_whence = libc::SEEK_SET as libc::c_short;
        fl.l_start = 0;
        fl.l_len = 0;
        fl.l_pid = 0;
        let rc = unsafe { libc::fcntl(f.as_raw_fd(), F_OFD_GETLK, &mut fl as *mut libc::flock) };
        if rc != 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(fl.l_type != libc::F_UNLCK as libc::c_short)
    }
    #[cfg(target_os = "macos")]
    {
        // Development only: flock has no test operation, so the probe takes a
        // shared lock for an instant and releases it.
        let rc = unsafe { libc::flock(f.as_raw_fd(), libc::LOCK_SH | libc::LOCK_NB) };
        if rc == 0 {
            unsafe { libc::flock(f.as_raw_fd(), libc::LOCK_UN) };
            return Ok(false);
        }
        let e = io::Error::last_os_error();
        match e.raw_os_error() {
            Some(libc::EWOULDBLOCK) => Ok(true),
            _ => Err(e),
        }
    }
}

// ---------------------------------------------------------------------------
// Store marker observations (INTERFACE 4.9).

/// The root's birth time as `"<sec>.<nsec>"`, if the filesystem reports one.
pub fn birth_time(f: &File) -> io::Result<Option<String>> {
    #[cfg(target_os = "linux")]
    {
        // statx through the raw syscall: the libc crate exposes the wrapper on
        // musl only behind an opt-in configuration, and the kernel ABI is fixed.
        // The full kernel layout is declared; only some fields are read.
        #[allow(dead_code)]
        #[repr(C)]
        struct StatxTimestamp {
            tv_sec: i64,
            tv_nsec: u32,
            _pad: i32,
        }
        #[allow(dead_code)]
        #[repr(C)]
        struct Statx {
            stx_mask: u32,
            stx_blksize: u32,
            stx_attributes: u64,
            stx_nlink: u32,
            stx_uid: u32,
            stx_gid: u32,
            stx_mode: u16,
            _pad1: u16,
            stx_ino: u64,
            stx_size: u64,
            stx_blocks: u64,
            stx_attributes_mask: u64,
            stx_atime: StatxTimestamp,
            stx_btime: StatxTimestamp,
            stx_ctime: StatxTimestamp,
            stx_mtime: StatxTimestamp,
            stx_rdev_major: u32,
            stx_rdev_minor: u32,
            stx_dev_major: u32,
            stx_dev_minor: u32,
            _spare: [u64; 14],
        }
        const STATX_INO: u32 = 0x100;
        const STATX_BTIME: u32 = 0x800;
        let mut buf: Statx = unsafe { std::mem::zeroed() };
        let empty = b"\0";
        let rc = unsafe {
            libc::syscall(
                libc::SYS_statx,
                f.as_raw_fd() as libc::c_long,
                empty.as_ptr() as *const libc::c_char,
                libc::AT_EMPTY_PATH as libc::c_long,
                (STATX_INO | STATX_BTIME) as libc::c_long,
                &mut buf as *mut Statx,
            )
        };
        if rc != 0 {
            return Err(io::Error::last_os_error());
        }
        if buf.stx_mask & STATX_BTIME == 0 {
            return Ok(None);
        }
        Ok(Some(format!(
            "{}.{:09}",
            buf.stx_btime.tv_sec, buf.stx_btime.tv_nsec
        )))
    }
    #[cfg(target_os = "macos")]
    {
        // Development only.
        let mut st: libc::stat = unsafe { std::mem::zeroed() };
        if unsafe { libc::fstat(f.as_raw_fd(), &mut st) } != 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(Some(format!(
            "{}.{:09}",
            st.st_birthtime, st.st_birthtime_nsec
        )))
    }
}

/// Filesystem observation for the allowlist (INTERFACE 4.1).
pub struct FsInfo {
    /// The observed type, by name when known (`ext4`, `tmpfs`) or as hex magic.
    pub name: String,
    pub supported: bool,
    /// `statfs` filesystem ID, recorded as an observation only.
    pub fsid: String,
}

pub fn filesystem(f: &File) -> io::Result<FsInfo> {
    let mut st: libc::statfs = unsafe { std::mem::zeroed() };
    if unsafe { libc::fstatfs(f.as_raw_fd(), &mut st) } != 0 {
        return Err(io::Error::last_os_error());
    }
    let fsid: [libc::c_int; 2] = unsafe { std::mem::transmute_copy(&st.f_fsid) };
    let fsid = format!("{:08x}{:08x}", fsid[0] as u32, fsid[1] as u32);
    #[cfg(target_os = "linux")]
    {
        // f_type is c_long on glibc and c_ulong on musl; the magic fits in 32 bits.
        let magic = (st.f_type as u64 & 0xffff_ffff) as u32;
        let (name, supported) = match magic {
            0xEF53 => ("ext4".to_string(), true), // shared by ext2, ext3 and ext4
            0x5846_5342 => ("xfs".to_string(), true),
            0x9123_683E => ("btrfs".to_string(), true),
            0x0102_1994 => ("tmpfs".to_string(), false),
            0x794C_7630 => ("overlayfs".to_string(), false),
            0x6969 => ("nfs".to_string(), false),
            0x6573_5546 => ("fuse".to_string(), false),
            0x0102_1997 => ("v9fs".to_string(), false),
            0xFF53_4D42 => ("cifs".to_string(), false),
            0xFE53_4D42 => ("smb2".to_string(), false),
            0x5346_544E => ("ntfs".to_string(), false),
            0x4d44 => ("vfat".to_string(), false),
            0x2FC1_2FC1 => ("zfs".to_string(), false),
            0x5345_4E4F => ("drvfs".to_string(), false),
            0x9fa0 => ("proc".to_string(), false),
            0x6265_6572 => ("sysfs".to_string(), false),
            0x0000_517B => ("smb".to_string(), false),
            0xF2F5_2010 => ("f2fs".to_string(), false),
            other => (format!("0x{other:x}"), false),
        };
        Ok(FsInfo {
            name,
            supported,
            fsid,
        })
    }
    #[cfg(target_os = "macos")]
    {
        // Development only: APFS stands in for the Linux allowlist.
        let raw: Vec<u8> = st
            .f_fstypename
            .iter()
            .take_while(|c| **c != 0)
            .map(|c| *c as u8)
            .collect();
        let name = String::from_utf8_lossy(&raw).into_owned();
        let supported = name == "apfs";
        Ok(FsInfo {
            name,
            supported,
            fsid,
        })
    }
}

// ---------------------------------------------------------------------------
// Writer identity (INTERFACE 4.7).

pub struct Exe {
    pub path: String,
    pub sha256: String,
}

/// Maximum executable size hashed; the release binary is a few MiB.
const EXE_LIMIT: u64 = 512 * 1024 * 1024;

/// Hash the running executable and resolve its path.
pub fn current_exe() -> io::Result<Exe> {
    #[cfg(target_os = "linux")]
    {
        // /proc/self/exe names the executable that is actually running, even
        // if its path was replaced after exec.
        let link = CString::new("/proc/self/exe").expect("no NUL");
        let fd = unsafe { libc::open(link.as_ptr(), libc::O_RDONLY | libc::O_CLOEXEC) };
        if fd < 0 {
            return Err(io::Error::last_os_error());
        }
        let file = unsafe { File::from_raw_fd(fd) };
        let sha256 = hash_file(file)?;
        let mut buf = vec![0u8; 4096];
        let n = unsafe { libc::readlink(link.as_ptr(), buf.as_mut_ptr().cast(), buf.len()) };
        if n < 0 {
            return Err(io::Error::last_os_error());
        }
        buf.truncate(n as usize);
        let path = String::from_utf8(buf).map_err(|_| {
            io::Error::new(io::ErrorKind::InvalidData, "executable path is not UTF-8")
        })?;
        Ok(Exe { path, sha256 })
    }
    #[cfg(target_os = "macos")]
    {
        // Development only.
        let p = std::env::current_exe()?.canonicalize()?;
        let path = p
            .to_str()
            .ok_or_else(|| {
                io::Error::new(io::ErrorKind::InvalidData, "executable path is not UTF-8")
            })?
            .to_string();
        let c = CString::new(path.clone())
            .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "NUL in path"))?;
        let fd = unsafe { libc::open(c.as_ptr(), libc::O_RDONLY | libc::O_CLOEXEC) };
        if fd < 0 {
            return Err(io::Error::last_os_error());
        }
        let sha256 = hash_file(unsafe { File::from_raw_fd(fd) })?;
        Ok(Exe { path, sha256 })
    }
}

fn hash_file(mut f: File) -> io::Result<String> {
    use sha2::{Digest, Sha256};
    let mut h = Sha256::new();
    let mut buf = vec![0u8; 1 << 16];
    let mut total = 0u64;
    loop {
        let n = f.read(&mut buf)?;
        if n == 0 {
            break;
        }
        total += n as u64;
        if total > EXE_LIMIT {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "executable exceeds the hashing bound",
            ));
        }
        h.update(&buf[..n]);
    }
    Ok(crate::util::hex(&h.finalize()))
}

// ---------------------------------------------------------------------------
// Invocation observations (recorded, never used as identity or evidence of a person).

pub fn host_name() -> Option<String> {
    let mut buf = vec![0u8; 256];
    if unsafe { libc::gethostname(buf.as_mut_ptr().cast(), buf.len()) } != 0 {
        return None;
    }
    let n = buf.iter().position(|b| *b == 0).unwrap_or(buf.len());
    String::from_utf8(buf[..n].to_vec()).ok()
}

pub fn boot_id() -> Option<String> {
    #[cfg(target_os = "linux")]
    {
        let s = std::fs::read_to_string("/proc/sys/kernel/random/boot_id").ok()?;
        Some(s.trim().to_string())
    }
    #[cfg(target_os = "macos")]
    {
        None
    }
}

/// This process's start time in clock ticks since boot: field 22 of
/// `/proc/self/stat`, recorded in `run_started` with the other holder
/// observations (INTERFACE 4.6). `None` where it cannot be read, including
/// the macOS development fallback, which has no `/proc`.
pub fn start_ticks() -> Option<u64> {
    #[cfg(target_os = "linux")]
    {
        let s = std::fs::read_to_string("/proc/self/stat").ok()?;
        // Field 2 (comm) is parenthesized and may contain spaces or
        // parentheses; the fields after the last `)` start at field 3.
        let rest = &s[s.rfind(')')? + 1..];
        rest.split_ascii_whitespace().nth(22 - 3)?.parse().ok()
    }
    #[cfg(target_os = "macos")]
    {
        None
    }
}

pub fn uid() -> u32 {
    unsafe { libc::getuid() }
}

pub fn pid() -> u32 {
    std::process::id()
}
