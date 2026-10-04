"""Small, reviewed slice. Imported records never become biological edges automatically."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEWED = '2026-10-04'


def build_dataset():
    nodes, edges, sources = [], [], []

    def node(id, kind, label, aliases=(), **kw):
        nodes.append(dict(id=id, kind=kind, label=label, aliases=list(aliases), **kw))

    def source(id, name, url, family, locator, **kw):
        sources.append(dict(id=id, name=name, url=url, family=family, locator=locator, reviewed_at=REVIEWED, **kw))

    def edge(id, a, b, relation, explanation, refs, status='observed', confidence='high', caveat='', **kw):
        evidence = [dict(source_id=r, stance='supports', locator=next(s['locator'] for s in sources if s['id'] == r)) for r in refs]
        edges.append(dict(id=id, subject=a, object=b, relation=relation, explanation=explanation, status=status,
                          confidence=confidence, confidence_basis='Curator assessment of directness and source coverage; not a clinical probability.',
                          reviewed_at=REVIEWED, caveat=caveat, evidence=evidence, **kw))

    source('gr-stx', 'GeneReviews · STXBP1', 'https://www.ncbi.nlm.nih.gov/books/NBK396561/', 'gr-stx', 'Molecular Pathogenesis; Clinical Characteristics; Resources', published_at='2023-09-28', tier='expert_review')
    source('gr-slc', 'GeneReviews · SLC6A1', 'https://www.ncbi.nlm.nih.gov/books/NBK589173/', 'gr-slc', 'Molecular Pathogenesis; Clinical Characteristics; Resources', published_at='2023-02-09', tier='expert_review')
    source('ss-stx', 'Simons Searchlight · STXBP1', 'https://www.simonssearchlight.org/research/what-we-study/stxbp1/', 'simons', 'Research Opportunities and Support Resources', tier='primary_organization')
    source('slc-reg', 'SLC6A1 Connect · registries', 'https://slc6a1connect.org/registry/', 'slc6a1-connect', 'Simons Searchlight registry description', tier='primary_organization')
    source('mondo', 'MONDO via EMBL-EBI OLS', 'https://www.ebi.ac.uk/ols4/ontologies/mondo/classes?iri=http%3A%2F%2Fpurl.obolibrary.org%2Fobo%2FMONDO_0012812', 'mondo', 'MONDO:0012812 native disease term', tier='ontology')
    source('hpo', 'Human Phenotype Ontology', 'https://hpo.jax.org/browse/term/HP:0001250', 'hpo', 'HP:0001250 Seizure', tier='ontology')

    stx, slc = 'MONDO:0012812', 'atlas:disease:slc6a1-ndd'
    node(stx, 'disease', 'STXBP1-related disorder', ['STXBP1 encephalopathy', 'DEE4', 'EIEE4', 'developmental and epileptic encephalopathy 4'], cluster='Vesicle release', description='A developmental disorder affecting communication between brain cells.', gene='STXBP1', identity_source='mondo')
    node(slc, 'disease', 'SLC6A1-related disorder', ['SLC6A1-NDD', 'SLC6A1 deficiency disorder'], cluster='GABA reuptake', description='A neurodevelopmental disorder affecting GABA transport.', gene='SLC6A1', identity_note='Local stable disease identifier. Myoclonic-atonic epilepsy is broader than SLC6A1-NDD and is deliberately not used as an equivalent MONDO identity.')
    node('NCBIGene:6812', 'gene', 'STXBP1', ['MUNC18-1', 'syntaxin binding protein 1'], cluster='Vesicle release', url='https://www.ncbi.nlm.nih.gov/gene/6812')
    node('NCBIGene:6529', 'gene', 'SLC6A1', ['GAT-1', 'GABA transporter 1'], cluster='GABA reuptake', url='https://www.ncbi.nlm.nih.gov/gene/6529')
    node('atlas:mechanism:vesicle', 'mechanism', 'Reduced synaptic vesicle release', ['vesicle fusion', 'neurotransmitter release'], cluster='Vesicle release')
    node('atlas:mechanism:gaba', 'mechanism', 'Reduced GABA reuptake', ['GABA transport', 'GABA reuptake'], cluster='GABA reuptake')
    node('HP:0001250', 'symptom', 'Seizure', ['seizures', 'epilepsy'], cluster='Shared observations', url='https://hpo.jax.org/browse/term/HP:0001250')
    node('HP:0001263', 'symptom', 'Global developmental delay', ['developmental delay', 'delayed development'], cluster='Shared observations', url='https://hpo.jax.org/browse/term/HP:0001263')
    node('HP:0001252', 'symptom', 'Hypotonia', ['low muscle tone'], cluster='Shared observations', url='https://hpo.jax.org/browse/term/HP:0001252')
    node('atlas:org:stx', 'organization', 'STXBP1 Foundation', ['STXBP1 patient group'], cluster='Shared infrastructure', url='https://www.stxbp1disorders.org/')
    node('atlas:org:slc', 'organization', 'SLC6A1 Connect', ['SLC6A1 patient group'], cluster='Shared infrastructure', url='https://slc6a1connect.org/')
    node('atlas:asset:simons', 'asset', 'Simons Searchlight registry', ['registry', 'natural history', 'biorepository'], cluster='Shared infrastructure', url='https://www.simonssearchlight.org/', description='Existing cross-gene research infrastructure. Access, consent, data fields, and suitability must be checked with the registry team.')

    edge('stx-gene', stx, 'NCBIGene:6812', 'associated_with_gene', 'Pathogenic STXBP1 variants are associated with this disorder.', ['gr-stx'])
    edge('slc-gene', slc, 'NCBIGene:6529', 'associated_with_gene', 'Pathogenic SLC6A1 variants are associated with this disorder.', ['gr-slc'])
    edge('stx-mechanism', 'NCBIGene:6812', 'atlas:mechanism:vesicle', 'loss_of_function_affects', 'STXBP1 supports vesicle docking and fusion; loss of function impairs neurotransmitter release.', ['gr-stx'], caveat='Gene-level summary. Do not assume every variant has the same effect.')
    edge('slc-mechanism', 'NCBIGene:6529', 'atlas:mechanism:gaba', 'loss_of_function_affects', 'SLC6A1 encodes GAT-1, which transports GABA into neurons and glia.', ['gr-slc'], caveat='The full molecular pathology remains incompletely understood; variant-specific interpretation is needed.')
    for prefix, disease, ref in [('stx', stx, 'gr-stx'), ('slc', slc, 'gr-slc')]:
        for symptom, label in [('HP:0001250', 'seizures'), ('HP:0001263', 'developmental delay'), ('HP:0001252', 'low muscle tone')]:
            edge(prefix + '-' + symptom, disease, symptom, 'has_reported_phenotype', label.capitalize() + ' have been reported in affected individuals.', [ref], caveat='A reported feature is not universal or diagnostic. Broad symptoms alone do not establish a shared mechanism.')
    edge('stx-community', stx, 'atlas:org:stx', 'has_patient_community', 'Simons Searchlight links the STXBP1 community to this foundation.', ['ss-stx'])
    edge('slc-community', slc, 'atlas:org:slc', 'has_patient_community', 'GeneReviews lists SLC6A1 Connect as a disease-specific organization.', ['gr-slc'])
    edge('stx-registry', stx, 'atlas:asset:simons', 'represented_in_registry', 'Simons Searchlight includes STXBP1 research participation.', ['ss-stx', 'gr-stx'])
    edge('slc-registry', slc, 'atlas:asset:simons', 'represented_in_registry', 'SLC6A1 Connect describes participation in Simons Searchlight.', ['slc-reg', 'gr-slc'])
    edge('research-bridge', stx, slc, 'candidate_shared_research', 'Different synaptic processes and overlapping observations suggest comparing registry measures, without assuming a common treatment.', ['gr-stx', 'gr-slc', 'ss-stx', 'slc-reg'], status='inferred', confidence='moderate', caveat='Vesicle release and GABA reuptake are different molecular mechanisms. Reuse is a proposal, not a validated cross-disease intervention.')
    # A deliberately visible counterexample to a tempting but unsupported generalization.
    edge('mechanism-counterexample', 'atlas:mechanism:vesicle', 'atlas:mechanism:gaba', 'same_mechanism_not_established', 'Both affect neural communication, but the cited sources describe different molecular functions.', ['gr-stx', 'gr-slc'], status='disputed', confidence='high', caveat='Shared seizures and broad pathway language cannot justify treating these as the same mechanism.')

    snapshots = ROOT / 'data' / 'snapshots'
    manifest = json.loads((snapshots / 'manifest.json').read_text()) if (snapshots / 'manifest.json').exists() else {}
    for name in ('papers_stxbp1', 'papers_slc6a1'):
        path = snapshots / (name + '.json')
        if not path.exists():
            continue
        disease, gene = (stx, 'NCBIGene:6812') if name.endswith('stxbp1') else (slc, 'NCBIGene:6529')
        for paper in json.loads(path.read_text(encoding='utf-8'))['resultList']['result']:
            if paper.get('source') != 'MED' or not str(paper.get('id', '')).isdigit():
                continue
            pmid = paper['id']
            title = re.sub('<[^>]*>', '', paper['title'])
            source('pmid-' + pmid, 'PubMed · PMID ' + pmid, 'https://pubmed.ncbi.nlm.nih.gov/' + pmid + '/', 'publication:' + pmid, 'Title and abstract, indexed through Europe PMC', tier='publication', published_at=paper.get('firstPublicationDate'), retrieved_at=manifest.get(name, {}).get('retrieved_at'), doi=paper.get('doi'), abstract_available=bool(paper.get('abstractText')))
            node('PMID:' + pmid, 'paper', title, [pmid], cluster='Published evidence', url='https://pubmed.ncbi.nlm.nih.gov/' + pmid + '/', year=paper.get('pubYear'), authors=paper.get('authorString'), doi=paper.get('doi'))
            edge('paper-' + pmid, disease, 'PMID:' + pmid, 'discussed_in_publication', 'This indexed publication discusses ' + ('STXBP1' if disease == stx else 'SLC6A1') + '. It is a reading lead; claims require full-text assessment.', ['pmid-' + pmid], caveat='Publication relevance is not confirmation of a specific mechanism or therapy.')
            # Investigator names and affiliation come from the publication, not fabricated contacts.
            first = (paper.get('authorList', {}).get('author') or [{}])[0]
            if first.get('fullName'):
                author_id = 'atlas:author:' + pmid + ':0'
                affiliations = first.get('authorAffiliationDetailsList', {}).get('authorAffiliation', [])
                node(author_id, 'researcher', first['fullName'], [], cluster='Published evidence', affiliation='; '.join(x.get('affiliation', '') for x in affiliations), identity_note='Publication-scoped author, not OpenAlex-disambiguated. Contact through the publication; current affiliation is unverified.')
                edge('author-' + pmid, 'PMID:' + pmid, author_id, 'authored_by', 'Named author on this publication; potential research contact subject to expertise and identity checks.', ['pmid-' + pmid])

    trial_path = snapshots / 'trial.json'
    if trial_path.exists():
        trial = json.loads(trial_path.read_text(encoding='utf-8'))
        p = trial['protocolSection']
        status = p['statusModule']
        source('ctg-trial', 'ClinicalTrials.gov · NCT04937062', 'https://clinicaltrials.gov/study/NCT04937062', 'study:NCT04937062', 'Conditions; Collaborators; Study Design; Eligibility; Status', tier='study_registry', published_at=status.get('lastUpdatePostDateStruct', {}).get('date'), retrieved_at=manifest.get('trial', {}).get('retrieved_at'))
        node('NCT:04937062', 'study', p['identificationModule']['briefTitle'], ['NCT04937062', 'phenylbutyrate'], cluster='Shared infrastructure', url='https://clinicaltrials.gov/study/NCT04937062', study_status=status['overallStatus'], last_updated=status.get('lastUpdatePostDateStruct', {}).get('date'), phases=p['designModule'].get('phases'), eligibility=p.get('eligibilityModule', {}).get('eligibilityCriteria'), results_posted=bool(trial.get('hasResults')), sponsor=p['sponsorCollaboratorsModule']['leadSponsor']['name'])
        for prefix, disease, org in [('stx', stx, 'atlas:org:stx'), ('slc', slc, 'atlas:org:slc')]:
            edge(prefix + '-study', disease, 'NCT:04937062', 'named_in_study', 'The registered study includes ' + ('STXBP1' if prefix == 'stx' else 'SLC6A1') + ' in its condition and arm descriptions.', ['ctg-trial'], caveat='Registry listing establishes study scope, not efficacy or personal eligibility. Snapshot status: ' + status['overallStatus'].replace('_', ' ').lower() + '.')
            collaborators = [x['name'] for x in p['sponsorCollaboratorsModule'].get('collaborators', [])]
            name = 'STXBP1 Foundation' if prefix == 'stx' else 'SLC6A1 Connect'
            if name in collaborators:
                edge(prefix + '-collaborator', org, 'NCT:04937062', 'listed_study_collaborator', 'The study registry names this patient organization as a collaborator.', ['ctg-trial'])
        sponsor = 'atlas:institution:cornell'
        node(sponsor, 'institution', p['sponsorCollaboratorsModule']['leadSponsor']['name'], [], cluster='Shared infrastructure')
        edge('study-sponsor', 'NCT:04937062', sponsor, 'sponsored_by', 'Listed lead sponsor in the study registry.', ['ctg-trial'])
    return {'nodes': nodes, 'edges': edges, 'sources': sources}
