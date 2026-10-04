"""Validate saved record hashes and report snapshot provider coverage."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'data' / 'snapshots'


def main():
    manifest = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))
    for name, entry in manifest.items():
        if entry['status'] == 'downloaded':
            path = ROOT / (name + '.json')
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != entry['sha256']:
                raise ValueError('Snapshot hash mismatch: ' + name)
            json.loads(path.read_text(encoding='utf-8'))
            print(name + ': verified')
        else:
            print(name + ': unavailable (no inferred replacement)')


if __name__ == '__main__':
    main()
