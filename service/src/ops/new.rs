//! `stewart new FOLDER [--archive ROOT]` (INTERFACE 5.2).

use super::{Place, check_overlap};
use crate::archive::{
    self, AUDIT_DIRS, Archive, Audit, Fail, LOCK_FILE, REFERENCE_FILE, RefFile, STORE_FILE,
};
use crate::fsx::{Dir, WalkError};
use crate::ids;
use crate::json::{self, J};
use crate::log::{self, PubErr};
use crate::platform;
use crate::reply::{Cause, Next, Reply};
use crate::util;
use std::io;

const OP: &str = "new";

fn eff(v: &'static str) -> Vec<(&'static str, &'static str)> {
    vec![("reference", v)]
}

fn parent_and_leaf(path: &str) -> (String, String) {
    let i = path.rfind('/').unwrap_or(0);
    let parent = if i == 0 {
        "/".to_string()
    } else {
        path[..i].to_string()
    };
    (parent, path[i + 1..].to_string())
}

enum Place2 {
    Existing(Dir),
    Absent { parent: Dir, leaf: String },
}

impl Place2 {
    fn chain(&self) -> io::Result<Vec<(u64, u64)>> {
        match self {
            Place2::Existing(d) => d.ancestry(),
            Place2::Absent { parent, .. } => parent.ancestry(),
        }
    }
    fn id(&self) -> Option<(u64, u64)> {
        match self {
            Place2::Existing(d) => d.stat().ok().map(|s| s.id()),
            Place2::Absent { .. } => None,
        }
    }
}

pub fn run(folder: &str, root_path: Option<&str>) -> Reply {
    match run_inner(folder, root_path) {
        Ok(r) => r,
        Err(f) => f.into_reply(OP, eff("none")),
    }
}

fn run_inner(folder: &str, root_path: Option<&str>) -> Result<Reply, Fail> {
    let Some(root_path) = root_path else {
        return Err(Fail::refused(
            "archive_unspecified",
            "new needs an archive root: give --archive ROOT, or set STEWART_ARCHIVE to an absolute path. Stewart never selects a store by default.",
        ));
    };
    // Overlap, lexically first: the authoritative identity checks follow,
    // but a folder named inside the archive (or the reverse) is refused
    // before either is looked up or created.
    let lex = |a: &str, b: &str| a == b || b == "/" || a.starts_with(&format!("{b}/"));
    if lex(folder, root_path) || lex(root_path, folder) {
        return Err(overlap_fail(folder, root_path));
    }
    let exe = platform::current_exe().map_err(|e| {
        Fail::failed(
            "writer_unavailable",
            format!(
                "Stewart could not hash its own executable to record this audit's writer: {}.",
                util::describe(&e)
            ),
        )
        .cause(Cause::io("hash running executable", &e))
    })?;

    // Locate the archive root without creating anything yet.
    let root_place = match Dir::open_nofollow(root_path) {
        Ok(d) => Place2::Existing(d),
        Err(WalkError::Missing(at)) if at == root_path => {
            let (parent, leaf) = parent_and_leaf(root_path);
            match Dir::open_nofollow(&parent) {
                Ok(p) => Place2::Absent { parent: p, leaf },
                Err(WalkError::Missing(_)) => {
                    return Err(Fail::refused(
                        "archive_unavailable",
                        format!(
                            "The archive root {root_path} does not exist and neither does its parent {parent}; Stewart creates an absent root only inside an existing directory."
                        ),
                    ));
                }
                Err(e) => return Err(archive::walk_fail(root_path, e)),
            }
        }
        Err(WalkError::NotDir(at)) if at == root_path => {
            return Err(Fail::refused(
                "archive_not_a_store",
                format!("{root_path} exists and is not a directory, so it cannot be an archive."),
            ));
        }
        Err(e) => return Err(archive::walk_fail(root_path, e)),
    };
    match &root_place {
        Place2::Existing(d) => archive::check_filesystem(d)?,
        Place2::Absent { parent, .. } => archive::check_filesystem(parent)?,
    };

    // Locate the folder.
    let folder_place = match Dir::open_follow(folder) {
        Ok(d) => Place2::Existing(d),
        Err(e) if e.raw_os_error() == Some(libc::ENOENT) => {
            let (parent, leaf) = parent_and_leaf(folder);
            match Dir::open_follow(&parent) {
                Ok(p) => Place2::Absent { parent: p, leaf },
                Err(e) => {
                    return Err(Fail::refused(
                        "folder_incomplete",
                        format!(
                            "The folder {folder} does not exist, and its parent {parent} cannot be opened ({}); Stewart scaffolds an absent folder only inside an existing directory.",
                            util::errno_name(&e)
                        ),
                    ));
                }
            }
        }
        Err(e) if e.raw_os_error() == Some(libc::ENOTDIR) => {
            return Err(Fail::refused(
                "folder_incomplete",
                format!(
                    "{folder} exists and is not a directory; the submission folder must be a directory."
                ),
            ));
        }
        Err(e) => {
            return Err(Fail::refused(
                "source_unreadable",
                format!(
                    "The folder {folder} cannot be opened: {}.",
                    util::describe(&e)
                ),
            )
            .cause(Cause::io("open folder", &e).at(folder)));
        }
    };

    // Overlap by identity, before anything is created.
    let rc = root_place.chain().map_err(|e| {
        Fail::failed(
            "location_overlap",
            format!(
                "The archive location could not be examined: {}.",
                util::describe(&e)
            ),
        )
    })?;
    let fc = folder_place.chain().map_err(|e| {
        Fail::failed(
            "location_overlap",
            format!(
                "The folder location could not be examined: {}.",
                util::describe(&e)
            ),
        )
    })?;
    if root_place.id().is_some_and(|r| fc.contains(&r))
        || folder_place.id().is_some_and(|f| rc.contains(&f))
    {
        return Err(overlap_fail(folder, root_path));
    }

    // The archive: create or initialize, or use the existing store.
    let mut archive_created = false;
    let root = match root_place {
        Place2::Existing(d) => d,
        Place2::Absent { parent, leaf } => {
            match parent.mkdir(&leaf) {
                Ok(()) => archive_created = true,
                Err(e) if e.raw_os_error() == Some(libc::EEXIST) => {}
                Err(e) => {
                    return Err(Fail::failed(
                        "archive_unavailable",
                        format!(
                            "The archive root {root_path} could not be created: {}.",
                            util::describe(&e)
                        ),
                    )
                    .cause(Cause::io("create archive root", &e).at(root_path)));
                }
            }
            archive::open_root(root_path)?
        }
    };
    let store = open_or_init_store(&root, root_path, &exe, &mut archive_created)?;
    let audits = root.ensure_dir("audits").map_err(|e| {
        Fail::failed(
            "archive_unavailable",
            format!(
                "{root_path}/audits could not be created: {}.",
                util::describe(&e)
            ),
        )
        .cause(Cause::io("create audits directory", &e).at(format!("{root_path}/audits")))
    })?;
    let archive = Archive {
        root,
        path: root_path.to_string(),
        store: store.clone(),
        moved: None,
    };

    // The folder: use it, or create the scaffold.
    let mut scaffold_created = false;
    let folder_dir = match folder_place {
        Place2::Existing(d) => d,
        Place2::Absent { parent, leaf } => {
            match parent.mkdir(&leaf) {
                Ok(()) => {}
                Err(e) if e.raw_os_error() == Some(libc::EEXIST) => {}
                Err(e) => {
                    return Err(Fail::failed(
                        "folder_incomplete",
                        format!(
                            "The folder {folder} could not be created: {}.",
                            util::describe(&e)
                        ),
                    )
                    .cause(Cause::io("create folder", &e).at(folder)));
                }
            }
            let d = Dir::open_follow(folder).map_err(|e| {
                Fail::failed(
                    "folder_incomplete",
                    format!(
                        "The new folder {folder} cannot be opened: {}.",
                        util::describe(&e)
                    ),
                )
            })?;
            if d.names().map(|n| n.is_empty()).unwrap_or(false) {
                d.write_excl("question.md", crate::frontmatter::scaffold().as_bytes())
                    .map_err(|e| {
                        Fail::failed(
                            "folder_incomplete",
                            format!(
                                "The scaffold {folder}/question.md could not be written: {}.",
                                util::describe(&e.err)
                            ),
                        )
                        .cause(
                            Cause::io(format!("write scaffold ({})", e.step.name()), &e.err)
                                .at(format!("{folder}/question.md")),
                        )
                    })?;
                d.mkdir("materials").map_err(|e| {
                    Fail::failed(
                        "folder_incomplete",
                        format!(
                            "{folder}/materials could not be created: {}.",
                            util::describe(&e)
                        ),
                    )
                    .cause(Cause::io("create materials", &e).at(format!("{folder}/materials")))
                })?;
                scaffold_created = true;
            }
            d
        }
    };
    check_overlap(&[
        Place {
            what: "archive",
            path: root_path,
            dir: &archive.root,
        },
        Place {
            what: "folder",
            path: folder,
            dir: &folder_dir,
        },
    ])?;

    // Other references naming this folder (a notice, not a refusal).
    let mut earlier = Vec::new();
    if let Ok(names) = audits.names() {
        for id in names {
            if let Ok(d) = audits.open_dir(&id) {
                if let Ok((bytes, _)) = d.read_regular(REFERENCE_FILE, archive::RECORD_LIMIT) {
                    if let Ok(r) = archive::decode_reference_file(&bytes) {
                        if r.folder == folder {
                            earlier.push((
                                r.at.clone(),
                                ids::encode_reference(&r.audit, &store, root_path),
                            ));
                        }
                    }
                }
            }
        }
    }
    earlier.sort();

    // The audit.
    let (id, dir) = loop {
        let id = ids::new_id('a').map_err(|e| {
            Fail::failed(
                "writer_unavailable",
                format!(
                    "No random identifier could be drawn: {}.",
                    util::describe(&e)
                ),
            )
        })?;
        match audits.mkdir(&id) {
            Ok(()) => {
                break (
                    id.clone(),
                    audits.open_dir(&id).map_err(|e| {
                        Fail::failed(
                            "archive_unavailable",
                            format!("audits/{id} cannot be opened: {}.", util::describe(&e)),
                        )
                    })?,
                );
            }
            Err(e) if e.raw_os_error() == Some(libc::EEXIST) => continue,
            Err(e) => {
                return Err(Fail::failed(
                    "archive_unavailable",
                    format!("audits/{id} could not be created: {}.", util::describe(&e)),
                )
                .cause(Cause::io("create audit directory", &e)));
            }
        }
    };
    let audit_path = format!("{root_path}/audits/{id}");
    let partial = |what: &str, e: &io::Error| {
        Fail::failed(
            "record_failed",
            format!(
                "The new audit's {what} could not be written ({}); no reference was created.",
                util::describe(e)
            ),
        )
        .cause(Cause::io(format!("write {what}"), e).at(audit_path.clone()))
        .retain(audit_path.clone())
    };
    for d in AUDIT_DIRS {
        dir.mkdir(d).map_err(|e| partial(d, &e))?;
    }
    let refbody = J::obj()
        .with("audit", id.as_str())
        .with("store", store.as_str())
        .with("archive", root_path)
        .with("folder", folder)
        .with(
            "writer",
            J::obj()
                .with("path", exe.path.as_str())
                .with("sha256", exe.sha256.as_str()),
        );
    let refbytes = archive::record_bytes("reference", Some(&id), &exe.sha256, refbody);
    dir.write_excl(REFERENCE_FILE, &refbytes)
        .map_err(|e| partial(REFERENCE_FILE, &e.err))?;
    dir.write_excl(LOCK_FILE, b"")
        .map_err(|e| partial(LOCK_FILE, &e.err))?;
    let reference = ids::encode_reference(&id, &store, root_path);
    let refile = RefFile {
        audit: id.clone(),
        store: store.clone(),
        folder: folder.to_string(),
        writer_path: exe.path.clone(),
        writer_sha256: exe.sha256.clone(),
        at: String::new(),
        sha256: util::sha256_hex(&refbytes),
    };
    let audit = Audit {
        archive,
        id: id.clone(),
        dir,
        reference: reference.clone(),
        refile,
        exe: Some(exe),
    };
    let published = log::publish(&audit, "reference", |s| {
        if s.recs.is_empty() {
            Ok(J::obj()
                .with("file", REFERENCE_FILE)
                .with("file_sha256", audit.refile.sha256.as_str())
                .with("folder", folder)
                .with(
                    "writer",
                    J::obj()
                        .with("path", audit.refile.writer_path.as_str())
                        .with("sha256", audit.refile.writer_sha256.as_str()),
                ))
        } else {
            Err(Fail::failed(
                "record_failed",
                "The new audit's log was not empty.",
            ))
        }
    });
    match published {
        Ok(_) => {}
        Err(PubErr::Uncertain { cause, .. }) => {
            let mut r = Fail::failed("record_failed", "The reference record was linked, but Stewart could not confirm it is durable; status reports whether it stands.")
                .cause(cause)
                .retain(audit_path.clone())
                .next(Next::new(audit.argv(&["status", &reference]), "Status reports whether this reference was recorded."))
                .into_reply(OP, eff("unknown"));
            audit.diagnose(&mut r, J::obj().with("reference", reference.as_str()));
            return Ok(r);
        }
        Err(e) => {
            let mut r = Fail::failed(
                "record_failed",
                format!(
                    "The reference record could not be published ({}); no reference was created.",
                    e.describe()
                ),
            )
            .retain(audit_path.clone())
            .into_reply(OP, eff("none"));
            if let PubErr::NotPublished(c) = e {
                r.causes.push(c);
            }
            audit.diagnose(&mut r, J::obj());
            return Ok(r);
        }
    }

    let notices: Vec<J> = if earlier.is_empty() {
        Vec::new()
    } else {
        vec![J::obj()
            .with("reason", "folder_already_referenced")
            .with(
                "message",
                format!(
                    "{} earlier reference(s) in this archive already name this folder. This new reference is separate: another commission always needs its own reference.",
                    earlier.len()
                ),
            )
            .with("references", json::strs(&earlier.iter().map(|(_, r)| r.clone()).collect::<Vec<_>>()))]
    };
    let data = J::obj()
        .with("reference", reference.as_str())
        .with("archive", root_path)
        .with("archive_created", archive_created)
        .with("folder", folder)
        .with("scaffold_created", scaffold_created)
        .with(
            "writer",
            J::obj()
                .with("path", audit.refile.writer_path.as_str())
                .with("sha256", audit.refile.writer_sha256.as_str()),
        )
        .with("notices", J::Arr(notices));
    let mut reply = Reply::completed(OP, eff("created"), data);
    reply.next.push(Next::new(
        audit.argv(&["prepare", &reference]),
        "Edit question.md and materials/, finish, then prepare. Leave the folder unchanged from prepare until commission returns.",
    ));
    Ok(reply)
}

fn overlap_fail(folder: &str, root: &str) -> Fail {
    Fail::refused(
        "location_overlap",
        format!(
            "The folder {folder} and the archive {root} overlap; the submission folder and the archive must not contain one another. Choose separate locations."
        ),
    )
}

/// Use an existing store, initialize an empty directory, or refuse.
fn open_or_init_store(
    root: &Dir,
    root_path: &str,
    exe: &platform::Exe,
    created: &mut bool,
) -> Result<String, Fail> {
    match root.read_regular(STORE_FILE, archive::RECORD_LIMIT) {
        Ok((bytes, _)) => {
            let m = archive::decode_marker(&bytes).map_err(|e| {
                Fail::refused("archive_not_a_store", format!("{root_path}/{STORE_FILE} exists but cannot be decoded ({e}); Stewart will not reinitialize or replace it."))
            })?;
            let st = root.stat().map_err(|e| {
                Fail::failed(
                    "archive_unavailable",
                    format!("{root_path} cannot be examined: {}.", util::describe(&e)),
                )
            })?;
            let birth = platform::birth_time(&root.file).ok().flatten();
            if st.ino != m.inode || (m.birth.is_some() && birth.is_some() && m.birth != birth) {
                return Err(Fail::refused(
                    "archive_moved_or_copied",
                    format!(
                        "The store marker in {root_path} was created for another root directory (a moved or copied archive); a copy never acquires execution, so new references are refused here."
                    ),
                ));
            }
            Ok(m.store)
        }
        Err(crate::fsx::ReadError::Missing) => {
            let (names, _) = root.names_bounded(2).map_err(|e| {
                Fail::failed(
                    "archive_unavailable",
                    format!("{root_path} cannot be listed: {}.", util::describe(&e)),
                )
            })?;
            if !names.is_empty() {
                return Err(Fail::refused(
                    "archive_not_a_store",
                    format!(
                        "{root_path} is not empty and has no Stewart store marker. Give an empty or absent directory, or an existing Stewart archive."
                    ),
                ));
            }
            let store = ids::new_id('s').map_err(|e| {
                Fail::failed(
                    "writer_unavailable",
                    format!(
                        "No random identifier could be drawn: {}.",
                        util::describe(&e)
                    ),
                )
            })?;
            let body = archive::marker_body(&store, root_path, root).map_err(|e| {
                Fail::failed(
                    "archive_unavailable",
                    format!("{root_path} cannot be examined: {}.", util::describe(&e)),
                )
            })?;
            let bytes = archive::record_bytes("store", None, &exe.sha256, body);
            match root.write_excl(STORE_FILE, &bytes) {
                Ok(()) => {
                    *created = true;
                    Ok(store)
                }
                Err(e)
                    if e.step == crate::fsx::Step::Create
                        && e.err.raw_os_error() == Some(libc::EEXIST) =>
                {
                    // Another new initialized it first; use that store.
                    let (bytes, _) = root
                        .read_regular(STORE_FILE, archive::RECORD_LIMIT)
                        .map_err(|e| Fail::failed("archive_unavailable", e.describe()))?;
                    archive::decode_marker(&bytes)
                        .map(|m| m.store)
                        .map_err(|e| Fail::refused("archive_not_a_store", e))
                }
                Err(e) => Err(Fail::failed(
                    "record_failed",
                    format!(
                        "The store marker {root_path}/{STORE_FILE} could not be written: {}.",
                        util::describe(&e.err)
                    ),
                )
                .cause(
                    Cause::io(format!("write store marker ({})", e.step.name()), &e.err)
                        .at(format!("{root_path}/{STORE_FILE}")),
                )
                .retain(format!("{root_path}/{STORE_FILE}"))),
            }
        }
        Err(e) => Err(Fail::refused(
            "archive_unavailable",
            format!("{root_path}/{STORE_FILE} cannot be read: {}.", e.describe()),
        )),
    }
}
