import os

from flask import Flask, render_template
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

from config import Config
from models import db, User

base_dir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, template_folder=os.path.join(base_dir, 'templates'))
app.config.from_object(Config)
app.config['TEMPLATES_AUTO_RELOAD'] = True

db.init_app(app)
csrf = CSRFProtect(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


from blueprints.auth import bp as auth_bp
from blueprints.usuarios import bp as usuarios_bp
from blueprints.ocs import bp as ocs_bp
from blueprints.etapas import bp as etapas_bp
from blueprints.dashboard import bp as dashboard_bp

app.register_blueprint(auth_bp)
app.register_blueprint(usuarios_bp)
app.register_blueprint(ocs_bp)
app.register_blueprint(etapas_bp)
app.register_blueprint(dashboard_bp)

# Cria schema, tabelas e o admin inicial se ainda não existirem. Vale para
# `python app.py`, `run_prod.py` e o container, sem duplicar código.
from db_init import init_db
init_db(app)


@app.errorhandler(403)
def acesso_negado(e):
    return render_template('403.html'), 403


if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'])
