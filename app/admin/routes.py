from flask import render_template, request, redirect, url_for, jsonify
from flask_login import login_required, current_user
from . import bp
from ..extensions import db
from ..models import User, Role, Setting, CollectionItem, CollectionDetail
from ..collector.service import _headers_with_cookie

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
