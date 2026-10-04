"""Prepare public Codex inputs or verify the generated artifact; no credentials."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from atlas.agent import evidence_packet, MODEL_SCHEMA, validate_model_review
from atlas.seed import build_dataset
from atlas.graph import filtered_graph
from atlas.codex_snapshot import DIRECTORY, load_review, packet_hash


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare', 'seal', 'verify'])
    args = parser.parse_args()
    packet = evidence_packet(filtered_graph(build_dataset(), 'MONDO:0012812', 'moderate', True))
    if args.command == 'prepare':
        DIRECTORY.mkdir(parents=True, exist_ok=True)
        for name, value in [('evidence.json', packet), ('schema.json', MODEL_SCHEMA)]:
            (DIRECTORY / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('Prepared public evidence and schema in data/codex')
    elif args.command == 'seal':
        review = json.loads((DIRECTORY / 'review.json').read_text(encoding='utf-8'))
        validate_model_review(review, {e['id'] for e in packet['edges']} | {s['id'] for s in packet['sources']})
        saved = json.loads((DIRECTORY / 'evidence.json').read_text(encoding='utf-8'))
        if saved != packet:
            raise ValueError('Prepare current evidence before generating output')
        manifest = {'producer': 'OpenAI Codex CLI', 'method': 'User-run Codex CLI output; structural and citation checks, not scientific validation',
                    'prompt': 'prompts/codex_review.md', 'audience': 'patient', 'language': 'en',
                    'evidence_sha256': packet_hash(packet), 'review_sha256': packet_hash(review)}
        (DIRECTORY / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        print('Sealed output. Record actual CLI execution and human review in your submission evidence.')
    else:
        saved = json.loads((DIRECTORY / 'evidence.json').read_text(encoding='utf-8'))
        if saved != packet:
            raise ValueError('Saved evidence differs from current starter dataset')
        load_review(packet)
        print('Verified packet binding, output checksum, structure and citation IDs. Scientific entailment still requires human review.')


if __name__ == '__main__':
    main()
