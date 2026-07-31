"""
Servidor de produção do Sistema OC.

Diferente de `python app.py` (servidor de desenvolvimento do Flask, só
localhost, com o depurador interativo do Werkzeug), este script:
  - roda com Waitress, um servidor WSGI de verdade;
  - escuta em todas as interfaces de rede (0.0.0.0), para que outros
    computadores/tablets na rede local (Portaria, Produção, Laboratório...)
    consigam acessar;
  - força o modo debug desligado, mesmo que o .env tenha FLASK_DEBUG=1
    (nunca queremos o depurador do Werkzeug exposto na rede).

Uso: python run_prod.py   (ou dê duplo clique em iniciar_producao.bat)
"""
import os
import socket

os.environ['FLASK_DEBUG'] = '0'

from waitress import serve
from app import app

HOST = '0.0.0.0'
PORT = 5000


def ip_local():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()


if __name__ == '__main__':
    ip = ip_local()
    print('=' * 60)
    print('Sistema OC — modo produção (Waitress)')
    print(f'  Neste computador:  http://127.0.0.1:{PORT}')
    print(f'  Na rede local:     http://{ip}:{PORT}')
    print('=' * 60)
    print('Pressione CTRL+C para encerrar.')
    serve(app, host=HOST, port=PORT)
