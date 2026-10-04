import unittest
from atlas.communities import matching_communities
from atlas.live_graph import build_live_view, view_graph
from atlas.leads import ranked_leads


class OutreachTests(unittest.TestCase):
    def fixture(self, query):
        return dict(query=query, retrieved_at='2026-10-04T10:00:00Z', identities=[], papers=[], studies=[], providers=[])

    def test_unknown_and_broad_symptom_do_not_get_unrelated_communities(self):
        for query in ('unknown disease', 'seizures', 'GBA1 other disease'):
            self.assertEqual(matching_communities(query), [])

    def test_matching_gene_communities_are_cited_graph_nodes(self):
        graph = view_graph(build_live_view(self.fixture('STXBP1'), annotate=False))
        leads = ranked_leads(graph)['communities']
        self.assertEqual(len(leads), 2)
        for lead in leads:
            self.assertTrue(lead['email'])
            self.assertTrue(lead['citations'])
            self.assertEqual(sum(c['weight'] for c in lead['criteria']), 100)
            self.assertAlmostEqual(lead['score'], sum(c['value']*c['weight']/100 for c in lead['criteria']), places=1)

    def test_study_contacts_are_scoped_and_missing_contacts_not_fabricated(self):
        live = self.fixture('unknown disease')
        live['studies'] = [dict(id='NCT00000001', title='A study', status='RECRUITING', conditions=['unknown disease'], url='https://clinicaltrials.gov/study/NCT00000001', results_posted=False, sponsor='Example Institute', contacts=[dict(name='Study coordinator', email='coordinator@example.org')])]
        graph = view_graph(build_live_view(live, annotate=False))
        leads = ranked_leads(graph)
        self.assertEqual(leads['communities'], [])
        self.assertEqual(len(leads['research']), 2)
        contact = next(n for n in leads['research'] if n['kind'] == 'researcher')
        self.assertEqual(contact['email'], 'coordinator@example.org')
        institute = next(n for n in leads['research'] if n['kind'] == 'institution')
        self.assertNotIn('email', institute)


if __name__ == '__main__':
    unittest.main()
