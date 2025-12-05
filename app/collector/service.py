import os
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import re
import importlib
import json
from ..extensions import db
from ..models import Crawler, CrawlerSource
from urllib.parse import urlparse, parse_qs, urlencode

DEFAULT_HEADERS = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'cache-control': 'max-age=0',
    'connection': 'keep-alive',
    'sec-ch-ua': '"Chromium";v="142", "Microsoft Edge";v="142", "Not_A Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'none',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0'
}

def _headers_with_cookie():
    headers = DEFAULT_HEADERS.copy()
    cookie = os.getenv('BAIDU_COOKIE')
    if cookie:
        headers['cookie'] = cookie
    return headers

def _extract_source(container: BeautifulSoup) -> str:
    # try multiple specific selectors
    for sel in ['.news-source', '.c-author', 'span.c-author', 'p.c-author', 'span.source', '.c-color-gray', '.c-color-gray2']:
        el = container.select_one(sel)
        if el and el.get_text(strip=True):
            text = el.get_text(' ', strip=True)
            # normalize using regex to capture source name before time separators
            m = re.search(r'([\u4e00-\u9fa5A-Za-z0-9_·\-]+)(?:\s*[·|]\s*|\s+)(?:\d{1,2}-\d{1,2}|\d{4}年\d{1,2}月\d{1,2}日|\d{2}:\d{2})', text)
            if m:
                return m.group(1).replace('·', '').strip()
            return text
    # fallback: scan text blocks
    text = container.get_text(' ', strip=True)
    m = re.search(r'来源[:：]\s*([\u4e00-\u9fa5A-Za-z0-9_·\-]+)', text)
    if m:
        return m.group(1).replace('·', '').strip()
    return ''

def fetch_baidu_news(keyword: str, limit: int = 20, pn: int = 0):
    base = 'https://www.baidu.com/s'
    items = []
    seen = set()
    offset = max(0, int(pn or 0))
    pages = 0
    while len(items) < limit and pages < 10:
        params = f'rtt=1&bsst=1&cl=2&tn=news&rsv_dl=ns_pc&word={quote(keyword)}&pn={offset}'
        url = f'{base}?{params}'
        resp = requests.get(url, headers=_headers_with_cookie(), timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'lxml')
        candidates = soup.select('div.result, div.news, div.new-pmd, div.result-op, div.c-container, article')
        for c in candidates:
            a = c.find('a', href=True)
            if not a:
                continue
            title = a.get_text(strip=True)
            href = a['href']
            if href in seen:
                continue
            img = c.find('img')
            cover = None
            if img:
                cover = img.get('src') or img.get('data-src') or img.get('data-thumb')
            source = _extract_source(c)
            items.append({
                'title': title,
                'cover': cover,
                'url': href,
                'source': source,
            })
            seen.add(href)
            if len(items) >= limit:
                break
        offset += 10
        pages += 1
    return items

def fetch_xinhua_sichuan(keyword: str | None = None, limit: int = 20):
    base = 'https://sc.news.cn/'
    url = urljoin(base, 'scyw.htm')
    resp = requests.get(url, headers=_headers_with_cookie(), timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'lxml')
    items = []
    seen = set()
    containers = soup.select('.news, .newslist, .list, .content, .con, .data, .dataList, .index-data, .xh-list, ul, section') or [soup]
    for ct in containers:
        for a in ct.select('a[href]'):
            href = a.get('href')
            if not href:
                continue
            full = href
            if href.startswith('//'):
                full = 'https:' + href
            elif href.startswith('/'): 
                full = urljoin(base, href)
            elif not re.match(r'^https?://', href):
                full = urljoin(base, href)
            if full in seen:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 6:
                continue
            cover = None
            p = a.parent
            img = a.find('img') or (p.find('img') if p else None)
            if img is None and p and p.parent:
                img = p.parent.find('img')
            if img:
                c = img.get('src') or img.get('data-src') or img.get('data-original') or img.get('data-ori') or img.get('data-original-src')
                if c:
                    if c.startswith('//'):
                        cover = 'https:' + c
                    elif c.startswith('/'):
                        cover = urljoin(base, c)
                    elif not re.match(r'^https?://', c):
                        cover = urljoin(base, c)
                    else:
                        cover = c
            source = '新华网'
            item = {
                'title': title,
                'cover': cover,
                'url': full,
                'source': source,
            }
            if keyword:
                if keyword in title:
                    items.append(item)
            else:
                items.append(item)
            seen.add(full)
            if len(items) >= limit:
                break
        if len(items) >= limit:
            break
    return items

def _resolve_callable(entry: str):
    if not entry or ':' not in entry:
        raise ValueError('invalid entry format, expected module:func')
    mod, func = entry.split(':', 1)
    module = importlib.import_module(mod)
    return getattr(module, func)

def run_crawler_by_entry(entry: str, params: dict):
    fn = _resolve_callable(entry)
    if not isinstance(params, dict):
        params = {}
    return fn(**{k: v for k, v in params.items() if v is not None})

def _resolve_class(entry: str):
    if not entry or ':' not in entry:
        raise ValueError('invalid class format, expected module:Class')
    mod, cls = entry.split(':', 1)
    module = importlib.import_module(mod)
    return getattr(module, cls)

def run_crawler_by_class(class_path: str, base_url: str | None, headers: dict | None, params: dict | None):
    Cls = _resolve_class(class_path)
    inst = None
    try:
        inst = Cls(base_url=base_url, headers=headers)
    except Exception:
        inst = Cls()
    if hasattr(inst, 'run'):
        return inst.run(params or {})
    if hasattr(inst, 'fetch'):
        return inst.fetch(params or {})
    raise ValueError('crawler class missing run/fetch')

def parse_raw_headers(raw: str) -> dict:
    lines = (raw or '').splitlines()
    hdrs = {}
    for ln in lines:
        ln = ln.strip()
        if not ln or ln.startswith(('GET ', 'POST ', 'PUT ', 'DELETE ', 'HTTP/')):
            continue
        if ':' in ln:
            k, v = ln.split(':', 1)
            k = k.strip().lower()
            v = v.strip()
            if k and v:
                hdrs[k] = v
    return hdrs

def analyze_crawler_from_request(source_url: str, headers_raw: str):
    if not source_url:
        raise ValueError('missing source_url')
    u = urlparse(source_url)
    base = f"{u.scheme}://{u.netloc}{u.path}"
    q = parse_qs(u.query)
    params = {k: (v[0] if isinstance(v, list) and v else '') for k, v in q.items()}
    headers = parse_raw_headers(headers_raw)
    name = u.netloc
    code = (u.netloc.replace('.', '_') + '_' + (u.path.strip('/').split('/')[0] or 'root')).lower()
    return {
        'name': name,
        'key': code,
        'code': code,
        'class_path': 'app.collector.service:GenericListCrawler',
        'base_url': base,
        'headers_json': headers,
        'params_json': params,
        'enabled': True,
    }

class GenericListCrawler:
    def __init__(self, base_url: str | None = None, headers: dict | None = None):
        self.base_url = base_url
        self.headers = headers or DEFAULT_HEADERS

    def _build_url(self, params: dict | None):
        if not self.base_url:
            raise ValueError('base_url missing')
        if params:
            return f"{self.base_url}?{urlencode(params)}"
        return self.base_url

    def _extract_items(self, soup: BeautifulSoup, limit: int = 20):
        items = []
        seen = set()
        candidates = soup.select('div.result, div.news, div.new-pmd, div.result-op, div.c-container, article, .news, .newslist, .list, .content, .con, .data, .dataList, .index-data, .xh-list, ul, section') or [soup]
        for c in candidates:
            for a in c.select('a[href]'):
                href = a.get('href')
                if not href or href in seen:
                    continue
                title = a.get_text(strip=True)
                if not title or len(title) < 6:
                    continue
                img = a.find('img') or c.find('img')
                cover = None
                if img:
                    cover = img.get('src') or img.get('data-src') or img.get('data-original') or img.get('data-thumb')
                items.append({'title': title, 'url': href, 'cover': cover})
                seen.add(href)
                if len(items) >= limit:
                    return items
        return items

    def run(self, params: dict | None = None):
        p = params or {}
        url = self._build_url(p)
        hdrs = dict(self.headers)
        resp = requests.get(url, headers=hdrs, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'lxml')
        items = self._extract_items(soup, limit=int(p.get('limit') or 20))
        return items

def run_crawler_by_code(code: str, params: dict):
    r = db.session.query(Crawler).filter_by(code=code, enabled=True).first()
    if not r:
        raise ValueError('crawler not found or disabled')
    cfg = None
    try:
        cfg = json.loads(r.config_json) if r.config_json else None
    except Exception:
        cfg = None
    hdr = None
    prm = None
    try:
        hdr = json.loads(r.headers_json) if r.headers_json else None
    except Exception:
        hdr = None
    try:
        prm = json.loads(r.params_json) if r.params_json else None
    except Exception:
        prm = None
    merged = {}
    if isinstance(cfg, dict):
        merged.update(cfg)
    if isinstance(params, dict):
        merged.update(params)
    if r.class_path:
        return run_crawler_by_class(r.class_path, r.base_url, hdr, merged if merged else prm)
    return run_crawler_by_entry(r.entry, merged)

def run_crawler_by_source(source: str, params: dict):
    m = db.session.query(CrawlerSource).filter_by(source=source, enabled=True).first()
    if not m:
        raise ValueError('no crawler mapped for source')
    r = db.session.get(Crawler, m.crawler_id)
    if not r or not r.enabled:
        raise ValueError('mapped crawler not available')
    cfg = None
    try:
        cfg = json.loads(r.config_json) if r.config_json else None
    except Exception:
        cfg = None
    hdr = None
    prm = None
    try:
        hdr = json.loads(r.headers_json) if r.headers_json else None
    except Exception:
        hdr = None
    try:
        prm = json.loads(r.params_json) if r.params_json else None
    except Exception:
        prm = None
    merged = {}
    if isinstance(cfg, dict):
        merged.update(cfg)
    if isinstance(params, dict):
        merged.update(params)
    if r.class_path:
        return run_crawler_by_class(r.class_path, r.base_url, hdr, merged if merged else prm)
    return run_crawler_by_entry(r.entry, merged)
