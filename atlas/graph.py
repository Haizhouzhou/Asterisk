"""Evidence-first filtering, auditable neighborhood paths, and conservative ranking."""
from collections import Counter, deque
from datetime import date

CONFIDENCE = {'low': 1, 'moderate': 2, 'high': 3}


def is_metadata_candidate(edge):
    return bool(edge.get('metadata_only')) and edge.get('relation') in {
        'identity_search_candidate', 'automatically_annotated_mention'}


def assess(edge, source_map):
    support, contradictions, missing = [], [], []
    for ev in edge.get('evidence', []):
        source = source_map.get(ev['source_id'])
        if not source or not source.get('url', '').startswith('https://') or not ev.get('locator'):
            missing.append(ev['source_id'])
        elif ev['stance'] == 'supports':
            support.append(source)
        else:
            contradictions.append(source)
    families = sorted({s['family'] for s in support})
    flags = []
    if not support:
        flags.append('No traceable supporting source')
    if missing:
        flags.append('Missing or incomplete provenance')
    if edge['status'] == 'inferred':
        flags.append('Search or annotation candidate; requires source and identity review' if is_metadata_candidate(edge)
                     else 'Research hypothesis; requires expert validation')
    if edge['status'] == 'disputed' or contradictions:
        flags.append('Counterevidence or limitation must be reviewed')
    if len(families) < 2:
        flags.append('Single source lineage; no independent corroboration established')
    return {'traceable': bool(support) and not missing, 'source_families': families,
            'source_count': len(support), 'contradictory_sources': [s['id'] for s in contradictions],
            'flags': flags, 'verification_scope': 'Provenance and consistency checks, not validation of scientific truth.'}


def filtered_graph(dataset, focus, min_confidence='moderate', include_inferred=True, kinds=None):
    node_map = {n['id']: n for n in dataset['nodes']}
    source_map = {s['id']: s for s in dataset['sources']}
    if focus not in node_map:
        raise ValueError('Unknown node identifier')
    accepted, excluded = [], []
    for e in dataset['edges']:
        assessment = assess(e, source_map)
        reason = None
        if not assessment['traceable']:
            reason = 'incomplete_provenance'
        elif CONFIDENCE[e['confidence']] < CONFIDENCE[min_confidence]:
            reason = 'below_confidence_filter'
        elif e['status'] == 'inferred' and not include_inferred and not is_metadata_candidate(e):
            reason = 'hypotheses_hidden'
        # Counterevidence is never silently discarded by the hypothesis filter.
        if reason:
            excluded.append({'id': e['id'], 'reason': reason})
        else:
            accepted.append({**e, 'assessment': assessment})
    adj = {}
    for e in accepted:
        for a, b in [(e['subject'], e['object']), (e['object'], e['subject'])]:
            adj.setdefault(a, []).append((b, e))
    # Undirected navigation only; edge direction retains its original semantics.
    distance = {focus: 0}
    queue = deque([focus])
    while queue:
        a = queue.popleft()
        if distance[a] >= 4:
            continue
        for b, e in adj.get(a, []):
            if b not in distance:
                distance[b] = distance[a] + 1
                queue.append(b)
    visible = {id for id in distance if not kinds or node_map[id]['kind'] in kinds or id == focus}
    edges = [e for e in accepted if e['subject'] in visible and e['object'] in visible]
    degrees = Counter(x for e in edges if e['status'] == 'observed' for x in [e['subject'], e['object']])
    denom = max(1, len(visible) - 1)
    nodes = [{**node_map[id], 'distance': distance[id], 'degree': degrees[id], 'centrality': round(degrees[id] / denom, 3)} for id in sorted(visible)]
    # Mechanism categories come from curated variant-effect summaries, not symptom clustering.
    clusters = [{'name': name, 'count': count, 'method': 'Curated mechanism / research layer; not a validated disease taxonomy'} for name, count in Counter(n.get('cluster', 'Other') for n in nodes).items()]
    return {'focus': focus, 'nodes': nodes, 'edges': edges, 'sources': dataset['sources'], 'clusters': clusters,
            'filters': {'min_confidence': min_confidence, 'include_inferred': include_inferred, 'kinds': kinds},
            'excluded': excluded, 'centrality_method': 'Degree / (visible node count - 1), using observed edges only. Measures map connectivity, not medical importance.'}


def shortest_path(graph, start, target):
    adj = {}
    for e in graph['edges']:
        if e['status'] == 'disputed':
            continue
        for a, b in [(e['subject'], e['object']), (e['object'], e['subject'])]:
            adj.setdefault(a, []).append((b, e['id']))
    queue = deque([(start, [])])
    seen = {start}
    while queue:
        node, path = queue.popleft()
        if node == target:
            return path
        for other, edge in adj.get(node, []):
            if other not in seen:
                seen.add(other)
                queue.append((other, path + [edge]))
    return None


def opportunities(graph):
    """Rank asset/collaboration leads, not therapies or diagnostic possibilities."""
    result = []
    nodes = {n['id']: n for n in graph['nodes']}
    diseases = [n for n in graph['nodes'] if n['kind'] == 'disease']
    focus = graph['focus']
    if nodes[focus]['kind'] == 'disease':
        diseases = [n for n in diseases if n['id'] == focus] + [n for n in diseases if n['id'] != focus]
    for target in [n for n in graph['nodes'] if n['kind'] in ('asset', 'study', 'organization', 'researcher')]:
        path = shortest_path(graph, focus, target['id'])
        if not path:
            continue
        path_edges = [next(e for e in graph['edges'] if e['id'] == id) for id in path]
        hypothesis = any(e['status'] == 'inferred' for e in path_edges)
        direct_diseases = {e['subject'] for e in graph['edges'] if e['object'] == target['id'] and nodes[e['subject']]['kind'] == 'disease' and e['status'] == 'observed'}
        shared = len(direct_diseases) >= 2
        score = (30 if shared else 0) + (20 if target['kind'] == 'asset' else 10) + max(0, 20 - 4 * len(path)) - (10 if hypothesis else 0)
        result.append({'target': target['id'], 'label': target['label'], 'kind': target['kind'], 'rank_score': score,
                       'path': path, 'shared_across_diseases': sorted(direct_diseases),
                       'status': 'research_proposal' if hypothesis else 'documented_lead',
                       'why': 'Documented infrastructure used by both communities.' if shared else 'A cited path connects your search to this research lead.',
                       'check_next': 'Compare consent, data dictionary, access policy, and disease-specific measures.' if target['kind'] == 'asset' else ('Confirm current study status and ask the investigator about reusable design elements; eligibility is not assessed.' if target['kind'] == 'study' else 'Verify current role, relevance, and availability before contacting.')})
    return sorted(result, key=lambda x: (-x['rank_score'], x['label']))


def coverage():
    return {
        'scope': 'Live disease, gene and symptom search across MONDO, HPO, NCBI Gene, PubMed, Europe PMC and ClinicalTrials.gov, with on-demand graphs. Curated STXBP1/SLC6A1 is a starter slice; no claim of complete coverage or validated biology for every rare disease.',
        'sources': [
            {'name': 'MONDO / HPO', 'status': 'snapshot + live lookup', 'use': 'Stable terms and synonyms. Human-native terms only; no automatic equivalence mapping.'},
            {'name': 'NCBI Gene / PubMed', 'status': 'live adapters + paper snapshot', 'use': 'Gene identity and indexed publications; abstracts are candidates, not confirmed graph claims.'},
            {'name': 'Europe PMC', 'status': 'live adapter + snapshot', 'use': 'Paper metadata, abstracts, preprint labels; PubMed records share a source lineage.'},
            {'name': 'PubTator3', 'status': 'live entity annotation', 'use': 'Paper-to-gene, disease and variant mentions with offsets. Automated mentions are candidates, not causal relations.'},
            {'name': 'ClinicalTrials.gov', 'status': 'live adapter + snapshot', 'use': 'Study scope, status, eligibility, collaborators. Registry listing is not evidence of efficacy.'},
            {'name': 'GeneReviews / verified community sites', 'status': 'curated cited links', 'use': 'Mechanism summaries and existing registries. Full text is linked, not redistributed.'},
            {'name': 'Reactome', 'status': 'mapping unavailable in snapshot', 'use': 'No pathway membership was invented when mapping requests failed.'},
            {'name': 'ClinVar / ClinGen / Gene2Phenotype', 'status': 'next integration', 'use': 'No patient-specific variants or variant-effect claims imported in this demo.'},
            {'name': 'OpenAlex / NIH RePORTER / model databases', 'status': 'next integration', 'use': 'No author disambiguation, grants, or model availability asserted.'}
        ],
        'gaps': ['Variant-specific effects and counterevidence require expert full-text review.', 'No validated cross-disease treatment recommendation.', 'Registry access and measure comparability have not been confirmed.', 'No patient records are collected.'],
        'reviewed_at': '2026-10-04',
        'moonshot': {'milestone': 'Reach a decision on reusing registry measures for a joint natural-history proposal.',
                     'baseline_days': 70, 'proposed_days': 7, 'factor': 10,
                     'status': 'Illustrative planning hypothesis; not measured impact.',
                     'assumptions': ['Existing registry team responds within a week.', 'Consent and data access permit comparison.', 'A clinician and both patient groups review the proposal.', 'No new registry or ethics approval is needed for the initial feasibility decision.'],
                     'validation': 'Measure actual time to a documented reuse decision against comparable prior efforts.'}
    }
