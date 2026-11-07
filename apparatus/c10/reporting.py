"""Read-only assembly of checked observations and explicitly attributed text."""
from datetime import datetime, timezone
import math
from pathlib import Path
import re
import tarfile
import time

from common import (REPO, compact, digest, fields, file_hash, identifier, read_file,
                    require, strict_json, write_json)
from verify import Evidence, verify


class ReportError(ValueError):
    """Only fixed codes cross the public diagnostic boundary."""
    def __init__(self, code):
        require(code in ['invalid_report_input','source_changed','output_exists',
                        'output_overlaps_evidence'], 'unknown report error')
        self.code = code
        super().__init__(code)


def identity(path, raw=None):
    return {'path':str(path.resolve()), 'sha256':digest(raw) if raw is not None else file_hash(path)}


def reviewer_sources():
    # Bind the code that reads, checks and assembles this position. Unrelated
    # test or prose edits do not create a different evidentiary position.
    paths = ['apparatus/c10/'+name+'.py' for name in
             ['reporting','verify','common','study','study_build']]
    paths += ['apparatus/sanity/session_support.py']
    paths += ['apparatus/driver/'+name+'.py' for name in ['answer_witness','driver_core','rawjson']]
    return [{'path':path,'sha256':file_hash(REPO/path)} for path in paths]


def review_exports(folder):
    """Review all exports; a bad snapshot must not erase the rest of the inventory."""
    folder = Path(folder)
    raw = read_file(folder/'PLAN.json')
    plan = strict_json(raw)
    require(plan['schema']=='stewart.c10-plan/1','unsupported plan')
    packet = plan['commission']
    ids = [item['id'] for item in packet['runs']]
    require(all(identifier(name) for name in ids) and len(ids)==len(set(ids)), 'invalid audit inventory')
    require(plan['audits']==ids and plan['binary_sha256']==packet['bindings']['binary_sha256'],
            'plan binding differs')
    results = []
    for item in packet['runs']:
        audit_folder = folder/item['id']
        snapshots = []
        if audit_folder.exists():
            for path in sorted(audit_folder.iterdir()):
                require(re.fullmatch(r'export-[0-9]{4}',path.name) and path.is_dir() and not path.is_symlink(),
                        'unknown export member')
                row = {'snapshot':path.name, 'source':None, 'interval':None,
                       'export':'unknown', 'reasons':[], 'review':None}
                e = None
                stage = 'export_metadata_unreadable'
                try:
                    raw_meta = read_file(path/'EXPORT.json')
                    row['source'] = identity(path/'EXPORT.json',raw_meta)
                    meta = strict_json(raw_meta)
                    require(meta['outcome'] in ['exported','withheld','failed'],'unknown export outcome')
                    require(all(type(meta[key]) in [float,int] and math.isfinite(meta[key])
                                for key in ['started_at','ended_at'])
                            and 0 <= meta['started_at'] <= meta['ended_at'] < 253402300799,
                            'invalid export interval')
                    row.update(export=meta['outcome'], interval=[meta['started_at'],meta['ended_at']])
                    # These source facts exist in the original export format too.
                    # Derive reasons; do not rewrite or migrate the source receipt.
                    if meta['evidence_state'] != 'complete':
                        row['reasons'].append('evidence_incomplete')
                    if meta['scan']['files_with_matches']:
                        row['reasons'].append('credential_match')
                    if meta['scan']['errors']:
                        row['reasons'].append('scan_incomplete')
                    if meta['outcome']=='failed':
                        row['reasons'].append('archive_write_failed')
                    if meta['outcome']=='exported':
                        stage = 'export_archive_unreadable_or_identity_differs'
                        require(not row['reasons'],'export contradicts safety checks')
                        require((path/'work.tar').stat().st_size==meta['archive']['bytes'],'export size differs')
                        e = Evidence(path/'work.tar',meta['archive']['sha256'])
                        row['archive'] = {'path':str((path/'work.tar').resolve()), **meta['archive']}
                        binding = e.json('evidence/binding.json')
                        stage = 'export_crossed_audit_binding'
                        require(binding['commission']==packet and binding['run']==item
                                and binding['binary_sha256']==plan['binary_sha256'],'export crossed audit binding')
                        row['review'] = verify(e)
                        if row['review']['outcome']=='checked':
                            stage = 'caller_observation_unreadable'
                            execution = e.json('evidence/RESULT.json')
                            require(type(execution['caller_reply_lost']) is bool,'invalid caller observation')
                            row['caller_reply_lost'] = execution['caller_reply_lost']
                except (OSError, ValueError, KeyError, TypeError, IndexError, UnicodeError, tarfile.TarError):
                    row['review'] = None
                    row['reasons'].append(stage)
                finally:
                    if e is not None:
                        e.close()
                snapshots.append(row)
        results.append({'audit':item['id'],'case':item['case'],'snapshots':snapshots})
    return {'schema':'stewart.c10-batch-review/2','plan':identity(folder/'PLAN.json',raw),
            'commission':packet,'planned':len(ids),'audits':results}


def read_session(folder, ids):
    path = folder/'RESULT.json'
    value = {'source':None,'assessment':'missing','record':None}
    try:
        raw = read_file(path)
        value['source'] = identity(path,raw)
        record = strict_json(raw)
        if record.get('schema') != 'stewart.c10-session/2':
            value['assessment'] = 'unsupported_schema'
            return value
        require([row['audit'] for row in record['audits']]==ids, 'session inventory differs')
        require(record['planned']==len(ids), 'session count differs')
        require(record['mode'] in ['live','rehearse'] and type(record['local_iteration_only']) is bool,
                'session scope invalid')
        require(all(row['placement'] in ['observed','unknown','not_started'] for row in record['audits']),
                'session placement invalid')
        require(record['observed']==sum(row['placement']=='observed' for row in record['audits'])
                and record['not_started']==sum(row['placement']=='not_started' for row in record['audits'])
                and record['failed']==sum(row.get('failed') is True for row in record['audits']),
                'session counts differ')
        value.update(assessment='read',record=record)
    except FileNotFoundError:
        pass
    except (OSError,ValueError,KeyError,TypeError,UnicodeError):
        value['assessment'] = 'unreadable'
    return value


def latest_review(audit):
    if not audit['snapshots']:
        return None
    snapshot = audit['snapshots'][-1]
    review = snapshot.get('review')
    return review if review and review['outcome']=='checked' else None


def reference(base, value):
    fields(value,['path','sha256'],'source reference')
    require(isinstance(value['path'],str) and value['path'], 'source path missing')
    require(isinstance(value['sha256'],str) and re.fullmatch(r'[0-9a-f]{64}',value['sha256']), 'invalid source digest')
    path = (base/value['path']).resolve()
    raw = read_file(path)
    if digest(raw) != value['sha256']:
        raise ReportError('source_changed')
    return path,raw


def authored(base, value):
    fields(value,['author','document'],'authored text')
    require(isinstance(value['author'],str) and 0<len(value['author'])<=200, 'author missing')
    path, raw = reference(base,value['document'])
    require(len(raw)<=65536, 'authored text too large')
    return {'author':value['author'],'source':identity(path,raw),'text':raw.decode('utf-8')}


def assemble(manifest_path, assessment_path=None):
    """Build a reading without evaluating authored claims or changing evidence."""
    try:
        manifest_path = Path(manifest_path).resolve()
        raw = read_file(manifest_path)
        manifest = strict_json(raw)
        fields(manifest,['schema','proposal','batches'],'block')
        require(manifest['schema']=='stewart.experiment-block/1','unsupported block')
        proposal = authored(manifest_path.parent,manifest['proposal'])
        require(isinstance(manifest['batches'],list) and bool(manifest['batches']), 'no batches selected')
        batches, paths = [], set()
        for ref in manifest['batches']:
            path, plan_raw = reference(manifest_path.parent,ref)
            require(path.name=='PLAN.json' and path not in paths,'repeated or invalid batch plan')
            paths.add(path)
            batch = review_exports(path.parent)
            require(batch['plan']['sha256']==digest(plan_raw),'plan changed during review')
            batch['session'] = read_session(path.parent,[row['audit'] for row in batch['audits']])
            batches.append(batch)
        technical = {'schema':'stewart.experiment-technical/1',
                     'proposal':{'source':proposal['source'],'author':proposal['author']},
                     'reviewer_sources':reviewer_sources(), 'batches':batches}
        position = digest(compact(technical))
        assessment = None
        if assessment_path is not None:
            assessment_path = Path(assessment_path).resolve()
            account_raw = read_file(assessment_path)
            account = strict_json(account_raw)
            fields(account,['schema','technical_sha256','assessment'],'assessment')
            require(account['schema']=='stewart.experiment-assessment/1'
                    and isinstance(account['technical_sha256'],str)
                    and re.fullmatch(r'[0-9a-f]{64}',account['technical_sha256']), 'invalid assessment basis')
            assessment = {**authored(assessment_path.parent,account['assessment']),
                          'declaration':identity(assessment_path,account_raw),
                          'technical_sha256':account['technical_sha256'],
                          'basis':'current' if account['technical_sha256']==position else 'earlier_position'}
        return {'schema':'stewart.experiment-report/1','assembled_at':time.time(),
                'manifest':identity(manifest_path,raw),'proposal':proposal,
                'technical_sha256':position,'technical':technical,'assessment':assessment}
    except ReportError:
        raise
    except (OSError,ValueError,KeyError,TypeError,UnicodeError):
        raise ReportError('invalid_report_input') from None


def current_issues(report):
    """Technical gaps only; prose assessment cannot clear these observations."""
    issues = []
    for batch in report['technical']['batches']:
        label = batch['plan']['path']
        session = batch['session']
        if session['assessment'] != 'read':
            issues.append((label,'session_'+session['assessment']))
        for row in batch['audits']:
            review = latest_review(row)
            if review is None:
                issues.append((label+' / '+row['audit'],'current_evidence_unavailable_or_incomplete'))
            elif session['assessment']=='read':
                observed = next(r for r in session['record']['audits'] if r['audit']==row['audit'])
                if observed['placement']=='not_started':
                    issues.append((label+' / '+row['audit'],'placement_observed_after_not_started_record'))
    return issues


def render(report):
    """Human reading uses the same values as the JSON; no additional verdict."""
    proposal = report['proposal']
    lines = ['# Experiment report','',f"Assembled {datetime.fromtimestamp(report['assembled_at'],timezone.utc).isoformat()}.",
             '',f"## Proposal — attributed to {proposal['author']}",'',proposal['text'],'',
             source_link('Proposal source',proposal['source'])+'.']
    lines += assessment_reading(report)
    lines += ['', '## Checked technical observations','',
             'Procedural checks do not establish answer quality, model competence or billing.',
             f"Technical position: `{report['technical_sha256']}`."]
    for batch in report['technical']['batches']:
        packet = batch['commission']
        label = Path(batch['plan']['path']).parent
        label = label.parent.name if label.name in ['results','container'] else label.name
        limits = packet['limits']
        lines += ['',f"### Batch: {label}",'',
                  f"{batch['planned']} planned audit(s); model `{packet['model']}`. "+source_link('Commission and placement inventory',batch['plan'])+'.',
                  f"Per audit: at most {limits['turns']:,} turns, {limits['input_tokens']:,} input tokens and {limits['output_tokens']:,} output tokens; watchdog {packet['stop_after_seconds']:,} seconds.",
                  f"At most {packet['max_placements']} placement; {packet['permitted_request_attempts']} built-in attempts per provider request; automatic continuation {'permitted' if packet['automatic_continuation'] else 'not permitted'}."]
        if packet.get('study_build'):
            lines += ['The commission declares an unqualified study build.']
        session = batch['session']
        if session['assessment']=='read':
            r = session['record']
            lines += [f"Batch-end record: {r['observed']} observed, {r['failed']} failed, {r['not_started']} not started.",
                      f"Scope: {'native iteration only' if r['local_iteration_only'] else 'Linux batch'}; mode `{r['mode']}`."]
            if r['halt'] is not None:
                lines += [f"Placement policy stopped after `{r['halt']['audit']}`: `{r['halt']['reason']}`. No continuation authorized."]
            if r['skipped_checks']:
                lines += ['Skipped checks: '+', '.join(r['skipped_checks'])+'.']
        else:
            lines += ['Batch-end record: '+session['assessment'].replace('_',' ')+'; no inference about unobserved execution.']
        if session['source']:
            lines += [source_link('Batch-end source',session['source'])+'.']
        for row in batch['audits']:
            lines += ['',f"#### Audit `{row['audit']}` ({row['case']})",'']
            if session['assessment']=='read':
                placement = next(r for r in session['record']['audits'] if r['audit']==row['audit'])
                lines += [f"Placement at batch end: `{placement['placement']}`."]
                if 'failure' in placement:
                    # Fixed safe classifications; arbitrary exception messages are never included.
                    detail = placement['failure']
                    lines += [f"Operation failure: `{detail.get('error_type','unknown')}`; phase `{detail.get('phase','unknown')}`. Inspect retained private records."]
            if not row['snapshots']:
                lines += ['No collected snapshot. Evidence, ending, usage and custody remain unknown.']
            checked = [i for i,s in enumerate(row['snapshots']) if s['review'] and s['review']['outcome']=='checked']
            for index,snapshot in enumerate(row['snapshots']):
                current = index==len(row['snapshots'])-1
                ended = ('time unknown' if snapshot['interval'] is None else
                         datetime.fromtimestamp(snapshot['interval'][1],timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'))
                receipt = source_link(snapshot['snapshot'],snapshot['source']) if snapshot['source'] else snapshot['snapshot']
                lines += ['',f"{'Latest collection' if current else 'Earlier collection'}: {ended} ({receipt}); export {snapshot['export']}."]
                if snapshot['reasons']:
                    lines += ['Collection reasons: '+', '.join(r.replace('_',' ') for r in snapshot['reasons'])+'.']
                review = snapshot['review']
                if not review or review['outcome']!='checked':
                    lines += ['No checked observation from this snapshot; absence of an observation is not an observed absence.']
                    if review:
                        lines += ['Review reasons: '+', '.join('`'+r+'`' for r in review['failures'])+'.']
                    continue
                ending = review['ending'].replace('_',' ')
                if review['cause'] is not None:
                    ending += ' ('+review['cause'].replace('_',' ')+')'
                seal = 'unsealed' if review['seal_actor'] is None else 'sealed by '+review['seal_actor']
                lines += [f"Procedural checks completed ({len(review['checks'])}); ending: {ending}. "+
                          ('Auditor submitted' if review['auditor_submitted'] else 'No auditor submission')+
                          '; '+seal+'; '+('delivery verified' if review['delivery_verified'] else 'delivery not verified')+
                          '; custody '+('closed' if review['closed'] else 'open')+'.']
                if snapshot['caller_reply_lost']:
                    lines += ['The caller reply was lost. This later checked observation does not imply the reply was received.']
                if index==checked[-1]:
                    if not current:
                        lines += ['The following usage and coverage belong to this earlier checked snapshot; current values are unknown.']
                    for basis in ['reported','estimated']:
                        usage = review['usage']
                        lines += [f"{basis.capitalize()} usage: {usage['turns'][basis]:,} turns, {usage['input_tokens'][basis]:,} input tokens, {usage['output_tokens'][basis]:,} output tokens."]
                    coverage = review['coverage']
                    calls = ', '.join(f'{name} {count}' for name,count in coverage['operations'].items()) or 'none observed'
                    lines += ['Observed tool calls: '+calls+'.',
                              f"Selected entries: {coverage['selected_entries']}; citations checked: {coverage['citations_checked']}; refused or failed calls: {coverage['refused_or_failed_calls']}."]
                    paging = coverage['pagination']
                    lines += [f"Pagination observation: {paging['completed_read_search_calls']} completed read/search calls; {paging['incomplete_pages']} incomplete pages; {paging['next_calls_offered']} next-page calls offered; {paging['exact_next_call_attempts']} exact next-call attempts.",
                              'Witness scope: '+ '; '.join(review['witness_scope'].values())+'.']
                if current and not review['closed']:
                    lines += ['Remaining custody work: operator to inspect status and choose the authorized disposition; collection/reporting grants no close or continuation permission.']
    issues = current_issues(report)
    lines += ['', '## Remaining technical work','']
    for where,reason in issues:
        path, _, audit = where.partition(' / ')
        label = Path(path).parent.parent.name + (' / '+audit if audit else '')
        lines += [f'- [{label}](<{path}>): {reason.replace("_"," ")}; experimenter/operator to inspect the retained sources under existing authority.']
    if not issues:
        lines += ['No missing current technical observations identified. This does not settle the scientific question or independently reconcile billing.']
    lines += ['', 'Exact source hashes, observation intervals, complete checks and values are in [report.json](report.json). This report grants no model call, retry, continuation, loss surrender or spending authority.','']
    return '\n'.join(lines)


def assessment_reading(report):
    lines = ['', '## Experimenter assessment','']
    assessment = report['assessment']
    if assessment is None:
        lines += ['Pending. Scientific interpretation, cost calculation/billing disposition and any unresolved judgment or principal decision have not been supplied.',
                  'Technical review and authorized custody work do not wait for this assessment.']
    else:
        lines += [f"Attributed to {assessment['author']}; not apparatus-certified.",
                  'Assessment basis: '+assessment['basis'].replace('_',' ')+'. The exact position binding is in report.json.']
        if assessment['basis']!='current':
            lines += ['This assessment concerns an earlier technical position. The experimenter must reconcile it with the current observations; its dispositions are not assumed current.']
        lines += ['',assessment['text'],'',source_link('Assessment source',assessment['source'])+'.']
    return lines


def source_link(label, source):
    return f"[{label}](<{source['path']}>)"


def write_report(manifest, output, assessment=None):
    output = Path(output).resolve()
    if output.exists():
        raise ReportError('output_exists')
    report = assemble(manifest,assessment)
    if any(output.is_relative_to(Path(batch['plan']['path']).parent)
           for batch in report['technical']['batches']):
        raise ReportError('output_overlaps_evidence')
    output.mkdir(mode=0o700)
    write_json(output/'report.json',report)
    with (output/'report.md').open('x',encoding='utf-8') as stream:
        stream.write(render(report))
    return report
