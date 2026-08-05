import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


def _uri_postgres():
    """Monta a URI do Postgres a partir das partes definidas no .env.

    A senha passa por quote_plus porque senhas com '@', '/' ou ':' quebram o
    parsing da URI.
    """
    host  = os.environ.get('DB_HOST', 'localhost')
    port  = os.environ.get('DB_PORT', '5432')
    nome  = os.environ.get('DB_NAME', 'sistema_oc')
    user  = os.environ.get('DB_USER', 'sistema_oc')
    senha = os.environ.get('DB_PASSWORD', '')
    return (f"postgresql+psycopg://{quote_plus(user)}:{quote_plus(senha)}"
            f"@{host}:{port}/{nome}")


class Config:
    DEBUG = os.environ.get('FLASK_DEBUG', '0') == '1'

    # Em produção a chave precisa vir do .env. O fallback inseguro só vale em
    # modo debug — antes ele entrava silenciosamente em produção também.
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        if DEBUG:
            SECRET_KEY = 'dev-key-insegura-troque-em-producao'
        else:
            raise RuntimeError(
                'SECRET_KEY não definida. Defina-a no .env antes de subir em '
                'produção (ex.: python -c "import secrets; print(secrets.token_hex(32))").'
            )

    # DATABASE_URL continua sendo respeitada como override — é assim que a
    # suíte de testes (tests/conftest.py) aponta para um SQLite temporário.
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or _uri_postgres()

    # Schema dedicado no Postgres. Não é aplicado via metadata (isso quebraria
    # os testes em SQLite, onde "schema" significa banco anexado); em vez disso
    # entra no search_path da conexão, abaixo.
    DB_SCHEMA = os.environ.get('DB_SCHEMA', 'sistema_oc')

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,   # reconecta se o servidor derrubou a conexão ociosa
        'pool_recycle': 1800,
    }
    if SQLALCHEMY_DATABASE_URI.startswith('postgresql'):
        SQLALCHEMY_ENGINE_OPTIONS['connect_args'] = {
            'options': f'-csearch_path={DB_SCHEMA},public'
        }

    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB por requisição (uploads de fotos)
