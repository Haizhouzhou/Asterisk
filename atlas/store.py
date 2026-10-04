"""SQLite persistence; normalized provenance and evidence links."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / 'data' / 'atlas.sqlite'

SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS nodes (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, label TEXT NOT NULL, data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS aliases (
 alias TEXT NOT NULL, node_id TEXT NOT NULL REFERENCES nodes(id),
 PRIMARY KEY(alias, node_id)
);
CREATE TABLE IF NOT EXISTS sources (
 id TEXT PRIMARY KEY, data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS edges (
 id TEXT PRIMARY KEY, subject TEXT NOT NULL REFERENCES nodes(id),
 object TEXT NOT NULL REFERENCES nodes(id), relation TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('observed','inferred','disputed')), data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence (
 id TEXT PRIMARY KEY, edge_id TEXT NOT NULL REFERENCES edges(id),
 source_id TEXT NOT NULL REFERENCES sources(id), stance TEXT NOT NULL,
 data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL, data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS graph_views (
 id TEXT PRIMARY KEY, data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_edges_subject ON edges(subject);
CREATE INDEX IF NOT EXISTS idx_edges_object ON edges(object);
CREATE INDEX IF NOT EXISTS idx_evidence_edge ON evidence(edge_id);
'''


def normalize(value):
    import re
    return re.sub(r'[^a-z0-9]+', ' ', value.casefold()).strip()


class Store:
    def __init__(self, path=DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def seed(self, dataset):
        with self.connect() as db:
            for node in dataset['nodes']:
                db.execute('INSERT OR REPLACE INTO nodes VALUES (?,?,?,?)', (node['id'], node['kind'], node['label'], json.dumps(node)))
                for alias in [node['id'], node['label'], *node.get('aliases', [])]:
                    db.execute('INSERT OR IGNORE INTO aliases VALUES (?,?)', (normalize(alias), node['id']))
            for source in dataset['sources']:
                db.execute('INSERT OR REPLACE INTO sources VALUES (?,?)', (source['id'], json.dumps(source)))
            for edge in dataset['edges']:
                db.execute('INSERT OR REPLACE INTO edges VALUES (?,?,?,?,?,?)', (edge['id'], edge['subject'], edge['object'], edge['relation'], edge['status'], json.dumps(edge)))
                db.execute('DELETE FROM evidence WHERE edge_id=?', (edge['id'],))
                for i, ev in enumerate(edge['evidence']):
                    db.execute('INSERT INTO evidence VALUES (?,?,?,?,?)', (edge['id'] + ':' + str(i), edge['id'], ev['source_id'], ev['stance'], json.dumps(ev)))

    def dataset(self):
        with self.connect() as db:
            return {table: [json.loads(row['data']) for row in db.execute('SELECT data FROM ' + table)] for table in ('nodes', 'edges', 'sources')}

    def search(self, query, kind=None):
        q = normalize(query)
        if not q:
            return []
        # Escape SQL LIKE wildcards and use prepared parameters for user input.
        pattern = '%' + q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        with self.connect() as db:
            rows = db.execute('''SELECT n.data, a.alias FROM aliases a JOIN nodes n ON n.id=a.node_id
                WHERE a.alias LIKE ? ESCAPE '\\' ORDER BY CASE WHEN a.alias=? THEN 0 ELSE 1 END, n.label''', (pattern, q)).fetchall()
        matches = {}
        for row in rows:
            node = json.loads(row['data'])
            if kind and node['kind'] != kind:
                continue
            if node['id'] not in matches:
                matches[node['id']] = {**node, 'matched_alias': row['alias'], 'exact': row['alias'] == q}
        return list(matches.values())[:20]

    def save_report(self, report):
        with self.connect() as db:
            db.execute('INSERT INTO reports VALUES (?,?,?)', (report['id'], report['created_at'], json.dumps(report)))

    def report(self, report_id):
        with self.connect() as db:
            row = db.execute('SELECT data FROM reports WHERE id=?', (report_id,)).fetchone()
        return json.loads(row['data']) if row else None

    def save_graph_view(self, view):
        with self.connect() as db:
            db.execute('INSERT INTO graph_views VALUES (?,?)', (view['id'], json.dumps(view)))

    def graph_view(self, id):
        with self.connect() as db:
            row = db.execute('SELECT data FROM graph_views WHERE id=?', (id,)).fetchone()
        return json.loads(row['data']) if row else None
