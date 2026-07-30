import os
import tempfile

# CRÍTICO: precisa rodar ANTES de "from app import app", porque config.py lê
# DATABASE_URL do ambiente no momento em que a classe Config é definida (ou
# seja, no import de app.py). Um app.config.update(...) feito depois do
# import já é tarde demais — Flask-SQLAlchemy resolve o engine real na
# primeira vez que é usado, e um incidente anterior mostrou que o real
# database.db acaba sendo aberto mesmo tentando sobrescrever a config depois.
# Isolando por env var antes do import, o arquivo real nunca chega a ser
# referenciado em nenhum momento do processo de teste.
_tmp_fd, _tmp_db_path = tempfile.mkstemp(suffix='.db', prefix='sistema_oc_test_')
os.close(_tmp_fd)
os.environ['DATABASE_URL'] = 'sqlite:///' + _tmp_db_path.replace('\\', '/')

import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app, db
from models import User


@pytest.fixture()
def app():
    flask_app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    # IMPORTANTE: este app_context só cobre o setup. Não deve ficar aberto
    # durante o teste em si — se ficar, o test_client reaproveita esse
    # contexto em vez de abrir um por requisição, e o current_user cacheado
    # pelo Flask-Login (em flask.g) vaza de uma requisição pra outra mesmo
    # trocando de usuário na sessão (já causou falso-positivo de bug de
    # permissão numa rodada anterior).
    with flask_app.app_context():
        resolvida = str(db.engine.url)
        assert 'sistema_oc_test_' in resolvida, (
            f"ABORTANDO: engine de teste resolveu para {resolvida!r} em vez do "
            f"banco temporário isolado — não prosseguir para não arriscar o "
            f"banco real."
        )
        db.create_all()
        db.session.add_all([
            User(nome='Admin', email='admin@teste.com',
                 senha=generate_password_hash('123456'),
                 area='Administrativo', is_admin=True),
            User(nome='Analista PCP', email='pcp@teste.com',
                 senha=generate_password_hash('123456'),
                 area='PCP', is_admin=False),
            User(nome='Vigilante', email='portaria@teste.com',
                 senha=generate_password_hash('123456'),
                 area='Portaria', is_admin=False),
        ])
        db.session.commit()

    yield flask_app

    with flask_app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login_as(app, client, email):
    with app.app_context():
        user_id = User.query.filter_by(email=email).first().id
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


def criar_oc(app, client, cliente='Cliente Teste', produto='Produto Teste'):
    """Cria uma OC via rota real e devolve (id, numero_oc) — não o objeto ORM,
    para evitar acessar atributos fora do app_context em que foi carregado."""
    login_as(app, client, 'admin@teste.com')
    client.post('/oc/nova', data={
        'pedido': 'PV123', 'frete': 'CIF', 'cliente': cliente,
        'produto': produto, 'codigo': 'COD1', 'transportadora': 'Transp X',
    })
    with app.app_context():
        from models import OrdemCarregamento
        oc = OrdemCarregamento.query.order_by(OrdemCarregamento.id.desc()).first()
        return oc.id, oc.numero_oc


def pytest_sessionfinish(session, exitstatus):
    if os.path.exists(_tmp_db_path):
        try:
            os.remove(_tmp_db_path)
        except OSError:
            pass
