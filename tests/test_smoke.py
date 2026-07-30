import pytest
from sqlalchemy.exc import IntegrityError

from app import db
from models import OrdemCarregamento, EtapaOC, DadosEtapa
from conftest import login_as, criar_oc


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
