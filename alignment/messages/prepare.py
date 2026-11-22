"""Prepare unpaid single-placement Messages catalog proposals for the selected release models."""
import argparse
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'alignment/messages/procedure'))
from billing import price_card, worst_case
from common import FILE_SIZE_LIMIT, file_hash, proposal, validate_packet, write_json


RELEASE_MODELS = ('claude-haiku-5-5', 'claude-opus-5-5')


def prepare(output, case, effort, prices, *, models=RELEASE_MODELS):
    rates = json.loads(prices.read_bytes())
    packets = []
    for model in models:
        family = model.split('-')[1]
        card = rates[model]
        price_card(card)
        packet = proposal(model, [case])
        packet['runs'][0]['id'] = f'{family}-{case}'
        packet.update(effort=effort, file_size_limit=FILE_SIZE_LIMIT,
                      limits={'turns': 16, 'input_tokens': 115000, 'output_tokens': 32000})
        validate_packet(packet)
        packets.append((packet, worst_case(card, packet['limits'])))
    output.mkdir(mode=0o700)
    manifest = {'prices_sha256': file_hash(prices), 'case': case, 'effort': effort,
                'proposals': [], 'maximum_reserved_cents': sum(c for _, c in packets)}
    for packet, reserve in packets:
        name = packet['runs'][0]['id'] + '.json'
        path = output / name
        write_json(path, packet)
        manifest['proposals'].append({'model': packet['model'], 'file': name,
                                      'sha256': file_hash(path), 'reserved_cents': reserve})
    write_json(output / 'PROPOSALS.json', manifest)
    return manifest


if __name__ == '__main__':
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='New output directory')
    parser.add_argument('--case', required=True, help='One C10 catalog specimen')
    parser.add_argument('--model', choices=RELEASE_MODELS, help='Prepare a single model; default: both release models')
    parser.add_argument('--effort', choices=('low', 'medium', 'high', 'xhigh', 'max'),
                        help='Omit to leave the wire setting absent')
    parser.add_argument('--prices', required=True, type=Path, help='Dated Messages queue rate cards')
    args = parser.parse_args()
    models = (args.model,) if args.model else RELEASE_MODELS
    print(json.dumps(prepare(args.output, args.case, args.effort, args.prices, models=models), indent=2))
