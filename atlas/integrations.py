"""Server-only integration boundaries. Credentials never enter evidence packets."""
import json
import os
from urllib.parse import urlparse, urlencode
from urllib.request import Request, HTTPRedirectHandler, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward an Authorization header to a redirect destination.
        return None


def secure_request(url, body, headers, allowed_hosts, raw=False):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in allowed_hosts or parsed.username or parsed.password:
        raise ValueError('Integration endpoint must be HTTPS on an explicitly allowed host')
    req = Request(url, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', **headers})
    with build_opener(NoRedirect()).open(req, timeout=90) as response:
        content = response.read(2_000_001)
    if len(content) > 2_000_000:
        raise ValueError('Integration response too large')
    return content.decode('utf-8', errors='replace') if raw else json.loads(content)


def configuration():
    provider = os.environ.get('ATLAS_AGENT_PROVIDER', 'openai')
    configured = bool(os.environ.get('OPENAI_API_KEY')) if provider == 'openai' else bool(
        provider == 'webhook' and os.environ.get('ATLAS_AGENT_ENDPOINT') and os.environ.get('ATLAS_AGENT_TOKEN') and os.environ.get('ATLAS_AGENT_ALLOWED_HOSTS'))
    return {'provider': provider, 'configured': configured,
            'brightdata_configured': bool(os.environ.get('BRIGHTDATA_API_KEY') and os.environ.get('BRIGHTDATA_ZONE'))}


def external_agent(packet, task, schema, previous=None):
    endpoint = os.environ.get('ATLAS_AGENT_ENDPOINT', '')
    allowed = {h.strip().lower() for h in os.environ.get('ATLAS_AGENT_ALLOWED_HOSTS', '').split(',') if h.strip()}
    body = {'version': '1', 'task': task, 'evidence_packet': packet, 'previous_draft': previous, 'response_schema': schema}
    result = secure_request(endpoint, body, {'Authorization': 'Bearer ' + os.environ['ATLAS_AGENT_TOKEN']}, allowed)
    # Detect accidental secret reflection before anything is persisted or shown.
    serialized = json.dumps(result)
    for key in ('ATLAS_AGENT_TOKEN', 'OPENAI_API_KEY', 'BRIGHTDATA_API_KEY'):
        secret = os.environ.get(key)
        if secret and secret in serialized:
            raise ValueError('Agent returned sensitive configuration')
    return result


def brightdata_page(url):
    """Opt-in, bounded retrieval for verified community sources; not a reasoning model."""
    allowed = {h.strip().lower() for h in os.environ.get('BRIGHTDATA_ALLOWED_HOSTS', 'rarediseases.org,globalgenes.org,www.orpha.net,rarediseases.info.nih.gov').split(',')}
    target = urlparse(url)
    if target.scheme != 'https' or target.hostname not in allowed or target.username or target.password:
        raise ValueError('Community source must be on the configured source allowlist')
    key, zone = os.environ.get('BRIGHTDATA_API_KEY'), os.environ.get('BRIGHTDATA_ZONE')
    if not key or not zone:
        raise ValueError('Bright Data is not configured')
    text = secure_request('https://api.brightdata.com/request', {'zone': zone, 'url': url, 'format': 'raw'},
                          {'Authorization': 'Bearer ' + key}, {'api.brightdata.com'}, raw=True)
    from atlas.providers import clean, utcnow
    # Remove active and non-content sections before passing text to an agent.
    import re
    text = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', text, flags=re.I | re.S)
    text = clean(text)[:16000]
    if key in text:
        raise ValueError('Provider returned sensitive configuration')
    return {'id': 'community-page', 'url': url, 'text': text, 'retrieved_at': utcnow(), 'claim_status': 'unreviewed_candidate', 'provider': 'Bright Data'}
