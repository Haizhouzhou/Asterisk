"""Optional UI QA using an installed Chromium browser and websocket-client.

These tools are already present in the development machine's Conda base.
They are not dependencies of the application.
"""
import base64
import json
import os
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen
import websocket
import argparse

ROOT = Path(__file__).resolve().parents[1]
BROWSER = Path(os.environ.get('ATLAS_TEST_BROWSER', 'C:/Program Files/Google/Chrome/Application/chrome.exe'))
OUT = ROOT / 'data' / 'qa'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen([str(BROWSER), '--headless=new', '--disable-gpu', '--no-first-run',
                                '--remote-debugging-port=9229', '--remote-allow-origins=http://localhost:9229',
                                '--user-data-dir=' + str(ROOT / 'data' / 'browser-profile'), 'about:blank'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    ws = None
    errors = []
    try:
        target = None
        for _ in range(30):
            try:
                targets = json.loads(urlopen('http://127.0.0.1:9229/json', timeout=.5).read())
                target = next((t for t in targets if t['type'] == 'page'), None)
                if target:
                    break
            except Exception:
                pass
            time.sleep(.2)
        if not target:
            raise RuntimeError('Installed Chromium did not expose a headless page')
        ws = websocket.create_connection(target['webSocketDebuggerUrl'], origin='http://localhost:9229', timeout=20)
        counter = 0

        def command(method, params=None):
            nonlocal counter
            counter += 1
            id = counter
            ws.send(json.dumps({'id': id, 'method': method, 'params': params or {}}))
            while True:
                message = json.loads(ws.recv())
                if message.get('method') == 'Runtime.exceptionThrown':
                    errors.append(message['params'])
                if message.get('method') == 'Log.entryAdded' and message['params']['entry'].get('level') == 'error':
                    errors.append(message['params'])
                if message.get('id') == id:
                    if 'error' in message:
                        raise RuntimeError(message['error'])
                    return message.get('result', {})

        def js(expression):
            result = command('Runtime.evaluate', {'expression': expression, 'returnByValue': True, 'awaitPromise': True})
            if result.get('exceptionDetails'):
                raise RuntimeError(result['exceptionDetails'])
            return result.get('result', {}).get('value')

        def wait(expression):
            for _ in range(60):
                if js(expression):
                    return
                time.sleep(.2)
            raise AssertionError('Timed out: ' + expression)

        def screenshot(name):
            shot = command('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False})
            (OUT / (name + '.png')).write_bytes(base64.b64decode(shot['data']))

        command('Page.enable')
        command('Runtime.enable')
        command('Log.enable')
        command('Emulation.setDeviceMetricsOverride', {'width': 1440, 'height': 1100, 'deviceScaleFactor': 1, 'mobile': False})
        command('Page.navigate', {'url': args.url})
        wait("document.querySelectorAll('#graph .node').length > 10")
        initial = js("({nodes:document.querySelectorAll('#graph .node').length,edges:document.querySelectorAll('#graph .edge-group').length,overflow:document.body.scrollWidth>innerWidth})")
        assert not initial['overflow'], initial
        js("document.querySelector('#language').value='zh-CN';document.querySelector('#language').dispatchEvent(new Event('change'))")
        assert js("document.documentElement.lang==='zh-CN' && document.querySelector('h1').textContent==='下一步研究可以走向哪里？'")
        assert js("document.querySelector('#search').placeholder==='搜索疾病、基因或症状…'")
        js("document.querySelector('#progress').textContent='Reviewing…'")
        time.sleep(.1)
        assert js("document.querySelector('#progress').textContent==='正在审核…'")
        js("document.querySelector('#language').value='en';document.querySelector('#language').dispatchEvent(new Event('change'))")
        assert js("document.querySelector('h1').textContent==='Where could your research go next?'")
        screenshot('desktop-network')
        js("document.querySelector('[data-edge=\"research-bridge\"]').dispatchEvent(new MouseEvent('click',{bubbles:true}))")
        assert js("document.querySelector('#details').textContent.includes('Research hypothesis')")
        js("document.querySelector('#hypotheses').click()")
        wait("document.querySelectorAll('.edge-line.inferred').length === 0")
        assert js("!!document.querySelector('[data-edge=\"mechanism-counterexample\"]')")
        js("document.querySelector('#hypotheses').click()")
        wait("document.querySelectorAll('.edge-line.inferred').length > 0")
        js("search('Gaucher disease')")
        wait("document.querySelector('#identity').textContent.includes('MONDO:0018150')")
        assert js("state.graph.graph_id && state.graph.nodes.some(n=>n.kind==='paper')")
        gaucher_id=js('state.graph.graph_id')
        screenshot('live-gaucher')
        js("search('Fabry disease')")
        wait("state.graph.live && state.graph.live.query==='Fabry disease'")
        assert js('state.graph.graph_id') != gaucher_id
        assert not js("document.querySelector('#graph').textContent.includes('STXBP1')")
        js("document.querySelector('#confidence').value='high'; document.querySelector('#confidence').dispatchEvent(new Event('change'))")
        wait("state.graph.filters.min_confidence==='high'")
        assert js("state.graph.live.query==='Fabry disease'")
        screenshot('live-fabry')
        js("document.querySelector('#confidence').value='moderate'")
        js("search('unknown-disease-9999')")
        wait("document.querySelector('#search-results').textContent.includes('No identity was resolved')")
        js("document.querySelector('#search-results').hidden=true; state.graph=null; loadGraph('MONDO:0012812')")
        wait("document.querySelector('#identity').textContent.includes('MONDO:0012812')")
        js("document.querySelector('#review').click()")
        wait("!!document.querySelector('.export')")
        assert js("document.querySelector('#details').textContent.includes('active not recruiting')")
        screenshot('desktop-actions')
        js("document.querySelector('#papers-tab').click()")
        assert js("document.querySelectorAll('#paper-list .paper-card').length >= 4")
        js("document.querySelector('#network-tab').click()")
        command('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': True})
        assert not js('document.body.scrollWidth > innerWidth'), 'Mobile horizontal overflow'
        screenshot('mobile-network')
        command('Emulation.setDeviceMetricsOverride', {'width': 1440, 'height': 1100, 'deviceScaleFactor': 1, 'mobile': False})
        js("document.querySelector('#coverage-open').click()")
        wait("document.querySelector('#coverage-dialog').open")
        assert js("document.querySelector('#coverage-content').textContent.includes('Illustrative planning hypothesis')")
        js("document.querySelector('#coverage-close').click()")
        assert not errors, errors
        result = {'status': 'passed', 'initial_graph': initial,
                  'checks': ['node and edge interaction', 'hypothesis filter preserves counterexample', 'live Gaucher graph', 'live Fabry graph isolation', 'live graph filters', 'unknown identity gap', 'review and proposal export', 'related paper view', 'mobile overflow', 'coverage dialog', 'no browser errors'],
                  'screenshots': ['desktop-network.png', 'desktop-actions.png', 'mobile-network.png','live-gaucher.png','live-fabry.png']}
        (OUT / 'browser-check.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result, indent=2))
    finally:
        if ws:
            ws.close()
        process.terminate()
        process.wait(timeout=10)


if __name__ == '__main__':
    main()
