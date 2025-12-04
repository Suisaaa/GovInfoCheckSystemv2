from flask import request, jsonify
from . import bp
from .service import fetch_baidu_news, fetch_xinhua_sichuan

@bp.get('/collect')
def collect():
    q = request.args.get('q') or request.args.get('keyword') or ''
    limit = int(request.args.get('limit') or 20)
    pn = int(request.args.get('pn') or 0)
    if not q:
        return jsonify({'error': 'keyword required'}), 400
    try:
        items = fetch_baidu_news(q, limit=limit, pn=pn)
        return jsonify({'keyword': q, 'pn': pn, 'count': len(items), 'items': items})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.get('/collect/xinhua')
def collect_xinhua():
    q = request.args.get('q') or request.args.get('keyword') or ''
    limit = int(request.args.get('limit') or 20)
    try:
        items = fetch_xinhua_sichuan(keyword=(q or None), limit=limit)
        return jsonify({'keyword': q, 'count': len(items), 'items': items})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
