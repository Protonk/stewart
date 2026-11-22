"""Meter one commissioned Messages campaign from Stewart's verified placement records."""
from common import COMPACTION_FILE_LIMIT, FILE_LIMITS, FILE_SIZE_LIMIT, LIMITS, fields, require

CATEGORIES = ('input_tokens','cache_creation_input_tokens','cache_read_input_tokens','output_tokens')
MICRODOLLARS_PER_CENT = 10000


def price_card(card):
    fields(card, ['bands','context_tokens'], 'model rate card')
    require(type(card['context_tokens']) is int and card['context_tokens'] > 0, 'invalid context window')
    bands = card['bands']
    require(isinstance(bands,list) and len(bands)>=1, 'rate bands missing')
    last=0
    for band in bands:
        fields(band, ['through_input_tokens', *CATEGORIES], 'model rate band')
        require(type(band['through_input_tokens']) is int and band['through_input_tokens'] > last,
                'rate bands must be ordered')
        require(all(type(band[k]) is int and band[k]>=0 for k in CATEGORIES), 'invalid microdollar rates')
        last=band['through_input_tokens']
    require(last>=card['context_tokens'], 'price bands do not cover context window')


def rounded_cents(units):
    divisor = 1000000 * MICRODOLLARS_PER_CENT
    return (units + divisor - 1)//divisor


def request_body_bound(turns, file_limit=FILE_SIZE_LIMIT):
    return file_limit + turns * (file_limit + 1) + 1024


def worst_case(card, limits, *, synthetic=False, file_limit=FILE_SIZE_LIMIT):
    # Ordinary packets must exhaust a cumulative allowance before a summary.
    # The larger protected study limit enables the on-demand path below.
    require(file_limit in FILE_LIMITS, 'unsupported reservation file limit')
    require(synthetic or file_limit == COMPACTION_FILE_LIMIT or limits['input_tokens'] + limits['output_tokens'] <= 150000,
            'packet may enter unbounded compaction iterations')
    input_price = max(band[k] for band in card['bands'] for k in CATEGORIES[:-1])
    output_price = max(band['output_tokens'] for band in card['bands'])
    # A later attempt can overrun remaining input once; a retry reuses its
    # original max_tokens, including after a previously estimated response.
    # Each complete pre-send capture includes every newly appended message byte.
    # Retries send exactly that body. Another request after a success consumes
    # a turn. The pinned arrangement covers all fixed fields plus constant framing.
    body_bytes = request_body_bound(limits['turns'], file_limit)
    terminal_input = max(card['context_tokens'], (body_bytes + 2) // 3)
    if file_limit == COMPACTION_FILE_LIMIT:
        # Direct, on-demand compaction reads the context once and max_tokens caps
        # its whole output. A response lost after transmission may still be billed
        # a full context even when the writer's byte-based estimate was smaller.
        # An estimate consumes 16k output or exhausts the remaining allowance.
        # Retries keep the original cap. Reserve separate maxima for provider
        # billing and for settlement from captures, including one final overrun.
        lost = min(limits['turns'], (limits['output_tokens'] + 15999) // 16000)
        terminal_input = max(terminal_input, (1 + lost) * card['context_tokens'])
    return rounded_cents((limits['input_tokens'] + terminal_input)*input_price
                         + (limits['output_tokens'] + min(16000,limits['output_tokens']))*output_price)


def five_minute_writes(usage):
    rows=usage.get('iterations') or [usage]
    total=0
    for row in rows:
        split=row.get('cache_creation')
        if isinstance(split,dict):
            short=split.get('ephemeral_5m_input_tokens')
            long=split.get('ephemeral_1h_input_tokens')
            if type(short) is int and type(long) is int and min(short,long)>=0 and short+long==row.get('cache_creation_input_tokens'):
                total+=short
    return total


def charge(card, placement):
    totals = {basis:{key:0 for key in LIMITS} for basis in ('reported','estimated')}
    units=0
    rows=placement['billing']
    for row in rows:
        basis=row['basis']
        counts={key:row[key] for key in CATEGORIES}
        require(all(type(v) is int and v>=0 for v in counts.values()), 'invalid billing count')
        input_tokens=sum(counts[k] for k in CATEGORIES[:-1])
        totals[basis]['turns']+=1
        totals[basis]['input_tokens']+=input_tokens
        totals[basis]['output_tokens']+=counts['output_tokens']
        bands=card['bands']
        if basis=='estimated':
            # Without a provider usage statement, use the highest input and output rates.
            units+=input_tokens*max(b[k] for b in bands for k in CATEGORIES[:-1])
            units+=counts['output_tokens']*max(b['output_tokens'] for b in bands)
        else:
            band=next((b for b in bands if input_tokens<=b['through_input_tokens']),None)
            require(band is not None, 'reported input outside committed rate bands')
            # A cache creation report does not distinguish TTLs. Its priced
            # category therefore uses the highest applicable creation rate.
            units+=sum(counts[k]*band[k] for k in CATEGORIES)
            short=row.get('five_minute_cache_writes',0)
            require(type(short) is int and 0<=short<=counts['cache_creation_input_tokens'],
                    'invalid cache lifetime breakdown')
            # Standard direct Messages prices five-minute writes at 1.25x.
            # When the provider names a lifetime, apply that actual list rate.
            usual=(5*band['input_tokens']+3)//4
            require(not short or usual<=band['cache_creation_input_tokens'], 'rate band excludes cache creation price')
            units-=short*(band['cache_creation_input_tokens']-usual)
    require(all(totals[b][k]==placement['usage'][k][b] for b in totals for k in LIMITS),
            'billing does not equal the verified placement charge')
    return {'cents': rounded_cents(units), 'microdollars_times_million':units,
            'usage':placement['usage'], 'attempts':rows}
