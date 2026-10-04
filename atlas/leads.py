"""Explainable ranking of sourced outreach leads, never treatment relevance."""
from atlas.graph import shortest_path
from atlas.communities import enrich_community


def ranked_leads(graph):
    result = {'communities': [], 'research': []}
    edges = {e['id']: e for e in graph['edges']}
    sources = {s['id']: s for s in graph['sources']}
    for raw in graph['nodes']:
        if raw['kind'] not in ('organization', 'asset', 'institution', 'researcher'):
            continue
        node = enrich_community(raw)
        path = shortest_path(graph, graph['focus'], node['id'])
        if path is None:
            continue
        selected = [edges[id] for id in path]
        inferred = any(e['status'] == 'inferred' for e in selected)
        relevance = max(10, 100 - 20 * max(0, len(path)-1) - (25 if inferred else 0))
        support = round(100 * sum(e['status'] == 'observed' for e in selected) / max(1, len(selected)))
        website = node.get('website') or node.get('url')
        contact = 100 if node.get('email') or node.get('phone') else 60 if node.get('contact_url') else 0
        completeness = round(100 * sum(bool(node.get(k)) for k in ('description', 'image', 'email', 'phone')) / 4)
        criteria = [dict(label='Search connection', value=relevance, weight=45), dict(label='Source support', value=support, weight=25), dict(label='Contact route', value=contact, weight=20), dict(label='Profile details', value=completeness, weight=10)]
        refs = {ev['source_id'] for e in selected for ev in e['evidence']}
        citations = [sources[id] for id in sorted(refs) if id in sources]
        if not website and citations:
            website = citations[-1].get('url')
        if node.get('source'):
            citations.append(dict(name='Public organization profile / contact source', url=node['source']))
        if node.get('description_source'):
            citations.append(dict(name='About this community — official website', url=node['description_source']))
        result['communities' if node['kind'] in ('organization', 'asset') else 'research'].append({
            **node, 'website': website, 'criteria': criteria, 'score': round(sum(c['value']*c['weight']/100 for c in criteria), 1),
            'path': path, 'citations': citations, 'indirect': len(path)>1 or inferred,
            'why': ('Related through shared research or resources; may focus on a different condition.' if len(path)>1 or inferred else 'The sources link this person or organization to your search.'),
            'contact_note': 'Use the listed contact details to ask about their work or support.' if contact else 'Contact details are not listed. Visit the source or official website to find them.'})
    for values in result.values():
        values.sort(key=lambda x: (-x['score'], x['label'], x['id']))
    result['coverage'] = 'Community directory currently covers STXBP1, SLC6A1, Gaucher and Fabry. Other searches show only communities supported by available records. Symptoms can produce indirect leads; this is not a diagnosis. Ranking weights: connection 45%, source support 25%, contact route 20%, profile details 10%. Scores rank outreach leads, not clinical importance or likelihood of response.'
    return result
