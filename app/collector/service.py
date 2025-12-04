import os
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup
import re

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
            summary = ''
            summ_el = c.select_one('.c-span-last, .content, .c-summary, .news-summary, p')
            if summ_el:
                summary = summ_el.get_text(' ', strip=True)
            img = c.find('img')
            cover = None
            if img:
                cover = img.get('src') or img.get('data-src') or img.get('data-thumb')
            source = _extract_source(c)
            items.append({
                'title': title,
                'summary': summary,
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
