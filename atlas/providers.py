"""Bounded HTTPS adapters with disk cache and honest provider failure reporting."""
import hashlib
import html
import json
import re
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen, build_opener
from atlas.integrations import NoRedirect

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_HOSTS = {'www.ebi.ac.uk', 'www.ncbi.nlm.nih.gov', 'eutils.ncbi.nlm.nih.gov', 'clinicaltrials.gov', 'api.openai.com'}
_ncbi_lock = threading.Lock()
_ncbi_last = 0.0


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def clean(text):
    return html.unescape(re.sub('<[^>]*>', ' ', text or '')).strip()


def request_json(url, body=None, headers=None, timeout=20):
    if urlparse(url).scheme != 'https' or urlparse(url).hostname not in ALLOWED_HOSTS:
        raise ValueError('Untrusted provider URL')
    hdr = {'User-Agent': 'Asterisk-demo/0.1', 'Accept': 'application/json', **(headers or {})}
    if body is not None:
        hdr['Content-Type'] = 'application/json'
    req = Request(url, data=json.dumps(body).encode() if body is not None else None, headers=hdr)
    with build_opener(NoRedirect()).open(req, timeout=timeout) as response:
        if urlparse(response.url).hostname not in ALLOWED_HOSTS:
            raise ValueError('Untrusted redirect')
        data = response.read(3_000_001)
        if len(data) > 3_000_000:
            raise ValueError('Provider response exceeds limit')
    return json.loads(data)


def ncbi_request(endpoint, params, xml=False):
    global _ncbi_last
    with _ncbi_lock:
        time.sleep(max(0, 0.36 - (time.monotonic() - _ncbi_last)))
        _ncbi_last = time.monotonic()
        url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/' + endpoint + '?' + urlencode(params)
        if not xml:
            return request_json(url)
        with urlopen(Request(url, headers={'User-Agent': 'Asterisk-demo/0.1'}), timeout=20) as response:
            raw = response.read(3_000_001)
        if len(raw) > 3_000_000:
            raise ValueError('Provider response exceeds limit')
        return ET.fromstring(raw)


def literal(query):
    # Treat query as text, never as arbitrary upstream query syntax.
    return ' '.join(re.findall(r'[A-Za-z0-9]+', query))[:160]


def pubmed(query):
    term = '"' + literal(query) + '"[Title/Abstract]'
    search = ncbi_request('esearch.fcgi', {'db': 'pubmed', 'term': term, 'retmode': 'json', 'retmax': 12, 'sort': 'relevance'})
    ids = search['esearchresult']['idlist']
    if not ids:
        return []
    tree = ncbi_request('efetch.fcgi', {'db': 'pubmed', 'id': ','.join(ids), 'retmode': 'xml'}, xml=True)
    papers = []
    for article in tree.findall('.//PubmedArticle'):
        med = article.find('MedlineCitation')
        pmid = med.findtext('PMID')
        title = ''.join(med.find('Article/ArticleTitle').itertext())
        parts = [''.join(x.itertext()) for x in med.findall('Article/Abstract/AbstractText')]
        types = [x.text or '' for x in med.findall('Article/PublicationTypeList/PublicationType')]
        doi = next((x.text for x in article.findall('PubmedData/ArticleIdList/ArticleId') if x.get('IdType') == 'doi'), None)
        papers.append({'id': 'PMID:' + pmid, 'pmid': pmid, 'title': title, 'abstract': '\n'.join(parts)[:10000], 'doi': doi,
                       'url': 'https://pubmed.ncbi.nlm.nih.gov/' + pmid + '/', 'source': 'PubMed', 'lineage': 'publication:' + pmid,
                       'publication_types': types, 'preprint': 'Preprint' in types, 'retracted': any('Retract' in t for t in types),
                       'authors': [((x.findtext('ForeName') or '') + ' ' + (x.findtext('LastName') or '')).strip() for x in med.findall('Article/AuthorList/Author')],
                       'author_profiles': [{'name': ((x.findtext('ForeName') or '') + ' ' + (x.findtext('LastName') or '')).strip(),
                                            'affiliation': ' '.join(a.itertext()).strip(),
                                            'email': (re.findall(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', ' '.join(a.itertext())) or [None])[0]}
                                           for x in med.findall('Article/AuthorList/Author') for a in x.findall('AffiliationInfo/Affiliation')[:1]],
                       'year': med.findtext('Article/Journal/JournalIssue/PubDate/Year') or med.findtext('Article/Journal/JournalIssue/PubDate/MedlineDate'),
                       'claim_status': 'unreviewed_candidate'})
    return papers


def europe_pmc(query):
    q = 'TITLE_ABS:"' + literal(query) + '"'
    data = request_json('https://www.ebi.ac.uk/europepmc/webservices/rest/search?' + urlencode({'query': q, 'format': 'json', 'resultType': 'core', 'pageSize': 12}))
    result = []
    for p in data.get('resultList', {}).get('result', []):
        pmid = p.get('pmid') or (p['id'] if p.get('source') == 'MED' else None)
        result.append({'id': 'PMID:' + pmid if pmid else 'EPMC:' + p.get('source', '') + ':' + p['id'], 'pmid': pmid,
                       'title': clean(p.get('title')), 'abstract': clean(p.get('abstractText'))[:10000], 'doi': p.get('doi'),
                       'url': 'https://europepmc.org/article/' + p.get('source', 'MED') + '/' + p['id'], 'source': 'Europe PMC',
                       'lineage': 'publication:' + pmid if pmid else 'doi:' + str(p.get('doi') or p['id']),
                       'publication_types': p.get('pubTypeList', {}).get('pubType', []), 'preprint': p.get('source') == 'PPR',
                       'retracted': 'retracted' in ' '.join(p.get('pubTypeList', {}).get('pubType', [])).lower(),
                       'authors': [x.strip() for x in p.get('authorString', '').split(',') if x.strip()], 'year': p.get('pubYear'), 'claim_status': 'unreviewed_candidate'})
    return result


def ontology(query, ontology_name):
    data = request_json('https://www.ebi.ac.uk/ols4/api/search?' + urlencode({'q': query, 'ontology': ontology_name, 'rows': 10}))
    prefix = 'MONDO:' if ontology_name == 'mondo' else 'HP:'
    return [{'id': x['obo_id'], 'label': x['label'], 'synonyms': x.get('related_synonyms', []) + x.get('exact_synonyms', []), 'description': x.get('description', []), 'url': 'https://www.ebi.ac.uk/ols4/ontologies/' + ontology_name + '/classes?iri=' + urlencode({'x': x['iri']})[2:], 'status': 'identity_candidate'}
            for x in data.get('response', {}).get('docs', []) if x.get('obo_id', '').startswith(prefix) and not x.get('isObsolete', False) and not any(s in x.get('label', '').lower() for s in ['macaque', 'mouse', 'zebrafish'])]


def gene(query):
    search = ncbi_request('esearch.fcgi', {'db': 'gene', 'term': literal(query) + '[Gene Name] AND 9606[Taxonomy ID]', 'retmode': 'json', 'retmax': 5})
    ids = search['esearchresult']['idlist']
    if not ids:
        return []
    data = ncbi_request('esummary.fcgi', {'db': 'gene', 'id': ','.join(ids), 'retmode': 'json'})['result']
    return [{'id': 'NCBIGene:' + id, 'label': data[id]['name'], 'synonyms': [x.strip() for x in data[id].get('otheraliases', '').split(',') if x.strip()], 'description': data[id].get('description'), 'url': 'https://www.ncbi.nlm.nih.gov/gene/' + id, 'status': 'identity_candidate'} for id in data['uids']]


def trials(query):
    data = request_json('https://clinicaltrials.gov/api/v2/studies?' + urlencode({'query.term': literal(query), 'pageSize': 8, 'format': 'json'}))
    result = []
    for t in data.get('studies', []):
        p = t['protocolSection']
        id = p['identificationModule']['nctId']
        result.append({'id': id, 'title': p['identificationModule']['briefTitle'], 'status': p['statusModule']['overallStatus'],
                       'last_updated': p['statusModule'].get('lastUpdatePostDateStruct', {}).get('date'),
                       'conditions': p.get('conditionsModule', {}).get('conditions', []), 'url': 'https://clinicaltrials.gov/study/' + id,
                       'eligibility': p.get('eligibilityModule', {}).get('eligibilityCriteria', ''), 'results_posted': bool(t.get('hasResults')),
                       'sponsor': p.get('sponsorCollaboratorsModule', {}).get('leadSponsor', {}).get('name'),
                       'collaborators': p.get('sponsorCollaboratorsModule', {}).get('collaborators', []),
                       'contacts': p.get('contactsLocationsModule', {}).get('centralContacts', []),
                       'officials': p.get('contactsLocationsModule', {}).get('overallOfficials', []),
                       'claim_status': 'unreviewed_candidate', 'eligibility_assessed': False})
    return result


def deduplicate(papers, include_preprints=False):
    selected, excluded = {}, []
    for paper in papers:
        reason = 'retracted' if paper['retracted'] else ('preprint_hidden' if paper['preprint'] and not include_preprints else ('abstract_missing' if not paper['abstract'] else None))
        if reason:
            excluded.append({'id': paper['id'], 'reason': reason})
            continue
        key = ('pmid:' + paper['pmid']) if paper.get('pmid') else ('doi:' + paper['doi'].casefold() if paper.get('doi') else paper['id'])
        if key in selected:
            selected[key]['seen_in'].append(paper['source'])
            excluded.append({'id': paper['id'], 'reason': 'duplicate_same_publication'})
        else:
            selected[key] = {**paper, 'seen_in': [paper['source']]}
    return list(selected.values()), excluded


def live_search(query, kind='auto', include_preprints=False, cache_dir=None, refresh=False):
    cache_dir = Path(cache_dir or ROOT / 'data' / 'live')
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(json.dumps([query.casefold(), kind, include_preprints]).encode()).hexdigest()
    path = cache_dir / (key + '.json')
    if not refresh and path.exists() and time.time() - path.stat().st_mtime < 3600:
        result = json.loads(path.read_text(encoding='utf-8'))
        result['cached'] = True
        return result
    tasks = {'PubMed': lambda: pubmed(query), 'Europe PMC': lambda: europe_pmc(query), 'ClinicalTrials.gov': lambda: trials(query)}
    if kind in ('auto', 'disease'):
        tasks['MONDO'] = lambda: ontology(query, 'mondo')
    if kind in ('auto', 'symptom'):
        tasks['HPO'] = lambda: ontology(query, 'hp')
    if kind in ('auto', 'gene'):
        tasks['NCBI Gene'] = lambda: gene(query)
    records, provider_status = {}, []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {name: pool.submit(fn) for name, fn in tasks.items()}
        for name, future in futures.items():
            try:
                records[name] = future.result()
                provider_status.append({'provider': name, 'status': 'ok', 'count': len(records[name])})
            except Exception as exc:
                records[name] = []
                provider_status.append({'provider': name, 'status': 'unavailable', 'error_type': type(exc).__name__})
    papers, excluded = deduplicate(records.get('PubMed', []) + records.get('Europe PMC', []), include_preprints)
    result = {'query': query, 'retrieved_at': utcnow(), 'cached': False, 'providers': provider_status, 'papers': papers,
              'studies': records.get('ClinicalTrials.gov', []), 'identities': records.get('MONDO', []) + records.get('HPO', []) + records.get('NCBI Gene', []),
              'excluded': excluded, 'coverage': 'Bounded top results, not a systematic review. No imported candidate is a confirmed graph edge.',
              'independence_note': 'PubMed and Europe PMC copies of one publication count once. Distinct papers can still share cohorts, authors, or underlying experiments.'}
    # Atomic write prevents readers from seeing a partial cache entry.
    temporary = path.with_suffix('.' + str(threading.get_ident()) + '.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)
    return result


def pubtator_annotations(pmids):
    """Automated entity mentions only. Never treat co-mentions as causal relations."""
    ids = [str(x) for x in pmids[:8] if str(x).isdigit()]
    if not ids:
        return []
    data = request_json('https://www.ncbi.nlm.nih.gov/research/pubtator3-api/publications/export/biocjson?' + urlencode({'pmids': ','.join(ids)}))
    if isinstance(data, list):
        documents = data
    else:
        documents = data.get('PubTator3', data.get('documents', []))
    mentions = []
    for doc in documents:
        pmid = str(doc.get('id', '')).split('|')[0]
        for passage in doc.get('passages', []):
            pmid = str(passage.get('infons', {}).get('article-id_pmid', pmid))
            for annotation in passage.get('annotations', []):
                info = annotation.get('infons', {})
                kind = info.get('type', '').lower()
                identifier = info.get('identifier', '')
                if kind not in ('gene', 'disease', 'mutation') or not identifier or identifier == '-':
                    continue
                mentions.append({'pmid': pmid, 'kind': 'variant' if kind == 'mutation' else kind, 'identifier': identifier,
                                 'text': annotation.get('text', ''), 'locations': annotation.get('locations', []),
                                 'passage': passage.get('infons', {}).get('type', 'abstract')})
    return mentions[:160]
