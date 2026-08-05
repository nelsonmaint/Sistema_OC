import sqlite3
import os

# Procura o banco nos dois lugares possíveis
possiveis = [
    os.path.join('instance', 'database.db'),
    'database.db'
]

caminho = None
for p in possiveis:
    if os.path.exists(p):
        caminho = p
        break

if not caminho:
    print('ERRO: database.db não encontrado.')
    print('Arquivos na pasta atual:', os.listdir('.'))
    print('Arquivos em instance/:', os.listdir('instance') if os.path.exists('instance') else 'pasta não existe')
    exit()

print(f'Banco encontrado em: {caminho}')

conn   = sqlite3.connect(caminho)
cursor = conn.cursor()

# Ver colunas atuais da tabela user
cursor.execute("PRAGMA table_info(user)")
colunas = [row[1] for row in cursor.fetchall()]
print(f'Colunas atuais: {colunas}')

# Adicionar is_admin se não existir
if 'is_admin' not in colunas:
    cursor.execute("ALTER TABLE user ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0")
    conn.commit()
    print('Coluna is_admin adicionada!')
else:
    print('Coluna is_admin já existe.')

# Tornar o usuário admin
email = 'admin@teste.com' 
cursor.execute("UPDATE user SET is_admin = 1 WHERE email = ?", (email,))
conn.commit()

if cursor.rowcount > 0:
    print(f'Usuário {email} agora é admin!')
else:
    # Mostrar usuários cadastrados para ajudar a identificar
    cursor.execute("SELECT id, nome, email FROM user")
    usuarios = cursor.fetchall()
    print('Usuário não encontrado. Usuários cadastrados no banco:')
    for u in usuarios:
        print(f'  id={u[0]} | nome={u[1]} | email={u[2]}')

conn.close()
