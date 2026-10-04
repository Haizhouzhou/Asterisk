import copy
import unittest
from unittest.mock import patch
import os
from atlas.agent import evidence_packet, analyze
from atlas.seed import build_dataset
from atlas.graph import filtered_graph
from atlas.codex_snapshot import load_review


class CodexSnapshotTests(unittest.TestCase):
    def graph(self):
        return filtered_graph(build_dataset(), 'MONDO:0012812', 'moderate', True)

    def test_exact_committed_packet_loads_without_key(self):
        with patch.dict(os.environ, {'ATLAS_AGENT_PROVIDER': 'codex_snapshot'}, clear=True):
            report = analyze(self.graph(), use_openai=True)
        self.assertEqual(report['mode'], 'codex_snapshot_review')
        self.assertTrue(report['agent_review']['findings'])

    def test_changed_packet_is_not_replayed(self):
        packet = copy.deepcopy(evidence_packet(self.graph()))
        packet['focus'] = 'another-disease'
        with self.assertRaises(ValueError):
            load_review(packet)

    def test_changed_filters_preserve_checks_without_snapshot(self):
        graph = filtered_graph(build_dataset(), 'MONDO:0012812', 'high', False)
        with patch.dict(os.environ, {'ATLAS_AGENT_PROVIDER': 'codex_snapshot'}, clear=True):
            report = analyze(graph, use_openai=True)
        self.assertEqual(report['mode'], 'evidence_checks')
        self.assertIsNone(report['agent_review'])
        self.assertIn('agent_error', report)
