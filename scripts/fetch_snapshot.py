"""Download bounded public records used to reproduce the demo. No API keys needed."""
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    out = ROOT / 'data' / 'snapshots'
    out.mkdir(parents=True, exist_ok=True)
    base = 'https://www.ebi.ac.uk/ols4/api/search?'
    requests = {
        'mondo_stxbp1': base + urlencode({'q': 'developmental and epileptic encephalopathy 4', 'ontology': 'mondo', 'rows': 6}),
        'mondo_slc6a1': base + urlencode({'q': 'myoclonic-atonic epilepsy', 'ontology': 'mondo', 'rows': 6}),
        'hpo_seizure': base + urlencode({'q': 'Seizure', 'ontology': 'hp', 'exact': 'true', 'rows': 3}),
        'trial': 'https://clinicaltrials.gov/api/v2/studies/NCT04937062',
        'papers_stxbp1': 'https://www.ebi.ac.uk/europepmc/webservices/rest/search?' + urlencode({'query': 'EXT_ID:26865513 OR EXT_ID:38137001', 'format': 'json', 'resultType': 'core', 'pageSize': 10}),
        'papers_slc6a1': 'https://www.ebi.ac.uk/europepmc/webservices/rest/search?' + urlencode({'query': 'TITLE:"Current knowledge of SLC6A1" OR TITLE:"Haploinsufficiency underlies the neurodevelopmental consequences of SLC6A1 variants"', 'format': 'json', 'resultType': 'core', 'pageSize': 10}),
        'reactome_stxbp1': 'https://reactome.org/ContentService/data/mapping/NCBI/6812/pathways?species=9606',
        'reactome_slc6a1': 'https://reactome.org/ContentService/data/mapping/NCBI/6529/pathways?species=9606',
    }
    manifest = {}
    for name, url in requests.items():
        try:
            with urlopen(Request(url, headers={'User-Agent': 'Raraction-demo/0.1'}), timeout=30) as response:
                raw = response.read(4_000_001)
                if len(raw) > 4_000_000:
                    raise ValueError('record too large')
                payload = json.loads(raw)
            stored = json.dumps(payload, indent=2, ensure_ascii=False).encode('utf-8')
            (out / (name + '.json')).write_bytes(stored)
            manifest[name] = {'url': url, 'retrieved_at': datetime.now(timezone.utc).isoformat(), 'sha256': hashlib.sha256(stored).hexdigest(), 'status': 'downloaded'}
            print(name, 'OK')
        except Exception as exc:
            manifest[name] = {'url': url, 'status': 'unavailable', 'error_type': type(exc).__name__}
            print(name, 'unavailable:', type(exc).__name__)
        time.sleep(0.4)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Snapshot complete. Curated relationships are separate from imported records.')


if __name__ == '__main__':
    main()
