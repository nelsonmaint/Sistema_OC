"""
Execute este script UMA VEZ após atualizar models.py
para adicionar as colunas de exclusão suave na tabela ordem_carregamento.

Rode com:  python migrar_exclusao.py
"""
import sqlite3
import os

possiveis = [os.path.join('instance', 'database.db'), 'database.db']
caminho   = next((p for p in possiveis if os.path.exists(p)), None)

if not caminho:
    print('ERRO: database.db não encontrado.')
    exit()

print(f'Banco encontrado: {caminho}')
conn   = sqlite3.connect(caminho)
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(ordem_carregamento)")
colunas = [row[1] for row in cursor.fetchall()]
print(f'Colunas atuais: {colunas}')

novas = [
    ("excluida",               "BOOLEAN NOT NULL DEFAULT 0"),
    ("data_exclusao",          "DATETIME"),
    ("justificativa_exclusao", "TEXT"),
    ("excluida_por",           "INTEGER"),
]

for col, tipo in novas:
    if col not in colunas:
        cursor.execute(f"ALTER TABLE ordem_carregamento ADD COLUMN {col} {tipo}")
        conn.commit()
        print(f'  ✔ Coluna "{col}" adicionada.')
    else:
        print(f'  — Coluna "{col}" já existe.')

print('\nMigração concluída!')
conn.close()
