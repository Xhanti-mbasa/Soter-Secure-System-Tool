"""Public Parliament rosters, with explicit capture dates and bounded refreshes."""
import copy
import html
import json
import re
import threading
import urllib.parse
from pathlib import Path

from .core import now, digest
from .services import read

DATA = Path(__file__).resolve().parent.parent / 'android/app/src/main/assets/party-data.json'
PARLIAMENT = 'https://www.parliament.gov.za'
DIRECTORY = PARLIAMENT + '/members-of-parliament'


def text(markup):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', markup))).strip()


def parse_roster(markup, code, name):
    """Only Composition belongs to the party; featured members are unrelated."""
    heading = re.search(r'<h1[^>]*>(.*?)</h1>', markup, re.S | re.I)
    if not heading or text(heading[1]).casefold() != name.casefold():
        raise ValueError('Parliament party heading did not match the requested party')
    composition = re.search(r'<h5[^>]*>\s*Composition\s*\((\d+)\s+members?\)\s*</h5>\s*<ul[^>]*>(.*?)</ul>', markup, re.S | re.I)
    if not composition:
        raise ValueError('Parliament composition was not found; saved roster retained')
    members = []
    for member_id, label in re.findall(r'<a\s+href=["\']/person-details/(\d+)["\'][^>]*>(.*?)</a>', composition[2], re.S | re.I):
        members.append({'id': member_id, 'name': text(label), 'party_code': code,
                        'source_url': PARLIAMENT + '/person-details/' + member_id})
    if len(members) != int(composition[1]) or len({m['id'] for m in members}) != len(members):
        raise ValueError('Incomplete or duplicated composition; saved roster retained')
    return members


def parse_directory(markup, codes):
    component = re.search(r'<group-details\b([^>]+)>', markup, re.S | re.I)
    if not component:
        raise ValueError('Parliament member directory was not found')
    attrs = dict(re.findall(r"([\w-]+)='([^']*)'", component[1]))
    groups = json.loads(html.unescape(attrs.get('members', '{}')))
    rows = [m for group in groups.values() for m in group]
    if not rows or len(rows) != int(attrs.get('member-count', '-1')):
        raise ValueError('Incomplete Parliament directory; saved roster retained')
    result = {code: [] for code in codes}
    seen = set()
    for m in rows:
        member_id = str(m['id'])
        if not re.fullmatch(r'\d{1,10}', member_id) or member_id in seen or m['party'] not in result:
            raise ValueError('Invalid, duplicated or unknown-party directory entry')
        seen.add(member_id)
        result[m['party']].append({'id': member_id, 'name': str(m['full_name']), 'party_code': m['party'],
                                  'source_url': PARLIAMENT + '/person-details/' + member_id})
    for members in result.values():
        members.sort(key=lambda m: m['name'].casefold())
    return result


def parse_member(markup, expected_id):
    section = re.search(r'<div[^>]*class=["\'][^"\']*\bmember-info\b[^"\']*["\'][^>]*>(.*?)<div\s+id=["\']contact-details', markup, re.S | re.I)
    if not section:
        raise ValueError('Parliament member summary was not found')
    body = section[1]
    name = re.search(r'<h2[^>]*>(.*?)</h2>', body, re.S | re.I)
    chamber = re.search(r'<span[^>]*class=["\']label[^"\']*["\'][^>]*>(.*?)</span>', body, re.S | re.I)
    greens = re.findall(r'<span[^>]*class=["\']green["\'][^>]*>(.*?)</span>', body, re.S | re.I)
    if not name or not greens:
        raise ValueError('Incomplete Parliament member summary')
    return {'id': str(expected_id), 'name': text(name[1]), 'chamber': text(chamber[1]) if chamber else '',
            'role': text(greens[-2]) if len(greens) > 1 else '', 'party_name': text(greens[-1]),
            'source_url': PARLIAMENT + '/person-details/' + str(expected_id)}


def attach_salary(member, schedules):
    """Map only an explicit executive title. Do not assume the ordinary MP rate."""
    role = member.get('role', '').casefold()
    schedule_role = 'Deputy Minister' if role.startswith('deputy minister') else 'Minister' if role.startswith('minister') else 'Deputy President' if role == 'deputy president' else ''
    member['remuneration'] = copy.deepcopy(next((r for r in schedules if r['role'] == schedule_role), None))
    return member


class PartyService:
    def __init__(self, reader=read, data_path=DATA):
        self.reader = reader
        self.data = json.loads(Path(data_path).read_text())
        self.lock = threading.RLock()

    def catalog(self, query=''):
        q = str(query).strip().casefold()
        with self.lock:
            rows = [{k: copy.deepcopy(v) for k, v in p.items() if k != 'members'} for p in self.data['parties']
                    if not q or q in (p['code'] + ' ' + p['name'] + ' ' + ' '.join(p.get('aliases', []))).casefold()]
            return {'parties': rows, 'captured_at': self.data['captured_at'], 'coverage': self.data['coverage']}

    def party(self, code, refresh=False):
        with self.lock:
            party = next((p for p in self.data['parties'] if p['code'].casefold() == str(code).casefold()), None)
            if not party:
                raise ValueError('Choose a party from the published Parliament directory')
            result = copy.deepcopy(party)
        result['status'] = 'saved_roster'
        if refresh:
            try:
                raw = self.reader(DIRECTORY)
                members = parse_directory(raw, [p['code'] for p in self.data['parties']])[result['code']]
                result.update(members=members, captured_at=now(), source_url=DIRECTORY,
                              content_hash=digest(raw), status='refreshed')
                result['member_count'] = len(result['members'])
                with self.lock:
                    party.update({k: result[k] for k in ('members', 'captured_at', 'content_hash', 'member_count', 'source_url')})
            except Exception as e:
                result.update(status='refresh_unavailable', detail=str(e)[:200])
        result['coverage'] = self.data['coverage']
        return result

    def member(self, member_id, refresh=False):
        member_id = str(member_id)
        if not re.fullmatch(r'\d{1,10}', member_id):
            raise ValueError('Invalid Parliament member ID')
        with self.lock:
            pair = next(((p, m) for p in self.data['parties'] for m in p['members'] if m['id'] == member_id), None)
            if not pair:
                raise KeyError('Member is not in the captured public roster')
            party, member = pair
            result = copy.deepcopy(member)
            result.update(party_name=party['name'], roster_url=party['source_url'], captured_at=party['captured_at'])
            result.update(copy.deepcopy(self.data.get('profiles', {}).get(member_id, {})))
            schedules = self.data['remuneration_schedules']
        result['status'] = 'saved_profile' if result.get('profile_captured_at') else 'roster_only'
        if refresh:
            try:
                raw = self.reader(PARLIAMENT + '/person-details/' + member_id)
                current = parse_member(raw, member_id)
                if current['party_name'].casefold() != party['name'].casefold():
                    result['membership_note'] = 'Member page differs from saved party roster. Refresh the roster and review both sources.'
                    current['party_code'] = None
                result.update(current, profile_captured_at=now(), profile_content_hash=digest(raw), status='refreshed')
                # Never copy an unverified old role into a fresh profile.
                with self.lock:
                    self.data.setdefault('profiles', {}).setdefault(member_id, {}).update(current,
                        profile_captured_at=result['profile_captured_at'], profile_content_hash=result['profile_content_hash'])
            except Exception as e:
                result.update(status='refresh_unavailable', detail=str(e)[:200])
        attach_salary(result, schedules)
        result['search_name'] = result.get('search_name') or re.sub(r'^(Mr|Ms|Mrs|Dr|Prof|Rev|Hon)\.?\s+', '', result['name'])
        result['coverage'] = 'Public representative profile. Education and business relationships need their own dated sources; a news mention is not a verified relationship.'
        result['interests_register'] = copy.deepcopy(self.data['interests_register'])
        return result
