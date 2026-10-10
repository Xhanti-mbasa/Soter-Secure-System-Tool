#!/usr/bin/env python3
"""Capture official parliamentary rosters; only successful complete rosters replace data.

Optional --interests-pdf indexes the public business-interest sections, excluding
residential property, contact details and other sections from member dossiers.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import html
import json
from pathlib import Path
import re
import sys
import urllib.parse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engine.parties import DATA, PARLIAMENT, DIRECTORY, parse_directory, parse_member
from engine.services import read
from engine.core import now, digest

REGISTER = 'https://www.parliament.gov.za/storage/app/media/Register%20of%20Members%20Interests/Register_of_members_interests_june_2026_v2.pdf'
PAY = 'https://www.gov.za/sites/default/files/gcis_document/202601/53965gon7004.pdf'
BIO = 'https://www.gov.za/about-government/contact-directory/mineral-and-petroleum-resources-ministry/gwede-mantashe-mr'


def name_key(name):
    return sorted(w for w in re.findall(r'\w+', name.casefold()) if w not in ('mr', 'ms', 'mrs', 'dr', 'doctor', 'prof', 'rev', 'hon'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--interests-pdf', type=Path)
    args = parser.parse_args()
    captured = now()
    existing = json.loads(DATA.read_text()) if DATA.exists() else {'profiles': {}, 'parties': []}
    # Parliament publishes the codes in its own member filter, including spaces/apostrophes.
    raw = read(PARLIAMENT + '/person-details/5975')
    codes = json.loads(html.unescape(re.search(r" parties='([^']+)'", raw)[1]))
    directory_raw = read(DIRECTORY)
    directory = parse_directory(directory_raw, codes)
    existing_by_code = {p['code']: p for p in existing['parties']}

    def collect(pair):
        code, name = pair
        url = PARLIAMENT + '/party-details/' + urllib.parse.quote(code, safe='')
        try:
            members = directory[code]
            return dict(code=code, name=name, source_url=DIRECTORY, party_detail_url=url, members=members, member_count=len(members),
                        captured_at=captured, content_hash=digest(directory_raw), aliases={'FF PLUS': ['FF+', 'VF+'], "ALJAMA'AH": ['Al Jama-ah'], 'MK': ['MK Party']}.get(code, []))
        except Exception as e:
            if code in existing_by_code:
                return existing_by_code[code]
            return dict(code=code, name=name, source_url=url, members=[], member_count=0,
                        captured_at=None, collection_error=str(e)[:200], aliases=[])

    with ThreadPoolExecutor(max_workers=3) as pool:
        parties = list(pool.map(collect, codes.items()))
    for p in parties:
        print(p['code'], p['member_count'], p.get('collection_error', 'captured'))
    current_ids = {m['id'] for p in parties for m in p['members']}
    profiles = {k: v for k, v in existing.get('profiles', {}).items() if k in current_ids}
    profiles['5975'] = {**profiles.get('5975', {}), **parse_member(raw, '5975'),
                        'search_name': 'Gwede Mantashe', 'profile_captured_at': captured, 'profile_content_hash': digest(raw)}
    # These facts are paraphrases from the government biography; do not infer current business ownership.
    bio = read(BIO)
    if all(s in bio for s in ('Bcom Honours', 'Witwatersrand', 'Samancor', '2006')):
        profiles['5975'].update(education=[
            {'text': 'The government biography reports a master’s degree from the University of the Witwatersrand.', 'source_url': BIO},
            {'text': 'It reports a Bachelor of Commerce and BCom Honours from the University of South Africa.', 'source_url': BIO}],
            historical_business=[
                {'text': 'The biography describes a past appointment to Samancor’s board; it does not establish a current directorship.', 'source_url': BIO},
                {'text': 'It reports an executive director appointment at the Development Bank of Southern Africa in 2006 for two years.', 'source_url': BIO}],
            biography_captured_at=captured, biography_content_hash=digest(bio))
    if args.interests_pdf:
        from pypdf import PdfReader
        pages = [re.sub(r'\A\s*\d+\s*\n', '', p.extract_text() or '', count=1) for p in PdfReader(args.interests_pdf).pages]
        offsets = []
        full = ''
        for page in pages:
            offsets.append(len(full)); full += page + '\n'
        matches = list(re.finditer(r'(?m)^\s*\d+\.\d+\s+([^\n]+,\s*(?:Mr\.?|Ms\.?|Mrs\.?|Doctor|Dr\.?|Prof\.?|Rev\.?)\s+[^\n]+)\s*\n\s*([^\n]+)\n\s*1\.\s*SHARES AND OTHER FINANCIAL INTERESTS', full))
        lookup = {(p['code'].casefold(), tuple(name_key(m['name']))): m['id'] for p in parties for m in p['members']}
        linked = 0
        for i, match in enumerate(matches):
            member_id = lookup.get((match[2].strip().casefold(), tuple(name_key(match[1]))))
            if not member_id:
                continue
            end = matches[i + 1].start() if i + 1 < len(matches) else len(full)
            section = full[match.end():end]
            finish = re.search(r'\n\s*5\.\s*SPONSORSHIPS', section)
            if not finish or finish.start() > 12000:
                continue
            excerpt = '1. SHARES AND OTHER FINANCIAL INTERESTS\n' + section[:finish.start()].strip()
            page_start = max(i for i, offset in enumerate(offsets) if offset <= match.start()) + 1
            page_end = max(i for i, offset in enumerate(offsets) if offset <= match.end() + finish.start()) + 1
            profiles.setdefault(member_id, {})['business_interests'] = {'text': excerpt, 'source_url': REGISTER,
                'period': 'June 2026 public register', 'page': page_start, 'page_end': page_end,
                'captured_at': captured, 'content_hash': digest(excerpt),
                'label': 'Declared shares, outside work, directorships and consultancies. Self-disclosure, not a CIPC registry check.'}
            linked += 1
        print('Linked dated business disclosures:', linked)
    data = {'schema_version': 1, 'captured_at': captured,
            'coverage': 'Parliament-listed representatives, including National Assembly and NCOP members. This is not a list of every party member nationwide. Counts reflect this captured roster, not election seat totals. Sourced party leadership is listed separately from MPs.',
            'catalog_source': PARLIAMENT + '/political-party-list', 'parties': parties, 'profiles': profiles, 'leaders': existing.get('leaders', []),
            'interests_register': {'source_url': REGISTER, 'directory_url': PARLIAMENT + '/register-members-Interests', 'period': 'June 2026', 'captured_at': captured},
            'remuneration_schedules': [dict(role=role, annual_zar=amount, effective_from='2025-04-01', published_at='2026-01-16', source_url=PAY, page=3,
                label='Published annual remuneration for this office. Dated 2025/26 schedule, not verified personal pay or a claim about later rates.')
                for role, amount in [('Minister', 2792155), ('Deputy Minister', 2299398), ('Deputy President', 3284911)]]}
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
