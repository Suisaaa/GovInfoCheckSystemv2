from flask import Blueprint

bp = Blueprint('collector', __name__, url_prefix='/api')

from . import routes
