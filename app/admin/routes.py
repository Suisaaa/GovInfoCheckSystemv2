from flask import render_template, request, redirect, url_for, jsonify
import json
from flask_login import login_required, current_user
from . import bp
from ..extensions import db
from ..models import User, Role, Setting, CollectionItem, CollectionDetail, CrawlRule, AIEngine, Crawler, CrawlerSource
from ..collector.service import _headers_with_cookie
from urllib.parse import urlparse
from lxml import html
import requests

def is_admin():
    return current_user.is_authenticated and current_user.role and current_user.role.name == 'admin'

@bp.before_request
def _check_admin():
    if not is_admin():
        return redirect(url_for('main.index'))

@bp.route('/')
@login_required
def index():
    return render_template('admin/index.html')

@bp.route('/users', methods=['GET', 'POST'])
@login_required
def users():
    roles = db.session.query(Role).all()
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role_id = request.form.get('role_id')
        if username and password and role_id:
            r = db.session.get(Role, int(role_id))
            u = User(username=username, role=r)
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
        return redirect(url_for('admin.users'))
    users = db.session.query(User).all()
    return render_template('admin/users.html', users=users, roles=roles)

@bp.route('/roles', methods=['GET', 'POST'])
@login_required
def roles():
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            db.session.add(Role(name=name))
            db.session.commit()
        return redirect(url_for('admin.roles'))
    roles = db.session.query(Role).all()
    return render_template('admin/roles.html', roles=roles)

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    s = db.session.query(Setting).first()
    if request.method == 'POST':
        app_name = request.form.get('app_name')
        logo_path = request.form.get('logo_path')
        if s is None:
            s = Setting(app_name=app_name or '', logo_path=logo_path)
            db.session.add(s)
        else:
            s.app_name = app_name or s.app_name
            s.logo_path = logo_path or s.logo_path
        db.session.commit()
        return redirect(url_for('admin.settings'))
    return render_template('admin/settings.html', setting=s)

@bp.route('/collect', methods=['GET'])
@login_required
def collect_page():
    return render_template('admin/collect.html')

@bp.route('/collect/save', methods=['POST'])
@login_required
def collect_save():
    data = request.get_json(silent=True) or {}
    items = data.get('items') or []
    saved = 0
    for it in items:
        url = it.get('url')
        if not url:
            continue
        exists = db.session.query(CollectionItem).filter_by(url=url).first()
        if exists:
            exists.title = it.get('title') or exists.title
            exists.cover = it.get('cover') or exists.cover
            exists.source = it.get('source') or exists.source
            exists.keyword = it.get('keyword') or exists.keyword
        else:
            obj = CollectionItem(
                title=it.get('title') or '',
                cover=it.get('cover'),
                url=url,
                source=it.get('source'),
                keyword=it.get('keyword'),
            )
            db.session.add(obj)
        saved += 1
    db.session.commit()
    return {'saved': saved}

@bp.route('/collect/deep', methods=['POST'])
@login_required
def collect_deep():
    url = request.json.get('url')
    keyword = request.json.get('keyword')
    item = db.session.query(CollectionItem).filter_by(url=url).first()
    if item is None:
        item = CollectionItem(title=request.json.get('title') or '', cover=request.json.get('cover'), url=url, source=request.json.get('source'), keyword=keyword)
        db.session.add(item)
        db.session.commit()
    import requests
    from bs4 import BeautifulSoup
    try:
        r = requests.get(url, headers=_headers_with_cookie(), timeout=15)
        final_url = r.url
        soup = BeautifulSoup(r.text, 'lxml')
        for tag in soup(['script','style','noscript']):
            tag.extract()
        selectors = [
            'article',
            '.article',
            '.article-content',
            '#article',
            '.content',
            '#content',
            '.news-content',
            '.post-content',
            '.detail',
            '.wrap .content'
        ]
        best = None
        best_len = 0
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                txt = el.get_text('\n', strip=True)
                if len(txt) > best_len:
                    best = el
                    best_len = len(txt)
        if best is None:
            ps = soup.select('p')
            if ps:
                txt = '\n'.join([p.get_text(' ', strip=True) for p in ps])
            else:
                txt = soup.get_text('\n', strip=True)
        else:
            txt = best.get_text('\n', strip=True)
        if txt:
            txt = txt[:20000]
        det = CollectionDetail(item_id=item.id, content_text=txt, content_html=r.text, final_url=final_url)
        db.session.add(det)
        item.deep_status = True
        db.session.commit()
        preview = (txt or '')[:600]
        return jsonify({'status': 'ok', 'item_id': item.id, 'detail_id': det.id, 'preview': preview, 'final_url': final_url})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/warehouse', methods=['GET'])
@login_required
def warehouse_page():
    return render_template('admin/warehouse.html')

@bp.route('/warehouse/list', methods=['GET'])
@login_required
def warehouse_list():
    page = int(request.args.get('page') or 1)
    size = int(request.args.get('size') or 10)
    q = request.args.get('q') or ''
    query = db.session.query(CollectionItem)
    if q:
        like = f"%{q}%"
        query = query.filter((CollectionItem.title.ilike(like)) | (CollectionItem.source.ilike(like)))
    total = query.count()
    items = query.order_by(CollectionItem.created_at.desc()).offset((page-1)*size).limit(size).all()
    
    # Pre-fetch all enabled rules to avoid N+1
    all_rules = db.session.query(CrawlRule).filter_by(enabled=True).all()
    
    data = []
    for it in items:
        # Match rules logic
        matched_rules = []
        # 1. Match by source name
        if it.source:
            matched_rules.extend([r.name for r in all_rules if r.name == it.source])
        
        # 2. Match by site domain
        try:
            dom = urlparse(it.url).netloc
            if dom:
                matched_rules.extend([r.name or r.site for r in all_rules if r.site and r.site in dom])
        except Exception:
            pass
            
        # Deduplicate
        matched_rules = list(set(matched_rules))
        
        data.append({
            'id': it.id,
            'title': it.title,
            'cover': it.cover,
            'url': it.url,
            'source': it.source,
            'keyword': it.keyword,
            'deep_status': it.deep_status,
            'created_at': it.created_at.isoformat() if it.created_at else None,
            'matched_rules': matched_rules
        })
    return jsonify({'page': page, 'size': size, 'total': total, 'items': data})

@bp.route('/warehouse/update', methods=['POST'])
@login_required
def warehouse_update():
    data = request.get_json(silent=True) or {}
    id_ = data.get('id')
    if not id_:
        return jsonify({'error': 'missing id'}), 400
    it = db.session.get(CollectionItem, int(id_))
    if not it:
        return jsonify({'error': 'not found'}), 404
    title = data.get('title'); source = data.get('source'); cover = data.get('cover'); keyword = data.get('keyword'); deep_status = data.get('deep_status')
    if title is not None:
        it.title = title
    if source is not None:
        it.source = source
    if cover is not None:
        it.cover = cover
    if keyword is not None:
        it.keyword = keyword
    if deep_status is not None:
        it.deep_status = bool(deep_status)
    db.session.commit()
    return jsonify({'status': 'ok'})

@bp.route('/warehouse/collect_dynamic', methods=['POST'])
@login_required
def warehouse_collect_dynamic():
    data = request.get_json(silent=True) or {}
    keyword = (data.get('keyword') or '').strip()
    source = (data.get('source') or '').strip()
    try:
        from ..collector.service import run_crawler_by_source
        items = run_crawler_by_source(source, {'keyword': keyword, 'limit': int(data.get('limit') or 20)})
        return jsonify({'status': 'ok', 'count': len(items), 'items': items})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/warehouse/delete', methods=['POST'])
@login_required
def warehouse_delete():
    data = request.get_json(silent=True) or {}
    ids = data.get('ids') or []
    id_ = data.get('id')
    if id_:
        ids.append(id_)
    ids = [int(i) for i in ids if i]
    if not ids:
        return jsonify({'error': 'missing ids'}), 400
    deleted = 0
    for i in ids:
        it = db.session.get(CollectionItem, i)
        if it:
            db.session.delete(it)
            deleted += 1
    db.session.commit()
    return jsonify({'status': 'ok', 'deleted': deleted})

@bp.route('/warehouse/analyze', methods=['POST'])
@login_required
def warehouse_analyze():
    data = request.get_json(silent=True) or {}
    ids = data.get('ids') or []
    return jsonify({'status': 'ok', 'message': 'AI解析入口预留', 'count': len(ids)})

@bp.route('/warehouse/deep_collect', methods=['POST'])
@login_required
def warehouse_deep_collect():
    data = request.get_json(silent=True) or {}
    ids = data.get('ids') or []
    id_ = data.get('id')
    if id_:
        ids.append(id_)
    ids = [int(i) for i in ids if i]
    results = []
    
    def find_rules(it):
        rules = []
        # 1. Match by source name (Highest Priority)
        if it.source:
            # Exact match by name
            by_name = db.session.query(CrawlRule).filter(CrawlRule.name == it.source, CrawlRule.enabled == True).all()
            rules.extend(by_name)
            
        # 2. Match by site domain
        try:
            dom = urlparse(it.url).netloc
            if dom:
                # Domain contains site or site contains domain (flexible match)
                by_site = db.session.query(CrawlRule).filter(CrawlRule.enabled == True).filter(CrawlRule.site.ilike(f"%{dom}%")).all()
                for r in by_site:
                    if r not in rules:
                        rules.append(r)
                
                # Also try partial domain match if no exact match
                if not by_site:
                    parts = dom.split('.')
                    for j in range(len(parts)-2):
                        base = '.'.join(parts[j:])
                        sub_rules = db.session.query(CrawlRule).filter(CrawlRule.enabled == True).filter(CrawlRule.site.ilike(f"%{base}%")).all()
                        for r in sub_rules:
                            if r not in rules:
                                rules.append(r)
        except Exception:
            pass
            
        return rules

    import requests
    for i in ids:
        it = db.session.get(CollectionItem, i)
        if not it:
            continue
        
        # Find all applicable rules
        rules = find_rules(it)
        
        # If no rules found, use a dummy None rule to trigger default extraction
        if not rules:
            rules = [None]
            
        success = False
        for rule in rules:
            headers = _headers_with_cookie()
            if rule and rule.request_headers:
                try:
                    hdr = json.loads(rule.request_headers)
                    if isinstance(hdr, dict):
                        headers = hdr
                except Exception:
                    headers = headers
            try:
                r = requests.get(it.url, headers=headers, timeout=15)
                final_url = r.url
                doc = html.fromstring(r.text)
                title_text = None
                
                if rule and rule.title_xpath:
                    try:
                        ns = doc.xpath(rule.title_xpath)
                        if ns:
                            title_text = ' '.join([n.text_content().strip() for n in ns]).strip()
                    except Exception:
                        title_text = None
                
                if not title_text:
                    ns = doc.xpath('//h1')
                    if ns:
                        title_text = ' '.join([n.text_content().strip() for n in ns]).strip()
                    
                content_text = None
                if rule and rule.content_xpath:
                    try:
                        ns = doc.xpath(rule.content_xpath)
                        if ns:
                            content_text = ' '.join([n.text_content().strip() for n in ns]).strip()
                    except Exception:
                        content_text = None
                
                if not content_text:
                    ns = doc.xpath('//article')
                    if ns:
                        content_text = ' '.join([n.text_content().strip() for n in ns]).strip()
                    if not content_text:
                        ps = doc.xpath('//p')
                        if ps:
                            content_text = '\n'.join([p.text_content().strip() for p in ps if p.text_content().strip()])
                
                if content_text:
                    content_text = content_text[:20000]
                    
                    det = db.session.query(CollectionDetail).filter_by(item_id=it.id).first()
                    if det:
                        det.content_text = content_text
                        det.content_html = r.text
                        det.final_url = final_url
                    else:
                        det = CollectionDetail(item_id=it.id, content_text=content_text, content_html=r.text, final_url=final_url)
                        db.session.add(det)
                        
                    it.deep_status = True
                    if title_text and title_text != it.title:
                        it.title = title_text
                        
                    db.session.commit()
                    results.append({'id': it.id, 'detail_id': det.id, 'rule_used': rule.name if rule else 'default'})
                    success = True
                    break # Stop if successful
            except Exception:
                continue
        
        if not success:
            # Log failure or handle appropriately
            pass
            
    return jsonify({'status': 'ok', 'count': len(results), 'items': results})

@bp.route('/warehouse/detail/<int:id>', methods=['GET'])
@login_required
def warehouse_detail_preview(id):
    it = db.session.get(CollectionItem, id)
    if not it:
        return '数据不存在', 404
    det = db.session.query(CollectionDetail).filter_by(item_id=id).first()
    if not det:
        return '暂无详细内容，请先执行采集', 404
    return render_template('admin/preview.html', item=it, detail=det)

@bp.route('/rules', methods=['GET'])
@login_required
def rules_page():
    return render_template('admin/rules.html')

@bp.route('/ai_engines', methods=['GET'])
@login_required
def ai_engines_page():
    return render_template('admin/ai_engines.html')

@bp.route('/ai_engines/chat/<int:id>', methods=['GET'])
@login_required
def ai_engines_chat_page(id):
    r = db.session.get(AIEngine, int(id))
    if not r:
        return '引擎不存在', 404
    return render_template('admin/ai_chat.html', engine=r)

@bp.route('/rules/list', methods=['GET'])
@login_required
def rules_list():
    page = int(request.args.get('page') or 1)
    size = int(request.args.get('size') or 10)
    q = request.args.get('q') or ''
    query = db.session.query(CrawlRule)
    if q:
        like = f"%{q}%"
        query = query.filter(CrawlRule.site.ilike(like))
    total = query.count()
    rows = query.order_by(CrawlRule.created_at.desc()).offset((page-1)*size).limit(size).all()
    data = []
    for r in rows:
        data.append({
            'id': r.id,
            'name': r.name,
            'site': r.site,
            'title_xpath': r.title_xpath,
            'content_xpath': r.content_xpath,
            'request_headers': r.request_headers,
            'enabled': r.enabled,
        })
    return jsonify({'page': page, 'size': size, 'total': total, 'items': data})

@bp.route('/ai_engines/list', methods=['GET'])
@login_required
def ai_engines_list():
    page = int(request.args.get('page') or 1)
    size = int(request.args.get('size') or 12)
    q = request.args.get('q') or ''
    query = db.session.query(AIEngine)
    if q:
        like = f"%{q}%"
        query = query.filter((AIEngine.provider.ilike(like)) | (AIEngine.model_name.ilike(like)))
    total = query.count()
    rows = query.order_by(AIEngine.created_at.desc()).offset((page-1)*size).limit(size).all()
    data = []
    for r in rows:
        mask = None
        if r.api_key:
            if len(r.api_key) <= 6:
                mask = '***'
            else:
                mask = r.api_key[:3] + '***' + r.api_key[-3:]
        data.append({
            'id': r.id,
            'provider': r.provider,
            'api_url': r.api_url,
            'api_key_mask': mask,
            'model_name': r.model_name,
            'enabled': r.enabled,
        })
    return jsonify({'page': page, 'size': size, 'total': total, 'items': data})

@bp.route('/ai_engines/create', methods=['POST'])
@login_required
def ai_engines_create():
    data = request.get_json(silent=True) or {}
    provider = (data.get('provider') or '').strip()
    api_url = (data.get('api_url') or '').strip()
    model_name = (data.get('model_name') or '').strip()
    if not provider or not api_url or not model_name:
        return jsonify({'error': 'missing fields'}), 400
    api_key = (data.get('api_key') or '').strip() or None
    enabled = bool(data.get('enabled', True))
    r = AIEngine(provider=provider, api_url=api_url, api_key=api_key, model_name=model_name, enabled=enabled)
    db.session.add(r)
    db.session.commit()
    return jsonify({'status': 'ok', 'id': r.id})

@bp.route('/ai_engines/update', methods=['POST'])
@login_required
def ai_engines_update():
    data = request.get_json(silent=True) or {}
    id_ = data.get('id')
    if not id_:
        return jsonify({'error': 'missing id'}), 400
    r = db.session.get(AIEngine, int(id_))
    if not r:
        return jsonify({'error': 'not found'}), 404
    provider = data.get('provider')
    if provider is not None and str(provider).strip() != '':
        r.provider = str(provider).strip()
    api_url = data.get('api_url')
    if api_url is not None and str(api_url).strip() != '':
        r.api_url = str(api_url).strip()
    model_name = data.get('model_name')
    if model_name is not None and str(model_name).strip() != '':
        r.model_name = str(model_name).strip()
    api_key = data.get('api_key')
    if api_key is not None:
        val = str(api_key).strip()
        if val != '':
            r.api_key = val
    enabled = data.get('enabled')
    if enabled is not None:
        r.enabled = bool(enabled)
    db.session.commit()
    return jsonify({'status': 'ok'})

@bp.route('/ai_engines/delete', methods=['POST'])
@login_required
def ai_engines_delete():
    data = request.get_json(silent=True) or {}
    ids = data.get('ids') or []
    id_ = data.get('id')
    if id_:
        ids.append(id_)
    ids = [int(i) for i in ids if i]
    if not ids:
        return jsonify({'error': 'missing ids'}), 400
    deleted = 0
    for i in ids:
        r = db.session.get(AIEngine, i)
        if r:
            db.session.delete(r)
            deleted += 1
    db.session.commit()
    return jsonify({'status': 'ok', 'deleted': deleted})

def _is_azure_engine(engine: AIEngine) -> bool:
    host = (engine.api_url or '').lower()
    prov = (engine.provider or '').lower()
    return ('.azure.com' in host) or ('azure' in prov)

def _call_ai_engine(engine: AIEngine, messages: list):
    headers = {'Content-Type': 'application/json'}
    payload = {'messages': messages}
    if _is_azure_engine(engine):
        if engine.api_key:
            headers['api-key'] = engine.api_key
        # Azure 路径携带 deployment，payload通常无需 model 字段
    else:
        if engine.api_key:
            headers['Authorization'] = f'Bearer {engine.api_key}'
        payload['model'] = engine.model_name
    try:
        resp = requests.post(engine.api_url, json=payload, headers=headers, timeout=30)
        status = resp.status_code
        data = None
        try:
            data = resp.json()
        except Exception:
            data = None
        if status >= 400:
            msg = None
            if isinstance(data, dict):
                err = data.get('error')
                if isinstance(err, dict):
                    msg = err.get('message') or err.get('code') or str(err)
                elif isinstance(err, str):
                    msg = err
            return {'status': 'error', 'message': msg or f'HTTP {status}'}
        txt = None
        if isinstance(data, dict):
            choices = data.get('choices')
            if isinstance(choices, list) and choices:
                msg = choices[0].get('message') or {}
                txt = msg.get('content')
            elif isinstance(data.get('message'), dict):
                txt = data.get('message', {}).get('content')
        return {'status': 'ok', 'text': txt or '', 'raw': data}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

@bp.route('/ai_engines/chat/send', methods=['POST'])
@login_required
def ai_engines_chat_send():
    data = request.get_json(silent=True) or {}
    id_ = data.get('id')
    messages = data.get('messages') or []
    if not id_:
        return jsonify({'error': 'missing id'}), 400
    r = db.session.get(AIEngine, int(id_))
    if not r or not r.enabled:
        return jsonify({'error': 'engine not available'}), 400
    result = _call_ai_engine(r, messages)
    return jsonify(result)

@bp.route('/crawlers', methods=['GET'])
@login_required
def crawlers_page():
    return render_template('admin/crawlers.html')

@bp.route('/crawlers/list', methods=['GET'])
@login_required
def crawlers_list():
    page = int(request.args.get('page') or 1)
    size = int(request.args.get('size') or 12)
    q = request.args.get('q') or ''
    query = db.session.query(Crawler)
    if q:
        like = f"%{q}%"
        query = query.filter((Crawler.name.ilike(like)) | (Crawler.code.ilike(like)))
    total = query.count()
    rows = query.order_by(Crawler.created_at.desc()).offset((page-1)*size).limit(size).all()
    items = []
    for r in rows:
        items.append({
            'id': r.id,
            'name': r.name,
            'code': r.code,
            'key': r.key,
            'class_path': r.class_path,
            'base_url': r.base_url,
            'headers_json': r.headers_json,
            'params_json': r.params_json,
            'dynamic_keys': r.dynamic_keys,
            'entry': r.entry,
            'config_json': r.config_json,
            'enabled': r.enabled,
        })
    return jsonify({'page': page, 'size': size, 'total': total, 'items': items})

@bp.route('/crawlers/create', methods=['POST'])
@login_required
def crawlers_create():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    code = (data.get('code') or '').strip()
    key = (data.get('key') or '').strip() or None
    class_path = (data.get('class_path') or '').strip() or None
    base_url = (data.get('base_url') or '').strip() or None
    headers_json = (data.get('headers_json') or '').strip() or None
    params_json = (data.get('params_json') or '').strip() or None
    dynamic_keys = (data.get('dynamic_keys') or '').strip() or None
    entry = (data.get('entry') or '').strip() or None
    if not name:
        return jsonify({'error': 'missing name'}), 400
    if not class_path and not entry:
        return jsonify({'error': 'missing class_path or entry'}), 400
    config_json = (data.get('config_json') or '').strip() or None
    enabled = bool(data.get('enabled', True))
    r = Crawler(name=name, code=code, key=key, class_path=class_path, base_url=base_url, headers_json=headers_json, params_json=params_json, dynamic_keys=dynamic_keys, entry=entry, config_json=config_json, enabled=enabled)
    db.session.add(r)
    db.session.commit()
    return jsonify({'status': 'ok', 'id': r.id})

@bp.route('/crawlers/update', methods=['POST'])
@login_required
def crawlers_update():
    data = request.get_json(silent=True) or {}
    id_ = data.get('id')
    if not id_:
        return jsonify({'error': 'missing id'}), 400
    r = db.session.get(Crawler, int(id_))
    if not r:
        return jsonify({'error': 'not found'}), 404
    name = data.get('name')
    if name is not None and str(name).strip() != '':
        r.name = str(name).strip()
    code = data.get('code')
    if code is not None and str(code).strip() != '':
        r.code = str(code).strip()
    key = data.get('key')
    if key is not None and str(key).strip() != '':
        r.key = str(key).strip()
    class_path = data.get('class_path')
    if class_path is not None and str(class_path).strip() != '':
        r.class_path = str(class_path).strip()
    base_url = data.get('base_url')
    if base_url is not None and str(base_url).strip() != '':
        r.base_url = str(base_url).strip()
    headers_json = data.get('headers_json')
    if headers_json is not None:
        r.headers_json = str(headers_json).strip()
    params_json = data.get('params_json')
    if params_json is not None:
        r.params_json = str(params_json).strip()
    dynamic_keys = data.get('dynamic_keys')
    if dynamic_keys is not None:
        r.dynamic_keys = str(dynamic_keys).strip()
    entry = data.get('entry')
    if entry is not None and str(entry).strip() != '':
        r.entry = str(entry).strip()
    cfg = data.get('config_json')
    if cfg is not None:
        r.config_json = str(cfg).strip()
    enabled = data.get('enabled')
    if enabled is not None:
        r.enabled = bool(enabled)
    db.session.commit()
    return jsonify({'status': 'ok'})

@bp.route('/crawlers/delete', methods=['POST'])
@login_required
def crawlers_delete():
    data = request.get_json(silent=True) or {}
    ids = data.get('ids') or []
    id_ = data.get('id')
    if id_:
        ids.append(id_)
    ids = [int(i) for i in ids if i]
    if not ids:
        return jsonify({'error': 'missing ids'}), 400
    deleted = 0
    for i in ids:
        r = db.session.get(Crawler, i)
        if r:
            db.session.delete(r)
            deleted += 1
    db.session.commit()
    return jsonify({'status': 'ok', 'deleted': deleted})

@bp.route('/crawlers/sources/list', methods=['GET'])
@login_required
def crawler_sources_list():
    cid = int(request.args.get('crawler_id') or 0)
    rows = db.session.query(CrawlerSource).filter_by(crawler_id=cid).all()
    return jsonify({'items': [{'id': s.id, 'source': s.source, 'enabled': s.enabled} for s in rows]})

@bp.route('/crawlers/sources/add', methods=['POST'])
@login_required
def crawler_sources_add():
    data = request.get_json(silent=True) or {}
    cid = data.get('crawler_id')
    source = (data.get('source') or '').strip()
    if not cid or not source:
        return jsonify({'error': 'missing fields'}), 400
    r = db.session.get(Crawler, int(cid))
    if not r:
        return jsonify({'error': 'crawler not found'}), 404
    s = CrawlerSource(source=source, crawler_id=r.id, enabled=True)
    db.session.add(s)
    db.session.commit()
    return jsonify({'status': 'ok', 'id': s.id})

@bp.route('/crawlers/sources/delete', methods=['POST'])
@login_required
def crawler_sources_delete():
    data = request.get_json(silent=True) or {}
    ids = data.get('ids') or []
    id_ = data.get('id')
    if id_:
        ids.append(id_)
    ids = [int(i) for i in ids if i]
    if not ids:
        return jsonify({'error': 'missing ids'}), 400
    deleted = 0
    for i in ids:
        s = db.session.get(CrawlerSource, i)
        if s:
            db.session.delete(s)
            deleted += 1
    db.session.commit()
    return jsonify({'status': 'ok', 'deleted': deleted})

@bp.route('/crawlers/run', methods=['POST'])
@login_required
def crawlers_run():
    data = request.get_json(silent=True) or {}
    id_ = data.get('id')
    code = (data.get('code') or '').strip()
    params = data.get('params') or {}
    from ..collector.service import run_crawler_by_entry, run_crawler_by_code, run_crawler_by_class
    items = []
    try:
        if id_:
            r = db.session.get(Crawler, int(id_))
            if not r or not r.enabled:
                return jsonify({'error': 'crawler not available'}), 400
            if r.class_path:
                import json as _json
                hdr = None
                prm = None
                try:
                    hdr = _json.loads(r.headers_json) if r.headers_json else None
                except Exception:
                    hdr = None
                try:
                    prm = _json.loads(r.params_json) if r.params_json else None
                except Exception:
                    prm = None
                merged = prm or {}
                if isinstance(params, dict):
                    merged.update(params)
                items = run_crawler_by_class(r.class_path, r.base_url, hdr, merged)
            else:
                items = run_crawler_by_entry(r.entry, params)
        elif code:
            items = run_crawler_by_code(code, params)
        else:
            return jsonify({'error': 'missing id or code'}), 400
        return jsonify({'status': 'ok', 'count': len(items), 'items': items})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/crawlers/collect_by_source', methods=['POST'])
@login_required
def crawlers_collect_by_source():
    data = request.get_json(silent=True) or {}
    source = (data.get('source') or '').strip()
    params = data.get('params') or {}
    from ..collector.service import run_crawler_by_source
    try:
        items = run_crawler_by_source(source, params)
        return jsonify({'status': 'ok', 'source': source, 'count': len(items), 'items': items})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/crawlers/headers_refresh', methods=['POST'])
@login_required
def crawlers_headers_refresh():
    data = request.get_json(silent=True) or {}
    id_ = data.get('id')
    raw = data.get('headers_raw') or ''
    if not id_:
        return jsonify({'error': 'missing id'}), 400
    r = db.session.get(Crawler, int(id_))
    if not r:
        return jsonify({'error': 'not found'}), 404
    from ..collector.service import parse_raw_headers
    try:
        hdr = parse_raw_headers(raw)
        import json as _json
        r.headers_json = _json.dumps(hdr or {})
        db.session.commit()
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/crawlers/vars_by_source', methods=['GET'])
@login_required
def crawlers_vars_by_source():
    source = (request.args.get('source') or '').strip()
    if not source:
        return jsonify({'error': 'missing source'}), 400
    m = db.session.query(CrawlerSource).filter_by(source=source, enabled=True).first()
    if not m:
        return jsonify({'error': 'no mapping'}), 404
    r = db.session.get(Crawler, m.crawler_id)
    if not r:
        return jsonify({'error': 'crawler not found'}), 404
    return jsonify({'crawler_id': r.id, 'dynamic_keys': r.dynamic_keys or ''})

@bp.route('/crawlers/analyze', methods=['POST'])
@login_required
def crawlers_analyze():
    data = request.get_json(silent=True) or {}
    source_url = (data.get('source_url') or '').strip()
    headers_raw = data.get('headers_raw') or ''
    source_name = (data.get('source') or '').strip() or None
    if not source_url:
        return jsonify({'error': 'missing source_url'}), 400
    from ..collector.service import analyze_crawler_from_request
    try:
        cfg = analyze_crawler_from_request(source_url, headers_raw)
        name = cfg.get('name')
        code = cfg.get('code')
        exists = db.session.query(Crawler).filter_by(code=code).first()
        import json as _json
        if exists:
            exists.name = name
            exists.key = cfg.get('key')
            exists.class_path = cfg.get('class_path')
            exists.base_url = cfg.get('base_url')
            exists.headers_json = _json.dumps(cfg.get('headers_json') or {})
            exists.params_json = _json.dumps(cfg.get('params_json') or {})
            exists.dynamic_keys = _json.dumps(cfg.get('dynamic_keys') or [])
            exists.enabled = True
            db.session.commit()
            cid = exists.id
        else:
            r = Crawler(
                name=name,
                code=code,
                key=cfg.get('key'),
                class_path=cfg.get('class_path'),
                base_url=cfg.get('base_url'),
                headers_json=_json.dumps(cfg.get('headers_json') or {}),
                params_json=_json.dumps(cfg.get('params_json') or {}),
                dynamic_keys=_json.dumps(cfg.get('dynamic_keys') or []),
                enabled=True,
            )
            db.session.add(r)
            db.session.commit()
            cid = r.id
        if source_name:
            m = CrawlerSource(source=source_name, crawler_id=cid, enabled=True)
            db.session.add(m)
            db.session.commit()
        return jsonify({'status': 'ok', 'id': cid, 'code': code})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/ai_clean', methods=['GET'])
@login_required
def ai_clean_page():
    engines = db.session.query(AIEngine).filter_by(enabled=True).order_by(AIEngine.created_at.desc()).all()
    return render_template('admin/ai_clean.html', engines=engines)

@bp.route('/ai_clean/run', methods=['POST'])
@login_required
def ai_clean_run():
    data = request.get_json(silent=True) or {}
    engine_id = data.get('engine_id')
    limit = int(data.get('limit') or 10)
    task = (data.get('task') or 'analyze').strip()
    if not engine_id:
        return jsonify({'error': 'missing engine_id'}), 400
    eng = db.session.get(AIEngine, int(engine_id))
    if not eng or not eng.enabled:
        return jsonify({'error': 'engine not available'}), 404
    from sqlalchemy import text as _text
    rows = []
    err = None
    try:
        sql = _text('SELECT id, title, content, created_at FROM article_details ORDER BY created_at DESC LIMIT :lim')
        rs = db.session.execute(sql, {'lim': limit})
        for r in rs:
            rows.append({'id': r[0], 'title': r[1], 'content': (r[2] or '')[:1000], 'created_at': str(r[3])})
    except Exception as e:
        err = str(e)
    messages = []
    sys = '你是一个数据清洗与分析助手，基于提供的文章列表，执行清洗与统计任务。'
    if task == 'clean':
        usr = '请针对以下文章列表执行清洗：移除冗余空格、去除明显的乱码段、标记可能的重复标题，并给出清洗建议。用简体中文输出，列出问题与建议，每条尽量简洁。'
    else:
        usr = '请对以下文章列表进行分析：统计标题重复情况、内容长度分布、可能的采集异常，并给出改进建议。用简体中文输出。'
    payload = {'rows': rows, 'error': err}
    messages.append({'role': 'system', 'content': sys})
    messages.append({'role': 'user', 'content': f'{usr}\n数据: ' + json.dumps(payload, ensure_ascii=False)})
    result = _call_ai_engine(eng, messages)
    return jsonify(result)

@bp.route('/rules/create', methods=['POST'])
@login_required
def rules_create():
    data = request.get_json(silent=True) or {}
    site = data.get('site')
    if not site:
        return jsonify({'error': 'missing site'}), 400
    headers_raw = data.get('request_headers')
    def _normalize_headers(h):
        if not h:
            return None
        try:
            obj = json.loads(h)
            return json.dumps(obj, ensure_ascii=False)
        except Exception:
            lines = [ln.strip() for ln in h.splitlines()]
            d = {}
            k = None
            buf = []
            for ln in lines:
                if not ln:
                    continue
                if ln.endswith(':') and ln.count(':') == 1:
                    if k and buf:
                        d[k] = ' '.join(buf).strip()
                    k = ln[:-1].strip()
                    buf = []
                else:
                    if ':' in ln and not k:
                        parts = ln.split(':', 1)
                        d[parts[0].strip()] = parts[1].strip()
                    elif k is not None:
                        buf.append(ln)
            if k and buf:
                d[k] = ' '.join(buf).strip()
            return json.dumps(d, ensure_ascii=False)
    headers = _normalize_headers(headers_raw)
    r = CrawlRule(name=data.get('name'), site=site, title_xpath=data.get('title_xpath'), content_xpath=data.get('content_xpath'), request_headers=headers, enabled=bool(data.get('enabled', True)))
    db.session.add(r)
    db.session.commit()
    return jsonify({'status': 'ok', 'id': r.id})

@bp.route('/rules/copy', methods=['POST'])
@login_required
def rules_copy():
    data = request.get_json(silent=True) or {}
    id_ = data.get('id')
    if not id_:
        return jsonify({'error': 'missing id'}), 400
    r = db.session.get(CrawlRule, int(id_))
    if not r:
        return jsonify({'error': 'not found'}), 404
    
    # Create new rule based on existing one (exact copy)
    new_rule = CrawlRule(
        name=r.name,
        site=r.site,
        title_xpath=r.title_xpath,
        content_xpath=r.content_xpath,
        request_headers=r.request_headers,
        enabled=r.enabled
    )
    db.session.add(new_rule)
    db.session.commit()
    return jsonify({'status': 'ok', 'id': new_rule.id})

@bp.route('/rules/update', methods=['POST'])
@login_required
def rules_update():
    data = request.get_json(silent=True) or {}
    id_ = data.get('id')
    if not id_:
        return jsonify({'error': 'missing id'}), 400
    r = db.session.get(CrawlRule, int(id_))
    if not r:
        return jsonify({'error': 'not found'}), 404
    name = data.get('name')
    if name is not None:
        r.name = name
    site = data.get('site')
    if site is not None and str(site).strip() != '':
        r.site = site
    title_xpath = data.get('title_xpath')
    if title_xpath is not None and str(title_xpath).strip() != '':
        r.title_xpath = title_xpath
    content_xpath = data.get('content_xpath')
    if content_xpath is not None and str(content_xpath).strip() != '':
        r.content_xpath = content_xpath
    headers = data.get('request_headers')
    if headers is not None:
        if str(headers).strip() != '':
            try:
                obj = json.loads(headers)
                r.request_headers = json.dumps(obj, ensure_ascii=False)
            except Exception:
                lines = [ln.strip() for ln in headers.splitlines()]
                d = {}
                k = None
                buf = []
                for ln in lines:
                    if not ln:
                        continue
                    if ln.endswith(':') and ln.count(':') == 1:
                        if k and buf:
                            d[k] = ' '.join(buf).strip()
                        k = ln[:-1].strip()
                        buf = []
                    else:
                        if ':' in ln and not k:
                            parts = ln.split(':', 1)
                            d[parts[0].strip()] = parts[1].strip()
                        elif k is not None:
                            buf.append(ln)
                if k and buf:
                    d[k] = ' '.join(buf).strip()
                r.request_headers = json.dumps(d, ensure_ascii=False)
    enabled = data.get('enabled')
    if enabled is not None:
        r.enabled = bool(enabled)
    db.session.commit()
    return jsonify({'status': 'ok'})

@bp.route('/rules/delete', methods=['POST'])
@login_required
def rules_delete():
    data = request.get_json(silent=True) or {}
    ids = data.get('ids') or []
    id_ = data.get('id')
    if id_:
        ids.append(id_)
    ids = [int(i) for i in ids if i]
    if not ids:
        return jsonify({'error': 'missing ids'}), 400
    deleted = 0
    for i in ids:
        r = db.session.get(CrawlRule, i)
        if r:
            db.session.delete(r)
            deleted += 1
    db.session.commit()
    return jsonify({'status': 'ok', 'deleted': deleted})
