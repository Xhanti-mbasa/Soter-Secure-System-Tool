import html
import json
from pathlib import Path
import tempfile
import unittest

from engine.parties import PartyService, parse_directory, parse_member, parse_roster, attach_salary, DATA
from engine.services import PublicServices

MEMBER = '''<nav>Ministers Deputy President</nav><div class="cell auto member-info"><h2>Mr Gwede Samson Mantashe</h2><span class="label National Assembly">National Assembly</span><span class="green">Minister of Mineral and Petroleum Resources<BR></span><span class="dark-gold">Party:</span><span class="green">African National Congress</span><div id='contact-details'><span class="green">Not a role</span></div>'''

def directory(rows, count=None):
    return "<group-details members='" + html.escape(json.dumps({'a-d': rows}), quote=True) + "' member-count='" + str(len(rows) if count is None else count) + "'></group-details>"

class PartyTests(unittest.TestCase):
    def setUp(self):
        self.service = PartyService(lambda url: MEMBER)

    def test_bundled_directory_is_consistent_and_not_a_national_membership_claim(self):
        data = json.loads(DATA.read_text())
        self.assertEqual(len(data['parties']), 18)
        members = [m for p in data['parties'] for m in p['members']]
        self.assertEqual(len(members), len({m['id'] for m in members}))
        self.assertTrue(all(p['member_count'] == len(p['members']) for p in data['parties']))
        self.assertIn('not a list of every party member', data['coverage'])
        self.assertIn('5975', {m['id'] for m in self.service.party('ANC')['members']})

    def test_roster_excludes_featured_member_from_another_party(self):
        raw = '<h1>African National Congress</h1><h5>Composition (1 member)</h5><ul><li><a href="/person-details/5975">Gwede Samson Mantashe</a></li></ul><aside><a href="/person-details/999">Another Party Member</a></aside>'
        self.assertEqual([m['id'] for m in parse_roster(raw,'ANC','African National Congress')], ['5975'])
        with self.assertRaises(ValueError):parse_roster(raw.replace('(1 member)','(2 members)'),'ANC','African National Congress')

    def test_directory_checks_count_duplicates_and_explicit_party(self):
        rows = [{'id': 1, 'party': 'ANC', 'full_name': 'Example Representative'}, {'id': 2, 'party': 'DA', 'full_name': 'Other Representative'}]
        result = parse_directory(directory(rows), ['ANC','DA'])
        self.assertEqual(result['ANC'][0]['id'], '1')
        self.assertEqual(result['DA'][0]['party_code'], 'DA')
        for raw in (directory(rows,3), directory(rows+rows), directory(rows).replace('DA','UNKNOWN')):
            with self.assertRaises(ValueError):parse_directory(raw,['ANC','DA'])

    def test_member_role_is_not_navigation_or_contact_text(self):
        member = parse_member(MEMBER,'5975')
        self.assertEqual(member['role'],'Minister of Mineral and Petroleum Resources')
        self.assertEqual(member['party_name'],'African National Congress')
        self.assertEqual(member['chamber'],'National Assembly')

    def test_dated_remuneration_is_office_schedule_not_personal_pay(self):
        member = self.service.member('5975')
        self.assertEqual(member['remuneration']['annual_zar'],2792155)
        self.assertEqual(member['remuneration']['effective_from'],'2025-04-01')
        self.assertIn('not verified personal pay',member['remuneration']['label'])
        self.assertIsNone(attach_salary({'role':'Portfolio committee member'},self.service.data['remuneration_schedules'])['remuneration'])
        self.assertEqual(attach_salary({'role':'Deputy Minister of Example'},self.service.data['remuneration_schedules'])['remuneration']['role'],'Deputy Minister')

    def test_refresh_failure_preserves_roster_and_provenance(self):
        def fail(url):raise ValueError('Provider offline')
        service = PartyService(fail)
        before = service.party('ANC')
        after = service.party('ANC',True)
        self.assertEqual(after['members'],before['members'])
        self.assertEqual(after['captured_at'],before['captured_at'])
        self.assertEqual(after['status'],'refresh_unavailable')
        self.assertEqual(service.member('5975',True)['status'],'refresh_unavailable')

    def test_fresh_role_replaces_old_role_without_inventing_pay(self):
        service = PartyService(lambda url: MEMBER.replace('Minister of Mineral and Petroleum Resources',''))
        result = service.member('5975',True)
        self.assertEqual(result['role'],'')
        self.assertIsNone(result['remuneration'])
        self.assertEqual(service.member('5975')['role'],'')

    def test_disclosure_is_business_only_and_not_current_cipc_claim(self):
        data = json.loads(DATA.read_text())
        for profile in data['profiles'].values():
            if profile.get('business_interests'):
                record = profile['business_interests']
                self.assertNotIn('9. OWNERSHIP IN LAND',record['text'])
                self.assertNotIn('5. SPONSORSHIPS',record['text'])
                self.assertIn('not a CIPC registry check',record['label'])
                self.assertGreater(record['page'],1)
        self.assertIn('Nothing to disclose',self.service.member('5975')['business_interests']['text'])
        with self.assertRaises(ValueError):self.service.member('../../private',True)
        with self.assertRaises(ValueError):self.service.party('UNKNOWN',True)

    def test_education_query_matches_name_not_every_optional_topic_word(self):
        urls=[]
        raw='<a class="l1" href="https://www.gov.za/profile"><span class="title">Gwede Mantashe profile</span>Gwede Mantashe holds a degree from Wits.</a>'
        service=PublicServices(lambda url,headers=None:urls.append(url) or raw)
        result=service.discover('Gwede Mantashe',topic='education')
        self.assertEqual(result['hit_count'],1)
        self.assertIn('university',urls[0])
        self.assertFalse(service.discover('Gwede Mantashe',topic='remuneration')['cached'])
        with self.assertRaises(ValueError):service.discover('Gwede Mantashe',topic='arbitrary')

if __name__=='__main__':unittest.main()
