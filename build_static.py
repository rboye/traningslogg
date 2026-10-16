#!/usr/bin/env python3
"""Bygger den statiska PWA-versionen av Träningslogg (för GitHub Pages) från Index.html.

Index.html är källan för båda varianterna: inuti Apps Script fylls <?!= … ?> i av mallen och
google.script.run används; här fylls värdena i av det här skriptet och klienten pratar JSON med doPost.

Kör:  python3 build_static.py   → skriver till ./site/
"""
import hashlib, json, os, re, shutil
from PIL import Image, ImageDraw

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Index.html')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'site')
APP_URL = 'https://script.google.com/macros/s/AKfycbxHM0BTXQ8NV3Wojjlg5zHgx9xjeBfTpukpjigthGf6XCKpVJgee8BMuyVjKwKadsQq/exec'

HEAD_EXTRA = '''<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="Träning">
<meta name="theme-color" content="#f2f3f6" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0f1115" media="(prefers-color-scheme: dark)">
<meta name="robots" content="noindex, nofollow">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="192x192" href="icon-192.png">'''

SW_REG = '''<script>
// Service worker: appens filer cachas i telefonen så att den öppnas direkt (även offline); uppdateringar hämtas i bakgrunden.
if ('serviceWorker' in navigator) window.addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(() => {}));
</script>
'''

SW_JS = '''// Träningslogg – service worker. Appens egna filer serveras från cache och uppdateras i bakgrunden (stale-while-revalidate).
// Anrop till Apps Script (annan domän) rörs inte. Versionen byts av build_static.py när index.html ändras.
const VERSION = '__VERSION__';
const CACHE = 'traningslogg-' + VERSION;
const FILES = ['./', './index.html', './manifest.webmanifest', './icon-192.png', './icon-512.png', './apple-touch-icon.png'];
self.addEventListener('install', (e) => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES)).then(() => self.skipWaiting())); });
self.addEventListener('activate', (e) => { e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== self.location.origin) return;
  const key = e.request.mode === 'navigate' ? './index.html' : e.request;
  e.respondWith(caches.open(CACHE).then(async (c) => {
    const cached = await c.match(key);
    const fresh = fetch(e.request).then(res => { if (res && res.ok) c.put(key, res.clone()); return res; }).catch(() => null);
    return cached || (await fresh) || new Response('Offline', { status: 503 });
  }));
});
'''

MANIFEST = {
    "name": "Träningslogg",
    "short_name": "Träning",
    "display": "standalone",
    "background_color": "#f2f3f6",
    "theme_color": "#0a7d4f",
    "lang": "sv",
    "icons": [
        {"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"},
    ],
}


def make_icon(size, path):
    """Grön ikon med en vit hantel – samma grön som appens accentfärg."""
    im = Image.new('RGBA', (size, size), (10, 125, 79, 255))
    d = ImageDraw.Draw(im)
    s = size / 100.0
    white = (255, 255, 255, 255)
    # stång
    d.rounded_rectangle([18 * s, 46 * s, 82 * s, 54 * s], radius=4 * s, fill=white)
    # inre vikter
    d.rounded_rectangle([22 * s, 32 * s, 32 * s, 68 * s], radius=4 * s, fill=white)
    d.rounded_rectangle([68 * s, 32 * s, 78 * s, 68 * s], radius=4 * s, fill=white)
    # yttre vikter
    d.rounded_rectangle([12 * s, 38 * s, 19 * s, 62 * s], radius=3 * s, fill=white)
    d.rounded_rectangle([81 * s, 38 * s, 88 * s, 62 * s], radius=3 * s, fill=white)
    im.save(path)


def main():
    html = open(SRC, encoding='utf-8').read()
    assert html.count("'<?!= pinFromUrl ?>'") == 1 and html.count("'<?!= appUrl ?>'") == 1 and html.count("'<?!= sheetUrl ?>'") == 1
    html = html.replace("'<?!= pinFromUrl ?>'", "''").replace("'<?!= appUrl ?>'", "'" + APP_URL + "'").replace("'<?!= sheetUrl ?>'", "''")
    assert '<?!=' not in html
    # Samma viewport som Apps Script lägger till (maximum-scale=1 hindrar zoom vid inmatning i iOS)
    html = html.replace('<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
                        '<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover">', 1)
    html = html.replace('<title>Träningslogg</title>', '<title>Träningslogg</title>\n' + HEAD_EXTRA, 1)
    assert html.count('</body>') == 1
    html = html.replace('</body>', SW_REG + '</body>')

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(html)
    version = hashlib.sha1(html.encode('utf-8')).hexdigest()[:10]
    open(os.path.join(OUT, 'sw.js'), 'w', encoding='utf-8').write(SW_JS.replace('__VERSION__', version))
    open(os.path.join(OUT, 'manifest.webmanifest'), 'w', encoding='utf-8').write(json.dumps(MANIFEST, ensure_ascii=False, indent=2) + '\n')
    make_icon(192, os.path.join(OUT, 'icon-192.png'))
    make_icon(512, os.path.join(OUT, 'icon-512.png'))
    make_icon(180, os.path.join(OUT, 'apple-touch-icon.png'))
    open(os.path.join(OUT, '.nojekyll'), 'w').close()
    print('Byggt till', OUT, '– version', version)


if __name__ == '__main__':
    main()
