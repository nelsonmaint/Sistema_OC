import pytest
from sqlalchemy.exc import IntegrityError

from werkzeug.security import check_password_hash

from app import db
from models import OrdemCarregamento, EtapaOC, DadosEtapa, User
from conftest import login_as, criar_oc


def _id_de(app, email):
    with app.app_context():
        return User.query.filter_by(email=email).first().id


def test_login_valido_e_invalido(client):
    r = client.post('/login', data={'email': 'admin@teste.com', 'senha': '123456'},
                     follow_redirects=True)
    assert r.status_code == 200

    r = client.post('/login', data={'email': 'admin@teste.com', 'senha': 'errada'})
    assert b'inv\xc3\xa1lidos' in r.data


def test_criar_oc_gera_numero_sequencial(app, client):
    oc1_id, oc1_numero = criar_oc(app, client, cliente='Cliente A')
    oc2_id, oc2_numero = criar_oc(app, client, cliente='Cliente B')
    assert oc1_numero != oc2_numero
    assert oc1_numero.startswith('OC')

    with app.app_context():
        etapa_010 = EtapaOC.query.filter_by(oc_id=oc1_id, codigo_etapa='010').first()
        assert etapa_010 is not None
        assert etapa_010.fim is not None


def test_numero_oc_tem_constraint_unica(app):
    with app.app_context():
        db.session.add(OrdemCarregamento(numero_oc='OC99999', status='em_andamento'))
        db.session.commit()
        db.session.add(OrdemCarregamento(numero_oc='OC99999', status='em_andamento'))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_permissao_bloqueia_area_errada(app, client):
    oc_id, _ = criar_oc(app, client)

    login_as(app, client, 'pcp@teste.com')
    r = client.get(f'/oc/{oc_id}/iniciar/040')
    assert r.status_code == 403

    r = client.get(f'/oc/{oc_id}/iniciar/020', follow_redirects=False)
    assert r.status_code == 302


def test_fluxo_etapa_020_completa(app, client):
    oc_id, _ = criar_oc(app, client)
    login_as(app, client, 'pcp@teste.com')

    client.get(f'/oc/{oc_id}/iniciar/020')
    r = client.post(f'/oc/{oc_id}/formulario/020', data={'lote': 'LOTE-001'},
                     follow_redirects=False)
    assert r.status_code == 302

    with app.app_context():
        etapa_020 = EtapaOC.query.filter_by(oc_id=oc_id, codigo_etapa='020').first()
        assert etapa_020.fim is not None
        assert etapa_020.duracao is not None

        lote = DadosEtapa.query.filter_by(etapa_id=etapa_020.id, campo='numero_lote').first()
        assert lote.valor == 'LOTE-001'


def test_excluir_oc_soft_delete_esconde_de_usuario_comum(app, client):
    oc_id, oc_numero = criar_oc(app, client)

    login_as(app, client, 'admin@teste.com')
    client.post(f'/oc/{oc_id}/excluir', data={
        'motivo_cancelamento': 'CANCELAMENTO', 'justificativa': 'Teste',
    })
    with app.app_context():
        oc_recarregada = OrdemCarregamento.query.get(oc_id)
        assert oc_recarregada.excluida is True
        assert oc_recarregada.motivo_cancelamento == 'CANCELAMENTO'

    login_as(app, client, 'pcp@teste.com')
    r = client.get('/ocs')
    assert oc_numero.encode() not in r.data


def test_resumo_oc_retorna_200(app, client):
    oc_id, oc_numero = criar_oc(app, client)
    login_as(app, client, 'admin@teste.com')
    r = client.get(f'/oc/{oc_id}/resumo')
    assert r.status_code == 200
    assert oc_numero.encode() in r.data


def test_admin_edita_nome_e_area_de_outro_usuario(app, client):
    pcp_id = _id_de(app, 'pcp@teste.com')
    login_as(app, client, 'admin@teste.com')

    r = client.post(f'/admin/usuarios/{pcp_id}/editar', data={
        'nome': 'Analista PCP Renomeado', 'area': 'Produção', 'is_admin': 'on',
    })
    assert r.status_code == 200

    with app.app_context():
        u = db.session.get(User, pcp_id)
        assert u.nome == 'Analista PCP Renomeado'
        assert u.area == 'Produção'
        assert u.is_admin is True


def test_admin_redefine_senha_e_usuario_loga_com_a_nova(app, client):
    pcp_id = _id_de(app, 'pcp@teste.com')
    login_as(app, client, 'admin@teste.com')

    client.post(f'/admin/usuarios/{pcp_id}/editar', data={
        'nome': 'Analista PCP', 'area': 'PCP',
        'senha': 'novasenha1', 'senha2': 'novasenha1',
    })

    client.get('/logout')
    r = client.post('/login', data={'email': 'pcp@teste.com', 'senha': 'novasenha1'},
                     follow_redirects=False)
    assert r.status_code == 302  # 302 = autenticou; senha errada devolve 200


def test_admin_nao_remove_o_proprio_perfil_de_admin(app, client):
    admin_id = _id_de(app, 'admin@teste.com')
    login_as(app, client, 'admin@teste.com')

    # is_admin ausente do form = checkbox desmarcada
    r = client.post(f'/admin/usuarios/{admin_id}/editar', data={
        'nome': 'Admin', 'area': 'Administrativo',
    })
    assert 'próprio perfil de administrador'.encode() in r.data

    with app.app_context():
        assert db.session.get(User, admin_id).is_admin is True


def test_edicao_de_usuario_e_so_para_admin(app, client):
    admin_id = _id_de(app, 'admin@teste.com')
    login_as(app, client, 'pcp@teste.com')
    assert client.get(f'/admin/usuarios/{admin_id}/editar').status_code == 403


def test_perfil_troca_a_propria_senha(app, client):
    pcp_id = _id_de(app, 'pcp@teste.com')
    login_as(app, client, 'pcp@teste.com')

    # senha atual errada: recusa e não altera nada
    r = client.post('/perfil', data={
        'nome': 'Analista PCP', 'senha_atual': 'errada',
        'senha': 'novasenha1', 'senha2': 'novasenha1',
    })
    assert 'Senha atual incorreta'.encode() in r.data
    with app.app_context():
        assert check_password_hash(db.session.get(User, pcp_id).senha, '123456')

    # senha atual correta: troca nome e senha
    r = client.post('/perfil', data={
        'nome': 'Analista PCP II', 'senha_atual': '123456',
        'senha': 'novasenha1', 'senha2': 'novasenha1',
    })
    assert r.status_code == 200
    with app.app_context():
        u = db.session.get(User, pcp_id)
        assert u.nome == 'Analista PCP II'
        assert check_password_hash(u.senha, 'novasenha1')


def test_perfil_recusa_confirmacao_divergente(app, client):
    pcp_id = _id_de(app, 'pcp@teste.com')
    login_as(app, client, 'pcp@teste.com')

    r = client.post('/perfil', data={
        'nome': 'Analista PCP', 'senha_atual': '123456',
        'senha': 'novasenha1', 'senha2': 'outracoisa',
    })
    assert 'confirmação de senha não confere'.encode() in r.data
    with app.app_context():
        assert check_password_hash(db.session.get(User, pcp_id).senha, '123456')
