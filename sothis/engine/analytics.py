"""Dated election evidence. Polls measure intention, never win probability."""
import datetime as dt
import json
from pathlib import Path
from .core import now

DATA = Path(__file__).resolve().parent.parent / 'android/app/src/main/assets/analytics-data.json'


def validate(data):
    elections = data['national_elections']
    if not elections or len({e['date'] for e in elections}) != len(elections):
        raise ValueError('Supply distinct, dated National Assembly allocations')
    for e in elections:
        dt.date.fromisoformat(e['date'])
        if e['total_seats'] != 400 or sum(e['seats'].values()) != 400:
            raise ValueError('National Assembly allocation must total 400 seats')
        if any(type(n) is not int or n < 0 for n in e['seats'].values()):
            raise ValueError('Seats must be non-negative integers')
        if not e['source_url'].startswith('https://'):
            raise ValueError('Each allocation needs a public evidence URL')
    if len(data['provinces']) != 9 or len({p['name'] for p in data['provinces']}) != 9:
        raise ValueError('Nine distinct provincial results required')
    for p in data['provinces']:
        if not p['results'] or not p['path']:
            raise ValueError('Each province needs results and a boundary')
        if any(not 0 <= r['share'] <= 100 or type(r['votes']) is not int or r['votes'] < 0 for r in p['results']):
            raise ValueError('Invalid provincial votes or share')
        if p['leader'] != max(p['results'], key=lambda r: r['votes'])['code']:
            raise ValueError('Province leader must be the highest ballot vote total')
    for p in data.get('polls', []):
        if p['election_type'] != 'national' or p['measure'] != 'voting_intention':
            raise ValueError('Only national voting-intention polls belong in this outlook')
        if p['target_after'] not in {e['date'] for e in elections}:
            raise ValueError('Poll must identify the last completed election it follows')
        for key in ('published_at', 'fieldwork_from', 'fieldwork_to', 'expires_at'):
            dt.date.fromisoformat(p[key])
        if not p['fieldwork_from'] <= p['fieldwork_to'] <= p['published_at'] < p['expires_at']:
            raise ValueError('Invalid poll date order or expiry')
        if not p['publisher'] or not p['methodology'] or not p['population'] or type(p['sample_size']) is not int or p['sample_size'] < 1 or not p['source_url'].startswith('https://'):
            raise ValueError('Polls need source, sample, population and methodology')
        if any(not 0 <= n <= 100 for n in p['shares'].values()) or sum(p['shares'].values()) > 100.1:
            raise ValueError('Invalid voting-intention percentages')
        if 'win_probability' in p:
            raise ValueError('Voting intention is not a win probability')
    validate_elections(data.get('elections', []), {e['date'] for e in elections})
    return data


ELECTION_KINDS = {'national_provincial', 'municipal', 'by_election'}


def validate_elections(items, allocation_dates=frozenset()):
    """Election calendar entries. Status (previous / in progress / upcoming) is
    derived from these dates at display time, so it is never stored."""
    ids = set()
    for e in items:
        if not e.get('id') or e['id'] in ids or not e.get('name'):
            raise ValueError('Each election needs a distinct id and name')
        ids.add(e['id'])
        if e.get('kind') not in ELECTION_KINDS:
            raise ValueError('Unknown election kind')
        if not e.get('sources') or any(not s.get('label') or not s.get('url', '').startswith('https://') for s in e['sources']):
            raise ValueError('Each election needs public https evidence')
        if 'win_probability' in e:
            raise ValueError('Election entries do not carry win probabilities')
        date = e.get('date')
        if date is None:
            if type(e.get('due_year')) is not int or e.get('results_declared_at') or e.get('shares'):
                raise ValueError('An unproclaimed election needs a due year and no results')
            continue
        dt.date.fromisoformat(date)
        for day in e.get('special_votes', []):
            if not dt.date.fromisoformat(day) < dt.date.fromisoformat(date):
                raise ValueError('Special votes must precede election day')
        for key in ('polls_open', 'polls_close'):
            if key in e:
                dt.time.fromisoformat(e[key])
        if 'polls_open' in e and 'polls_close' in e and not e['polls_open'] < e['polls_close']:
            raise ValueError('Polls must open before they close')
        declared, shares = e.get('results_declared_at'), e.get('shares') or {}
        if declared:
            if dt.date.fromisoformat(declared) < dt.date.fromisoformat(date):
                raise ValueError('Results cannot be declared before polling day')
            if not shares or not e.get('measure'):
                raise ValueError('Declared results need party shares and the ballot they measure')
        elif shares:
            raise ValueError('Party shares need a results declaration date')
        if any(isinstance(n, bool) or not isinstance(n, (int, float)) or not 0 <= n <= 100 for n in shares.values()) or sum(shares.values()) > 100.1:
            raise ValueError('Invalid election vote shares')
        if e['kind'] == 'national_provincial' and declared and date not in allocation_dates:
            raise ValueError('Declared national results need a matching National Assembly allocation')
        if e.get('turnout') is not None and not 0 < e['turnout'] <= 100:
            raise ValueError('Invalid turnout')
    return items


def snapshot(path=DATA):
    data = validate(json.loads(Path(path).read_text()))
    data['served_at'] = now()
    return data
