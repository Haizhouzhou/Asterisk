"""Offline browser checks for the patient guide and research gallery."""
import json
import os
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen

import websocket

ROOT = Path(__file__).resolve().parents[1]


def main():
    browser = os.environ.get('ATLAS_TEST_BROWSER', 'C:/Program Files/Google/Chrome/Application/chrome.exe')
    process = subprocess.Popen(
        [browser, '--headless=new', '--disable-gpu', '--no-first-run',
         '--remote-debugging-port=9230', '--remote-allow-origins=http://localhost:9230',
         '--user-data-dir=' + str(ROOT / 'data' / 'people-ui-profile'), 'about:blank'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW)
    ws = None
    errors = []
    try:
        for _ in range(40):
            try:
                targets = json.loads(urlopen('http://127.0.0.1:9230/json', timeout=.5).read())
                target = next(t for t in targets if t['type'] == 'page')
                break
            except Exception:
                time.sleep(.2)
        else:
            raise RuntimeError('Browser did not start')
        ws = websocket.create_connection(target['webSocketDebuggerUrl'], origin='http://localhost:9230', timeout=20)
        counter = 0

        def command(method, params=None):
            nonlocal counter
            counter += 1
            ws.send(json.dumps(dict(id=counter, method=method, params=params or {})))
            while True:
                result = json.loads(ws.recv())
                if result.get('method') == 'Runtime.exceptionThrown':
                    errors.append(result['params'])
                if result.get('id') == counter:
                    if 'error' in result:
                        raise RuntimeError(result['error'])
                    return result.get('result', {})

        def js(expression):
            result = command('Runtime.evaluate', dict(expression=expression, returnByValue=True, awaitPromise=True))
            if result.get('exceptionDetails'):
                raise RuntimeError(result['exceptionDetails'])
            return result.get('result', {}).get('value')

        command('Page.enable')
        command('Runtime.enable')
        command('Emulation.setDeviceMetricsOverride', dict(width=1440, height=1100, deviceScaleFactor=1, mobile=False))
        command('Page.navigate', dict(url=os.environ.get('ATLAS_UI_URL', 'http://127.0.0.1:8017')))
        for _ in range(70):
            if js("document.querySelectorAll('.research-tile').length > 0"):
                break
            time.sleep(.2)
        else:
            raise AssertionError({'message':'Research gallery did not load', 'errors':errors, 'page':js("document.body.innerText.slice(-1800)"), 'leads':js("document.querySelector('#research-results')?.innerHTML")})
        js("document.querySelector('#language').value='en';document.querySelector('#language').dispatchEvent(new Event('change'))")
        count = js("document.querySelectorAll('#research-results .research-tile').length")
        assert count == 3, count
        assert js("document.querySelectorAll('#community-results .research-tile').length === Math.min(3,outreachLeads.communities.length)")
        assert js("document.querySelector('.research-tile-toggle').textContent.trim() === outreachLeads.communities[0].label")
        assert js("document.querySelectorAll('.research-hover .criterion-track').length === document.querySelectorAll('.research-tile').length*4")
        assert js("getComputedStyle(document.querySelector('.research-hover')).opacity === '0'")
        assert js("new Set([...document.querySelectorAll('.research-hover')].map(n=>n.id)).size===document.querySelectorAll('.research-hover').length")
        assert js("document.querySelector('.featured .research-art').offsetHeight > document.querySelectorAll('.research-art')[1].offsetHeight")
        assert js("!document.querySelector('.locale-note') && document.querySelector('.ai-jump').hash === '#ai-guide'")
        assert js("document.querySelector('#review-output').textContent.includes('patients, families')")
        assert js("document.querySelector('#cluster-list').textContent.includes('Symptoms in common')")
        js("document.querySelector('.research-tile').scrollIntoView({block:'center'})")
        point = js("(()=>{const r=document.querySelector('.research-tile').getBoundingClientRect();return {x:r.left+30,y:r.top+30}})()")
        command('Input.dispatchMouseEvent', dict(type='mouseMoved', **point))
        time.sleep(.3)
        assert js("getComputedStyle(document.querySelector('.research-hover')).visibility === 'visible'")
        command('Input.dispatchMouseEvent', dict(type='mouseMoved', x=0, y=0))
        js("document.querySelector('.research-tile-toggle').click()")
        assert js("document.querySelector('.research-tile').classList.contains('is-open')")
        js("document.querySelector('.research-tile-toggle').click()")
        js("document.querySelector('.research-tile-toggle').focus()")
        assert js("getComputedStyle(document.querySelector('.research-hover')).visibility === 'visible'")
        js("document.querySelector('#community-results .find-more').click()")
        assert js("document.querySelector('#research-dialog').open && document.querySelectorAll('#research-list .lead-card').length === outreachLeads.communities.length")
        js("document.querySelector('#research-close').click()")
        js("document.querySelector('#research-results .find-more').click()")
        assert js("document.querySelector('#research-dialog').open && document.querySelectorAll('#research-list .lead-card').length === outreachLeads.research.length")
        command('Input.dispatchKeyEvent', dict(type='keyDown', key='Escape', code='Escape', windowsVirtualKeyCode=27))
        command('Input.dispatchKeyEvent', dict(type='keyUp', key='Escape', code='Escape', windowsVirtualKeyCode=27))
        assert js("!document.querySelector('#research-dialog').open")
        js("document.querySelector('#language').value='zh-CN';document.querySelector('#language').dispatchEvent(new Event('change'))")
        assert js("document.querySelector('#cluster-list').textContent.includes('\u5171\u540c\u75c7\u72b6')")
        assert js("document.querySelector('#review').textContent.includes('\u5e2e\u6211\u8bfb\u61c2')")
        assert js("document.querySelector('.find-more').textContent.includes('\u67e5\u770b\u66f4\u591a')")
        for width in (390, 700, 1440):
            command('Emulation.setDeviceMetricsOverride', dict(width=width, height=900, deviceScaleFactor=1, mobile=width < 700))
            assert not js('document.body.scrollWidth > innerWidth'), width
        # Simulate a broken image and a search with fewer results without public APIs.
        js("outreachLeads.research[0].image='/missing-photo.png';outreachLeads.research=outreachLeads.research.slice(0,2);renderLeads()")
        time.sleep(.2)
        assert js("document.querySelectorAll('#research-results .research-tile').length===2 && document.querySelector('#research-results .research-art img').hidden")
        js("outreachLeads.research=[];renderLeads()")
        assert js("!document.querySelector('#research-results .research-tile') && Boolean(document.querySelector('#research-results .empty'))")
        assert not errors, errors
        print(json.dumps(dict(status='passed', checks=['top three and featured size', 'patient guide and anchor', 'category labels', 'hover, click and keyboard detail layer', 'full list and Escape', 'Chinese translations', 'responsive overflow', 'missing photo fallback', 'two and zero results', 'no JavaScript exceptions'])))
    finally:
        if ws:
            ws.close()
        process.terminate()
        process.wait(timeout=10)


if __name__ == '__main__':
    main()
