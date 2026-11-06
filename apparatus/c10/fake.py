"""A reacting, independently recorded auditor for offline C10 rehearsals."""
from common import strict_json, require
from exercise import Fake
import driver_core as spec
from study_build import system_bytes


class Auditor(Fake):
    def __init__(self, scenario, evidence, materials, question, family, auth_observer=None, packet=None):
        super().__init__(scenario, evidence, materials, question, auth_observer)
        self.family = family
        self.packet = packet or {}

    def respond(self, body):
        require(body['model'] == 'rehearsal-only' and 'output_config' not in body, 'fake model/settings changed')
        require(body['system'] == strict_json(system_bytes(self.packet, self.family))
                and body['tools'] == spec.expected_tools(self.family), 'fake arrangement differs from specification')
        require(body['messages'][0] == {'role':'user', 'content':[{'type':'text','text':self.question}]}, 'fake question changed')
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
            if call['name'] == 'read' and call['input']['source'] in self.materials:
                text = blocks[1]['text'] if len(blocks)>1 else reply['data']['text']
                require(text.encode() == self.materials[call['input']['source']], 'fake read differs from witness')
        if self.mode == 'empty':
            if self.requests == 1:
                return self.tools([('prepare', {})])
            return self.tools([('submit', {'prepared':replies['prepare']['prepared'], 'confirm':True})])
        if self.requests == 1:
            return self.tools([('list', {}), ('what_am_i_working_with', {})])
        if self.requests == 2:
            require({m['source'] for m in replies['list']['materials']} == set(self.materials), 'fake material membership differs')
            return self.tools([('read', {'source':source}) for source in sorted(self.materials)])
        citations = [strict_json(results[c['id']][0]['text'])['data']['cite'] for c in self.calls
                     if c['name']=='read' and c['input']['source'] in self.materials]
        citations = [c for c in citations if c is not None]
        kind = {'open-inquiry':'record_account', 'inquiry-framing':'record_working_question',
                'comparison':'record_criterion'}[self.family]
        if self.requests == 3:
            return self.tools([(kind, {'text':'A synthetic procedural entry; no substantive finding is required.', 'citations':citations}),
                               ('record_artifact', {'label':'temporary fixture', 'base64':'AP8='})])
        if self.requests == 4:
            return self.tools([('replace', {'entry':replies[kind]['entry'], 'label':'',
                'text':'The synthetic entry was revised using its returned handle.', 'citations':citations}),
                ('delete', {'entry':replies['record_artifact']['entry']})])
        if self.mode == 'unsubmitted':
            return self.message([{'type':'text','text':'Deliberately ending without submitting.'}], 'end_turn')
        if self.requests == 5:
            return self.tools([('prepare', {})])
        if self.requests == 6:
            return self.tools([('read', {'source':replies['prepare']['rendering']['source']}),
                               ('submit', {'prepared':replies['prepare']['prepared'], 'confirm':False})])
        if self.requests == 7:
            return self.tools([('submit', {'prepared':replies['prepare']['prepared'], 'confirm':True})])
        raise ValueError('unexpected fake request')
