"""Generate a scoped, source-backed graph for any query; never invent biology."""
import hashlib
import re
import uuid
from collections import Counter
from urllib.parse import quote

from atlas.graph import filtered_graph, coverage
from atlas.providers import pubtator_annotations
from atlas.store import normalize
from atlas.communities import matching_communities


def build_live_view(live, identity_id=None, annotate=True):
    query, timestamp = live['query'], live['retrieved_at']
    identities = live['identities']
    for candidate in identities:
        if candidate.get('url', '').startswith('http://purl.obolibrary.org/'):
            ontology = 'mondo' if candidate['id'].startswith('MONDO:') else 'hp'
            candidate['url'] = 'https://www.ebi.ac.uk/ols4/ontologies/' + ontology + '/classes?iri=' + quote(candidate['url'], safe='')
    if identity_id:
        selected = next((x for x in identities if x['id'] == identity_id), None)
        if not selected:
            raise ValueError('Selected identity is not in the retrieved candidates')
    else:
        exact = [x for x in identities if normalize(query) in {normalize(x['label']), normalize(x['id']), *[normalize(s) for s in x.get('synonyms', [])]}]
        selected = exact[0] if len(exact) == 1 else None
    root = selected['id'] if selected else 'atlas:query:' + hashlib.sha256(normalize(query).encode()).hexdigest()[:20]
    nodes, edges, sources = {}, [], {}

    def add_node(id, kind, label, **kw):
        if id not in nodes:
            nodes[id] = dict(id=id, kind=kind, label=label, aliases=[], cluster={'paper':'Publications','study':'Studies','researcher':'Investigators','gene':'Genes','variant':'Variants','disease':'Diseases','symptom':'Phenotypes','search':'Search context'}.get(kind,'Other'), **kw)

    def source(id, name, url, locator, family=None):
        sources[id] = dict(id=id, name=name, url=url, family=family or id, locator=locator, reviewed_at=timestamp[:10], retrieved_at=timestamp, tier='live_record')

    scope = hashlib.sha256((query + timestamp).encode()).hexdigest()[:16]
    def edge(a, b, relation, text, source_id, locator, status='observed', confidence='high', caveat=''):
        edges.append(dict(id='live:' + scope + ':' + str(len(edges)), subject=a, object=b, relation=relation,
                          explanation=text, status=status, confidence=confidence, reviewed_at=timestamp[:10],
                          confidence_basis='Confidence in the stated metadata relationship only; not in disease causation, efficacy, or clinical applicability.',
                          caveat=caveat, metadata_only=True, evidence=[dict(source_id=source_id, stance='supports', locator=locator)]))

    def identity_kind(id):
        return 'gene' if id.startswith('NCBIGene:') else 'symptom' if id.startswith('HP:') else 'disease'

    add_node(root, identity_kind(root) if selected else 'search', selected['label'] if selected else query,
             description='Live research map. Literature retrieval and automated mentions do not establish biological causation.',
             graph_label=(selected['label'] if selected else query), url=selected.get('url') if selected else None,
             identity_note='Resolved by exact label or synonym.' if selected else 'Identity is unresolved or ambiguous. Choose an ontology candidate before interpreting disease-specific evidence.')
    for candidate in identities[:10]:
        id = candidate['id']
        add_node(id, identity_kind(id), candidate['label'], url=candidate['url'], graph_label=candidate['label'], description='; '.join(candidate.get('description', [])) if isinstance(candidate.get('description'), list) else candidate.get('description', ''))
        if id == root:
            continue
        src = 'identity:' + id
        source(src, 'Public identity lookup · ' + id, candidate['url'], 'Search result for ' + query)
        edge(root, id, 'identity_search_candidate', 'The identity service returned this term for the search; it is not asserted equivalent to the selected disease.', src, 'Search result label and synonyms', 'inferred', 'moderate', 'Subtype and broad symptom matches require explicit identity review.')
    for paper in live['papers'][:12]:
        id = paper['id']
        add_node(id, 'paper', paper['title'], url=paper['url'], year=paper.get('year'), authors=', '.join(paper.get('authors', [])), abstract=paper['abstract'], graph_label=paper['title'][:27])
        src = 'publication:' + id
        source(src, paper['source'] + ' · ' + id, paper['url'], 'Retrieved title, abstract and author list', paper['lineage'])
        edge(root, id, 'returned_by_literature_search', 'This publication was returned for "' + query + '". Read its abstract to assess relevance.', src, 'Search query: ' + query, caveat='Retrieval is not confirmation of a mechanistic relationship. This may be background or tangential evidence.')
        for index, author in enumerate(paper.get('authors', [])[:1]):
            if not author:
                continue
            author_id = 'atlas:author:' + id + ':' + str(index)
            profile = next((x for x in paper.get('author_profiles', []) if x['name'] == author), {})
            add_node(author_id, 'researcher', author, url=paper['url'], affiliation=profile.get('affiliation'), email=profile.get('email'),
                     identity_note='Publication-scoped identity and affiliation contact. Not disambiguated; current role and contact information must be verified.')
            edge(id, author_id, 'authored_by', 'This person is listed as an author in the indexed publication.', src, 'Author list')
    for trial in live['studies'][:8]:
        id = 'NCT:' + trial['id'][3:]
        add_node(id, 'study', trial['title'], url=trial['url'], study_status=trial['status'], last_updated=trial.get('last_updated'),
                 eligibility=trial.get('eligibility'), results_posted=trial['results_posted'], graph_label=trial['id'])
        src = 'study:' + trial['id']
        source(src, 'ClinicalTrials.gov · ' + trial['id'], trial['url'], 'Study search, conditions, status and eligibility')
        edge(root, id, 'returned_by_study_search', 'This study was returned for "' + query + '"; listed conditions: ' + '; '.join(trial['conditions']) + '.', src, 'query.term=' + query,
             caveat='Search relevance, biological applicability, and personal eligibility require review. Status: ' + trial['status'].replace('_', ' ').lower() + '.')
        for index, person in enumerate(trial.get('contacts', []) + trial.get('officials', [])):
            if not person.get('name'):
                continue
            person_id = 'study-contact:' + trial['id'] + ':' + str(index)
            add_node(person_id, 'researcher', person['name'], email=person.get('email'), phone=person.get('phone'),
                     contact_url=trial['url'], url=trial['url'], affiliation=person.get('affiliation'))
            edge(id, person_id, 'listed_study_contact', 'The registry lists this person as a study contact or official.', src, 'contactsLocationsModule')
        if trial.get('sponsor'):
            sponsor_id = 'study-sponsor:' + hashlib.sha256(trial['sponsor'].encode()).hexdigest()[:16]
            add_node(sponsor_id, 'institution', trial['sponsor'], url=trial['url'], contact_url=trial['url'], description='Lead sponsor in the retrieved study record. The registry is a source link, not the institution website.')
            edge(id, sponsor_id, 'sponsored_by', 'Listed lead study sponsor.', src, 'sponsorCollaboratorsModule.leadSponsor')
    for community in matching_communities(query, selected):
        cid = community['id']
        add_node(cid, 'asset' if cid == 'atlas:asset:simons' else 'organization', community['name'],
                 **{k: v for k, v in community.items() if k not in ('id', 'name', 'terms')}, url=community['website'])
        src = 'community:' + cid
        source(src, community['name'] + ' public profile', community['source'], 'Reviewed community directory; exact disease/gene match')
        edge(root, cid, 'has_patient_community', 'The reviewed directory links this disease or gene query to this community.', src,
             'Exact directory term match: ' + query, caveat='Directory coverage is limited. Confirm current services and suitability with the organization.')
    annotations = []
    if annotate:
        try:
            annotations = pubtator_annotations([p['pmid'] for p in live['papers'][:8] if p.get('pmid')])
            live['providers'].append({'provider': 'PubTator3', 'status': 'ok', 'count': len(annotations)})
        except Exception as exc:
            live['providers'].append({'provider': 'PubTator3', 'status': 'unavailable', 'error_type': type(exc).__name__})
    # Keep frequent entities so the first graph remains usable; original records remain available.
    frequency = Counter((a['kind'], a['identifier']) for a in annotations)
    chosen = set(key for key, count in frequency.most_common(12))
    seen = set()
    for mention in annotations:
        if (mention['kind'], mention['identifier']) not in chosen:
            continue
        paper_id = 'PMID:' + mention['pmid']
        if paper_id not in nodes:
            continue
        rawid = mention['identifier']
        entity_id = 'NCBIGene:' + rawid if mention['kind'] == 'gene' and rawid.isdigit() else 'PubTator:' + mention['kind'] + ':' + rawid
        if (paper_id, entity_id) in seen:
            continue
        seen.add((paper_id, entity_id))
        add_node(entity_id, mention['kind'], mention['text'], description='Automatically annotated entity mention; biological meaning needs source review.')
        src = 'pubtator:' + mention['pmid']
        source(src, 'PubTator3 annotations · PMID ' + mention['pmid'], 'https://www.ncbi.nlm.nih.gov/research/pubtator3-api/publications/export/biocjson?pmids=' + mention['pmid'], 'BioC annotations and character offsets', 'publication:' + mention['pmid'])
        edge(paper_id, entity_id, 'automatically_annotated_mention', 'PubTator annotated "' + mention['text'] + '" in this publication.', src,
             mention['passage'] + ' locations: ' + str(mention['locations']), 'inferred', 'moderate', 'Automated entity normalization can be wrong. A mention is not a causal, therapeutic, or shared-mechanism claim.')
    dataset = {'nodes': list(nodes.values()), 'edges': edges, 'sources': list(sources.values())}
    return {'id': str(uuid.uuid4()), 'focus': root, 'dataset': dataset, 'live': live,
            'coverage': {**coverage(), 'scope': 'Live graph for "' + query + '" across public disease, phenotype, gene, literature and study databases. Results are bounded; completeness and rarity classification are not guaranteed.',
                         'reviewed_at': timestamp[:10], 'providers': live['providers']},
            'identity_resolved': bool(selected)}


def view_graph(view, min_confidence='moderate', include_inferred=True):
    graph = filtered_graph(view['dataset'], view['focus'], min_confidence, include_inferred)
    graph.update(graph_id=view['id'], live=view['live'], coverage=view['coverage'], identity_resolved=view['identity_resolved'], metadata_only=True)
    for cluster in graph['clusters']:
        cluster['method'] = 'Live record type; not a validated biological mechanism cluster.'
    return graph
