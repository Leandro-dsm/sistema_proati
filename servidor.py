from flask import Flask, request, jsonify, render_template, session
import pymysql
from pymysql.cursors import DictCursor
import bcrypt
from datetime import datetime
import secrets
from datetime import timedelta

# app = Flask(__name__)
# # Chave dinâmica para proteção das sessões
# app.secret_key = secrets.token_hex(32)

app = Flask(__name__)

app.config["SECRET_KEY"] = "geni_cunha_chave_super_secreta_2026"
app.config["SESSION_PERMANENT"] = True
app.permanent_session_lifetime = timedelta(hours=8)

# ============================================
# CONFIGURAÇÃO DO BANCO DE DADOS MYSQL
# ============================================
# ⚠️ SUBSTITUA 'seu_usuario' e 'sua_senha' PELAS SUAS CREDENCIAIS
DB_CONFIG = {
    'host': 'localhost',        # Se for local, mantenha 'localhost'
    'user': 'root',             # Usuário padrão do MySQL
    'password': 'mysql1234',    # ← COLOQUE A SENHA QUE VOCÊ DEFINIU
    'database': 'GeniCunha',    # Nome do banco de dados
    'charset': 'utf8mb4',
    'cursorclass': DictCursor   # Retorna resultados como dicionário
}

def obter_conexao():
    """Cria e retorna uma conexão com o MySQL"""
    return pymysql.connect(**DB_CONFIG)

def iniciar_banco():
    """Cria as tabelas necessárias se não existirem"""
    conn = obter_conexao()
    cursor = conn.cursor()
    
    # Tabela: Alunos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alunos (
            id_aluno INT AUTO_INCREMENT PRIMARY KEY,
            turma CHAR(2) NOT NULL,
            nome_aluno VARCHAR(100) NOT NULL,
            ra CHAR(14) UNIQUE
        )
    ''')
    
    # Tabela: Máquinas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS maquinas (
            id_maquina INT AUTO_INCREMENT PRIMARY KEY,
            numero_serie VARCHAR(20) UNIQUE,
            nome_maquina VARCHAR(20),
            descricao TEXT,
            status_maquina ENUM(
                "disponivel",
                "em manutencao",
                "analise",
                "indisponivel"
            ) DEFAULT "disponivel"
        )
    ''')
    
    # Tabela: Movimentações (Empréstimos)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movimentacoes (
            id_movimentacao INT AUTO_INCREMENT PRIMARY KEY,
            id_aluno INT NOT NULL,
            id_maquina INT NOT NULL,
            data_retirada DATETIME DEFAULT CURRENT_TIMESTAMP,
            data_devolucao DATETIME NULL,
            status_movimentacao ENUM('em_uso', 'devolvido') DEFAULT 'em_uso',
            CONSTRAINT fk_movimentacao_aluno
                FOREIGN KEY (id_aluno) REFERENCES alunos(id_aluno)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT fk_movimentacao_maquina
                FOREIGN KEY (id_maquina) REFERENCES maquinas(id_maquina)
                ON DELETE RESTRICT ON UPDATE CASCADE
        )
    ''')
    
    # Tabela: Usuários Administrativos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INT AUTO_INCREMENT PRIMARY KEY,
            usuario VARCHAR(10) UNIQUE NOT NULL,
            senha_hash TEXT NOT NULL
        )
    ''')
    
    # Tabela: Logs Automáticos (heartbeat das máquinas)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs_automaticos (
            id INT AUTO_INCREMENT PRIMARY KEY,
            notebook VARCHAR(50) UNIQUE NOT NULL,
            usuario_windows VARCHAR(100) NOT NULL,
            horario VARCHAR(20) NOT NULL
        )
    ''')
    
    # Tabela: Logs do Sistema (Auditoria)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs_sistema (
            id INT AUTO_INCREMENT PRIMARY KEY,
            usuario_admin VARCHAR(50) NOT NULL,
            acao VARCHAR(50) NOT NULL,
            detalhes TEXT NOT NULL,
            horario VARCHAR(20) NOT NULL
        )
    ''')
    
    # Cria usuário admin padrão
    cursor.execute("SELECT * FROM usuarios WHERE usuario = 'admin'")
    if not cursor.fetchone():
        senha_plana = "admin123".encode('utf-8')
        sal = bcrypt.gensalt(12)
        hash_seguro = bcrypt.hashpw(senha_plana, sal).decode('utf-8')
        cursor.execute("INSERT INTO usuarios (usuario, senha_hash) VALUES ('admin', %s)", (hash_seguro,))
    
    conn.commit()
    conn.close()
    print("✅ Banco de dados inicializado com sucesso!")

# ============================================
# DECORATOR PARA VALIDAÇÃO DE SESSÃO
# ============================================
def login_obrigatorio(f):
    def decorada(*args, **kwargs):
        if 'usuario_logado' not in session:
            return jsonify({"status": "Erro", "mensagem": "Sessão expirada. Autentique-se."}), 401
        return f(*args, **kwargs)
    decorada.__name__ = f.__name__
    return decorada

# ============================================
# ROTAS DA API
# ============================================
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    dados = request.json or {}
    usuario = dados.get('usuario', '').strip()
    senha = dados.get('senha', '').strip()
    
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("SELECT senha_hash FROM usuarios WHERE usuario = %s", (usuario,))
    registro = cursor.fetchone()
    conn.close()

    if registro and bcrypt.checkpw(senha.encode('utf-8'), registro['senha_hash'].encode('utf-8')):

        session.permanent = True
        session['usuario_logado'] = usuario

        return jsonify({
            "status": "OK"
        }), 200
    
    # if registro and bcrypt.checkpw(senha.encode('utf-8'), registro['senha_hash'].encode('utf-8')):
    #     session['usuario_logado'] = usuario
    #     return jsonify({"status": "OK", "usuario": usuario}), 200
    
    return jsonify({"status": "Erro", "mensagem": "Credenciais incorretas."}), 401

@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.pop('usuario_logado', None)
    return jsonify({"status": "OK"}), 200

@app.route('/api/emprestimo', methods=['POST'])
@login_obrigatorio
def criar_emprestimo():
    dados = request.json or {}
    notebook = dados.get('notebook', '').upper().strip()
    aluno = dados.get('aluno', '').strip()
    #sala = dados.get('sala_aluno', '').strip()
    #local = dados.get('local_notebook', '').strip()
    agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if not notebook or not aluno:
        return jsonify({"status": "Erro", "mensagem": "Campos obrigatórios ausentes."}), 400

    conn = obter_conexao()
    cursor = conn.cursor()
    
    # Verifica se o aluno já existe
    cursor.execute("SELECT id_aluno FROM alunos WHERE id_aluno = %s", (aluno,))
    aluno_existente = cursor.fetchone()
    
    if aluno_existente:
        id_aluno = aluno_existente['id_aluno']
    # else:
    #     cursor.execute("INSERT INTO alunos (nome_aluno, turma) VALUES (%s, %s)", (aluno, sala))
    #     id_aluno = cursor.lastrowid
    
    # Verifica se a máquina já existe
    cursor.execute("SELECT id_maquina FROM maquinas WHERE id_maquina = %s", (notebook,))
    maquina_existente = cursor.fetchone()
    
    if maquina_existente:
        id_maquina = maquina_existente['id_maquina']
    # else:
    #     cursor.execute("INSERT INTO maquinas (nome_maquina, descricao) VALUES (%s, %s)", (notebook, local))
    #     id_maquina = cursor.lastrowid
    
    # Cria a movimentação
    cursor.execute('''
        INSERT INTO movimentacoes (id_aluno, id_maquina, data_retirada, status_movimentacao)
        VALUES (%s, %s, %s, 'em_uso')
    ''', (id_aluno, id_maquina, agora))

    # Atualiza o status da máquina para "em uso"
    cursor.execute("UPDATE maquinas SET status_maquina = 'indisponivel' WHERE id_maquina = %s", (id_maquina,))
    
    # Log da ação
    cursor.execute("INSERT INTO logs_sistema (usuario_admin, acao, detalhes, horario) VALUES (%s, 'CRIAR_EMPRESTIMO', %s, %s)",
                   (session['usuario_logado'], f"Notebook {notebook} alocado para {aluno}", agora))
    
    conn.commit()
    conn.close()
    return jsonify({"status": "OK"}), 200

@app.route('/api/dashboard', methods=['GET'])
@login_obrigatorio
def buscar_dados():
    conn = obter_conexao()
    cursor = conn.cursor()
    
    # Busca empréstimos ativos
    cursor.execute('''
        SELECT m.id_movimentacao AS id, a.turma AS turma, a.nome_aluno AS aluno,
        ma.nome_maquina AS notebook, ma.descricao AS descricao, m.status_movimentacao, m.data_retirada
        FROM movimentacoes m JOIN alunos a ON m.id_aluno = a.id_aluno JOIN maquinas ma ON m.id_maquina = ma.id_maquina
        ORDER BY m.id_movimentacao DESC;
    ''')
    emprestados = [dict(row) for row in cursor.fetchall()]
    
    # Busca logs automáticos
    cursor.execute("SELECT notebook, usuario_windows, horario FROM logs_automaticos ORDER BY horario DESC")
    logs = [dict(row) for row in cursor.fetchall()]
    
    # Gráfico: Top 5 salas
    cursor.execute('''
        SELECT a.turma as sala_aluno, COUNT(*) as qtd 
        FROM movimentacoes m
        JOIN alunos a ON m.id_aluno = a.id_aluno
        GROUP BY a.turma 
        ORDER BY qtd DESC 
        LIMIT 5
    ''')
    grafico_salas = [{"sala": row['sala_aluno'], "qtd": row['qtd']} for row in cursor.fetchall()]
    
    conn.close()
    return jsonify({
        "total_emprestados": len(emprestados),
        "emprestimos": emprestados,
        "logs": logs,
        "grafico_salas": grafico_salas
    })

@app.route('/api/emprestimo/<int:id>', methods=['PUT'])
@login_obrigatorio
def atualizar_emprestimo(id):
    dados = request.json or {}
    notebook = dados.get('notebook', '').upper().strip()
    aluno = dados.get('aluno', '').strip()
    # sala = dados.get('sala_aluno', '').strip()
    # local = dados.get('local_notebook', '').strip()
    agora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

    conn = obter_conexao()
    cursor = conn.cursor()
    
    # Atualiza aluno
    cursor.execute("""
        UPDATE alunos 
        SET nome_aluno = %s, turma = %s 
        WHERE id_aluno = (SELECT id_aluno FROM movimentacoes WHERE id_movimentacao = %s)
    """, (aluno, sala, id))
    
    # Atualiza máquina
    cursor.execute("""
        UPDATE maquinas 
        SET nome_maquina = %s, descricao = %s 
        WHERE id_maquina = (SELECT id_maquina FROM movimentacoes WHERE id_movimentacao = %s)
    """, (notebook, local, id))
    
    # Log da ação
    cursor.execute("INSERT INTO logs_sistema (usuario_admin, acao, detalhes, horario) VALUES (%s, 'EDITAR_EMPRESTIMO', %s, %s)",
                   (session['usuario_logado'], f"Alterou ID {id} para {notebook} - {aluno}", agora))
    
    conn.commit()
    conn.close()
    return jsonify({"status": "OK"}), 200

@app.route('/api/emprestimo/<int:id>', methods=['DELETE'])
@login_obrigatorio
def deletar_emprestimo(id):
    agora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    conn = obter_conexao()
    cursor = conn.cursor()
    
    # Busca dados antes de deletar
    cursor.execute('''
        SELECT a.nome_aluno, ma.nome_maquina 
        FROM movimentacoes m
        JOIN alunos a ON m.id_aluno = a.id_aluno
        JOIN maquinas ma ON m.id_maquina = ma.id_maquina
        WHERE m.id_movimentacao = %s
    ''', (id,))
    dados = cursor.fetchone()

    #Atualiza o status da máquina para "disponivel" antes de deletar a movimentação
    cursor.execute('''
        UPDATE maquinas ma
        JOIN movimentacoes m ON ma.id_maquina = m.id_maquina
        SET ma.status_maquina = 'disponivel'
        WHERE m.id_movimentacao = %s
    ''', (id,))

    if dados:
        cursor.execute("INSERT INTO logs_sistema (usuario_admin, acao, detalhes, horario) VALUES (%s, 'DELETAR_EMPRESTIMO', %s, %s)",
                       (session['usuario_logado'], f"Removeu ID {id} - {dados['nome_aluno']} / {dados['nome_maquina']}", agora))
    
    cursor.execute("DELETE FROM movimentacoes WHERE id_movimentacao = %s", (id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "OK"}), 200

@app.route('/api/logon', methods=['POST'])
def receber_logon():
    if request.headers.get('User-Agent') != "GENI-Core-Secure-Heartbeat/3.0":
        return jsonify({"status": "Erro", "mensagem": "Acesso não autorizado."}), 403
        
    dados = request.json or {}
    notebook = dados.get('notebook', '').upper().strip()
    usuario = dados.get('usuario', '').strip()
    agora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    
    conn = obter_conexao()
    cursor = conn.cursor()
    
    # UPSERT: Se o notebook já existir, atualiza
    cursor.execute('''
        INSERT INTO logs_automaticos (notebook, usuario_windows, horario) 
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE 
            usuario_windows = VALUES(usuario_windows),
            horario = VALUES(horario)
    ''', (notebook, usuario, agora))
    
    conn.commit()
    conn.close()
    return jsonify({"status": "OK"}), 200

@app.route('/api/logs', methods=['DELETE'])
@login_obrigatorio
def limpar_todos_logs():
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM logs_automaticos")
    conn.commit()
    conn.close()
    return jsonify({"status": "OK"}), 200

@app.route('/api/notebooks', methods=['GET'])
@login_obrigatorio
def listar_notebooks():
    """Lista todos os notebooks disponíveis"""
    conn = obter_conexao()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id_maquina, nome_maquina
        FROM maquinas
        WHERE status_maquina = 'disponivel'
        ORDER BY nome_maquina
    ''')

    notebooks = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify(notebooks), 200

@app.route('/api/todos-notebooks', methods=['GET'])
@login_obrigatorio
def listar_todos_notebooks():
    """Lista todos os notebooks"""
    conn = obter_conexao()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id_maquina, nome_maquina, numero_serie, descricao, status_maquina
        FROM maquinas
        ORDER BY nome_maquina
    ''')

    notebooks = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify(notebooks), 200

@app.route('/api/cadastrar-notebook', methods=['POST'])
@login_obrigatorio
def cadastrar_notebook():

    if 'excel' not in request.files:
        return jsonify({
            "mensagem": "Nenhum arquivo enviado"
        }), 400

    arquivo = request.files['excel']

    if arquivo.filename == '':
        return jsonify({
            "mensagem": "Nome do arquivo vazio"
        }), 400

    if not arquivo.filename.lower().endswith(('.xlsx', '.xls')):
        return jsonify({
            "mensagem": "Formato inválido. Use .xlsx ou .xls"
        }), 400

    conn = None

    try:

        import pandas as pd

        # Ler Excel
        df = pd.read_excel(arquivo)

        # Remove somente linhas totalmente vazias
        df = df.dropna(
            subset=df.columns,
            how='all'
        )

        # Normaliza cabeçalhos
        df.columns = (
            df.columns
            .astype(str)
            .str.strip()
            .str.lower()
        )

        # Encontrar colunas
        mapa = {}

        for col in df.columns:

            nome = (
                col
                .replace(" ", "")
                .replace("_", "")
            )

            if "numeroserie" in nome:
                mapa["serie"] = col

            elif "descricao" in nome:
                mapa["descricao"] = col

            elif "statuschamado" in nome:
                mapa["status"] = col

            elif "nomemaquina" in nome:
                mapa["maquina"] = col

        conn = obter_conexao()
        cursor = conn.cursor()

        total_importados = 0

        for _, row in df.iterrows():

            def pegar(chave):

                coluna = mapa.get(chave)

                if not coluna:
                    return ''

                valor = row[coluna]

                if pd.isna(valor):
                    return ''

                return str(valor).strip()

            numero_serie = pegar("serie")
            descricao = pegar("descricao")
            status = pegar("status")
            nome_maquina = pegar("maquina")

            # Remove valores "nan"
            numero_serie = (
                ''
                if numero_serie.lower() == 'nan'
                else numero_serie
            )

            descricao = (
                ''
                if descricao.lower() == 'nan'
                else descricao
            )

            status = (
                ''
                if status.lower() == 'nan'
                else status
            )

            nome_maquina = (
                ''
                if nome_maquina.lower() == 'nan'
                else nome_maquina
            )

            # Impede máquina fantasma
            if not any([
                numero_serie,
                descricao,
                status,
                nome_maquina
            ]):
                continue

            # Ajustar status
            status_upper = status.upper()

            if status_upper == 'OK':
                status = 'disponivel'

            elif status_upper == 'NF' or status_upper == 'NF CHAMADO':
                status = 'em manutencao'

            elif status_upper ==  "*":
                status = 'indisponivel'

            else:
                status = 'disponivel'

            # Converter vazio para NULL
            numero_serie = numero_serie or None
            descricao = descricao or None
            nome_maquina = nome_maquina or None

            cursor.execute(
                """
                INSERT INTO maquinas
                (
                    numero_serie,
                    descricao,
                    status_maquina,
                    nome_maquina
                )
                VALUES
                (%s,%s,%s,%s)
                """,
                (
                    numero_serie,
                    descricao,
                    status,
                    nome_maquina
                )
            )

            total_importados += 1

        conn.commit()

        return jsonify({
            "mensagem":
            f"Importação concluída. "
            f"{total_importados} máquinas cadastradas."
        }), 200

    except ImportError:

        return jsonify({
            "mensagem":
            "Instale: pip install pandas openpyxl"
        }), 500

    except Exception as e:

        if conn:
            conn.rollback()

        return jsonify({
            "mensagem":
            f"Erro ao importar: {str(e)}"
        }), 500

    finally:

        if conn:
            conn.close()
    
# ============================================
# NOVOS ENDPOINTS PARA TURMAS
# ============================================

@app.route("/api/buscar-turmas", methods=["GET"])
@login_obrigatorio
def buscar_turmas():

    conn = obter_conexao()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT DISTINCT turma
            FROM alunos
            WHERE turma IS NOT NULL
            AND turma <> ''
            ORDER BY turma
        """)

        turmas = cursor.fetchall()

        return jsonify(turmas), 200

    except Exception as e:

        return jsonify({
            "status": "Erro",
            "mensagem": str(e)
        }), 500

    finally:

        cursor.close()
        conn.close()


@app.route("/api/buscar-alunos/<string:turma>", methods=["GET"])
@login_obrigatorio
def buscar_alunos(turma):

    conn = obter_conexao()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT a.id_aluno, a.nome_aluno, a.ra FROM alunos a WHERE a.turma = %s
            AND NOT EXISTS (SELECT 1 FROM movimentacoes m WHERE m.id_aluno = a.id_aluno AND m.status_movimentacao = 'em_uso')
            ORDER BY a.nome_aluno;
        """, (turma,))

        alunos = cursor.fetchall()

        return jsonify(alunos), 200

    except Exception as e:

        return jsonify({
            "status": "Erro",
            "mensagem": str(e)
        }), 500

    finally:

        cursor.close()
        conn.close()

@app.route('/api/turmas', methods=['GET'])
@login_obrigatorio
def listar_turmas():
    """Lista todas as turmas com a quantidade de alunos"""
    conn = obter_conexao()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT turma, COUNT(*) as quantidade 
        FROM alunos 
        WHERE turma IS NOT NULL AND turma != ''
        GROUP BY turma 
        ORDER BY turma
    ''')
    
    turmas = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(turmas), 200

@app.route('/api/importar', methods=['POST'])
@login_obrigatorio
def importar_turmas():
    """Importa turmas de um arquivo Excel"""
    
    # Verifica se o arquivo foi enviado
    if 'excel' not in request.files:
        return jsonify({"mensagem": "Nenhum arquivo enviado"}), 400
    
    arquivo = request.files['excel']
    
    if arquivo.filename == '':
        return jsonify({"mensagem": "Nome do arquivo vazio"}), 400
    
    # Verifica extensão
    if not arquivo.filename.endswith(('.xlsx', '.xls')):
        return jsonify({"mensagem": "Formato inválido. Use .xlsx ou .xls"}), 400
    
    try:
        # Importa o pandas (se não tiver, instale com pip install pandas openpyxl)
        import pandas as pd
        
        # Lê o Excel
        df = pd.read_excel(arquivo)
        
        # Verifica se tem as colunas necessárias
        coluna_turma = None
        coluna_aluno = None
        
        for col in df.columns:
            if 'turma' in col.lower():
                coluna_turma = col
            if 'aluno' in col.lower() or 'nome' in col.lower():
                coluna_aluno = col
        
        if not coluna_turma or not coluna_aluno:
            return jsonify({
                "mensagem": "Arquivo deve ter colunas 'turma' e 'nome_aluno' (ou 'aluno')"
            }), 400
        
        total_importados = 0
        
        conn = obter_conexao()
        cursor = conn.cursor()
        
        # Para cada linha do Excel
        for _, row in df.iterrows():
            turma = str(row[coluna_turma]).strip()
            nome_aluno = str(row[coluna_aluno]).strip()
            
            # Pula linhas vazias
            if not turma or not nome_aluno or nome_aluno == 'nan' or turma == 'nan':
                continue
            
            # Verifica se o aluno já existe
            cursor.execute(
                "SELECT id_aluno FROM alunos WHERE nome_aluno = %s AND turma = %s",
                (nome_aluno, turma)
            )
            
            if not cursor.fetchone():
                # Insere o aluno
                cursor.execute(
                    "INSERT INTO alunos (nome_aluno, turma) VALUES (%s, %s)",
                    (nome_aluno, turma)
                )
                total_importados += 1
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "mensagem": f"Arquivo importado com sucesso! {total_importados} alunos cadastrados."
        }), 200
        
    except ImportError:
        return jsonify({
            "mensagem": "Biblioteca pandas não instalada. Execute: pip install pandas openpyxl"
        }), 500
    except Exception as e:
        return jsonify({
            "mensagem": f"Erro ao processar arquivo: {str(e)}"
        }), 500

# ============================================
# INICIALIZAÇÃO DO SERVIDOR
# ============================================
if __name__ == '__main__':
    print("🚀 Iniciando servidor GENI...")
    iniciar_banco()
    print("📡 Servidor rodando em http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)