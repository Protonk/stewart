"""Shared reservations for commissioned subscription checks and service placements."""
import fcntl
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def load(path, digest):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('campaign envelope must be a regular file')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('campaign envelope digest differs')
    data = json.loads(raw)
    if (data['schema'] != 'stewart.runtime-trials.envelope/1' or data['waves'] != 2
            or data['harness']['extra_usage_allowed'] is not False
            or data['harness']['billing'] != 'included-subscription-only'):
        raise ValueError('unsupported campaign billing or wave scope')
    return data


def reserve(path, digest, wave, trial, packet, commission, placement, model, version):
    """Reserve before any invocation. A crash consumes the slot and blocks another launch."""
    scope = load(path, digest)['harness']
    if wave not in (1, 2) or model != scope['model'] or version != scope['version']:
        raise ValueError('harness trial differs from the granted bindings')
    if wave == 1 and trial not in ('S0', 'R1', 'R2', 'R3a', 'R3b', 'R4'):
        raise ValueError('unknown first-wave harness trial')
    root = Path(path).parent / 'harness-reservations'
    with (root / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        rows = sorted(root.glob('[0-9][0-9][0-9].json'))
        prior = [json.loads(row.read_bytes()) for row in rows]
        if any(row['envelope'] != digest for row in prior):
            raise ValueError('reservation belongs to a different envelope')
        if (root / 'STOP').exists() or any(row['wave'] > wave for row in prior):
            raise ValueError('campaign stopped or wave already completed')
        if rows:
            last = prior[-1]
            receipt = root / (rows[-1].stem + '.review.json')
            if not receipt.is_file():
                raise ValueError('previous reservation needs a reviewed disposition')
            disposition = json.loads(receipt.read_bytes())
            if (disposition['reservation_sha256'] != hashlib.sha256(rows[-1].read_bytes()).hexdigest()
                    or disposition['safe_to_continue'] is not True):
                raise ValueError('previous reservation has no positive disposition')
        if any((r['packet'], r['placement']) == (str(packet), placement)
               or (r['wave'], r['trial'], r['placement']) == (wave, trial, placement) for r in prior):
            raise ValueError('harness slot already reserved')
        slots = [row for row in prior if row['trial'] != 'S0']
        if trial == 'S0':
            if wave != 1 or placement != 0 or any(r['trial'] == 'S0' for r in prior):
                raise ValueError('surface allowance exhausted')
        elif not any(r['trial'] == 'S0' for r in prior):
            raise ValueError('service admission requires the reviewed surface check')
        elif (not 1 <= placement <= 3 or len(slots) >= scope['service_starts']
                or (wave == 1 and sum(r['wave'] == 1 for r in slots) >= scope['wave_one_service_starts'])):
            raise ValueError('service start allowance exhausted')
        dest = root / ('%03d.json' % (len(rows) + 1))
        record = dict(envelope=digest, wave=wave, trial=trial, packet=str(packet),
                      commission_sha256=commission, placement=placement, model=model,
                      reserved_utc=datetime.now(timezone.utc).isoformat())
        with dest.open('x') as output:
            json.dump(record, output, sort_keys=True)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return dest


def unique_fields(pairs):
    value = dict(pairs)
    if len(value) != len(pairs):
        raise ValueError('duplicate native frame field')
    return value


class AllowanceObserver:
    """Observe native allowance events and retain scoped warnings and terminal stop reasons."""
    def __init__(self, envelope, version, model, trial, placement):
        self.version = version
        self.model_window = 'seven_day_' + model.removeprefix('claude-').split('-', 1)[0]
        self.trial = trial
        self.placement = placement
        self.directory = Path(envelope).parent / 'harness-reservations'
        self.buffers = {'stdout': bytearray(), 'stderr': bytearray()}

    def feed(self, channel, chunk):
        buffer = self.buffers[channel]
        buffer.extend(chunk)
        while b'\n' in buffer:
            line, _, tail = buffer.partition(b'\n')
            buffer[:] = tail
            if channel == 'stdout':
                try:
                    row = json.loads(line, object_pairs_hook=unique_fields)
                except (json.JSONDecodeError, UnicodeError):
                    continue  # The stream observer checks framing independently.
                except ValueError:
                    self.stop('invalid native frame with ambiguous fields')
                if not isinstance(row, dict):
                    continue
                if row.get('type') == 'system' and row.get('subtype') == 'init' and self.version:
                    if row.get('claude_code_version') != self.version:
                        self.stop('initialization differs from the commissioned harness version')
                if row.get('type') == 'rate_limit_event':
                    self.rate_limit(row.get('rate_limit_info'))
                if row.get('type') == 'system' and row.get('subtype') in ('rate_limit', 'usage_limit', 'overage'):
                    self.stop('allowance event')
                if row.get('is_error') and self.billing_text(str(row.get('result', ''))):
                    self.stop('allowance error')
            elif self.billing_text(line.decode('utf-8', 'replace')):
                self.stop('allowance diagnostic')
        if len(buffer) > 4 * 1024 * 1024:
            raise ValueError('billing monitor frame exceeded observation bound')

    def rate_limit(self, info):
        """The subscription status and the pay-as-you-go status describe different allowances."""
        allowed = ('allowed', 'allowed_warning')
        if not isinstance(info, dict):
            self.stop('invalid rate-limit information')
        for flag in ('overageEnabled', 'isUsingOverage'):
            if flag in info and type(info[flag]) is not bool:
                self.stop('invalid paid-extra-usage flag')
            if info.get(flag):
                self.stop('paid extra usage enabled or in use')
        overage = info.get('overageStatus')
        if overage in allowed:
            self.stop('paid extra usage available')
        if overage not in (None, 'rejected'):
            self.stop('invalid paid-extra-usage status')

        status = info.get('status')
        if status == 'rejected':
            self.stop('subscription quota rejected')
        if status not in allowed:
            self.stop('invalid subscription status')
        window = info.get('rateLimitType')
        if window == 'overage':
            self.stop('paid extra usage available')
        if window is not None and window not in ('five_hour', 'seven_day', 'seven_day_sonnet', 'seven_day_opus'):
            self.stop('invalid subscription window')
        windows = info.get('unifiedWindows', {})
        if not isinstance(windows, dict):
            self.stop('invalid subscription window information')
        for name, details in windows.items():
            if not isinstance(details, dict) or details.get('status') not in (*allowed, 'rejected'):
                self.stop('invalid subscription window status')
            # Other model-specific windows can be exhausted while this one permits use.
            if name == 'overage' and details['status'] in allowed:
                self.stop('paid extra usage available')
            if name in (window, 'five_hour', 'seven_day', self.model_window) and details['status'] == 'rejected':
                self.stop('subscription quota rejected')
            if name == window and details['status'] != status:
                self.stop('invalid conflicting subscription status')

        utilization = info.get('utilization')
        reset = info.get('resetsAt')
        if utilization is not None and (type(utilization) not in (int, float) or not 0 <= utilization <= 1):
            self.stop('invalid subscription utilization')
        if reset is not None and (type(reset) is not int or reset < 0):
            self.stop('invalid subscription reset time')
        if status == 'allowed_warning':
            details = {key: info[key] for key in ('status', 'rateLimitType', 'utilization', 'resetsAt')
                       if info.get(key) is not None}
            row = {'at': datetime.now(timezone.utc).isoformat(), 'trial': self.trial,
                   'placement': self.placement, 'rate_limit_info': details}
            with (self.directory / 'warnings.jsonl').open('a') as stream:
                stream.write(json.dumps(row) + '\n')
                stream.flush()
                os.fsync(stream.fileno())

    def finish(self, channel):
        if self.buffers[channel]:
            self.feed(channel, b'\n')

    @staticmethod
    def billing_text(text):
        return any(token in text.lower() for token in (
            'rate limit', 'rate_limit', 'rate-limit', 'usage limit', 'usage allowance',
            'usage credit', 'extra usage', 'quota exceeded', 'using overage', 'using credits'))

    def stop(self, reason):
        try:
            with (self.directory / 'STOP').open('x') as out:
                out.write(reason + '\n')
                out.flush()
                os.fsync(out.fileno())
        except FileExistsError:
            pass
        raise ValueError('campaign harness stop: ' + reason)


def acknowledge(reservation, review_path, review_digest):
    """Release the latest slot only against the exact successful review of its own execution."""
    reservation, review_path = Path(reservation), Path(review_path)
    root = reservation.parent
    with (root / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if (root / 'STOP').exists() or reservation != sorted(root.glob('[0-9][0-9][0-9].json'))[-1]:
            raise ValueError('cannot release a stopped campaign or an earlier slot')
        raw = reservation.read_bytes()
        claim = json.loads(raw)
        packet = Path(claim['packet'])
        if hashlib.sha256((packet / 'COMMISSION.json').read_bytes()).hexdigest() != claim['commission_sha256']:
            raise ValueError('commission changed since reservation')
        if claim['trial'] == 'S0':
            expected = packet / 'observation/CHECK.json'
        else:
            expected = packet / 'placements' / str(claim['placement']) / 'review/REVIEW.json'
        if review_path != expected:
            raise ValueError('review is not the reserved packet and placement')
        review_raw = review_path.read_bytes()
        review = json.loads(review_raw)
        if hashlib.sha256(review_raw).hexdigest() != review_digest or review['outcome'] != 'observed':
            raise ValueError('missing or changed successful review')
        if claim['trial'] == 'S0':
            observation = (packet / 'observation/OBSERVATION.json').read_bytes()
            result = json.loads((packet / 'observation/RESULT.json').read_bytes())
            if (review['schema'] != 'stewart.claude-code.reviewed-check/1' or
                    review['observation_sha256'] != hashlib.sha256(observation).hexdigest() or
                    result['commission_sha256'] != claim['commission_sha256'] or result['outcome'] != 'observed'):
                raise ValueError('surface review differs from reserved observation')
        elif review['commission_sha256'] != claim['commission_sha256']:
            raise ValueError('review differs from reserved commission')
        receipt = {'reservation_sha256': hashlib.sha256(raw).hexdigest(), 'review_sha256': review_digest,
                   'safe_to_continue': True, 'at': datetime.now(timezone.utc).isoformat()}
        with reservation.with_suffix('.review.json').open('x') as out:
            json.dump(receipt, out, sort_keys=True)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=acknowledge.__doc__)
    parser.add_argument('--reservation', required=True, type=Path)
    parser.add_argument('--review', required=True, type=Path)
    parser.add_argument('--review-sha256', required=True)
    args = parser.parse_args()
    acknowledge(args.reservation, args.review, args.review_sha256)
