import json
import unittest
import urllib.parse as up
from engine.services import PublicServices, public_search_rows, tender_matches
from engine.daily import JobsProvider


class TenderReliabilityTests(unittest.TestCase):
    def test_ignored_keyword_search_does_not_become_fake_match_count(self):
        calls = []
        notices = [{'id': 1, 'description': 'Office furniture'}, {'id': 2, 'description': 'Construction of a library', 'tender_No': 'LIB-02'}]
        def read(url, headers=None):
            calls.append(up.parse_qs(up.urlsplit(url).query))
            return json.dumps({'data': notices, 'recordsFiltered': 2202})
        service = PublicServices(read)
        result = service.tenders('construction')
        self.assertEqual([row['id'] for row in result['results']], [2])
        self.assertIsNone(result['total'])
        self.assertEqual(result['scanned'], 2)
        self.assertEqual(result['next_offset'], 2)
        self.assertTrue(result['has_more'])
        self.assertEqual(calls[0]['length'], ['90'])
        empty = service.tenders('ZZZNOMATCH', start=result['next_offset'])
        self.assertFalse(empty['results'])
        self.assertEqual(empty['scanned'], 2)
        self.assertEqual(empty['next_offset'], 4)
        self.assertTrue(empty['has_more'])

    def test_bounded_cursor_and_unfiltered_provider_count(self):
        rows = [{'id': i, 'description': 'Construction'} for i in range(100)]
        r = PublicServices(lambda *a: json.dumps({'data': rows, 'recordsFiltered': 100})).tenders('construction', start=10)
        self.assertEqual(len(r['results']), 90)
        self.assertEqual(r['next_offset'], 100)
        self.assertFalse(r['has_more'])
        all_rows = PublicServices(lambda *a: json.dumps({'data': rows, 'recordsFiltered': 100})).tenders()
        self.assertEqual(all_rows['total'], 100)
        self.assertEqual(all_rows['scanned'], 30)
        self.assertTrue(all_rows['has_more'])

    def test_structured_supplier_and_number_checks_do_not_match_json_keys(self):
        row = {'tender_No': 'QA-123/26', 'awards': [{'company': 'Library Construction', 'supplierNumber': 'MAAA12345'}]}
        self.assertTrue(tender_matches(row, 'QA123', 'number'))
        self.assertFalse(tender_matches(row, '---', 'number'))
        self.assertTrue(tender_matches(row, 'Library Construction', 'company'))
        self.assertTrue(tender_matches(row, 'MAAA12345', 'supplier'))
        self.assertFalse(tender_matches({'awards': None}, 'company', 'company'))
        self.assertFalse(tender_matches(row, 'Other Supplier', 'company'))

    def test_malformed_provider_response_is_unavailable(self):
        for value in ({}, [], {'data': None}, {'data': [{'description': 'No identifier'}]}):
            with self.assertRaises(ValueError):
                PublicServices(lambda *a: json.dumps(value)).tenders('library')


class DiscoveryReliabilityTests(unittest.TestCase):
    def test_http_200_challenge_uses_ordinary_alternative_provider(self):
        calls = []
        def read(url, headers=None):
            calls.append(url)
            if 'brave.com' in url:
                return '<html><form id="challenge-form">Verify you are human</form></html>'
            return "<a class='result-link' href='https://example.org/alex'>Alex Example</a>"
        result = PublicServices(read).discover('Alex Example')
        self.assertEqual(len(calls), 2)
        self.assertEqual(result['hit_count'], 1)
        self.assertEqual(result['statuses'][0]['service'], 'DuckDuckGo public search (best effort)')

    def test_unreadable_pages_are_not_cached_as_empty_success(self):
        page = ['<html>Server error</html>']
        service = PublicServices(lambda *a: page[0])
        failed = service.discover('Alex Example')
        self.assertEqual(failed['statuses'][0]['status'], 'unavailable')
        self.assertFalse(service.cache)
        page[0] = '<a class="l1" href="https://example.org/alex">Alex Example</a>'
        self.assertEqual(service.discover('Alex Example')['hit_count'], 1)

    def test_explicit_zero_results_is_a_success_but_a_challenge_is_not(self):
        self.assertEqual(public_search_rows('<p>No results found</p>'), [])
        for page in ('<p>CAPTCHA</p>', '<form id="anomaly-modal">Continue</form>', '<html>Changed layout</html>'):
            with self.assertRaises(ValueError):
                public_search_rows(page)

    def test_refresh_updates_the_successful_cache(self):
        page = ['<a class="l1" href="https://example.org/alex">Alex Example</a>']
        service = PublicServices(lambda *a: page[0])
        self.assertEqual(service.discover('Alex Example')['hit_count'], 1)
        page[0] = '<p>No results found</p>'
        self.assertEqual(service.discover('Alex Example', fresh=True)['hit_count'], 0)
        self.assertEqual(service.discover('Alex Example')['hit_count'], 0)

    def test_expired_readable_vacancies_are_a_genuine_empty_success(self):
        html = b'<span id="gvAllJobs_ctl02_lblJobTitle">Library Assistant</span>Unrelated label<span id="gvAllJobs_ctl02_lblClosingDate">01/01/2020</span>'
        self.assertEqual(JobsProvider(lambda *a: html).collect(), [])
