//! Prospective command effects (INTERFACE 5.10), compiled into both help and
//! the structured inspection reply. Looking up a command never calls it.
use crate::json::J;

type Effect = (&'static str, &'static str, &'static str);

struct Variant {
    form: &'static str,
    runtime: &'static str,
    possible: &'static [Effect],
}

const fn common(form: &'static str, possible: &'static [Effect]) -> Variant {
    Variant {
        form,
        runtime: "common",
        possible,
    }
}

const NEW: &[Variant] = &[common(
    "stewart new FOLDER [--archive ROOT] [--json]",
    &[
        (
            "always",
            "read",
            "Inspect the absolute submission folder and archive. STEWART_ARCHIVE can supply the archive for new.",
        ),
        (
            "when creating a reference",
            "write",
            "Initialize the archive if needed and create a new reference bound to this writer. Scaffold an absent folder. Existing submission files stay in place.",
        ),
        (
            "after interruption or reply loss",
            "interruption",
            "A folder, archive or reference may already exist. Inspect status --archive ROOT and the submission folder before repeating new.",
        ),
        (
            "on repeat",
            "repeat",
            "Each successful new creates its own reference, even for the same folder.",
        ),
    ],
)];
const PREPARE: &[Variant] = &[common(
    "stewart prepare REF [--json]",
    &[
        (
            "always",
            "read",
            "Inspect the reference, question, selected guidance and materials, their names and bounds, and the destination.",
        ),
        (
            "when preparation succeeds",
            "write",
            "Store the selection, hashes and readable and machine arrangements. Return the handle for this preparation.",
        ),
        (
            "on refusal or interruption",
            "interruption",
            "A diagnostic or partial preparation may remain. Inspect status for the latest recorded preparation and its handle.",
        ),
        (
            "when editing or repeating",
            "repeat",
            "Finish editing and prepare again for a fresh handle. Commission accepts only the current exact selection.",
        ),
        (
            "always",
            "custody",
            "Preparation accepts nothing and starts no auditor.",
        ),
    ],
)];
const COMMISSION: &[Variant] = &[common(
    "stewart commission REF HANDLE --i-am-finished [--json]",
    &[
        (
            "before acceptance",
            "read",
            "Check the writer, latest handle, explicit declaration and current folder against the preparation.",
        ),
        (
            "during intake",
            "write",
            "Capture and verify the question, materials and selected guidance and bind the receipt with an accepted record.",
        ),
        (
            "on refusal or interruption",
            "interruption",
            "An attempt, partial captures or diagnostic can remain without acceptance. A lost reply leaves acceptance unknown to the caller. Inspect status and receipt.",
        ),
        (
            "on repeat",
            "repeat",
            "Repeating the accepted handle reports the recorded acceptance. A failed intake keeps its captures. Correct the reported condition and use the current handle.",
        ),
        (
            "after acceptance",
            "custody",
            "Later folder changes do not change the accepted commission. Only its exact writer can run or close it.",
        ),
    ],
)];
const RECEIPT: &[Variant] = &[
    common(
        "stewart receipt REF [--json]",
        &[(
            "always",
            "read",
            "Read the accepted receipt and its captured item identities from the archive. Repeat during a run or after closure.",
        )],
    ),
    common(
        "stewart receipt REF --verify [--json]",
        &[(
            "always",
            "read",
            "Read and verify each captured item against its recorded size and digest and report individual failures.",
        )],
    ),
    common(
        "stewart receipt REF --read ITEM",
        &[(
            "when verification succeeds",
            "read",
            "Read the accepted capture, verify the item and emit its exact bytes on stdout. The verification line goes to stderr. question-body also verifies the whole question file.",
        )],
    ),
];
const STATUS: &[Variant] = &[
    common(
        "stewart status REF [--details | --json]",
        &[
            (
                "always",
                "read",
                "Read archive records and observe the active lock. Report uncertainty, historical refusals, the last recorded stop and supported next commands.",
            ),
            (
                "after interruption or reply loss",
                "repeat",
                "Inspect again to reconcile acceptance, launch, seal, delivery and closure before repeating a mutation.",
            ),
        ],
    ),
    common(
        "stewart status --archive ROOT [--details | --json]",
        &[(
            "always",
            "read",
            "List references in the named archive with independently observed state and supported next commands. No reference is selected.",
        )],
    ),
];
const RUN_FORM: &str = "stewart run REF [--key-fd FD] [--details | --json]";
const RUN: &[Variant] = &[
    Variant {
        form: RUN_FORM,
        runtime: "messages",
        possible: &[
            (
                "before a placement",
                "read",
                "Check the accepted commission, exact writer, authoring state, lock, limits and provider configuration.",
            ),
            (
                "when a Messages placement requires authentication",
                "credential",
                "Read one Anthropic API key from --key-fd FD or ANTHROPIC_API_KEY. With the descriptor route, unset the environment key. The two sources together are refused.",
            ),
            (
                "on launch",
                "process",
                "Run the Messages loop in the foreground. A run_started record reserves a placement. The record alone establishes neither authentication nor a provider request.",
            ),
            (
                "when sending a request",
                "network",
                "Contact the Anthropic Messages API, or the explicit provider URL, using the configured proxy if present. A loopback fake provider exercises the same custody rules.",
            ),
            (
                "when sending a request",
                "transmit",
                "Send model and system instructions, tool definitions, the accepted question, conversation and tool results including material pages read by the auditor. A full read page can carry 64 KiB.",
            ),
            (
                "when a response calls an unlisted tool",
                "write",
                "Capture the call and return tool_unknown. The auditor can correct it in a subsequent turn.",
            ),
            (
                "during a placement",
                "write",
                "Record requests, attempts, responses, tool calls, entry versions and the run ending. Submission seals the answer and initiates verified delivery.",
            ),
            (
                "while requesting",
                "limit",
                "Turns and input/output tokens accumulate across placements. The per-response cap is 16,000 tokens including thinking. Usage is recorded from responses or estimated for uncovered attempts.",
            ),
            (
                "on a retryable HTTP, timeout or connection failure",
                "repeat",
                "Retry the same request up to four attempts, checking remaining allowances. Local DNS, proxy, TLS or connection failures can exhaust retries and interrupt the placement.",
            ),
            (
                "after a signal, process loss or lost reply",
                "interruption",
                "Inspect status, the recorded cause, allowances and stopping evidence. An eligible run continues in a fresh placement. A sent request can have effects without a complete response.",
            ),
            (
                "after submission",
                "custody",
                "The seal stands, even if delivery fails. Check status for verified members and losses. Close handles outstanding delivery without another investigation.",
            ),
        ],
    },
    #[cfg(feature = "claude-code")]
    Variant {
        form: "stewart run REF [--details | --json]",
        runtime: "claude-code",
        possible: &[
            (
                "before launch",
                "read",
                "Verify the captured runtime profile, pinned executable, commissioned arrangement, private directory ancestry, remaining placements and observed stopping.",
            ),
            (
                "on an authorized placement",
                "credential",
                "Run the pinned harness's subscription authentication check using its own configuration. Credential arguments and credential environment variables are refused. There is no API fallback.",
            ),
            (
                "on reservation",
                "process",
                "Reserve one start, then supervise the authentication and model processes. Startup can stop before either process runs. The launch record alone establishes neither.",
            ),
            (
                "while the harness runs",
                "network",
                "The harness manages provider access. Local socket, relay or network failures can interrupt the placement. Stewart cannot infer which remote requests reached the provider.",
            ),
            (
                "when supplying input and tool results",
                "transmit",
                "Send the question, instructions and subsequent tool results through the harness. Full 64 KiB read pages request a 500,000-character inline threshold. Exact MCP bytes alone do not establish what appeared in the conversation.",
            ),
            (
                "if an unlisted tool is requested",
                "limit",
                "The hook denies an unlisted tool. An observed assistant call outside the commissioned inventory stops the placement.",
            ),
            (
                "during the placement",
                "write",
                "Record harness traffic, observations and accepted tool effects. The same authoring, seal and delivery rules apply.",
            ),
            (
                "on API retry or relay loss",
                "interruption",
                "Request zero harness retries. An observed API retry or relay loss stops the placement. Inspect status for the recorded cause and whether process-group stopping was established.",
            ),
            (
                "at a deadline or placement limit",
                "limit",
                "Enforce the commissioned starts and deadline. Usage comes from reported checkpoints and may remain partial or unknown, including after submission.",
            ),
            (
                "after interruption",
                "repeat",
                "Only an eligible, separately authorized start can continue. A refused call, uncertain stopping or exhausted starts confer no permission to retry.",
            ),
            (
                "after submission",
                "custody",
                "Keep the seal and account for delivery and closure independently of process stopping and usage completeness.",
            ),
        ],
    },
];
const CLOSE: &[Variant] = &[
    common(
        "stewart close REF [--details | --json]",
        &[
            (
                "always",
                "read",
                "Check the writer, close state, recorded placements, seal and delivery.",
            ),
            (
                "on the first close",
                "write",
                "Record the close request and end authoring. An active run is asked to stop. Before launch, close records closure without creating a return.",
            ),
            (
                "after launch",
                "custody",
                "Keep an existing seal or seal the recorded selection as manager. Deliver to a fresh package and verify by rereading. An ordinary close can settle an already verified delivery.",
            ),
            (
                "on interruption or a partial delivery",
                "interruption",
                "A request, seal, partial package, or verified delivery may stand without closure. Inspect status for the supported continuation, confirmation or named losses.",
            ),
            (
                "on repeat",
                "repeat",
                "Continue the recorded close or report completed closure. Earlier packages stay intact.",
            ),
        ],
    ),
    common(
        "stewart close REF --destination DIR [--details | --json]",
        &[
            (
                "when delivery is still owed",
                "read",
                "Validate the existing replacement directory and its separation from the submission and archive.",
            ),
            (
                "when copying",
                "write",
                "Plan a fresh delivery, copy the sealed members and verify the resulting package. Partial writes are retained.",
            ),
            (
                "after interruption",
                "repeat",
                "Read status before repeating. An existing package is never overwritten or adopted.",
            ),
        ],
    ),
    common(
        "stewart close REF --confirm TOKEN [--surrender LOSS]... [--details | --json]",
        &[
            (
                "when confirming",
                "read",
                "Check the token and the exact set of named losses against the outstanding verified delivery.",
            ),
            (
                "when the bindings match",
                "custody",
                "Record placement confirmation and any explicitly surrendered losses, then close. Confirmation acknowledges custody of this copy.",
            ),
            (
                "after reply loss",
                "repeat",
                "Inspect status for completed closure and surrendered losses before repeating.",
            ),
        ],
    ),
];
const HELP: &[Variant] = &[common(
    "stewart help [TOPIC]",
    &[(
        "always",
        "read",
        "Print help compiled into this binary. No reference, provider or credentials are required.",
    )],
)];
const DESCRIBE: &[Variant] = &[common(
    "stewart describe COMMAND [--json]",
    &[(
        "always",
        "read",
        "Inspect compiled descriptions in this binary. Reading them has no filesystem, network, credential or audit effects.",
    )],
)];
const MCP_FORM: &str = "stewart manager-mcp [--workspace DIR]";
const MCP: &[Variant] = &[
    common(
        MCP_FORM,
        &[(
            "on a discover call",
            "read",
            "Serve compiled family descriptors on stdio.",
        )],
    ),
    common(
        MCP_FORM,
        &[(
            "on an explain call",
            "read",
            "Explain the selected family's requirements and advice from compiled descriptors.",
        )],
    ),
    common(
        MCP_FORM,
        &[
            (
                "on an assess call",
                "read",
                "Assess only the supplied question and material inventory on stdio. The server opens no submission or archive and contacts no provider.",
            ),
            (
                "on repeat",
                "repeat",
                "Each assessment uses only that call's inputs. It creates no files, preparation, handle or commission.",
            ),
        ],
    ),
    common(
        MCP_FORM,
        &[
            (
                "at launch with --workspace DIR",
                "read",
                "Check that DIR is an existing absolute directory outside any Stewart store or delivery package, by metadata only. Otherwise exit 2 before reading stdin.",
            ),
            (
                "on an assemble call",
                "read",
                "Generate the question file from the supplied fields and body, and read only the named source files under DIR/sources/, checking intake rules, links, hard links and mounts. A dry run writes nothing. Without a workspace only a dry run without source files works.",
            ),
            (
                "on an assemble call with create:true",
                "write",
                "Create one new candidate folder in DIR, named by destination: the folder, its directories, then each file exclusively (0700 directories, 0600 files), each verified by rereading. An existing name is refused, never reused or overwritten.",
            ),
            (
                "on a failed creation or interruption",
                "interruption",
                "Created entries are left in place for inspection and the reply names them and any incomplete file. After a lost reply, inspect the folder with ordinary tools; its presence alone does not establish completion.",
            ),
            (
                "on repeat",
                "repeat",
                "Each call uses only its own inputs. Retry a creation with a fresh destination. The CLI prepares and commissions a candidate; assembly accepts nothing.",
            ),
        ],
    ),
];
const COMMANDS: &[(&str, &[Variant])] = &[
    ("new", NEW),
    ("prepare", PREPARE),
    ("commission", COMMISSION),
    ("receipt", RECEIPT),
    ("status", STATUS),
    ("run", RUN),
    ("close", CLOSE),
    ("help", HELP),
    ("describe", DESCRIBE),
    ("manager-mcp", MCP),
];

fn variants(name: &str) -> Option<&'static [Variant]> {
    COMMANDS
        .iter()
        .find(|(command, _)| *command == name)
        .map(|(_, variants)| *variants)
}

pub fn data(name: &str) -> Option<J> {
    let rows = variants(name)?
        .iter()
        .map(|v| {
            let possible = v
                .possible
                .iter()
                .map(|&(when, kind, description)| {
                    J::obj()
                        .with("when", when)
                        .with("kind", kind)
                        .with("description", description)
                })
                .collect();
            J::obj()
                .with("form", v.form)
                .with("runtime", v.runtime)
                .with("possible", J::Arr(possible))
        })
        .collect();
    Some(
        J::obj()
            .with("schema", "stewart.command-effects/1")
            .with("command", name)
            .with("variants", J::Arr(rows)),
    )
}

pub fn human(name: &str) -> Option<String> {
    use std::fmt::Write;
    let mut text = String::new();
    for variant in variants(name)? {
        writeln!(&mut text, "{} ({})", variant.form, variant.runtime).unwrap();
        for &(when, kind, description) in variant.possible {
            writeln!(&mut text, "  {kind}, {when}: {description}").unwrap();
        }
    }
    Some(text)
}

pub fn help() -> String {
    let mut text = String::from("\nPossible effects by command\n");
    for (command, _) in COMMANDS {
        text.push('\n');
        text.push_str(&human(command).expect("listed command"));
    }
    text
}
