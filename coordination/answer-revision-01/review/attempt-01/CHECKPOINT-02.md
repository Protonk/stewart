# Review checkpoint 02

The initial design and transport review passed 1,169 static assertions, with
zero failed checks. Evidence: matching scratch `static-check-01/RESULT.json`,
exact checker/command and captured Git outputs. The reviewer performed seven
read-only Git object reads, zero subject or transport executions, and zero
installed-wheel/pytest nodes. Both 117-entry and 471-entry input manifests are
verified; their exact identities are in `static-check-01/ADMITTED.json`.

No design, source, fixture or transport blocker was found. Both omitted-consumer
grants lack that implementation; both complete grants and all four fixed releases
have identical consumer bytes. Common question/recipe/producer fixtures match.
The source hypothesis is a legitimate inspection opportunity, not a required
participant outcome. Recorded controls distinguish changed artifact bytes from
unchanged text/artifact bytes and transport escaping/order changes.

Root then admitted coordinator-only study_ops.py through OPS-PIN-01.json. Static
inspection found two integration weaknesses reported to root: the author barrier
does not require the private read/process files the protocol says must be frozen
before release; packets load the barrier but do not revalidate their capture
inputs against its identities. Root can dispose these by explicit checks or a
bounded implementation correction. Normal-path failure/correction behavior is
also outside the current utility's machinery and needs explicit handling if
encountered. No coordinator code has been executed by this review.

Next: inspect root's disposition or pinned revision, verify the additional input
bindings, then save PREFLIGHT.md. No author dispatch occurred at root's last
account. All review writes remain in the assigned attempt directories.
