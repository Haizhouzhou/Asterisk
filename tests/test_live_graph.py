import copy
import json
import os
import tempfile
import unittest
from urllib.error import HTTPError
from pathlib import Path
from unittest.mock import patch

from atlas.live_graph import build_live_view, view_graph
from atlas.integrations import configuration, external_agent, secure_request, brightdata_page, review_error, gemini_agent
from atlas.agent import analyze
from atlas.store import Store


def fixture(query='Gaucher disease'):
    return {'query': query, 'retrieved_at': '2026-10-04T12:00:00+00:00', 'providers': [], 'identities': [
        {'id': 'MONDO:0018150', 'label': 'Gaucher disease', 'synonyms': ['Gaucher syndrome'], 'url': 'https://www.ebi.ac.uk/ols4/', 'description': []}],
        'papers': [{'id':'PMID:123', 'pmid':'123', 'title':'Study of Gaucher disease', 'source':'PubMed', 'lineage':'publication:123', 'url':'https://pubmed.ncbi.nlm.nih.gov/123/', 'authors':['Researcher A'], 'abstract':'An abstract', 'year':'2025'}],
        'studies': [{'id':'NCT00000001', 'title':'An observational study', 'url':'https://clinicaltrials.gov/study/NCT00000001', 'status':'COMPLETED', 'conditions':['Gaucher disease'], 'eligibility':'Expert review', 'results_posted':False}],
        'excluded': [], 'coverage':'Bounded search', 'independence_note':'Not independent replication'}


class LiveGraphTests(unittest.TestCase):
    def test_any_disease_builds_a_graph(self):
        for query in ('Gaucher disease', 'Fabry disease', 'rare unknown condition'):
            view = build_live_view(fixture(query), annotate=False)
            graph = view_graph(view)
            self.assertGreater(len(graph['nodes']), 1)
            self.assertGreater(len(graph['edges']), 0)
            self.assertEqual(graph['live']['query'], query)

    def test_unknown_identity_stays_search_context(self):
        view = build_live_view(fixture('unknown'), annotate=False)
        self.assertFalse(view['identity_resolved'])
        self.assertEqual(view['dataset']['nodes'][0]['kind'], 'search')

    def test_exact_synonym_resolves_and_invalid_selection_rejected(self):
        self.assertEqual(build_live_view(fixture('Gaucher syndrome'), annotate=False)['focus'], 'MONDO:0018150')
        with self.assertRaises(ValueError):
            build_live_view(fixture(), identity_id='made-up', annotate=False)

    def test_mentions_never_become_causal_relations(self):
        mention = {'pmid':'123','kind':'gene','identifier':'2629','text':'GBA1','locations':[{'offset':10,'length':4}],'passage':'abstract'}
        with patch('atlas.live_graph.pubtator_annotations', return_value=[mention]):
            view=build_live_view(fixture())
        edge=next(e for e in view['dataset']['edges'] if e['relation']=='automatically_annotated_mention')
        self.assertEqual(edge['status'],'inferred')
        self.assertIn('offset',edge['evidence'][0]['locator'])
        self.assertNotIn('causes',[e['relation'] for e in view['dataset']['edges']])

    def test_annotation_failure_preserves_graph(self):
        with patch('atlas.live_graph.pubtator_annotations', side_effect=TimeoutError):
            view=build_live_view(fixture())
        self.assertGreater(len(view['dataset']['edges']),0)
        self.assertEqual(view['live']['providers'][-1]['status'],'unavailable')

    def test_dynamic_reports_do_not_claim_validated_biology(self):
        graph=view_graph(build_live_view(fixture(), annotate=False))
        report=analyze(graph,graph['live'])
        self.assertFalse(report['biological_route_validated'])
        self.assertIn('Live graph',report['coverage']['scope'])

    def test_graph_views_persist_and_are_isolated(self):
        folder=Path(__file__).resolve().parents[1]/'data'/'test-tmp'
        folder.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=folder) as tmp:
            store=Store(Path(tmp)/'test.sqlite')
            a=build_live_view(fixture(),annotate=False)
            b=build_live_view(fixture('Fabry disease'),annotate=False)
            store.save_graph_view(a);store.save_graph_view(b)
            reopened=Store(Path(tmp)/'test.sqlite')
            self.assertEqual(reopened.graph_view(a['id'])['live']['query'],'Gaucher disease')
            self.assertEqual(reopened.graph_view(b['id'])['live']['query'],'Fabry disease')


class IntegrationSecurityTests(unittest.TestCase):
    def test_gemini_configuration_and_key_in_header_only(self):
        review = {'summary': 'Public evidence'}
        response = {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps(review)}]}}]}
        with patch.dict(os.environ, {'ATLAS_AGENT_PROVIDER': 'gemini', 'GEMINI_API_KEY': 'secret-value'}, clear=True), patch('atlas.integrations.secure_request', return_value=response) as send:
            self.assertTrue(configuration()['configured'])
            self.assertNotIn('secret-value', json.dumps(configuration()))
            self.assertEqual(gemini_agent({'sources': []}, 'Review', {}), review)
            args = send.call_args.args
            self.assertNotIn('secret-value', args[0] + json.dumps(args[1]))
            self.assertEqual(args[2], {'x-goog-api-key': 'secret-value'})

    def test_gemini_rejects_incomplete_and_reflected_secret(self):
        responses = [
            {'candidates': [{'finishReason': 'MAX_TOKENS'}]},
            {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': '{"summary":"secret-value"}'}]}}]},
            {'promptFeedback': {'blockReason': 'SAFETY'}},
        ]
        for response in responses:
            with patch.dict(os.environ, {'GEMINI_API_KEY': 'secret-value'}, clear=True), patch('atlas.integrations.secure_request', return_value=response):
                with self.assertRaises(ValueError):
                    gemini_agent({}, 'Review', {})

    def test_http_diagnostics_expose_status_without_upstream_secrets(self):
        for status in (302, 401, 403, 404, 413, 415, 429, 500, 503):
            error = HTTPError('https://secret.example/token', status, 'secret-value', {'Authorization': 'secret-value'}, None)
            message = review_error(error)
            self.assertIn(f'HTTP {status}', message)
            self.assertNotIn('secret', message.replace('shared secret', 'configuration'))
            self.assertIn('Evidence checks remain available', message)

    def test_health_configuration_contains_no_secrets(self):
        with patch.dict(os.environ,{'ATLAS_AGENT_PROVIDER':'webhook','ATLAS_AGENT_ENDPOINT':'https://trusted.example/review','ATLAS_AGENT_TOKEN':'secret-value','ATLAS_AGENT_ALLOWED_HOSTS':'trusted.example'},clear=True):
            config=configuration()
        self.assertTrue(config['configured'])
        self.assertNotIn('secret-value',json.dumps(config))

    def test_http_and_unallowlisted_endpoints_are_rejected(self):
        for url in ('http://trusted.example','https://other.example','https://user:pass@trusted.example'):
            with self.assertRaises(ValueError):
                secure_request(url,{}, {}, {'trusted.example'})

    def test_webhook_credentials_never_enter_evidence_packet(self):
        with patch.dict(os.environ,{'ATLAS_AGENT_ENDPOINT':'https://trusted.example/review','ATLAS_AGENT_TOKEN':'secret-value','ATLAS_AGENT_ALLOWED_HOSTS':'trusted.example'},clear=True), patch('atlas.integrations.secure_request',return_value={'ok':True}) as send:
            external_agent({'sources':[]},'Review',{})
            args=send.call_args.args
            self.assertNotIn('secret-value',json.dumps(args[1]))
            self.assertEqual(args[2]['Authorization'],'Bearer secret-value')

    def test_reflected_secret_is_rejected_before_persistence(self):
        with patch.dict(os.environ,{'ATLAS_AGENT_ENDPOINT':'https://trusted.example','ATLAS_AGENT_TOKEN':'secret-value','ATLAS_AGENT_ALLOWED_HOSTS':'trusted.example'},clear=True), patch('atlas.integrations.secure_request',return_value={'summary':'secret-value'}):
            with self.assertRaises(ValueError):
                external_agent({},'Review',{})

    def test_brightdata_rejects_arbitrary_browser_url(self):
        with self.assertRaises(ValueError):
            brightdata_page('https://untrusted.example/')


if __name__=='__main__':
    unittest.main()
