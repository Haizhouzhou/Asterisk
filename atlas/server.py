"""Local HTTP API and UI. Start with python -m atlas.server."""
import argparse
import json
import mimetypes
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from atlas.agent import analyze, proposal_markdown
from atlas.graph import coverage, filtered_graph
from atlas.providers import live_search
from atlas.seed import build_dataset
from atlas.store import Store
from atlas.live_graph import build_live_view, view_graph
from atlas.integrations import configuration, brightdata_page

ROOT = Path(__file__).resolve().parents[1]
FOCUS = 'MONDO:0012812'


class Application:
    def __init__(self, db=None):
        self.store = Store(db) if db else Store()
        self.store.seed(build_dataset())
        self.jobs = {}
        self.lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=2)

    def graph(self, data):
        min_confidence = data.get('min_confidence', 'moderate')
        if min_confidence not in ('low', 'moderate', 'high'):
            raise ValueError('min_confidence must be low, moderate, or high')
        inferred = data.get('include_inferred', True)
        if isinstance(inferred, str):
            inferred = inferred.lower() == 'true'
        elif not isinstance(inferred, bool):
            raise ValueError('include_inferred must be boolean')
        if data.get('graph_id'):
            view = self.store.graph_view(data['graph_id'])
            if not view:
                raise ValueError('Live graph not found')
            return view_graph(view, min_confidence, inferred)
        return filtered_graph(self.store.dataset(), data.get('focus', FOCUS), min_confidence, inferred)

    def live_graph(self, data):
        query = data.get('query', '')
        kind = data.get('kind', 'auto')
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 160:
            raise ValueError('Enter 1–160 characters')
        if kind not in ('auto', 'disease', 'gene', 'symptom'):
            raise ValueError('Invalid search kind')
        refresh = data.get('refresh', False)
        if not isinstance(refresh, bool):
            raise ValueError('refresh must be boolean')
        live = live_search(query.strip(), kind, refresh=refresh)
        view = build_live_view(live, data.get('identity_id'))
        self.store.save_graph_view(view)
        return self.graph({**data, 'graph_id': view['id']})

    def start_job(self, data):
        role = data.get('role', 'maria')
        if role != 'maria':
            raise ValueError('Only Maria is supported in this demo')
        for key in ('use_live', 'use_openai', 'use_agent', 'use_brightdata'):
            if key in data and not isinstance(data[key], bool):
                raise ValueError(key + ' must be boolean')
        graph = self.graph(data)
        id = str(uuid.uuid4())
        with self.lock:
            if sum(job['status'] in ('queued', 'running') for job in self.jobs.values()) >= 4:
                raise ValueError('Analysis queue is full; please wait for an existing run')
            self.jobs[id] = {'id': id, 'status': 'queued', 'stage': 'filter', 'report_id': None}

        def update(stage):
            with self.lock:
                self.jobs[id]['stage'] = stage

        def run():
            with self.lock:
                self.jobs[id]['status'] = 'running'
            try:
                live = graph.get('live')
                if data.get('use_live', False):
                    update('retrieve')
                    focus_node = next(n for n in graph['nodes'] if n['id'] == graph['focus'])
                    query = graph.get('live', {}).get('query') or focus_node.get('gene') or focus_node['label']
                    live = live_search(query, focus_node['kind'] if focus_node['kind'] in ('gene', 'disease', 'symptom') else 'auto')
                if data.get('use_brightdata', False):
                    update('retrieve')
                    if not live:
                        live = {'papers': [], 'studies': [], 'providers': []}
                    live['community_candidates'] = [brightdata_page(data.get('community_url', ''))]
                report = analyze(graph, live, data.get('use_agent', data.get('use_openai', False)), update)
                report['export'] = proposal_markdown(report, graph)
                self.store.save_report(report)
                with self.lock:
                    self.jobs[id].update(status='complete', report_id=report['id'])
            except Exception as exc:
                with self.lock:
                    self.jobs[id].update(status='failed', error='Analysis failed (' + type(exc).__name__ + '). Please retry.')
        self.pool.submit(run)
        return dict(self.jobs[id])


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def send(self, status, body, content_type='application/json; charset=utf-8', extra=None):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode()
            elif isinstance(body, str):
                body = body.encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            try:
                path = parsed.path
                if path == '/api/health':
                    return self.send(200, {'status': 'ok', 'role': 'maria', 'openai_configured': bool(os.environ.get('OPENAI_API_KEY')), 'agent': configuration(), 'database': 'SQLite'})
                if path == '/api/coverage':
                    return self.send(200, coverage())
                if path == '/api/graph':
                    return self.send(200, app.graph(params))
                if path == '/api/search':
                    q = params.get('q', '').strip()
                    if not 1 <= len(q) <= 160:
                        raise ValueError('Enter 1–160 characters')
                    kind = params.get('kind', 'auto')
                    if kind not in ('auto', 'disease', 'gene', 'symptom', 'organization', 'mechanism', 'asset', 'paper', 'study', 'researcher', 'institution'):
                        raise ValueError('Unknown search kind')
                    matches = app.store.search(q, None if kind == 'auto' else kind)
                    return self.send(200, {'query': q, 'matches': matches, 'auto_focus': matches[0]['id'] if len(matches) == 1 else None,
                                           'ambiguous': len(matches) > 1, 'coverage': coverage()['scope'],
                                           'message': 'Choose the intended identity.' if len(matches) > 1 else ('No curated match. Search public sources to inspect candidates; no supported graph route is established.' if not matches else 'Resolved to a stable graph node.')})
                if path.startswith('/api/jobs/'):
                    with app.lock:
                        job = app.jobs.get(path.split('/')[-1])
                        job = dict(job) if job else None
                    return self.send(200 if job else 404, job or {'error': 'Job not found; reports persist but jobs reset when the server restarts.'})
                if path.startswith('/api/reports/'):
                    parts = path.split('/')
                    report = app.store.report(parts[3])
                    if not report:
                        return self.send(404, {'error': 'Report not found'})
                    if len(parts) == 5 and parts[4] == 'proposal':
                        return self.send(200, report['export'], 'text/markdown; charset=utf-8', {'Content-Disposition': 'attachment; filename="research-proposal.md"'})
                    return self.send(200, report)
                static = {'/': 'index.html', '/app.js': 'app.js', '/styles.css': 'styles.css', '/favicon.svg': 'favicon.svg'}
                if path in static:
                    file = ROOT / 'web' / static[path]
                    return self.send(200, file.read_bytes(), (mimetypes.guess_type(str(file))[0] or 'application/octet-stream') + '; charset=utf-8')
                return self.send(404, {'error': 'Not found'})
            except ValueError as exc:
                return self.send(400, {'error': str(exc)})
            except Exception:
                return self.send(500, {'error': 'Unable to load this resource. Please retry.'})

        def do_POST(self):
            origin = self.headers.get('Origin')
            if origin and origin not in ('http://' + self.headers.get('Host', ''), 'https://' + self.headers.get('Host', '')):
                return self.send(403, {'error': 'Cross-origin requests are not allowed'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 16384:
                    return self.send(413, {'error': 'Request body must be 1–16384 bytes'})
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('Expected a JSON object')
                if self.path == '/api/analysis':
                    return self.send(202, app.start_job(data))
                if self.path == '/api/live-graph':
                    return self.send(200, app.live_graph(data))
                if self.path == '/api/live-search':
                    q = data.get('query', '')
                    if not isinstance(q, str) or not 1 <= len(q.strip()) <= 160:
                        raise ValueError('Enter 1–160 characters')
                    kind = data.get('kind', 'auto')
                    if kind not in ('auto', 'disease', 'gene', 'symptom'):
                        raise ValueError('kind must be auto, disease, gene, or symptom')
                    preprints = data.get('include_preprints', False)
                    if not isinstance(preprints, bool):
                        raise ValueError('include_preprints must be boolean')
                    return self.send(200, live_search(q.strip(), kind, preprints))
                return self.send(404, {'error': 'Not found'})
            except (ValueError, TypeError) as exc:
                return self.send(400, {'error': str(exc)})
            except Exception:
                return self.send(500, {'error': 'Unable to complete this request. Please retry.'})

        def log_message(self, format, *args):
            # Keep queries, source text and credentials out of access logs.
            pass
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=int(os.environ.get('ATLAS_PORT', '8000')))
    parser.add_argument('--db', default=None)
    args = parser.parse_args()
    app = Application(args.db)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(app))
    print('Raraction is ready at http://' + args.host + ':' + str(args.port), flush=True)
    print('Maria demo · SQLite · ' + ('OpenAI configured' if os.environ.get('OPENAI_API_KEY') else 'evidence checks; OpenAI not configured'), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        app.pool.shutdown(wait=False, cancel_futures=True)


if __name__ == '__main__':
    main()
