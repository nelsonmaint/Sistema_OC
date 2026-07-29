import sqlite3, os
possiveis = [os.path.join('instance','database.db'), 'database.db']
caminho   = next((p for p in possiveis if os.path.exists(p)), None)
if not caminho: print('ERRO: database.db nao encontrado.'); exit()

conn = sqlite3.connect(caminho)
cur  = conn.cursor()
cur.execute("PRAGMA table_info(ordem_carregamento)")
colunas = [r[1] for r in cur.fetchall()]

if 'motivo_cancelamento' not in colunas:
    cur.execute("ALTER TABLE ordem_carregamento ADD COLUMN motivo_cancelamento VARCHAR(30)")
    conn.commit()
    print('Coluna motivo_cancelamento adicionada.')
else:
    print('Coluna motivo_cancelamento ja existe.')

conn.close()
