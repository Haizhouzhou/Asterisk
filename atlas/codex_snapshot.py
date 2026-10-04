"""Replay a reviewed artifact only against its exact evidence packet."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'data' / 'codex'


def packet_hash(packet):
    return hashlib.sha256(json.dumps(packet, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def load_review(packet):
    from atlas.agent import validate_model_review
    manifest = json.loads((DIRECTORY / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['evidence_sha256'] != packet_hash(packet):
        raise ValueError('Committed review does not match current evidence; regenerate it for this graph and filters')
    review = json.loads((DIRECTORY / 'review.json').read_text(encoding='utf-8'))
    if manifest['review_sha256'] != packet_hash(review):
        raise ValueError('Committed review checksum mismatch')
    allowed = {e['id'] for e in packet['edges']} | {s['id'] for s in packet['sources']}
    return validate_model_review(review, allowed)
