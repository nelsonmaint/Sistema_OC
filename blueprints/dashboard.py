import io
import csv
import json
import calendar
from datetime import datetime

from flask import Blueprint, render_template, request, Response
from flask_login import login_required

from constants import ETAPAS, TEMPO_META, AREAS, ORDEM_ETAPAS, LABELS_CAMPOS, LABELS_ASS, CAMPOS_ASSINATURAS, CAMPOS_FOTOS
from helpers import _ordem_efetiva

bp = Blueprint('dashboard', __name__)


@bp.route('/acompanhamento')
@login_required
def acompanhamento():
    from models import OrdemCarregamento
    from helpers import _campo_valor

    ocs_abertas = OrdemCarregamento.query\
                    .filter_by(status='em_andamento', excluida=False)\
                    .order_by(OrdemCarregamento.id).all()
    ocs_data = []

    for oc in ocs_abertas:
        etapas_dict = {e.codigo_etapa: e for e in oc.etapas}
        e010 = etapas_dict.get('010')

        cliente = transportadora = produto = '—'
        if e010:
            cliente        = _campo_valor(e010.dados, 'cliente')
            produto        = _campo_valor(e010.dados, 'produto')
            transportadora = _campo_valor(e010.dados, 'transportadora')

        # 040 check-in paralelo
        e040 = etapas_dict.get('040')
        placa_carreta = placa_cavalo = motorista = '—'
        if e040:
            placa_carreta = _campo_valor(e040.dados, 'placa_carreta')
            placa_cavalo  = _campo_valor(e040.dados, 'placa_cavalo')
            motorista     = _campo_valor(e040.dados, 'motorista_nome')

        # 020 PCP — número do lote
        e020 = etapas_dict.get('020')
        lote = '—'
        if e020:
            lote = _campo_valor(e020.dados, 'numero_lote')

        checkin_ts = None
        checkin_espera_fixa = None
        if e040 and e040.fim:
            checkin_ts = calendar.timegm(e040.fim.timetuple())
            e050 = etapas_dict.get('050')
            if e050 and e050.inicio:
                checkin_espera_fixa = int(
                    max(0, (e050.inicio - e040.fim).total_seconds() / 60))

        # Timer 1: Check-in (040.fim) → Checklist de Entrada (060.fim)
        e060 = etapas_dict.get('060')
        w1_from = calendar.timegm(e040.fim.timetuple()) if (e040 and e040.fim) else None
        w1_to   = calendar.timegm(e060.fim.timetuple()) if (e060 and e060.fim) else None

        # Timer 2: Checklist de Entrada (060.fim) → início do Carregamento (080.inicio)
        e080 = etapas_dict.get('080')
        w2_from = calendar.timegm(e060.fim.timetuple()) if (e060 and e060.fim) else None
        w2_to   = calendar.timegm(e080.inicio.timetuple()) if (e080 and e080.inicio) else None

        # Fluxo sequencial (sem 040)
        ordem = _ordem_efetiva(cliente)
        etapa_codigo = etapa_nome = etapa_area = '—'
        etapa_inicio_ts = calendar.timegm(oc.data_criacao.timetuple())
        ultimo_fim_ts   = etapa_inicio_ts

        for codigo in ordem:
            if codigo in etapas_dict:
                e = etapas_dict[codigo]
                if e.fim is None:
                    etapa_codigo    = codigo
                    etapa_nome      = ETAPAS.get(codigo,'—')
                    etapa_area      = AREAS.get(codigo,'—')
                    etapa_inicio_ts = calendar.timegm(e.inicio.timetuple())
                    break
                if e.fim:
                    ultimo_fim_ts = calendar.timegm(e.fim.timetuple())
            else:
                etapa_codigo    = codigo
                etapa_nome      = ETAPAS.get(codigo,'—')
                etapa_area      = AREAS.get(codigo,'—')
                etapa_inicio_ts = ultimo_fim_ts
                break

        ocs_data.append({
            'id': oc.id, 'numero_oc': oc.numero_oc,
            'cliente': cliente, 'produto': produto,
            'transportadora': transportadora, 'placa_carreta': placa_carreta,
            'placa_cavalo': placa_cavalo, 'motorista': motorista, 'lote': lote,
            'etapa_codigo': etapa_codigo, 'etapa_nome': etapa_nome,
            'etapa_area': etapa_area,
            'criacao_ts':           calendar.timegm(oc.data_criacao.timetuple()),
            'etapa_inicio_ts':      etapa_inicio_ts,
            'checkin_ts':           checkin_ts,
            'checkin_espera_fixa':  checkin_espera_fixa,
            'w1_from_ts':           w1_from,
            'w1_to_ts':             w1_to,
            'w2_from_ts':           w2_from,
            'w2_to_ts':             w2_to,
        })

    return render_template('acompanhamento.html',
                           ocs_json=json.dumps(ocs_data),
                           meta_json=json.dumps(TEMPO_META))


@bp.route('/dashboard/gerencial')
@login_required
def dashboard_gerencial():
    from models import OrdemCarregamento
    from helpers import _campo_valor

    data_ini_str = request.args.get('data_ini','')
    data_fim_str = request.args.get('data_fim','')

    # Inclui TODAS as OCs (inclusive excluídas) para visão completa da programação
    query = OrdemCarregamento.query
    if data_ini_str:
        try:
            query = query.filter(OrdemCarregamento.data_criacao >=
                                 datetime.strptime(data_ini_str,'%Y-%m-%d'))
        except ValueError: pass
    if data_fim_str:
        try:
            df = datetime.strptime(data_fim_str,'%Y-%m-%d').replace(hour=23,minute=59,second=59)
            query = query.filter(OrdemCarregamento.data_criacao <= df)
        except ValueError: pass

    ocs = query.order_by(OrdemCarregamento.id.desc()).all()

    MOTIVOS = {
        'NAO_COMPARECEU': 'Não Compareceu',
        'ALTERACAO_PROG': 'Alteração de Programação',
        'CANCELAMENTO':   'Cancelamento Operacional',
        'OUTRO':          'Outro',
    }

    def dur_e(etapas_dict, codigo):
        e = etapas_dict.get(codigo)
        return e.duracao if e and e.duracao else 0

    def avg_hm(lst):
        if not lst: return '—'
        avg = sum(lst) / len(lst)
        return f"{int(avg//60)}:{int(avg%60):02d}"

    tabela = []; detalhes = {}
    por_produto = {}
    tempo_por_etapa = {c: [] for c in ORDEM_ETAPAS}
    tempos_fase = {'criacao_lote':[], 'entrada':[], 'carregamento':[], 'laboratorio':[], 'faturamento':[]}
    kpis_count  = {'faturada':0, 'em_andamento':0, 'nao_compareceu':0, 'alteracao_prog':0, 'cancelamento':0}
    tempo_max_ref = sum(TEMPO_META.values())

    for oc in ocs:
        etapas_dict = {e.codigo_etapa: e for e in oc.etapas}
        e010 = etapas_dict.get('010')

        cliente = produto = transportadora = '—'
        if e010:
            cliente        = _campo_valor(e010.dados, 'cliente')
            produto        = _campo_valor(e010.dados, 'produto')
            transportadora = _campo_valor(e010.dados, 'transportadora')

        # Volume (t) = (pesagem_final - pesagem_inicial) / 1000
        volume = None
        e070 = etapas_dict.get('070')
        e090 = etapas_dict.get('090')
        if e070 and e090:
            v070 = _campo_valor(e070.dados, 'pesagem_inicial')
            v090 = _campo_valor(e090.dados, 'pesagem_final')
            if v070 != '—' and v090 != '—':
                try:
                    vol_kg = float(v090) - float(v070)
                    if vol_kg > 0: volume = round(vol_kg / 1000, 1)
                except (ValueError, TypeError): pass

        # Status
        if oc.excluida:
            motivo_k = (oc.motivo_cancelamento or 'OUTRO').upper()
            status_display = MOTIVOS.get(motivo_k, 'Cancelada')
            if motivo_k == 'NAO_COMPARECEU':  kpis_count['nao_compareceu'] += 1
            elif motivo_k == 'ALTERACAO_PROG': kpis_count['alteracao_prog'] += 1
            else:                              kpis_count['cancelamento']   += 1
        elif oc.status == 'concluida':
            status_display = 'Faturada'; kpis_count['faturada'] += 1
        else:
            status_display = 'Em Andamento'; kpis_count['em_andamento'] += 1

        ordem_oc = _ordem_efetiva(cliente)
        etapa_codigo = etapa_nome = '—'
        for codigo in ordem_oc:
            if codigo in etapas_dict:
                if etapas_dict[codigo].fim is None:
                    etapa_codigo = codigo; etapa_nome = ETAPAS.get(codigo,'—'); break
            else:
                etapa_codigo = codigo; etapa_nome = ETAPAS.get(codigo,'—'); break

        total_min = 0; etapas_detalhe = []
        for codigo in ordem_oc:
            e    = etapas_dict.get(codigo)
            dur  = e.duracao if e and e.duracao is not None else None
            regs = e.dados if e else []
            if dur is not None:
                total_min += dur
                if codigo in tempo_por_etapa: tempo_por_etapa[codigo].append(dur)
            etapas_detalhe.append({
                'codigo': codigo, 'nome': ETAPAS.get(codigo,''), 'duracao': dur,
                'dados': [{'campo': r.campo, 'valor': r.valor} for r in regs]
            })

        # Tempos por fase (só faturadas)
        if oc.status == 'concluida':
            clt = dur_e(etapas_dict,'020')
            if clt: tempos_fase['criacao_lote'].append(clt)
            ent = dur_e(etapas_dict,'040') + dur_e(etapas_dict,'050') + dur_e(etapas_dict,'060')
            if ent: tempos_fase['entrada'].append(ent)
            car = dur_e(etapas_dict,'080')
            if car: tempos_fase['carregamento'].append(car)
            lab = dur_e(etapas_dict,'030') + dur_e(etapas_dict,'110')
            if lab: tempos_fase['laboratorio'].append(lab)
            fat = dur_e(etapas_dict,'120')
            if fat: tempos_fase['faturamento'].append(fat)

        # Acumula por produto
        if produto not in por_produto:
            por_produto[produto] = {'count':0, 'volume':0.0, 'tempos':[]}
        por_produto[produto]['count'] += 1
        if volume: por_produto[produto]['volume'] += volume
        if total_min: por_produto[produto]['tempos'].append(total_min)

        status_t = 'na' if total_min==0 else ('critico' if total_min>tempo_max_ref else 'ok')
        pct = round((total_min/tempo_max_ref)*100) if total_min else 0

        tabela.append({
            'oc': oc, 'cliente': cliente, 'produto': produto,
            'transportadora': transportadora, 'volume': volume,
            'etapa_codigo': etapa_codigo, 'etapa_nome': etapa_nome,
            'tempo_total': total_min or None, 'tempo_total_status': status_t,
            'tempo_pct': pct, 'tempo_max': tempo_max_ref,
            'status_display': status_display,
        })
        detalhes[oc.id] = {
            'numero_oc': oc.numero_oc, 'cliente': cliente, 'produto': produto,
            'transportadora': transportadora,
            'data_criacao': oc.data_criacao.strftime('%d/%m/%Y %H:%M'),
            'status': oc.status, 'etapas': etapas_detalhe,
        }

    total_ocs = len(ocs)
    kpis = {
        'total':           total_ocs,
        'faturada':        kpis_count['faturada'],
        'em_andamento':    kpis_count['em_andamento'],
        'nao_compareceu':  kpis_count['nao_compareceu'],
        'alteracao_prog':  kpis_count['alteracao_prog'],
        'cancelamento':    kpis_count['cancelamento'],
    }

    tempos_medios = {
        'criacao_lote': avg_hm(tempos_fase['criacao_lote']),
        'entrada':      avg_hm(tempos_fase['entrada']),
        'carregamento': avg_hm(tempos_fase['carregamento']),
        'laboratorio':  avg_hm(tempos_fase['laboratorio']),
        'faturamento':  avg_hm(tempos_fase['faturamento']),
    }

    tabela_produto = sorted([
        {'produto': p, 'count': d['count'],
         'volume': round(d['volume'],1), 'tempo_medio': avg_hm(d['tempos'])}
        for p, d in por_produto.items()
    ], key=lambda x: x['count'], reverse=True)

    labels_g = [c for c in ORDEM_ETAPAS if c != '010']
    grafico = {
        'etapas': [ETAPAS.get(c, c) for c in labels_g],
        'medias': [round(sum(tempo_por_etapa[c])/len(tempo_por_etapa[c]),1)
                   if tempo_por_etapa[c] else 0 for c in labels_g],
        'metas':  [TEMPO_META.get(c) for c in labels_g],
    }

    return render_template('dashboard_gerencial.html',
        kpis=kpis, tabela=tabela,
        tabela_produto=tabela_produto, tempos_medios=tempos_medios,
        grafico_json=json.dumps(grafico), detalhes_json=json.dumps(detalhes),
        meta_json=json.dumps(TEMPO_META), etapas_json=json.dumps(ETAPAS),
        labels_campos_json=json.dumps(LABELS_CAMPOS),
        labels_ass_json=json.dumps(LABELS_ASS),
        campos_ass_json=json.dumps(CAMPOS_ASSINATURAS),
        campos_fotos_json=json.dumps(CAMPOS_FOTOS),
        data_ini=data_ini_str, data_fim=data_fim_str,
    )


@bp.route('/dashboard/gerencial/exportar')
@login_required
def exportar_csv():
    from models import OrdemCarregamento

    data_ini_str = request.args.get('data_ini','')
    data_fim_str = request.args.get('data_fim','')

    query = OrdemCarregamento.query
    if data_ini_str:
        try:
            query = query.filter(OrdemCarregamento.data_criacao >=
                                 datetime.strptime(data_ini_str,'%Y-%m-%d'))
        except ValueError: pass
    if data_fim_str:
        try:
            df = datetime.strptime(data_fim_str,'%Y-%m-%d').replace(hour=23,minute=59,second=59)
            query = query.filter(OrdemCarregamento.data_criacao <= df)
        except ValueError: pass

    ocs = query.order_by(OrdemCarregamento.id).all()

    MOTIVOS = {
        'NAO_COMPARECEU': 'Não Compareceu',
        'ALTERACAO_PROG': 'Alteração de Programação',
        'CANCELAMENTO':   'Cancelamento Operacional',
        'OUTRO':          'Outro',
    }

    buf = io.StringIO()
    w   = csv.writer(buf, delimiter=';')

    w.writerow([
        'Número OC', 'Data Criação', 'Status', 'Motivo Cancelamento',
        'Produto', 'Cliente', 'Transportadora',
        'Placa Carreta', 'Placa Cavalo', 'Motorista',
        'Pesagem Inicial (kg)', 'Pesagem Final (kg)', 'Volume (t)',
        'Número NF', 'Número Ticket',
        'PCP (020) min',
        'LCQ Inicial (030) min',
        'Check-in (040) min',
        'Espera Entrada 040→050 min',
        'Liberação Entrada (050) min',
        'Checklist Entrada (060) min',
        'Balança Inicial (070) min',
        'Checklist Carga (080) min',
        'Balança Final (090) min',
        'Check-out (100) min',
        'LCQ Final (110) min',
        'Faturamento (120) min',
        'Fase Entrada (040+050+060) min',
        'Fase Carregamento (080) min',
        'Fase Laboratório (030+110) min',
        'Fase Faturamento (120) min',
        'Tempo Total min',
    ])

    for oc in ocs:
        etapas_dict = {e.codigo_etapa: e for e in oc.etapas}

        # Achata todos os dados em um único dict (último valor vence para campos repetidos)
        dados = {}
        for e in oc.etapas:
            for d in e.dados:
                dados[d.campo] = d.valor or ''

        def dur(c):
            e = etapas_dict.get(c)
            return e.duracao if e and e.duracao is not None else ''

        def dur_int(c):
            e = etapas_dict.get(c)
            return e.duracao if e and e.duracao else 0

        def val(c):
            return dados.get(c, '')

        # Status
        if oc.excluida:
            mk = (oc.motivo_cancelamento or 'OUTRO').upper()
            status = MOTIVOS.get(mk, 'Cancelada')
            motivo = status
        elif oc.status == 'concluida':
            status, motivo = 'Faturada', ''
        else:
            status, motivo = 'Em Andamento', ''

        # Volume em toneladas
        volume = ''
        try:
            pi = float(dados.get('pesagem_inicial','') or 0)
            pf = float(dados.get('pesagem_final','')   or 0)
            if pf > pi: volume = round((pf - pi) / 1000, 1)
        except (ValueError, TypeError): pass

        # Espera entrada: intervalo entre fim do check-in (040) e início da liberação (050)
        espera_entrada = ''
        e040 = etapas_dict.get('040')
        e050 = etapas_dict.get('050')
        if e040 and e040.fim and e050 and e050.inicio:
            diff = (e050.inicio - e040.fim).total_seconds() / 60
            if diff >= 0: espera_entrada = round(diff, 1)

        # Fases agregadas
        fase_entrada      = dur_int('040') + dur_int('050') + dur_int('060') or ''
        fase_carregamento = dur_int('080') or ''
        fase_laboratorio  = dur_int('030') + dur_int('110') or ''
        fase_faturamento  = dur_int('120') or ''
        total_min         = sum(dur_int(c) for c in _ordem_efetiva(val('cliente'))) or ''

        w.writerow([
            oc.numero_oc,
            oc.data_criacao.strftime('%d/%m/%Y %H:%M'),
            status, motivo,
            val('produto'), val('cliente'), val('transportadora'),
            val('placa_carreta'), val('placa_cavalo'), val('motorista_nome'),
            val('pesagem_inicial'), val('pesagem_final'), volume,
            val('numero_nf'), val('numero_ticket'),
            dur('020'), dur('030'), dur('040'), espera_entrada,
            dur('050'), dur('060'), dur('070'), dur('080'),
            dur('090'), dur('100'), dur('110'), dur('120'),
            fase_entrada, fase_carregamento, fase_laboratorio, fase_faturamento,
            total_min,
        ])

    nome = 'relatorio_ocs'
    if data_ini_str: nome += f'_{data_ini_str}'
    if data_fim_str: nome += f'_a_{data_fim_str}'
    nome += '.csv'

    # BOM UTF-8 (﻿) para o Excel abrir com acentuação correta
    return Response(
        '﻿' + buf.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{nome}"'}
    )
