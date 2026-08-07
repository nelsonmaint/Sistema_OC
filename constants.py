ETAPAS = {
    "010": "Solicitação de Carregamento",
    "020": "PCP",
    "030": "LCQ Inicial",
    "040": "Check-in Portaria",
    "050": "Liberação de Entrada",
    "060": "Checklist de Entrada",
    "070": "Balança Inicial",
    "080": "Checklist de Carregamento",
    "090": "Balança Final",
    "100": "Check-out",
    "110": "LCQ Final",
    "120": "Faturamento"
}

ORDEM_ETAPAS = [
    "010","020","030","050","060",
    "070","080","090","100","110","120"
]

AREAS = {
    "010": "Faturamento",
    "020": "PCP",
    "030": "Laboratório",
    "040": "Portaria",
    "050": "Produção",
    "060": "Portaria",
    "070": "Faturamento",
    "080": "Produção",
    "090": "Faturamento",
    "100": "Portaria",
    "110": "Laboratório",
    "120": "Faturamento"
}

TEMPO_META = {
    "020": 10, "030": 20, "040": 15, "050": 15,
    "060": 10, "070": 8,  "080": 30, "090": 8,
    "100": 10, "110": 20, "120": 15
}

PERMISSOES = {
    "Administrativo": ["010","020","030","040","050","060","070","080","090","100","110","120"],
    "Faturamento":    ["010","070","090","120"],
    "Portaria":       ["040","060","100"],
    "Produção":       ["050","080"],
    "Laboratório":    ["030","110"],
    "PCP":            ["020"]
}

CLIENTE_LCQ_FINAL = 'DA FONTE'   # substring em upper() → "Raymundo da Fonte"

EXTENSOES_IMAGEM_PERMITIDAS = {'png', 'jpg', 'jpeg', 'webp'}

AREAS_CADASTRO = [
    "Administrativo","Faturamento","Portaria",
    "Produção","Laboratório","PCP"
]

CAMPOS_ASSINATURAS = [
    'assinatura_motorista','assinatura_faturamento',
    'assinatura_vigilante','assinatura_operador',
    'assinatura_supervisor_antes','assinatura_supervisor_depois'
]

CAMPOS_FOTOS = [
    'imagem','img_parte_superior','img_nivel',
    'img_domo','img_lacres','img_mangueira_reservatorio','img_valvula'
]

LABELS_CAMPOS = {
    'numero_lote':'Número do Lote','tanque':'Número do Tanque',
    'aprovacao':'Aprovação','motorista_nome':'Nome do Motorista',
    'cliente':'Cliente','transportadora':'Transportadora','produto':'Produto',
    'placa_carreta':'Placa Carreta','placa_cavalo':'Placa Cavalo',
    'aspecto_fisico':'Aspecto Físico','epis_ok':'EPIs Adequados',
    'mope':'Curso MOPE','civ_carreta':'CIV Carreta','civ_cavalo':'CIV Cavalo',
    'cipp':'CIPP','checkin_doc':'Check-in Documental',
    'entrada_liberada':'Entrada Liberada',
    'rotulos_risco':'Rótulos de Risco','painel_seguranca':'Painel de Segurança',
    'pneus':'Pneus','luzes':'Luzes','fios':'Fios','cabine':'Cabine',
    'tanque_combustivel':'Tanque Combustível','motor_arranque':'Motor de Arranque',
    'parachoque':'Para-choque','tanque_carga':'Tanque de Carga',
    'valvulas':'Válvulas','cabo_terra':'Cabo Terra','lacracao':'Lacração',
    'junta':'Junta','fumaca':'Emissão de Fumaça',
    'extintor':'Extintor','cinto':'Cinto','tacografo':'Tacógrafo',
    'kit_seguranca':'Kit de Segurança','aprovado':'Veículo Aprovado',
    'observacoes':'Observações','pesagem_inicial':'Pesagem Inicial (t)',
    'pesagem_final':'Pesagem Final (t)','numero_ticket':'Número do Ticket',
    'tanque_adequado':'Tanque Adequado','tanque_limpo':'Tanque Limpo',
    'parafusos_valvulas':'Parafusos/Válvulas','junta_vedacao':'Junta de Vedação',
    'valvula_suspiro':'Válvula do Suspiro','nivel_alinhado':'Nível Alinhado',
    'regua_utilizada':'Régua Utilizada','fechamento_domo':'Fechamento Domo',
    'domo_limpo':'Domo Limpo','lacres_ok':'Lacres OK',
    'mangueira_conectada':'Mangueira Conectada',
    'reservatorio_vazio':'Reservatório Vazio',
    'numero_amostra':'Número da Amostra','numero_lacre':'Número do Lacre',
    'valvula_fechada':'Válvula Fechada','numero_nf':'Número da NF',
    'pedido_de_venda':'Pedido de Venda','tipo_de_frete':'Tipo de Frete',
    'codigo_produto':'Código do Produto','lote':'Nº Lote',
}

LABELS_ASS = {
    'assinatura_motorista':'Motorista','assinatura_faturamento':'Faturamento',
    'assinatura_vigilante':'Vigilante','assinatura_operador':'Operador',
    'assinatura_supervisor_antes':'Supervisor (antes)',
    'assinatura_supervisor_depois':'Supervisor (depois)',
}
