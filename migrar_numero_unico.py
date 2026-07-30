import sqlite3, os

possiveis = [os.path.join('instance', 'database.db'), 'database.db']
caminho   = next((p for p in possiveis if os.path.exists(p)), None)
if not caminho:
    print('ERRO: database.db nao encontrado.')
    exit()

conn = sqlite3.connect(caminho)
cur  = conn.cursor()

cur.execute("""
    SELECT numero_oc, COUNT(*) FROM ordem_carregamento
    GROUP BY numero_oc HAVING COUNT(*) > 1
""")
duplicados = cur.fetchall()
if duplicados:
    print('ERRO: existem numero_oc duplicados, resolva antes de criar o indice unico:')
    for numero, qtd in duplicados:
        print(f'  {numero}: {qtd} ocorrencias')
    conn.close()
    exit()

cur.execute("PRAGMA index_list(ordem_carregamento)")
indices = [r[1] for r in cur.fetchall()]

if 'ix_ordem_carregamento_numero_oc' not in indices:
    cur.execute(
        "CREATE UNIQUE INDEX ix_ordem_carregamento_numero_oc "
        "ON ordem_carregamento (numero_oc)")
    conn.commit()
    print('Indice unico criado em numero_oc.')
else:
    print('Indice unico ja existe.')

conn.close()
