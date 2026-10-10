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
    return data


def snapshot(path=DATA):
    data = validate(json.loads(Path(path).read_text()))
    data['served_at'] = now()
    return data
