"""Reviewed public community directory; exact disease/gene matching only."""
from atlas.store import normalize
from pathlib import Path

IMAGE_ROOT = Path(__file__).resolve().parents[1] / 'web' / 'lead-images'

DIRECTORY = [
    dict(id='atlas:org:stx', name='STXBP1 Foundation', terms=['STXBP1', 'STXBP1 encephalopathy', 'STXBP1-related disorder', 'MONDO:0012812', 'NCBIGene:6812', 'MUNC18-1'], website='https://www.stxbp1disorders.org/', contact_url='https://www.stxbp1disorders.org/', email='info@stxbp1disorders.org', description='Patient and family community focused on STXBP1-related disorders.', source='https://www.stxbp1disorders.org/'),
    dict(id='atlas:org:slc', name='SLC6A1 Connect', terms=['SLC6A1', 'SLC6A1-related neurodevelopmental disorder', 'SLC6A1-NDD', 'NCBIGene:6529'], website='https://slc6a1connect.org/', contact_url='https://slc6a1connect.org/contact-us/', email='mtingley@slc6a1connect.org', description='Family support and research community for SLC6A1-related disorders.', source='https://slc6a1connect.org/contact-us/'),
    dict(id='atlas:asset:simons', name='Simons Searchlight', terms=['STXBP1', 'SLC6A1', 'STXBP1 encephalopathy', 'STXBP1-related disorder', 'MONDO:0012812', 'NCBIGene:6812', 'NCBIGene:6529', 'SLC6A1-NDD', 'SLC6A1-related neurodevelopmental disorder'], website='https://www.simonssearchlight.org/', contact_url='https://www.simonssearchlight.org/about-connect/', email='coordinator@simonssearchlight.org', phone='855-329-5638', description='Registry and research participation network; confirm consent, measures and eligibility with its team.', source='https://www.simonssearchlight.org/about-connect/'),
    dict(id='community:gaucher:ngf', name='National Gaucher Foundation', terms=['Gaucher disease', 'Gaucher', 'GBA1', 'GBA'], website='https://www.gaucherdisease.org/', contact_url='https://www.gaucherdisease.org/', phone='800-504-3189', description='Patient services, education and support for the Gaucher community.', source='https://www.gaucherdisease.org/'),
    dict(id='community:fabry:nfdf', name='National Fabry Disease Foundation', terms=['Fabry disease', 'Fabry', 'GLA'], website='https://www.fabrydisease.org/', contact_url='https://www.fabrydisease.org/', email='info@fabrydisease.org', description='Patient support, education and a directory of Fabry specialists.', source='https://www.fabrydisease.org/fabry-resources/other-support-organizations'),
    dict(id='community:fabry:fin', name='Fabry International Network', terms=['Fabry disease', 'Fabry', 'GLA'], website='https://www.fabrynetwork.org/', contact_url='https://www.fabrynetwork.org/contact/', email='info@fabrynetwork.org', description='International network connecting Fabry patient organizations.', source='https://www.fabrynetwork.org/contact/'),
    dict(id='community:fabry:fsig', name='Fabry Support & Information Group', terms=['Fabry disease', 'Fabry', 'GLA'], website='https://www.fabry.org/', contact_url='https://www.fabry.org/', email='info@fabry.org', phone='660-463-1355', description='Support and information for the Fabry community.', source='https://www.fabrydisease.org/fabry-resources/other-support-organizations'),
]

# Short paraphrases of each organization's own website, reviewed 2026-10-04.
WEBSITE_SUMMARIES = {
    'atlas:org:stx': ('A parent-led foundation supporting families affected by STXBP1-related disorders. It funds research and helps families understand the condition and get involved.', 'https://www.stxbp1disorders.org/about'),
    'atlas:org:slc': ('Supports families affected by SLC6A1-related disorders and funds research into new treatments. Offers guidance after diagnosis and connections to specialists and research opportunities.', 'https://slc6a1connect.org/'),
    'atlas:asset:simons': ('An international research program connecting families with rare genetic neurodevelopmental disorders and scientists. Collects medical histories, surveys and optional blood samples to support research.', 'https://www.simonssearchlight.org/'),
    'community:gaucher:ngf': ('Supports U.S. patients with Gaucher disease and their families through education, patient services and financial assistance. Helps families find specialists and connect with others.', 'https://www.gaucherdisease.org/'),
    'community:fabry:nfdf': ('Provides education and support for people with Fabry disease and their families. Offers family events, assistance programs and a directory of Fabry specialists.', 'https://www.fabrydisease.org/'),
    'community:fabry:fin': ('Connects Fabry patient organizations around the world. Shares information and supports collaboration to improve the lives of people affected by Fabry disease.', 'https://www.fabrynetwork.org/about-us/'),
    'community:fabry:fsig': ('Offers education, advocacy and a supportive community for people affected by Fabry disease. Provides resources, programs and events for patients and families.', 'https://www.fabry.org/'),
}


def matching_communities(query, identity=None):
    values = {normalize(query)}
    if identity:
        values |= {normalize(identity['id']), normalize(identity['label'])}
    return [profile(c) for c in DIRECTORY if values & {normalize(x) for x in c['terms']}]


def profile(entry):
    result = dict(entry)
    if entry['id'] in WEBSITE_SUMMARIES:
        result['description'], result['description_source'] = WEBSITE_SUMMARIES[entry['id']]
        result['description_reviewed_at'] = '2026-10-04'
    filename = entry['id'].replace(':', '-') + '.png'
    if (IMAGE_ROOT / filename).is_file():
        result['image'] = '/lead-images/' + filename
    return result


def enrich_community(node):
    entry = next((c for c in DIRECTORY if c['id'] == node['id']), None)
    return {**node, **({k: v for k, v in profile(entry).items() if k not in ('id', 'name', 'terms')} if entry else {})}
