import copy
import json
from pathlib import Path
import tempfile
import unittest
from engine.analytics import DATA, snapshot, validate
from engine.parties import PartyService
from engine.publications import PublicationPage, publication
from engine.services import normalize_hit


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads(DATA.read_text())

    def test_allocations_and_provincial_ballots_remain_distinct(self):
        validate(self.data)
        elections={e['date']:e for e in self.data['national_elections']}
        self.assertEqual(elections['2019-05-08']['seats']['ANC'],230)
        self.assertEqual(elections['2024-05-29']['seats']['ANC'],159)
        self.assertEqual(elections['2024-05-29']['seats']['NCC'],2)
        provinces={p['name']:p for p in self.data['provinces']}
        self.assertEqual(provinces['KwaZulu-Natal']['leader'],'MK')
        self.assertEqual(provinces['Western Cape']['leader'],'DA')
        self.assertEqual(provinces['Gauteng']['leader'],'ANC')
        self.assertEqual(provinces['KwaZulu-Natal']['results'][0]['share'],45.35)
        self.assertEqual(provinces['Western Cape']['results'][0]['votes'],1088423)
        self.assertTrue(all(p['path'].startswith('M') and p['path'].endswith('Z') for p in provinces.values()))
        self.assertEqual(self.data['polls'],[])

    def test_incomplete_allocations_fail_without_replacing_snapshot(self):
        self.data['national_elections'][-1]['seats']['ANC']=160
        with self.assertRaises(ValueError):validate(self.data)

    def test_poll_sources_dates_and_election_type_are_required(self):
        poll=dict(election_type='national',measure='voting_intention',target_after='2024-05-29',published_at='2026-09-01',fieldwork_from='2026-08-01',fieldwork_to='2026-08-20',expires_at='2026-12-01',publisher='Controlled test publisher',sample_size=1500,population='Registered voters',methodology='Controlled test methodology',source_url='https://example.org/poll',shares={'ANC':30,'DA':25})
        self.data['polls']=[poll];validate(self.data)
        for change in [dict(election_type='local'),dict(sample_size=0),dict(fieldwork_to='2026-09-02'),dict(target_after='2010-01-01'),dict(win_probability=30)]:
            invalid=copy.deepcopy(self.data);invalid['polls'][0].update(change)
            with self.assertRaises(ValueError):validate(invalid)

    def test_election_calendar_covers_previous_current_and_upcoming(self):
        elections={e['id']:e for e in self.data['elections']}
        self.assertEqual(set(elections),{'npe-2019','lge-2021','npe-2024','lge-2026','npe-2029'})
        self.assertEqual(elections['npe-2024']['shares']['ANC'],40.18)
        self.assertEqual(elections['npe-2024']['shares']['MK'],14.58)
        self.assertEqual(elections['npe-2019']['shares']['ANC'],57.5)
        self.assertEqual(elections['lge-2021']['shares']['DA'],21.62)
        lge=elections['lge-2026']
        self.assertEqual((lge['kind'],lge['date'],lge['polls_open'],lge['polls_close']),('municipal','2026-11-04','07:00','21:00'))
        self.assertIsNone(lge['results_declared_at']);self.assertNotIn('shares',lge)
        self.assertIsNone(elections['npe-2029']['date']);self.assertEqual(elections['npe-2029']['due_year'],2029)

    def test_invalid_election_entries_are_rejected(self):
        changes=[('lge-2026',dict(shares={'ANC':40})),('lge-2026',dict(kind='provincial_only')),('lge-2026',dict(special_votes=['2026-11-05'])),
                 ('lge-2026',dict(polls_open='21:00',polls_close='07:00')),('npe-2024',dict(results_declared_at='2024-05-01')),
                 ('npe-2024',dict(shares={'ANC':80,'DA':30})),('npe-2024',dict(sources=[{'label':'x','url':'http://insecure.example'}])),
                 ('npe-2029',dict(due_year=None)),('npe-2024',dict(win_probability=40)),('npe-2024',dict(date='2024-05-30'))]
        for eid,change in changes:
            invalid=copy.deepcopy(self.data);next(e for e in invalid['elections'] if e['id']==eid).update(change)
            with self.subTest(eid=eid,change=change),self.assertRaises(ValueError):validate(invalid)
        duplicate=copy.deepcopy(self.data);duplicate['elections'].append(copy.deepcopy(duplicate['elections'][0]))
        with self.assertRaises(ValueError):validate(duplicate)

    def test_declared_results_can_be_added_to_the_current_election(self):
        data=copy.deepcopy(self.data);lge=next(e for e in data['elections'] if e['id']=='lge-2026')
        lge.update(results_declared_at='2026-11-07',measure='Ward + PR vote share, all municipalities',shares={'ANC':40.0,'DA':22.0})
        validate(data)

    def test_snapshot_reads_updated_results_without_process_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'evidence.json';p.write_text(json.dumps(self.data));self.assertEqual(snapshot(p)['national_elections'][-1]['seats']['ANC'],159)
            self.data['national_elections'][-1]['seats'].update(ANC=158,DA=88);p.write_text(json.dumps(self.data))
            self.assertEqual(snapshot(p)['national_elections'][-1]['seats']['ANC'],158)

    def test_ramaphosa_is_leadership_not_an_extra_mp_or_salary_guess(self):
        reads=[];service=PartyService(lambda url:reads.append(url))
        leader=service.member('leader-anc-ramaphosa',True)
        self.assertEqual(leader['party_code'],'ANC');self.assertEqual(leader['entity_type'],'party_leader')
        self.assertIsNone(leader['remuneration']);self.assertEqual(reads,[])
        self.assertNotIn(leader['id'],{m['id'] for m in service.party('ANC')['members']})
        with self.assertRaises(ValueError):service.member('leader-anc-fabricated',True)


class PublicationTests(unittest.TestCase):
    def parse(self,html):
        parser=PublicationPage();parser.feed(html);return parser.result()

    def test_explicit_publication_is_separate_from_modified_and_retrieved(self):
        result=self.parse('<meta property="article:modified_time" content="2026-10-09"><meta property="article:published_time" content="2026-08-03T09:12:00+02:00">')
        self.assertEqual(result['published_at'],'2026-08-03')
        self.assertIn('article:published_time',result['publication_date_source'])
        self.assertIsNone(self.parse('<time datetime="2026-10-09">Updated</time>')['published_at'])
        hit=normalize_hit(dict(url='https://example.org/story',title='Gwede Mantashe article',description='Public statement',page_age='2026-10-09T08:00:00Z'),'Gwede Mantashe')
        self.assertEqual(hit['index_date'],'2026-10-09');self.assertIsNone(hit['published_at'])

    def test_structured_article_dates_and_conflicts(self):
        jsonld='<script type="application/ld+json">'+json.dumps({'@graph':[{'@type':'NewsArticle','datePublished':'2026-08-03','dateModified':'2026-10-09'}]})+'</script>'
        self.assertEqual(self.parse(jsonld)['published_at'],'2026-08-03')
        conflict=self.parse(jsonld+'<meta property="article:published_time" content="2026-08-04">')
        self.assertEqual(conflict['date_status'],'conflicting_metadata');self.assertIsNone(conflict['published_at'])
        self.assertIsNone(self.parse('<script type="application/ld+json">{"@type":null,"datePublished":"2026-01-01"}</script>')['published_at'])

    def test_source_fetch_uses_guarded_hosts_and_keeps_original_date_evidence(self):
        class Fetch:
            def fetch(self,url,hosts):
                self.url=url;self.hosts=hosts
                return b'<meta itemprop="datePublished" content="2026-07-10">','text/html',url,'utf-8'
        fetch=Fetch();result=publication('https://example.org/article',fetch)
        self.assertEqual(fetch.hosts,{'example.org'});self.assertEqual(result['published_at'],'2026-07-10')
        self.assertEqual(result['publication_source_url'],fetch.url);self.assertIn('date_checked_at',result)
        with self.assertRaises(ValueError):publication('file:///etc/passwd',fetch)


if __name__=='__main__':unittest.main()
