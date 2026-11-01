"""Diagnose each real native transaction without logging private handoff tickets."""


def check_handoff(send, snapshot, result, url):
    steps = result['handoff_steps'] = []
    baseline = {row['id'] for row in snapshot(None)}

    def request(stage, value):
        entry = {'stage': stage}
        steps.append(entry)
        try:
            reply = send(value)
        except Exception as error:
            entry['error_type'] = type(error).__name__
            raise
        entry.update({'type': reply.get('type'), 'ok': reply.get('ok'),
                      'code': reply.get('code'), 'has_ticket': isinstance(reply.get('ticket'), str)})
        return reply

    def prepare(stage):
        reply = request(stage, {'type': 'capture_prepare', 'url': url,
                                'referrer': None, 'filename': 'handoff-selftest.png'})
        ticket = reply.get('ticket')
        rows = [row for row in snapshot(ticket) if row['matching_ticket']]
        good = (reply.get('type') == 'capture_prepared' and isinstance(ticket, str)
                and len(rows) == 1 and rows[0]['status'] == 'handoff'
                and rows[0]['id'] not in baseline)
        steps[-1]['state_ok'] = good
        return ticket, rows[0]['id'] if good else None

    ticket, identifier = prepare('prepare-abort')
    if identifier is None:
        result['native_handoff'] = False
        return None
    reply = request('abort', {'type': 'capture_abort', 'ticket': ticket})
    rows = snapshot(ticket)
    abort_ok = (reply == {'type': 'capture_aborted', 'ok': True}
                and {row['id'] for row in rows} == baseline
                and not any(row['matching_ticket'] for row in rows))
    steps[-1]['state_ok'] = abort_ok
    ticket, identifier = prepare('prepare-commit')
    if identifier is None:
        result['native_handoff'] = False
        return None
    first = request('commit-first', {'type': 'capture_commit', 'ticket': ticket})
    rows = snapshot(ticket)
    first_state = ({row['id'] for row in rows} == baseline | {identifier}
                   and any(row['id'] == identifier and row['matching_ticket']
                           and row['status'] != 'handoff' for row in rows))
    steps[-1]['state_ok'] = first_state
    second = request('commit-repeat', {'type': 'capture_commit', 'ticket': ticket})
    rows = snapshot(ticket)
    matching = [row for row in rows if row['matching_ticket']]
    second_state = ({row['id'] for row in rows} == baseline | {identifier}
                    and len(matching) == 1 and matching[0]['id'] == identifier
                    and matching[0]['status'] != 'handoff')
    steps[-1]['state_ok'] = second_state
    result['native_handoff'] = bool(abort_ok and first_state and second_state
        and first == {'type': 'capture_result', 'ok': True} and first == second)
    # A failed acknowledgement must remain failed, but do not hide an accepted
    # transfer's file proof just because the combined protocol assertion failed.
    return identifier if second_state else None
