import copy
import json
import os
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from atlas.agent import analyze, evidence_packet, proposal_markdown, validate_model_review
from atlas.graph import assess, filtered_graph, opportunities, shortest_path
from atlas.providers import deduplicate, live_search, request_json
from atlas.seed import build_dataset
from atlas.server import Application, make_handler
from atlas.store import Store

TEST_TMP = Path(__file__).resolve().parents[1] / 'data' / 'test-tmp'
TEST_TMP.mkdir(parents=True, exist_ok=True)


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = build_dataset()

    def graph(self, **kw):
        return filtered_graph(self.dataset, 'MONDO:0012812', **kw)

    def test_seed_references_are_complete(self):
        nodes = {n['id'] for n in self.dataset['nodes']}
        sources = {s['id'] for s in self.dataset['sources']}
        for edge in self.dataset['edges']:
            self.assertIn(edge['subject'], nodes)
            self.assertIn(edge['object'], nodes)
            self.assertTrue(edge['reviewed_at'])
            self.assertTrue(edge['evidence'])
            for ev in edge['evidence']:
                self.assertIn(ev['source_id'], sources)
                self.assertTrue(ev['locator'])

    def test_filter_preserves_counterexamples(self):
        graph = self.graph(include_inferred=False)
        self.assertNotIn('inferred', [e['status'] for e in graph['edges']])
        self.assertIn('mechanism-counterexample', [e['id'] for e in graph['edges']])

    def test_provenance_gate_excludes_unsourced_edge(self):
        dataset = copy.deepcopy(self.dataset)
        dataset['edges'][0]['evidence'] = []
        graph = filtered_graph(dataset, 'MONDO:0012812')
        self.assertNotIn(dataset['edges'][0]['id'], [e['id'] for e in graph['edges']])
        self.assertIn('incomplete_provenance', [e['reason'] for e in graph['excluded']])

    def test_same_publication_is_not_two_families(self):
        edge = {'status': 'observed', 'evidence': [{'source_id': 'pubmed', 'stance': 'supports', 'locator': 'abstract'}, {'source_id': 'epmc', 'stance': 'supports', 'locator': 'abstract'}]}
        sources = {id: {'id': id, 'url': 'https://example.org', 'family': 'publication:123'} for id in ('pubmed', 'epmc')}
        self.assertEqual(len(assess(edge, sources)['source_families']), 1)

    def test_opportunities_reach_actual_shared_registry(self):
        graph = self.graph()
        lead = opportunities(graph)[0]
        self.assertEqual(lead['target'], 'atlas:asset:simons')
        self.assertEqual(len(lead['shared_across_diseases']), 2)
        for id in lead['path']:
            self.assertIn(id, [e['id'] for e in graph['edges']])

    def test_shortest_path_never_uses_disputed_link(self):
        graph = {'edges': [{'id': 'x', 'subject': 'a', 'object': 'b', 'status': 'disputed'}]}
        self.assertIsNone(shortest_path(graph, 'a', 'b'))

    def test_curated_disease_identity_is_not_broader_epilepsy(self):
        slc = next(n for n in self.dataset['nodes'] if n['id'] == 'atlas:disease:slc6a1-ndd')
        self.assertNotIn('myoclonic-atonic epilepsy', slc['aliases'])
        self.assertTrue(slc['identity_note'])

    def test_no_route_is_reported_as_coverage_gap(self):
        graph = self.graph()
        graph['nodes'] = [n for n in graph['nodes'] if n['id'] == graph['focus']]
        graph['edges'] = []
        report = analyze(graph)
        self.assertFalse(report['supported_route'])
        self.assertEqual(report['actions'][0]['status'], 'gap')

    def test_snapshot_study_status_is_not_recruiting_invitation(self):
        report = analyze(self.graph())
        study = next(a for a in report['actions'] if a['target'] == 'NCT:04937062')
        self.assertIn('active not recruiting', study['check'])
        self.assertIn('does not prove benefit', study['check'])

    def test_model_packet_includes_original_records(self):
        packet = evidence_packet(self.graph())
        self.assertTrue(any(x.get('source_id') == 'ctg-trial' for x in packet['source_extracts']))
        self.assertTrue(any(x.get('abstract') for x in packet['source_extracts']))

    def test_fabricated_citation_rejected(self):
        review = {'summary': 'x', 'findings': [{'statement': 'x', 'status': 'documented', 'citation_ids': ['fake'], 'limitations': 'x'}], 'actions': [], 'missing_evidence': []}
        with self.assertRaisesRegex(ValueError, 'Untraceable'):
            validate_model_review(review, {'real'})

    def test_openai_not_configured_is_not_simulated(self):
        with patch.dict(os.environ, {}, clear=True):
            report = analyze(self.graph(), use_openai=True)
        self.assertEqual(report['mode'], 'evidence_checks')
        self.assertIsNone(report['agent_review'])
        self.assertIn('not configured', report['agent_error'])

    def test_two_model_passes_and_citation_guard(self):
        review = {'summary': 'Careful draft', 'findings': [{'statement': 'Research lead', 'status': 'hypothesis', 'citation_ids': ['gr-stx'], 'limitations': 'Human review'}], 'actions': [], 'missing_evidence': ['Variant effect']}
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test'}), patch('atlas.agent.model_call', return_value=review) as call:
            report = analyze(self.graph(), use_openai=True)
        self.assertEqual(call.call_count, 2)
        self.assertEqual(report['mode'], 'openai_review')
        self.assertEqual(report['agent_review'], review)

    def test_export_has_sources_and_no_automatic_outreach(self):
        graph = self.graph()
        text = proposal_markdown(analyze(graph), graph)
        self.assertIn('https://', text)
        self.assertIn('No outreach has been sent', text)

    def test_audience_and_language_reach_both_passes_and_export(self):
        review = {'summary': 'Adapted review', 'findings': [{'statement': 'Evidence lead', 'status': 'hypothesis', 'citation_ids': ['gr-stx'], 'limitations': 'Uncertain'}], 'actions': [], 'missing_evidence': ['Functional evidence']}
        graph = self.graph()
        for role, phrase in (('maria', 'Explain every necessary technical term'), ('researcher', 'variant-specific mechanisms'), ('clinician', 'phenotype specificity'), ('industry', 'evidence maturity')):
            with patch.dict(os.environ, {'ATLAS_AGENT_PROVIDER': 'openai', 'OPENAI_API_KEY': 'test'}), patch('atlas.agent.model_call', return_value=review) as call:
                report = analyze(graph, use_openai=True, role=role, language='zh-CN')
            self.assertEqual(report['role'], role)
            self.assertEqual(report['language'], 'zh-CN')
            for invocation in call.call_args_list:
                self.assertIn(phrase, invocation.args[1])
                self.assertIn('Simplified Chinese', invocation.args[1])
                self.assertIn('never evidence strength', invocation.args[1])
            exported = proposal_markdown(report, graph)
            self.assertIn('Adapted review', exported)
            self.assertIn('Evidence lead', exported)
            self.assertIn('https://', exported)

    def test_unknown_audience_and_language_are_rejected(self):
        for args in ({'role': 'unknown'}, {'language': 'unknown'}, {'role': []}):
            with self.assertRaises(ValueError):
                analyze(self.graph(), **args)


class ProviderTests(unittest.TestCase):
    def test_deduplication_preprint_and_retraction_filters(self):
        base = {'id': 'PMID:1', 'pmid': '1', 'doi': '10/x', 'source': 'PubMed', 'abstract': 'Evidence', 'preprint': False, 'retracted': False}
        papers = [base, {**base, 'source': 'Europe PMC'}, {**base, 'id': 'ppr', 'pmid': None, 'preprint': True}, {**base, 'id': 'bad', 'pmid': '2', 'retracted': True}]
        selected, excluded = deduplicate(papers)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]['seen_in'], ['PubMed', 'Europe PMC'])
        self.assertEqual({x['reason'] for x in excluded}, {'duplicate_same_publication', 'preprint_hidden', 'retracted'})

    def test_provider_outage_is_visible_not_empty_success(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as folder, patch('atlas.providers.pubmed', side_effect=TimeoutError), patch('atlas.providers.europe_pmc', return_value=[]), patch('atlas.providers.trials', return_value=[]), patch('atlas.providers.gene', return_value=[]):
            result = live_search('STXBP1', kind='gene', cache_dir=folder)
            self.assertEqual(next(x for x in result['providers'] if x['provider'] == 'PubMed')['status'], 'unavailable')
            second = live_search('STXBP1', kind='gene', cache_dir=folder)
            self.assertTrue(second['cached'])

    def test_untrusted_provider_url_rejected(self):
        with self.assertRaises(ValueError):
            request_json('https://example.com/private')


class StoreAndHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=TEST_TMP)
        self.app = Application(Path(self.tmp.name) / 'test.sqlite')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.app))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.app.pool.shutdown(wait=True)
        self.tmp.cleanup()

    def get(self, path):
        with urlopen(self.url + path, timeout=10) as response:
            return json.loads(response.read())

    def test_search_synonyms_and_sql_input(self):
        self.assertEqual(self.app.store.search('MUNC18-1')[0]['id'], 'NCBIGene:6812')
        self.assertEqual(self.app.store.search("' OR 1=1 --"), [])
        self.assertEqual(self.app.store.search('low muscle tone')[0]['id'], 'HP:0001252')

    def test_unknown_query_no_fabricated_match(self):
        result = self.get('/api/search?q=unknown_disease_9999')
        self.assertEqual(result['matches'], [])
        self.assertIn('no supported graph route', result['message'])

    def test_invalid_graph_filter_rejected(self):
        with self.assertRaises(HTTPError) as cm:
            self.get('/api/graph?min_confidence=fake')
        self.assertEqual(cm.exception.code, 400)

    def test_reseeding_preserves_reports(self):
        graph = self.app.graph({})
        report = analyze(graph)
        self.app.store.save_report(report)
        self.app.store.seed(build_dataset())
        self.assertEqual(self.app.store.report(report['id'])['id'], report['id'])

    def test_analysis_job_round_trip_and_export(self):
        request = Request(self.url + '/api/analysis', data=json.dumps({'focus': 'MONDO:0012812', 'role': 'maria'}).encode(), headers={'Content-Type': 'application/json'})
        with urlopen(request) as response:
            self.assertEqual(response.status, 202)
            job = json.loads(response.read())
        for _ in range(50):
            job = self.get('/api/jobs/' + job['id'])
            if job['status'] == 'complete':
                break
            time.sleep(.05)
        self.assertEqual(job['status'], 'complete')
        report = self.get('/api/reports/' + job['report_id'])
        self.assertEqual(len(report['actions']), 3)
        with urlopen(self.url + '/api/reports/' + report['id'] + '/proposal') as response:
            self.assertIn('attachment', response.headers['Content-Disposition'])
            self.assertIn(b'Research collaboration draft', response.read())

    def test_cross_origin_mutation_rejected(self):
        request = Request(self.url + '/api/analysis', data=b'{}', headers={'Origin': 'https://untrusted.example'})
        with self.assertRaises(HTTPError) as cm:
            urlopen(request)
        self.assertEqual(cm.exception.code, 403)

    def test_source_files_not_served(self):
        with self.assertRaises(HTTPError) as cm:
            urlopen(self.url + '/atlas/server.py')
        self.assertEqual(cm.exception.code, 404)


if __name__ == '__main__':
    unittest.main()
