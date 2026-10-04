"""Retrieve public profile preview images from the reviewed directory only."""
import io
import json
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from atlas.communities import DIRECTORY, IMAGE_ROOT
from PIL import Image


class Preview(HTMLParser):
    def __init__(self):
        super().__init__()
        self.url = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta' and attrs.get('property', attrs.get('name')) == 'og:image':
            self.url = attrs.get('content')


def download(url):
    if urlparse(url).scheme != 'https':
        raise ValueError('HTTPS required')
    with urlopen(Request(url, headers={'User-Agent': 'atlas-backend/1.0'}), timeout=15) as response:
        body = response.read(5_000_001)
        if len(body) > 5_000_000:
            raise ValueError('Image or page too large')
        return body


def main():
    IMAGE_ROOT.mkdir(exist_ok=True)
    manifest = []
    for entry in DIRECTORY:
        try:
            parser = Preview()
            parser.feed(download(entry['website']).decode('utf-8', errors='replace'))
            if not parser.url:
                raise ValueError('No public preview image')
            url = urljoin(entry['website'], parser.url)
            image = Image.open(io.BytesIO(download(url)))
            image.thumbnail((480, 320))
            filename = entry['id'].replace(':', '-') + '.png'
            image.convert('RGB').save(IMAGE_ROOT / filename)
            manifest.append(dict(id=entry['id'], page=entry['website'], image_source=url, file=filename))
            print(entry['name'] + ': image saved')
        except Exception as exc:
            print(entry['name'] + ': unavailable (' + type(exc).__name__ + ')')
    (IMAGE_ROOT / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
