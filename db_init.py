"""Inicialização do banco no boot da aplicação.

Antes o schema existia só porque o arquivo SQLite havia sido criado à mão.
Rodando contra um Postgres em container, ninguém cria as tabelas — este módulo
cuida disso, de forma idempotente:

  1. espera o servidor de banco responder (o container pode subir antes dele);
  2. cria o schema dedicado (CREATE SCHEMA IF NOT EXISTS);
  3. cria as tabelas que faltarem (db.create_all);
  4. cria o primeiro usuário admin, se o banco estiver vazio.
"""
import os
import time

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from werkzeug.security import generate_password_hash

from models import db, User

TENTATIVAS = int(os.environ.get('DB_WAIT_TENTATIVAS', '30'))
INTERVALO  = float(os.environ.get('DB_WAIT_INTERVALO', '2'))


def _esperar_banco(app):
    """Tenta abrir uma conexão até o banco responder. Levanta se desistir."""
    ultimo_erro = None
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            with db.engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            return
        except OperationalError as e:
            ultimo_erro = e
            app.logger.warning(
                'Banco indisponível (tentativa %d/%d), aguardando %.1fs...',
                tentativa, TENTATIVAS, INTERVALO)
            time.sleep(INTERVALO)
    raise RuntimeError(
        f'Não foi possível conectar ao banco após {TENTATIVAS} tentativas: {ultimo_erro}'
    )


def _criar_schema(app):
    """CREATE SCHEMA IF NOT EXISTS — só faz sentido no Postgres."""
    if db.engine.dialect.name != 'postgresql':
        return
    schema = app.config['DB_SCHEMA']
    # O nome vem do .env, não de entrada de usuário; ainda assim, só aceitamos
    # identificadores simples para não montar DDL com qualquer coisa.
    if not schema.replace('_', '').isalnum():
        raise RuntimeError(f'DB_SCHEMA inválido: {schema!r}')
    with db.engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    app.logger.info('Schema "%s" pronto.', schema)


def _seed_admin(app):
    """Cria o primeiro admin a partir do .env, se o banco não tiver usuários."""
    if db.session.query(User.id).first() is not None:
        return

    email = os.environ.get('ADMIN_EMAIL')
    senha = os.environ.get('ADMIN_SENHA')
    if not email or not senha:
        app.logger.warning(
            'Banco sem usuários e ADMIN_EMAIL/ADMIN_SENHA não definidos no .env '
            '— nenhum admin foi criado e não será possível fazer login.')
        return

    db.session.add(User(
        nome=os.environ.get('ADMIN_NOME', 'Administrador'),
        email=email,
        senha=generate_password_hash(senha),
        area=os.environ.get('ADMIN_AREA', 'Administrativo'),
        is_admin=True,
    ))
    db.session.commit()
    app.logger.info('Usuário admin inicial criado: %s', email)


def init_db(app):
    # A suíte de testes monta o próprio banco (tests/conftest.py) e desliga
    # isto via DB_AUTO_INIT=0.
    if os.environ.get('DB_AUTO_INIT', '1') != '1':
        return
    with app.app_context():
        _esperar_banco(app)
        _criar_schema(app)
        db.create_all()
        _seed_admin(app)
