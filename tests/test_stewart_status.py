"""The read-only session view: facts stay separate from acknowledgments and judgments.

Controls plant broken records and partial attempts, vary observation time,
advance main irrelevantly, and prove the view writes nothing.
"""

from __future__ import annotations

from datetime import timedelta
import json
from pathlib import Path

import pytest

from stewart import session as session_mod
from stewart.collect import collect
from stewart._bootstrap import StewartError
from stewart.status import status
from stewart.triage import retain, triage
import stewart_support as support
from stewart_support import read_json, response_for, snapshot_tree

pytestmark = pytest.mark.system


def test_handoff_locations_do_not_infer_activity_from_live_report(checkout):
    prepared = support.prepared_session(checkout, report=None)
    before = snapshot_tree(prepared.session)
    view = status(checkout.ws, checkout.meta['audit_id'])
    assert snapshot_tree(prepared.session) == before, 'discovering a handoff must write nothing'
    assert view['schema'] == 'stewart.status/12'
    assert view['identities']['worktree']['path'] == str(prepared.worktree)
    assert 'live_report_path' not in view['identities'], 'the manager reads collected bytes, not the live report'
    assert view['exit_code'] == 0 and view['attention'] == [], 'a ready, unlaunched session is no news'
    assert view['preparation']['launch_path'] == prepared.prepared['launch']
    assert [a['action'] for a in view['next_actions']] == ['handoff', 'launch', 'collect']
    handoff = view['next_actions'][0]
    assert handoff['cwd'] == str(prepared.worktree)
    assert handoff['launch'] == prepared.prepared['launch']
    assert 'argv' not in handoff, 'manual handoff is not a Stewart or harness command'
    # A sub-agent inherits the manager's working directory and cannot be given
    # another, so a relative prompt would open whichever handoff sits beside the
    # manager's own checkout. The prompt names both absolute locations.
    assert prepared.prepared['launch'] in handoff['prompt'] and str(prepared.worktree) in handoff['prompt']
    assert '../LAUNCH.md' not in handoff['prompt'], 'the first prompt must not depend on the working directory'
    assert 'not already handed off' in ' '.join(handoff['prerequisites'])
    launch_action = view['next_actions'][1]
    argv = launch_action['argv']
    assert argv[argv.index('launch') + 1:argv.index('launch') + 3] == ['--audit-id', checkout.meta['audit_id']]
    assert 'acknowledgment' in launch_action['external'] and launch_action['env'] == {}
    assert view['auditor_reported']['completion']['value'] is None
    assert view['session']['same_build_as_viewer'] is True, 'the fixture session was written by this build'
    assert view['tool']['package_sha256'] == view['session']['stewart']['package_sha256']

    prepared.report.write_text('Status: complete\nAn auditor may have written this.\n')
    assert status(checkout.ws, checkout.meta['audit_id']) == view, (
        'a live report must not become evidence of auditor activity or completion')
    checkout.git('commit', '--allow-empty', '-qm', 'Checkout drift', cwd=prepared.worktree)
    drifted = status(checkout.ws, checkout.meta['audit_id'])
    assert not any(a['action'] == 'handoff' for a in drifted['next_actions']), (
        'the same handoff is unsafe when the checkout no longer matches the prompt')
    assert any(a['action'] == 'collect' for a in drifted['next_actions']), 'drift still needs preservation'


def test_each_collection_has_its_own_report_locator_and_review_draft(checkout):
    prepared = support.prepared_session(checkout, report='First captured report\n')
    first = collect(checkout.ws, checkout.meta['audit_id'], auditor_stopped='interrupted')
    prepared.report.write_text('Second captured report\n')
    second = collect(checkout.ws, checkout.meta['audit_id'], auditor_stopped='finished')
    view = status(checkout.ws, checkout.meta['audit_id'])
    for captured in (first, second):
        row = next(c for c in view['collections'] if c['name'] == captured['collection'])
        assert row['report_path'] == str(Path(captured['path']) / 'REPORT.md')
        assert row['report_path'] != str(prepared.report)
        drafts = [a for a in view['next_actions'] if a['action'] == 'triage-draft'
                  and a['argv'][-1] == captured['collection']]
        assert len(drafts) == 1, 'each review must address one named collection, never just the latest report'
        assert drafts[0]['argv'][-2] == '--collection'
        assert drafts[0]['env'] == {} and drafts[0]['argv'][1:3] == ['-I', '-B'], (
            'a pasted command must not load whichever copy of the tool sits in the caller\'s directory')
    assert not any(a['action'] == 'handoff' for a in view['next_actions'])
    assert any('no launch record' in item for item in view['outstanding']), (
        'collections without a launch record leave the launch unrecorded, and status must say so once')

    # Vary bytes at the live destination without changing either captured operand.
    prepared.report.unlink()
    prepared.report.symlink_to(checkout.repo / 'other.txt')
    before = snapshot_tree(prepared.session)
    assert status(checkout.ws, checkout.meta['audit_id']) == view, 'status must not follow a live report link'
    assert snapshot_tree(prepared.session) == before
    triage(checkout.ws, checkout.meta['audit_id'], collection=first['collection'],
           response=response_for(first), actor='manager')
    drafts = [a for a in status(checkout.ws, checkout.meta['audit_id'])['next_actions']
              if a['action'] == 'triage-draft']
    assert [a['argv'][-1] for a in drafts] == [second['collection']], (
        'reviewing one capture must not hide another capture that still needs triage')


def test_missing_corrupt_and_partial_records_stay_visible_without_repair(checkout):
    ws, meta = checkout.ws, checkout.meta
    prepared = support.prepared_session(checkout, report="- Status: partial\n")
    good = collect(ws, meta["audit_id"], auditor_stopped="finished")
    session = prepared.session
    corrupt = session / "collections" / "20260101T000000-deadbeef"
    corrupt.mkdir()
    (corrupt / "STARTED.json").write_text("{}")
    (corrupt / "collection.json").write_text("{not json")
    partial = session / "collections" / "20260102T000000-cafef00d"
    partial.mkdir()
    (partial / "STARTED.json").write_text("{}")
    (session / "triage").mkdir()
    (session / "triage" / "20260103T000000-0badf00d.json").write_text("[]")
    (session / "attempts" / "20260104T000000-11111111").mkdir(parents=True)
    (session / "attempts" / "20260104T000000-11111111" / "RESERVED.json").write_text("{}")
    before = snapshot_tree(session)

    view = status(ws, meta["audit_id"])
    assert snapshot_tree(session) == before, "status must not write, repair or touch records"
    by_name = {c["name"]: c for c in view["collections"]}
    assert by_name[good["collection"]]["complete"] and by_name[good["collection"]]["problems"] == []
    assert not by_name["20260101T000000-deadbeef"]["complete"]
    assert by_name["20260101T000000-deadbeef"]["problems"][0]["reason"] == "record_corrupt"
    assert by_name["20260102T000000-cafef00d"]["problems"][0]["reason"] == "collection_incomplete"
    assert view["dispositions"][0]["problems"][0]["reason"] == "record_corrupt"
    assert view["attempts"][0]["resolved"] is False
    assert any("partial attempt" in item for item in view["outstanding"])
    assert any("reserved but unresolved" in item for item in view["outstanding"])
    assert [a["action"] for a in view["next_actions"]] == ["triage-draft", "triage"], "only the complete collection is actionable"
    assert view["next_actions"][0]["argv"][-2:] == ["--collection", good["collection"]]
    assert by_name["20260102T000000-cafef00d"]["report_path"] == str(partial / 'REPORT.md'), (
        'a partial capture keeps its recovery location without pretending its report exists')


def test_unsupported_or_foreign_session_is_reported_not_rewritten(checkout):
    ws, meta = checkout.ws, checkout.meta
    prepared = support.prepared_session(checkout)
    record_path = prepared.session / "session.json"
    original = read_json(record_path)
    legacy = dict(original, schema_version=3)
    record_path.write_text(json.dumps(legacy, indent=2, sort_keys=True) + "\n")
    before = snapshot_tree(prepared.session)
    view = status(ws, meta["audit_id"])
    assert snapshot_tree(prepared.session) == before
    assert view["session"]["supported"] is False and view["session"]["schema_version"] == 3
    assert view["session"]["problems"][0]["reason"] == "session_schema_unsupported"
    assert view["next_actions"] == [] and view["outstanding"]
    with pytest.raises(StewartError) as refused:
        collect(ws, meta["audit_id"], auditor_stopped="finished")
    assert refused.value.reason == "session_schema_unsupported"
    assert read_json(record_path) == legacy, "the unsupported record is left exactly as found"


def test_acknowledgments_are_attributed_and_completion_is_the_auditors_claim(checkout):
    from stewart.report_declaration import report_declaration
    from stewart.workspace import workspace

    ws, meta = checkout.ws, checkout.meta
    prepared = support.prepared_session(checkout, mode="paused", report=None)
    kwargs = dict(expected_worktree=prepared.worktree, launch_prompt_commit=prepared.revision,
                  prompt_sha256=prepared.prepared["prompt_sha256"], launch_token=prepared.prepared["launch_token"])
    local = workspace(prepared.worktree, ws.rel)
    report_declaration(local, "start", **kwargs)
    report_declaration(local, "set", completion="complete", report_kind="answer", **kwargs)
    collected = collect(ws, meta["audit_id"], auditor_stopped="finished")
    # Corrupting the live file cannot change the attributed captured claim.
    prepared.report.write_text("Status: partial\n```audit-report\n{broken\n")
    view = status(ws, meta["audit_id"])
    assert view["coordination"]["writers_paused"] == {"acknowledged": True, "by": "maintainer via --writers-paused",
                                                      "note": support.PAUSE_NOTE}
    assert view["collections"][0]["auditor_stopped"] == {
        "acknowledged": True, "by": "maintainer via --auditor-stopped", "kind": "finished"}
    completion = view["auditor_reported"]["completion"]
    assert completion["value"] == "complete" and completion["attributed_to"] == "auditor"
    assert completion["source"] == f"collection {collected['collection']} REPORT.md"
    assert view["collections"][0]["errors"] == [] and view["collections"][0]["gaps"] == []
    collect(ws, meta["audit_id"], auditor_stopped="finished")
    assert status(ws, meta["audit_id"])["auditor_reported"]["completion"]["value"] is None
    prepared.report.write_text("Status: complete\nStatus: partial\n")
    collect(ws, meta["audit_id"], auditor_stopped="finished")
    completion = status(ws, meta["audit_id"])["auditor_reported"]["completion"]
    assert completion["value"] is None and completion["validation"]["status"] == "missing"


def test_observation_time_does_not_enter_the_view(checkout, monkeypatch):
    ws, meta = checkout.ws, checkout.meta
    support.prepared_session(checkout, report="Status: partial\n")
    collect(ws, meta["audit_id"], auditor_stopped="finished")
    first = status(ws, meta["audit_id"])
    monkeypatch.setattr(session_mod, "now", lambda: session_mod.datetime.now(session_mod.timezone.utc) + timedelta(days=400))
    assert status(ws, meta["audit_id"]) == first


def test_irrelevant_main_advancement_leaves_pinned_evidence_usable(checkout):
    repo, ws, meta, git = checkout.repo, checkout.ws, checkout.meta, checkout.git
    support.prepared_session(checkout, report="Report A\n")
    collected = collect(ws, meta["audit_id"], auditor_stopped="finished")
    disposition = triage(ws, meta["audit_id"], collection=collected["collection"],
                         response=response_for(collected), actor="maintainer")
    (repo / "input.txt").write_text("main moved on\n")
    git("add", "input.txt")
    git("commit", "-qm", "Unrelated development on main")
    view = status(ws, meta["audit_id"])
    assert view["identities"]["maintainer"]["status_changed_since_prepare"] is True
    assert view["identities"]["worktree"]["head_matches_prompt"] is True
    assert [a["action"] for a in view["next_actions"]] == ["retain"]
    published = retain(ws, meta["audit_id"], triage=disposition["triage"], report=True)["published"]
    assert (repo / meta["report_path"]).read_text() == "Report A\n"
    assert published[0]["source"] == "REPORT.md"


def test_status_refuses_a_missing_session_but_succeeds_on_a_failed_one(checkout):
    ws, meta = checkout.ws, checkout.meta
    with pytest.raises(StewartError) as refused:
        status(ws, "never-prepared")
    assert refused.value.reason == "session_missing"
    prepared = support.prepared_session(checkout)
    (prepared.session / "PREPARE-ERROR.json").write_text(json.dumps({"error": "synthetic", "worktree_retained": True}))
    view = status(ws, meta["audit_id"])
    assert {"record": "PREPARE-ERROR.json", "reason": "prepare_failed", "message": "synthetic"} in view["session"]["problems"]
    assert view["next_actions"][0]["action"] == "fresh_assignment"
    assert not any(a['action'] == 'handoff' for a in view['next_actions'])
    collect_action = next(a for a in view["next_actions"] if a["action"] == "collect")
    assert "stop the auditor first" in collect_action["external"]


@pytest.mark.parametrize('failure_stage', ['worktree', 'inputs'])
def test_preparation_failure_preserves_state_and_offers_fresh_draft(checkout, monkeypatch, failure_stage):
    import stewart.prepare as prepare_mod
    from stewart.cli import main

    checkout.meta['base_commit'] = checkout.meta['target_commit']
    revision = checkout.prompt_commit()
    real_git = prepare_mod.git
    def fail_at_worktree(repo, *args, **kwargs):
        if args[:2] == ('worktree', 'add'):
            if failure_stage == 'worktree':
                raise StewartError('synthetic Git administration denial', reason='git_failed')
            result = real_git(repo, *args, **kwargs)
            # The next input verification fails after the checkout was created.
            (Path(args[-2]) / 'input.txt').write_text('changed after checkout')
            return result
        return real_git(repo, *args, **kwargs)
    monkeypatch.setattr(prepare_mod, 'git', fail_at_worktree)
    with pytest.raises(StewartError) as refused:
        prepare_mod.prepare(checkout.ws, revision, mode='paused', writers_paused=True, pause_note=support.PAUSE_NOTE)
    assert refused.value.reason == 'prepare_failed' and refused.value.retained and refused.value.next_steps
    session = support.session_path(checkout, checkout.meta['audit_id'])
    failure = read_json(session / 'PREPARE-ERROR.json')
    assert failure['stage'] == failure_stage
    assert failure['worktree_add_completed'] == (failure_stage == 'inputs')
    assert failure['worktree_exists_after_failure'] == (failure_stage == 'inputs')
    assert failure['cleanup_performed'] is False
    assert not (session / 'LAUNCH.md').exists()
    before = snapshot_tree(session)
    view = status(checkout.ws, checkout.meta['audit_id'])
    assert view['preparation']['state'] == 'failed'
    assert not any('worktree is gone' in item for item in view['outstanding'])
    assert view['coordination']['resumed'] is None and 'paused' in view['coordination']['hold']
    action = next(a for a in view['next_actions'] if a['action'] == 'fresh_assignment')
    assert '--replace-prompt' not in action['argv']
    assert '--target-commit' in action['argv'] and checkout.meta['target_commit'] in action['argv']
    assert action['argv'][action['argv'].index('--base-commit') + 1] == checkout.meta['base_commit']
    assert any('writer hold' in item for item in action['prerequisites'])
    # Follow the actual suggested argv as a draft operation: the old session is unchanged.
    cli_args = action['argv'][action['argv'].index('--') + 1:]
    argv = ['new-assignment' if arg == '<fresh-audit-id>' else arg for arg in cli_args]
    assert main(argv) == 0
    assert snapshot_tree(session) == before
    with pytest.raises(StewartError) as again:
        prepare_mod.prepare(checkout.ws, revision, mode='paused', writers_paused=True, pause_note=support.PAUSE_NOTE)
    assert again.value.reason == 'destination_exists', 'a failure cannot be erased by retrying in place'
    assert snapshot_tree(session) == before


def test_prepared_then_lost_checkout_differs_from_incomplete_preparation(checkout):
    import shutil

    prepared = support.prepared_session(checkout)
    assert status(checkout.ws, checkout.meta['audit_id'])['preparation']['state'] == 'ready'
    shutil.rmtree(prepared.worktree)
    view = status(checkout.ws, checkout.meta['audit_id'])
    assert view['preparation']['state'] == 'worktree_missing'
    assert not any(a['action'] == 'handoff' for a in view['next_actions'])
    assert any('worktree is gone' in item for item in view['outstanding'])
    # Without a handoff there is no evidence preparation ever completed.
    (prepared.session / 'LAUNCH.md').unlink()
    view = status(checkout.ws, checkout.meta['audit_id'])
    assert view['preparation']['state'] == 'incomplete'
    assert any(a['action'] == 'fresh_assignment' for a in view['next_actions'])
    assert not any('worktree is gone' in item for item in view['outstanding'])


def test_experiment_awaits_review_after_report_retention_then_records_release_and_attempt(tmp_path, run_cmd):
    from stewart.experiment import release, run

    checkout = support.experiment_checkout(tmp_path, run_cmd)
    prepared = support.prepared_experiment(checkout)
    (prepared.worktree / checkout.meta['report_path']).write_text('Status: complete\nConstruction finished.\n')
    collected = collect(checkout.ws, checkout.meta['audit_id'], auditor_stopped="finished")
    disposition = triage(checkout.ws, checkout.meta['audit_id'], collection=collected['collection'],
                         response=response_for(collected), actor='manager')
    retain(checkout.ws, checkout.meta['audit_id'], triage=disposition['triage'], report=True)
    view = status(checkout.ws, checkout.meta['audit_id'])
    assert view['experiment']['state'] == 'awaiting_review'
    assert [a['action'] for a in view['next_actions']] == ['release'], 'retention does not finish an execution grant'
    assert 'unassessed' in ' '.join(view['outstanding']), 'no artifact readiness or approval is inferred'
    released = release(checkout.ws, checkout.meta['audit_id'], review=support.REVIEW, actor='manager')
    assert status(checkout.ws, checkout.meta['audit_id'])['experiment']['state'] == 'released'
    run(checkout.ws, checkout.meta['audit_id'], release=released['release'], timeout=60)
    view = status(checkout.ws, checkout.meta['audit_id'])
    assert view['experiment']['state'] == 'attempt_recorded'
    assert not any(a['action'] in {'release', 'run'} for a in view['next_actions'])
    attempt = prepared.session / 'attempts' / released['release'] / 'ATTEMPT.json'
    original = read_json(attempt)
    attempt.write_text(json.dumps(dict(original, schema_version=-1)))
    assert status(checkout.ws, checkout.meta['audit_id'])['experiment']['state'] == 'records_invalid'
    attempt.unlink()
    view = status(checkout.ws, checkout.meta['audit_id'])
    assert view['experiment']['state'] == 'attempt_unresolved'
    assert not any(a['action'] == 'run' for a in view['next_actions']), 'reserved attempts are never reusable'


def test_construction_permission_never_suggests_release(tmp_path, run_cmd):
    checkout = support.experiment_checkout(tmp_path, run_cmd, permission='construction')
    support.prepared_experiment(checkout)
    view = status(checkout.ws, checkout.meta['audit_id'])
    assert view['experiment']['state'] == 'construction_only'
    assert not any(a['action'] in {'release', 'run'} for a in view['next_actions'])


RECORD_VARIANTS = ['unique', 'reformatted', 'duplicate', 'malformed', 'foreign', 'schema', 'symlink', 'missing']


def _vary_status_record(location, variant, *, preimage, release_record=False):
    """Preserve a real generated record, then alter just the property under observation."""
    original = location.read_bytes()
    preimage.write_bytes(original)
    value = json.loads(original)
    if variant == 'reformatted':
        location.write_text(json.dumps(dict(reversed(list(value.items()))), indent=4) + '\n\n')
    elif variant == 'duplicate':
        # Identical, escape-equivalent names change ambiguity, not last-key meaning.
        location.write_text('{"\\u0061udit_id": ' + json.dumps(value['audit_id']) + ',' + original.decode()[1:])
        assert json.loads(location.read_bytes()) == value
    elif variant == 'malformed':
        location.write_text('{not json')
    elif variant in {'foreign', 'schema'}:
        if variant == 'foreign':
            value['audit_id'] = 'another-audit'
        else:
            value['schema_version'] = -1
        if release_record:
            # Invalid identity/schema must be handled before interpreting grant fields.
            value['grant'] = 7
        location.write_text(json.dumps(value))
    elif variant in {'symlink', 'missing'}:
        location.unlink()
        if variant == 'symlink':
            location.symlink_to(preimage)


def _status_cli_views(checkout, capsys):
    """Inspect via both real CLI formats; broken records must not break the envelope.

    Status renders a complete view over invalid evidence. Its exit code is the
    view's own: 3 when records do not verify, 1 for anomalies, 0 for no news.
    """
    from stewart.cli import main

    args = ['--repo', str(checkout.repo), '--workspace', checkout.ws.rel]
    code = main([*args, '--json', 'status', '--audit-id', checkout.meta['audit_id']])
    captured = capsys.readouterr()
    assert not captured.err
    envelope = json.loads(captured.out)
    assert envelope['error'] is None and envelope['result'] is not None, 'broken records must not break the envelope'
    assert envelope['exit_code'] == code == envelope['result']['exit_code'] and envelope['ok'] is (code == 0)
    assert main([*args, 'status', '--audit-id', checkout.meta['audit_id']]) == code
    human = capsys.readouterr()
    assert not human.err
    return envelope['result'], human.out


@pytest.mark.parametrize('variant', RECORD_VARIANTS)
def test_release_read_failures_keep_status_usable_and_healthy_releases_visible(tmp_path, run_cmd, capsys, variant):
    from stewart.experiment import release

    checkout = support.experiment_checkout(tmp_path, run_cmd)
    prepared = support.prepared_experiment(checkout)
    ident = checkout.meta['audit_id']
    captured = collect(checkout.ws, ident, auditor_stopped='finished')
    first = release(checkout.ws, ident, review=support.REVIEW, actor='manager')
    healthy = release(checkout.ws, ident, review=support.REVIEW, actor='manager')
    baseline = status(checkout.ws, ident)
    _vary_status_record(Path(first['path']), variant, preimage=checkout.tmp / 'release.original', release_record=True)
    before = snapshot_tree(prepared.session)
    view, human = _status_cli_views(checkout, capsys)
    assert snapshot_tree(prepared.session) == before, 'status must preserve every corrupt byte, link and missing path'
    rows = {item['name']: item for item in view['releases']}
    assert rows[healthy['release']]['captured_in'] == [captured['collection']]
    assert rows[healthy['release']]['problems'] == []
    offered = [a['argv'][-1] for a in view['next_actions'] if a['action'] == 'run']
    assert healthy['release'] in offered, 'a bad neighbor must not hide a usable release'
    if variant in {'unique', 'reformatted'}:
        assert view == baseline, 'unique object key order and whitespace do not change the status facts'
        assert first['release'] in offered
    elif variant == 'missing':
        assert first['release'] not in rows and first['release'] not in offered
        assert view['experiment']['state'] == 'released', 'the surviving release remains visible'
    else:
        expected = 'record_unreadable' if variant == 'symlink' else (
            'record_schema' if variant in {'foreign', 'schema'} else 'record_corrupt')
        assert rows[first['release']]['problems'][0]['reason'] == expected
        assert view['exit_code'] == 3, 'records that do not verify set exit 3'
        assert 'grant' not in rows[first['release']]
        assert 'captured_in' not in rows[first['release']], 'failed reads cannot make capture associations'
        assert first['release'] not in offered, 'invalid records must never authorize a suggested run'
        assert view['experiment']['state'] == 'records_invalid', 'a healthy sibling must not hide invalid records'
        assert first['release'] in human and 'Traceback' not in human
        assert f'problem [{expected}]' in human, 'release read diagnostics must survive human rendering'


@pytest.mark.parametrize('kind', ['collection', 'attempt'])
@pytest.mark.parametrize('variant', RECORD_VARIANTS)
def test_status_distinguishes_absent_receipts_from_present_invalid_receipts(tmp_path, run_cmd, capsys, kind, variant):
    from stewart.experiment import release, run

    checkout = support.experiment_checkout(tmp_path, run_cmd)
    prepared = support.prepared_experiment(checkout)
    ident = checkout.meta['audit_id']
    if kind == 'collection':
        healthy = collect(checkout.ws, ident, auditor_stopped='finished')
        selected = collect(checkout.ws, ident, auditor_stopped='finished')
        name = selected['collection']
        location = Path(selected['path']) / 'collection.json'
    else:
        released = release(checkout.ws, ident, review=support.REVIEW, actor='manager')
        selected = run(checkout.ws, ident, release=released['release'])
        assert selected['errors'] == [], 'the control is an actual completed attempt'
        name = selected['attempt']
        location = Path(selected['path']) / 'ATTEMPT.json'
    baseline = status(checkout.ws, ident)
    _vary_status_record(location, variant, preimage=checkout.tmp / (kind + '.original'))
    before = snapshot_tree(prepared.session)
    view, human = _status_cli_views(checkout, capsys)
    assert snapshot_tree(prepared.session) == before, 'inspection must neither repair nor follow the planted record'
    row = next(item for item in view[kind + 's'] if item['name'] == name)
    if kind == 'collection':
        good = next(item for item in view['collections'] if item['name'] == healthy['collection'])
        assert good['complete'] and not good['problems']
        assert any(a['action'] == 'triage-draft' and a['argv'][-1] == healthy['collection'] for a in view['next_actions'])
    else:
        assert not any(a['action'] == 'run' for a in view['next_actions']), 'a consumed release stays consumed'
    if variant in {'unique', 'reformatted'}:
        assert view == baseline, 'format-only changes must leave receipt interpretation unchanged'
        return
    if variant == 'missing':
        expected = 'collection_incomplete' if kind == 'collection' else 'attempt_unresolved'
        assert row['problems'][0]['reason'] == expected
        reasons = {item['reason']: item['code'] for item in view['attention']}
        assert reasons.get(expected) == 1, 'the latest partial state is news within the manager role, not invalid evidence'
        phrase = 'is a partial attempt' if kind == 'collection' else 'is reserved but unresolved'
        assert any(f'{kind} {name} {phrase}' in message for message in view['outstanding'])
        if kind == 'attempt':
            assert view['experiment']['state'] == 'attempt_unresolved'
    else:
        expected = 'record_unreadable' if variant == 'symlink' else (
            ('collection_schema' if kind == 'collection' else 'record_schema')
            if variant in {'foreign', 'schema'} else 'record_corrupt')
        assert row['problems'][0]['reason'] == expected
        assert view['exit_code'] == 3, 'records that do not verify set exit 3'
        assert any(f'{kind} {name}' in message and 'invalid or unreadable receipt' in message
                   for message in view['outstanding']), 'recovery guidance must name invalid evidence, not an absent receipt'
        for misleading in (f'{kind} {name} is a partial attempt', f'{name}: incomplete',
                           f'attempt {name}: reserved, unresolved', f'attempt {name} is reserved but unresolved'):
            assert misleading not in human, 'receipt labels must describe this record, not unrelated review judgments'
        assert f'problem [{expected}]' in human, 'human output must retain the machine-readable refusal reason'
        if kind == 'attempt':
            assert view['experiment']['state'] == 'records_invalid'
    if kind == 'collection':
        assert not any(a['action'] in {'triage-draft', 'triage'} and '--collection' in a.get('argv', [])
                       and a['argv'][a['argv'].index('--collection') + 1] == name for a in view['next_actions'])


def test_invalid_attempt_is_not_hidden_by_a_separate_unresolved_reservation(tmp_path, run_cmd, capsys):
    from stewart.experiment import release, run

    checkout = support.experiment_checkout(tmp_path, run_cmd)
    prepared = support.prepared_experiment(checkout)
    ident = checkout.meta['audit_id']
    finished = release(checkout.ws, ident, review=support.REVIEW, actor='manager')
    unfinished = release(checkout.ws, ident, review=support.REVIEW, actor='manager')
    result = run(checkout.ws, ident, release=finished['release'])
    assert result['errors'] == []
    _vary_status_record(Path(result['path']) / 'ATTEMPT.json', 'duplicate',
                        preimage=checkout.tmp / 'attempt.original')
    # A reservation without its completed receipt models interruption before
    # publication. It must stay visible without masking its corrupt sibling.
    reserved = prepared.session / 'attempts' / unfinished['release']
    reserved.mkdir()
    session_mod.write_receipt(reserved / 'RESERVED.json', {'release': unfinished['release'], 'audit_id': ident})
    before = snapshot_tree(prepared.session)
    view, human = _status_cli_views(checkout, capsys)
    assert snapshot_tree(prepared.session) == before
    assert view['experiment']['state'] == 'records_invalid'
    assert f"attempt {unfinished['release']} is reserved but unresolved" in human
    assert f"attempt {finished['release']} has an invalid or unreadable receipt" in human
    assert not any(action['action'] == 'run' for action in view['next_actions']), 'both reservations remain consumed'
