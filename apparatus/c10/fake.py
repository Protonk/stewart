"""A reacting, independently recorded auditor for offline C10 rehearsals."""
import threading
import time

from common import strict_json, require
from exercise import Fake
import driver_core as spec
from study_build import system_bytes


def follow_pages(calls, results, materials, continued):
    """Page through material reads the way the specification's envelope invites.

    A read page ends at 65,536 bytes (INTERFACE 7.2), so a larger material comes
    back incomplete with a ready ``next`` read. Returns the continuation reads to
    issue now, one per incomplete page not yet continued, and the pages seen so
    far per source as ``{source: {start: text}}``. Every source whose final page
    has arrived must reassemble to exactly its witnessed bytes.
    """
    pages, continuations, complete = {}, [], set()
    for call in calls:
        if call['name'] != 'read' or call['input'].get('source') not in materials:
            continue
        blocks = results[call['id']]
        envelope = strict_json(blocks[0]['text'])
        data = envelope['data']
        text = blocks[1]['text'] if len(blocks) > 1 else data['text']
        source = call['input']['source']
        pages.setdefault(source, {})[data['range'][0]] = text
        if data['complete']:
            complete.add(source)
        elif call['id'] not in continued:
            following = [n for n in envelope['next'] if n['tool'] == 'read' and n['input'].get('source') == source]
            require(len(following) == 1, 'fake incomplete read without a ready next page')
            continuations.append(('read', following[0]['input']))
            continued.add(call['id'])
    for source in complete:
        assembled = ''.join(text for _, text in sorted(pages[source].items())).encode()
        require(assembled == materials[source], 'fake read differs from witness')
    return continuations, pages


# One response per step, per placement. A scenario without an entry here answers
# before any step (a rejection or a reflected credential).
SUBMITS = ['orient', 'read', 'record', 'revise', 'prepare', 'inspect', 'submit']
SCRIPTS = {
    'submitted': [SUBMITS], 'lost-run-reply': [SUBMITS],
    'export-contamination': [SUBMITS], 'export-failure': [SUBMITS],
    'empty': [['prepare', 'submit']],
    'unsubmitted': [['orient', 'read', 'record', 'revise', 'prose', 'prose']],
    # A thinking-only response at the output cap, nothing recorded; then ordinary work.
    'continue-cap': [['cap'], SUBMITS],
    # The same stop after two recorded entries; the next placement finds them
    # through re-entry, revises one and removes the other by those handles.
    'continue-entries': [['orient', 'read', 'record', 'cap'],
        ['orient', 'read', 'revise_recorded', 'prepare', 'inspect_rendering', 'dry_submit', 'submit']],
    # Prose draws the reminder; the request carrying it is held until signalled.
    'reminder-spent': [['orient', 'read', 'record', 'prose', 'hold'], ['orient', 'prose']],
    'reminder-spent-submits': [['orient', 'read', 'record', 'prose', 'hold'], ['orient', 'prepare', 'submit']],
    # Nothing is withheld: the signal goes on sight of the reminder record, as
    # in a live placement. Any request that still arrives gets a harmless call,
    # again and again, so only the signal can end the placement.
    'reminder-spent-unheld': [['orient', 'read', 'record', 'prose', 'idle'], ['orient', 'prose']],
    # Held right after its entries, before any reminder; the next placement's
    # prose then draws the audit's one reminder and the auditor submits.
    'reminder-unused': [['orient', 'read', 'record', 'hold'], ['orient', 'prose', 'prepare', 'submit']],
}
# What re-entry must show a continuing placement, from the script alone:
# answer revision, selected entries, reminder used, estimated turns so far.
# An unheld interruption estimates one turn only if a request was on the wire.
REENTRY = {'continue-cap': (0, 0, False, [0]), 'continue-entries': (2, 2, False, [0]),
           'reminder-spent': (2, 2, True, [1]), 'reminder-spent-submits': (2, 2, True, [1]),
           'reminder-spent-unheld': (2, 2, True, [0, 1]), 'reminder-unused': (2, 2, False, [1])}


def text_block(text):
    return {'type': 'text', 'text': text}


def first_message(question, placement):
    """INTERFACE 6.2 and 6.7: the question, then the continuation notice when continuing."""
    blocks = [text_block(question)] + ([text_block(spec.CONTINUATION)] if placement > 1 else [])
    return {'role': 'user', 'content': blocks}


class Auditor(Fake):
    provider_latency = 0.3

    def __init__(self, scenario, evidence, materials, question, family, auth_observer=None, packet=None,
                 guidance=None, placement=1):
        super().__init__(scenario, evidence, materials, question, auth_observer)
        self.family = family
        self.packet = packet or {}
        self.guidance = guidance
        self.placement = placement
        self.stage = 0
        self.continued = set()
        self.reminded = 0
        # Set when a request is being held; the launcher releases it after signalling.
        self.holding, self.release = threading.Event(), threading.Event()

    def respond(self, body):
        require(body['model'] == 'rehearsal-only' and 'output_config' not in body, 'fake model/settings changed')
        require(body['system'] == strict_json(system_bytes(self.packet, self.family, self.guidance))
                and body['tools'] == spec.expected_tools(self.family), 'fake arrangement differs from specification')
        # A new conversation every placement; nothing earlier is replayed.
        require(body['messages'][0] == first_message(self.question, self.placement),
                'fake first message differs from the specification')
        if self.mode == 'provider-rejected':
            return 401, {'type':'error','error':{'type':'authentication_error','message':'Synthetic rejection.'}}
        if self.mode == 'reflected-body':
            return self.message([{'type':'text','text':self.key}], 'end_turn')
        results = {}
        for message in body['messages']:
            if message['role'] == 'user':
                for block in message['content']:
                    if block['type'] == 'tool_result':
                        results[block['tool_use_id']] = block['content']
        replies = {}
        for call in self.calls:
            require(call['id'] in results, 'fake missing tool reply')
            blocks = results[call['id']]
            reply = strict_json(blocks[0]['text'])
            require(reply['outcome'] == 'completed', 'fake unexpected refusal')
            replies[call['name']] = reply['data']
        continuations, _ = follow_pages(self.calls, results, self.materials, self.continued)
        if continuations:
            # Materials larger than one page: fetch the rest before the script advances.
            return self.tools(continuations)
        script = SCRIPTS[self.mode][self.placement - 1]
        self.stage += 1
        require(self.stage <= len(script) or script[-1] == 'idle', 'unexpected fake request')
        step = script[min(self.stage, len(script)) - 1]
        previous = script[min(self.stage, len(script) + 1) - 2] if self.stage > 1 else None
        carried = [block for block in body['messages'][-1]['content'] if block['type'] == 'text']
        if previous == 'prose':
            # The audit's one reminder follows an unsealed prose ending (INTERFACE 6.4).
            require(body['messages'][-1]['content'][:1] == [text_block(spec.REMINDER)],
                    'fake request after a prose ending does not carry the exact reminder')
            self.reminded += 1
        require(self.stage == 1 or sum(block == text_block(spec.REMINDER) for block in carried) == (previous == 'prose'),
                'fake received a reminder it did not draw')
        if previous == 'orient' and self.placement > 1:
            self.check_reentry(replies['what_am_i_working_with'])
        kind = {'open-inquiry':'record_account', 'inquiry-framing':'record_working_question',
                'comparison':'record_criterion'}[self.family]
        citations = [strict_json(results[c['id']][0]['text'])['data']['cite'] for c in self.calls
                     if c['name']=='read' and c['input']['source'] in self.materials]
        citations = [c for c in citations if c is not None]
        if step == 'hold':
            # The launcher signals the placement while this request is in flight.
            # No response is ever given: a late answer would let the run go on.
            self.holding.set()
            if not self.release.wait(self.packet.get('stop_after_seconds', 60) + 30):
                self.failures.append('held request was never released')
            return None
        if step == 'idle':
            # Provider latency. A real response takes seconds; without any, many
            # of these exchanges could fit before the signal and spend the turn
            # allowance. It gates nothing: the witness signals on sight of the
            # record and never waits for, or hears from, this fake.
            time.sleep(self.provider_latency)
            return self.tools([('what_am_i_working_with', {})])
        if step == 'cap':
            return self.message([{'type':'thinking','thinking':'Synthetic reasoning that reaches the output cap before any tool call.',
                                  'signature':'c10-synthetic-signature'}], 'max_tokens', output=body['max_tokens'])
        if step == 'prose':
            return self.message([text_block('Deliberately ending without submitting.')], 'end_turn')
        if step == 'orient':
            return self.tools([('list', {}), ('what_am_i_working_with', {})])
        if step == 'read':
            require({m['source'] for m in replies['list']['materials']} == set(self.materials), 'fake material membership differs')
            return self.tools([('read', {'source':source}) for source in sorted(self.materials)])
        if step == 'record':
            return self.tools([(kind, {'text':'A synthetic procedural entry; no substantive finding is required.', 'citations':citations}),
                               ('record_artifact', {'label':'temporary fixture', 'base64':'AP8='})])
        if step == 'revise':
            return self.tools([('replace', {'entry':replies[kind]['entry'], 'label':'',
                'text':'The synthetic entry was revised using its returned handle.', 'citations':citations}),
                ('delete', {'entry':replies['record_artifact']['entry']})])
        if step == 'revise_recorded':
            # Handles come from re-entry: this conversation never saw the entries made.
            recorded = {entry['kind']:entry['entry'] for entry in replies['what_am_i_working_with']['entries']}
            return self.tools([('replace', {'entry':recorded[kind], 'label':'',
                'text':'The entry recorded before the interruption was revised through re-entry.', 'citations':citations}),
                ('delete', {'entry':recorded['record_artifact']})])
        if step == 'prepare':
            return self.tools([('prepare', {})])
        rendering = ('read', {'source':replies['prepare']['rendering']['source']})
        dry = ('submit', {'prepared':replies['prepare']['prepared'], 'confirm':False})
        if step == 'inspect':
            return self.tools([rendering, dry])
        if step == 'inspect_rendering':
            return self.tools([rendering])
        if step == 'dry_submit':
            return self.tools([dry])
        if step == 'submit':
            return self.tools([('submit', {'prepared':replies['prepare']['prepared'], 'confirm':True})])
        raise ValueError('unexpected fake request')

    def check_reentry(self, data):
        """INTERFACE 7.5 against what the script did before the interruption."""
        revision, entries, reminder, estimated = REENTRY[self.mode]
        require(data['run'] == {'number':self.placement, 'continuing':True}, 'fake re-entry placement differs')
        require(data['authoring'] == {'state':'open','ended_by':None}
                and data['seal'] == {'state':'absent','actor':None}, 'fake re-entry authoring differs')
        require(data['revision'] == revision and len(data['entries']) == entries
                and len(data['receipts']) == entries
                and all(receipt['run'] == 1 for receipt in data['receipts']), 'fake re-entry ledger differs')
        require(data['notices_used']['reminder'] is reminder, 'fake re-entry reminder allowance differs')
        require(data['allowances']['turns']['estimated'] in estimated, 'fake re-entry estimated turns differ')
