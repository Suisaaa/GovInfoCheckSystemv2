from flask import request, jsonify
from . import bp
from .service import fetch_baidu_news

@bp.get('/collect')
def collect():
    q = request.args.get('q') or request.args.get('keyword') or ''
    limit = int(request.args.get('limit') or 20)
    if not q:
        return jsonify({'error': 'keyword required'}), 400
    try:
        items = fetch_baidu_news(q, limit=limit)
        return jsonify({'keyword': q, 'count': len(items), 'items': items})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
