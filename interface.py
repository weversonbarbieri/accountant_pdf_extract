import os
import threading
import webbrowser
import subprocess
import io
import sys
import socket
from contextlib import redirect_stdout, redirect_stderr
from flask import Flask, render_template, request, jsonify, send_from_directory
import glob
from analisar_json import AnalisadorJSON
from gerar_excel import processar_arquivo
import traceback
import textract_module
from dotenv import load_dotenv

app = Flask(__name__)

# Configuração das pastas
UPLOAD_FOLDER = 'uploads'
TEMPLATE_FOLDER = 'templates'
STATIC_FOLDER = 'static'

# Variável de controle para abrir o navegador apenas uma vez
NAVEGADOR_JA_ABERTO = False

# Criar pastas necessárias
for folder in [UPLOAD_FOLDER, TEMPLATE_FOLDER, STATIC_FOLDER, 
               os.path.join(STATIC_FOLDER, 'css'), 
               os.path.join(STATIC_FOLDER, 'js')]:
    os.makedirs(folder, exist_ok=True)

# Verificar arquivos JSON existentes no diretório
def obter_arquivos_json():
    # Buscar arquivos JSON na pasta uploads
    uploads_jsons = glob.glob(os.path.join(UPLOAD_FOLDER, "*_analysis.json"))
    uploads_jsons = [os.path.basename(arquivo) for arquivo in uploads_jsons]
    
    # Buscar também na raiz para compatibilidade
    root_jsons = glob.glob("*_analysis.json")
    
    # Combinar resultados, evitando duplicatas
    return list(set(uploads_jsons + root_jsons))

# Verificar se o servidor já está em execução
def servidor_em_execucao(porta=5000):
    try:
        # Tentar se conectar à porta
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', porta)) == 0
    except:
        return False

# Rota principal
@app.route('/')
def index():
    arquivos_json = obter_arquivos_json()
    return render_template('index.html', arquivos_json=arquivos_json)

# Rota para teste de seleção múltipla
@app.route('/teste-selecao-multipla')
def teste_selecao_multipla():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Teste de Seleção Múltipla</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }
            .form-group {
                margin-bottom: 20px;
            }
            label {
                display: block;
                margin-bottom: 5px;
            }
            button {
                padding: 8px 15px;
                background-color: #4285f4;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }
            #selected-files {
                margin-top: 20px;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                min-height: 100px;
            }
        </style>
    </head>
    <body>
        <h1>Teste de Seleção Múltipla de Arquivos</h1>
        
        <div class="form-group">
            <label for="pdf-upload">Selecione um ou mais arquivos PDF:</label>
            <input type="file" id="pdf-upload" name="pdf_files[]" accept=".pdf" multiple>
            <button type="button" id="select-btn">Selecionar PDFs</button>
        </div>
        
        <div id="selected-files">
            <p>Arquivos selecionados aparecerão aqui.</p>
        </div>
        
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                const fileInput = document.getElementById('pdf-upload');
                const selectBtn = document.getElementById('select-btn');
                const selectedFiles = document.getElementById('selected-files');
                
                selectBtn.addEventListener('click', function() {
                    fileInput.click();
                });
                
                fileInput.addEventListener('change', function() {
                    selectedFiles.innerHTML = '';
                    
                    if (this.files.length > 0) {
                        const header = document.createElement('h3');
                        header.textContent = `${this.files.length} arquivo(s) selecionado(s):`;
                        selectedFiles.appendChild(header);
                        
                        const list = document.createElement('ul');
                        
                        for (let i = 0; i < this.files.length; i++) {
                            const item = document.createElement('li');
                            item.textContent = this.files[i].name;
                            list.appendChild(item);
                        }
                        
                        selectedFiles.appendChild(list);
                    } else {
                        selectedFiles.innerHTML = '<p>Nenhum arquivo selecionado.</p>';
                    }
                });
            });
        </script>
    </body>
    </html>
    '''

# Adicionar nova rota para teste com script especializado
@app.route('/teste-pdf')
def teste_pdf():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Teste de Seleção PDF</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }
            .form-group {
                margin-bottom: 20px;
            }
            label {
                display: block;
                margin-bottom: 5px;
            }
            button {
                padding: 8px 15px;
                background-color: #4285f4;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }
            .file-input-wrapper {
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .file-input-placeholder {
                flex: 1;
                padding: 8px 12px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #f8f9fa;
            }
            .selected-file-list {
                margin-top: 20px;
                padding: 15px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #f8f9fa;
            }
            .selected-file-list ul {
                margin-top: 10px;
                padding-left: 20px;
            }
            .selected-file-list li {
                margin-bottom: 5px;
            }
        </style>
    </head>
    <body>
        <h1>Teste de Seleção PDF</h1>
        
        <form id="pdf-upload-form" enctype="multipart/form-data">
            <div class="form-group">
                <label for="pdf-file-upload">Selecione um ou mais arquivos PDF:</label>
                <div class="file-input-wrapper">
                    <input type="file" id="pdf-file-upload" name="pdf_files[]" accept=".pdf" multiple style="display: none;">
                    <div class="file-input-placeholder" id="pdf-filename">Nenhum arquivo selecionado</div>
                    <button type="button" id="pdf-select-btn">Selecionar PDFs</button>
                </div>
            </div>
            
            <div class="form-group">
                <button type="submit">Processar Arquivos</button>
            </div>
        </form>
        
        <script src="/static/js/file_select_test.js"></script>
    </body>
    </html>
    '''

# Função para processar arquivo com captura de saída
def processar_com_captura(arquivo):
    # Buffers para capturar stdout e stderr
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    
    try:
        # Capturar todas as saídas
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            processar_arquivo(arquivo)
        
        # Verificar se houve mensagens de aviso ou erro nas saídas
        stdout_output = stdout_buffer.getvalue()
        stderr_output = stderr_buffer.getvalue()
        
        # Procurar por mensagens de erro e aviso específicas nos outputs
        if "Nenhum bloco encontrado" in stdout_output or "Nenhum par chave-valor encontrado" in stdout_output:
            raise Exception("Não foram encontrados dados suficientes para gerar relatórios")
        
        if "At least one sheet must be visible" in stderr_output or "At least one sheet must be visible" in stdout_output:
            raise Exception("At least one sheet must be visible")
        
        # Se chegou até aqui, o processamento foi bem-sucedido
        return {
            'arquivo': arquivo,
            'status': 'Sucesso',
            'mensagem': 'Arquivo processado com sucesso',
            'tipo_erro': None,
            'stdout': stdout_output,
            'stderr': stderr_output
        }
        
    except Exception as e:
        # Capturar o traceback e outputs para análise
        erro_traceback = traceback.format_exc()
        stdout_output = stdout_buffer.getvalue()
        stderr_output = stderr_buffer.getvalue()
        
        print(f"Erro detalhado ao processar {arquivo}:")
        print(f"Traceback: {erro_traceback}")
        print(f"STDOUT: {stdout_output}")
        print(f"STDERR: {stderr_output}")
        
        # Determinar o tipo e mensagem de erro
        tipo_erro = 'erro_generico'
        mensagem = str(e)
        
        # Verificar tipos específicos de erro
        if "At least one sheet must be visible" in str(e) or "At least one sheet must be visible" in stdout_output:
            tipo_erro = 'sem_dados'
            mensagem = 'Não foram encontrados dados suficientes para gerar relatórios. Verifique se o arquivo JSON contém blocos válidos.'
        elif "Nenhum bloco encontrado" in str(e) or "Nenhum bloco encontrado" in stdout_output or "Nenhum par chave-valor encontrado" in stdout_output:
            tipo_erro = 'sem_blocos'
            mensagem = 'Nenhum bloco de texto ou par chave-valor foi encontrado no arquivo JSON.'
        elif "JSON" in str(e) and ("decode" in str(e) or "invalid" in str(e)):
            tipo_erro = 'json_invalido'
            mensagem = 'O arquivo JSON é inválido ou está corrompido.'
        
        return {
            'arquivo': arquivo,
            'status': 'Erro',
            'mensagem': mensagem,
            'tipo_erro': tipo_erro,
            'stdout': stdout_output,
            'stderr': stderr_output
        }

# Rota para processar arquivos
@app.route('/processar', methods=['POST'])
def processar():
    arquivos_selecionados = request.json.get('arquivos', [])
    resultados = []
    
    for arquivo in arquivos_selecionados:
        # Primeiro, procurar na pasta uploads
        caminho_arquivo = os.path.join(UPLOAD_FOLDER, arquivo)
        
        # Se não existir na pasta uploads, tentar na raiz (para compatibilidade)
        if not os.path.isfile(caminho_arquivo):
            if os.path.isfile(arquivo):
                caminho_arquivo = arquivo
            else:
                resultados.append({
                    'arquivo': arquivo,
                    'status': 'Erro',
                    'mensagem': 'Arquivo não encontrado',
                    'tipo_erro': 'arquivo_nao_encontrado'
                })
                continue
        
        # Processar arquivo com caminho completo
        resultado = processar_com_captura(caminho_arquivo)
        
        # Adicionar nome do arquivo original para exibição
        resultado['arquivo_exibicao'] = arquivo
        resultados.append(resultado)
    
    return jsonify({'resultados': resultados})

# Rota para processar arquivos PDF
@app.route('/processar-pdf', methods=['POST'])
def processar_pdf():
    if 'pdf_files[]' not in request.files:
        return jsonify({
            'sucesso': False,
            'mensagem': 'Nenhum arquivo enviado'
        })
    
    pdf_files = request.files.getlist('pdf_files[]')
    if not pdf_files or pdf_files[0].filename == '':
        return jsonify({
            'sucesso': False,
            'mensagem': 'Nomes de arquivos inválidos'
        })
    
    # Verificar a configuração AWS antes de processar
    aws_configurado, mensagem_config = textract_module.verificar_configuracao_aws()
    if not aws_configurado:
        return jsonify({
            'sucesso': False,
            'mensagem': mensagem_config
        })
    
    resultados = []
    
    for pdf_file in pdf_files:
        # Salvar o arquivo PDF na pasta uploads
        pdf_path = os.path.join(UPLOAD_FOLDER, pdf_file.filename)
        pdf_file.save(pdf_path)
        
        # Processar o PDF
        try:
            resultado = textract_module.processar_pdf(pdf_path)
            
            # Se o processamento foi bem-sucedido, retornar informações sobre os arquivos JSON gerados
            if resultado['sucesso']:
                # Adicionar informações extras ao resultado
                resultado['nome_arquivo'] = pdf_file.filename
                
                # Se houver arquivos JSON gerados, mostrar opções para processá-los
                arquivos_json = resultado['arquivos_json']
                resultado['arquivos_disponiveis'] = [os.path.basename(arquivo) for arquivo in arquivos_json]
            
            resultados.append(resultado)
            
        except Exception as e:
            resultados.append({
                'sucesso': False,
                'nome_arquivo': pdf_file.filename,
                'mensagem': f'Erro ao processar PDF: {str(e)}',
                'detalhes': traceback.format_exc()
            })
    
    return jsonify({
        'sucesso': True,
        'multiplos_arquivos': True,
        'total_processados': len(resultados),
        'resultados': resultados
    })

# Rota para servir arquivos estáticos
@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory(STATIC_FOLDER, path)

# Criar os arquivos estáticos necessários
def criar_arquivos_estaticos():
    # Verificar e criar as pastas necessárias
    for folder in [TEMPLATE_FOLDER, STATIC_FOLDER, 
                  os.path.join(STATIC_FOLDER, 'css'), 
                  os.path.join(STATIC_FOLDER, 'js')]:
        os.makedirs(folder, exist_ok=True)
    
    # Caminhos para os arquivos estáticos
    html_path = os.path.join(TEMPLATE_FOLDER, 'index.html')
    css_path = os.path.join(STATIC_FOLDER, 'css', 'style.css')
    js_path = os.path.join(STATIC_FOLDER, 'js', 'script.js')
    
    # Verificar se os arquivos já existem
    html_exists = os.path.exists(html_path)
    css_exists = os.path.exists(css_path)
    js_exists = os.path.exists(js_path)
    
    if not html_exists or not css_exists or not js_exists:
        print("Criando arquivos estáticos necessários...")
        
        # Criar HTML se não existir
        if not html_exists:
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write('''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Analisador de JSON</title>
    <link rel="stylesheet" href="/static/css/style.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>Analisador de JSON e Gerador Excel</h1>
            <p>Selecione os arquivos JSON para análise e geração de relatórios</p>
        </header>
        
        <main>
            <div class="tabs">
                <button class="tab-btn" data-tab="json-tab" id="json-tab-btn" style="display: none;">
                    <i class="fas fa-file-code"></i> Arquivos JSON
                </button>
                <button class="tab-btn active" data-tab="pdf-tab">
                    <i class="fas fa-file-pdf"></i> Extrair texto de PDF
                </button>
            </div>
            
            <!-- Tab de processamento JSON -->
            <div id="json-tab" class="tab-content">
                <div class="card">
                    <h2><i class="fas fa-file-upload"></i> Upload de arquivos</h2>
                    <div class="dropzone" id="drop-area">
                        <div class="dropzone-content">
                            <i class="fas fa-cloud-upload-alt"></i>
                            <p>Arraste e solte arquivos JSON aqui</p>
                            <span>ou</span>
                            <label for="file-upload" class="btn primary">Selecionar arquivos</label>
                            <input type="file" id="file-upload" multiple accept=".json" hidden>
                        </div>
                        <div class="file-preview" id="file-preview">
                            <!-- Arquivos selecionados serão mostrados aqui -->
                        </div>
                    </div>
                    <div class="upload-controls">
                        <button id="upload-button" class="btn primary">
                            <i class="fas fa-upload"></i> Enviar arquivos
                        </button>
                        <button id="clear-button" class="btn secondary">
                            <i class="fas fa-trash"></i> Limpar seleção
                        </button>
                    </div>
                </div>
                
                <div class="card">
                    <h2><i class="fas fa-list"></i> Arquivos disponíveis</h2>
                    <div class="file-list">
                        <div class="file-list-header">
                            <div class="file-select-all">
                                <input type="checkbox" id="select-all">
                                <label for="select-all">Selecionar todos</label>
                            </div>
                            <div class="file-name-header">Nome do arquivo</div>
                            <div class="file-actions-header">Ações</div>
                        </div>
                        <div id="files">
                        {% if arquivos_json %}
                            {% for arquivo in arquivos_json %}
                            <div class="file-item">
                                <input type="checkbox" id="file-{{ loop.index }}" class="file-checkbox" data-filename="{{ arquivo }}">
                                <label for="file-{{ loop.index }}" class="file-label">{{ arquivo }}</label>
                                <div class="file-actions">
                                    <button class="btn-icon delete-file" data-filename="{{ arquivo }}" title="Excluir arquivo">
                                        <i class="fas fa-trash-alt"></i>
                                    </button>
                                </div>
                            </div>
                            {% endfor %}
                        {% else %}
                            <p class="no-files">Nenhum arquivo JSON encontrado no diretório.</p>
                        {% endif %}
                        </div>
                    </div>
                    
                    <div class="actions">
                        <button id="process-button" class="btn primary">
                            <i class="fas fa-cogs"></i> Processar arquivos selecionados
                        </button>
                        <button id="refresh-button" class="btn secondary">
                            <i class="fas fa-sync-alt"></i> Atualizar lista
                        </button>
                    </div>
                </div>
                
                <div class="card results-card">
                    <h2><i class="fas fa-clipboard-list"></i> Resultados</h2>
                    <div id="processing-indicator" class="hidden">
                        <div class="spinner"></div>
                        <p>Processando arquivos, por favor aguarde...</p>
                    </div>
                    <div id="results">
                        <p class="no-results">Nenhum resultado ainda. Selecione e processe arquivos.</p>
                    </div>
                </div>
            </div>
            
            <!-- Tab de processamento PDF -->
            <div id="pdf-tab" class="tab-content active">
                <div class="card">
                    <h2><i class="fas fa-file-pdf"></i> Processamento de PDF com Amazon Textract</h2>
                    <div class="alert info">
                        <i class="fas fa-info-circle"></i>
                        <div>
                            <p>Este recurso utiliza o Amazon Textract para extrair texto e estrutura de documentos PDF.</p>
                            <p>É necessário ter as credenciais AWS configuradas.</p>
                        </div>
                    </div>
                    
                    <p class="workflow-description">
                        <strong>Fluxo de trabalho:</strong>
                        <ol>
                            <li>Selecione um ou mais arquivos PDF para processar</li>
                            <li>O Amazon Textract extrairá o texto e a estrutura dos documentos</li>
                            <li>Os resultados serão salvos como arquivos JSON</li>
                            <li>Você poderá selecionar um dos arquivos JSON gerados para criar relatórios Excel/CSV</li>
                        </ol>
                    </p>
                    
                    <form id="pdf-upload-form" enctype="multipart/form-data">
                        <div class="form-group">
                            <label for="pdf-file-upload">Selecione arquivos PDF:</label>
                            <div class="file-input-wrapper">
                                <input type="file" id="pdf-file-upload" name="pdf_files[]" accept=".pdf" multiple>
                                <div class="file-input-placeholder" id="pdf-filename">Nenhum arquivo selecionado</div>
                                <button type="button" class="btn secondary" id="pdf-select-btn">Selecionar PDFs</button>
                            </div>
                        </div>
                        
                        <div class="form-group">
                            <button type="submit" class="btn primary" id="pdf-process-btn">
                                <i class="fas fa-cloud-upload-alt"></i> Processar PDFs com Textract
                            </button>
                        </div>
                    </form>
                    
                    <div id="pdf-processing-indicator" class="hidden">
                        <div class="spinner"></div>
                        <p>Processando PDFs com Amazon Textract, isso pode levar alguns minutos...</p>
                        <div class="progress-bar-container">
                            <div class="progress-bar" id="pdf-progress-bar" style="width: 0%"></div>
                        </div>
                    </div>
                    
                    <div id="pdf-results" class="hidden">
                        <!-- Resultados do processamento PDF serão mostrados aqui -->
                    </div>
                </div>
                
                <div id="json-files-from-pdf" class="card hidden">
                    <h2><i class="fas fa-file-code"></i> Arquivos JSON gerados</h2>
                    <p class="info-text">Selecione qual arquivo JSON deseja processar para gerar relatórios Excel/CSV:</p>
                    
                    <div id="pdf-json-files" class="file-list">
                        <!-- Lista de arquivos JSON gerados a partir do PDF -->
                    </div>
                    
                    <div class="actions">
                        <button id="process-pdf-json-btn" class="btn primary">
                            <i class="fas fa-cogs"></i> Processar JSON selecionado
                        </button>
                    </div>
                </div>
            </div>
        </main>
        
        <footer>
            <p>Processamento de arquivos JSON para extração de texto e pares chave-valor</p>
        </footer>
    </div>
    
    <script src="/static/js/script.js"></script>
</body>
</html>''')
            print(f"Arquivo HTML criado: {html_path}")
    
        # Criar CSS se não existir
        if not css_exists:
            with open(css_path, 'w', encoding='utf-8') as f:
                # Aqui você pode incluir o código CSS ou simplesmente deixar em branco
                f.write('/* Arquivo CSS criado pelo sistema - pode ser editado manualmente */')
            print(f"Arquivo CSS criado: {css_path}")
        
        # Criar JS se não existir
        if not js_exists:
            with open(js_path, 'w', encoding='utf-8') as f:
                # Aqui você pode incluir o código JavaScript ou simplesmente deixar em branco
                f.write('/* Arquivo JavaScript criado pelo sistema - pode ser editado manualmente */')
            print(f"Arquivo JS criado: {js_path}")
    else:
        print("Arquivos estáticos já existem, não será necessário recriá-los.")

# Rota para upload de arquivos
@app.route('/upload', methods=['POST'])
def upload_files():
    try:
        if 'files[]' not in request.files:
            return jsonify({'success': False, 'message': 'Nenhum arquivo enviado'})
        
        files = request.files.getlist('files[]')
        
        for file in files:
            if file.filename == '':
                continue
            
            if file and file.filename.endswith('.json'):
                file.save(os.path.join(os.getcwd(), file.filename))
        
        return jsonify({'success': True, 'message': 'Arquivos enviados com sucesso'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# Adicionar rota para excluir arquivo
@app.route('/excluir-arquivo', methods=['POST'])
def excluir_arquivo():
    try:
        arquivo = request.json.get('arquivo', '')
        if not arquivo:
            return jsonify({'success': False, 'message': 'Nome do arquivo não fornecido'})
        
        # Verificar se o arquivo existe
        if not os.path.isfile(arquivo):
            return jsonify({'success': False, 'message': 'Arquivo não encontrado'})
        
        # Excluir o arquivo
        os.remove(arquivo)
        return jsonify({'success': True, 'message': f'Arquivo {arquivo} excluído com sucesso'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# Iniciar servidor
def abrir_navegador():
    # Aguardar um momento para o servidor iniciar
    import time
    time.sleep(1.0)
    
    # Verificar se o navegador já foi aberto antes
    global NAVEGADOR_JA_ABERTO
    if not NAVEGADOR_JA_ABERTO:
        # Verificar se o servidor já está em execução (isso pode indicar um reload)
        if not servidor_em_execucao():
            # Abrir navegador automaticamente
            print("Abrindo navegador em http://127.0.0.1:5000")
            webbrowser.open('http://127.0.0.1:5000')
            NAVEGADOR_JA_ABERTO = True
        else:
            print("Servidor já em execução, não abrindo novo navegador")
    else:
        print("Navegador já foi aberto anteriormente")

# Verifica e cria o arquivo .env se não existir
def verificar_env():
    if not os.path.exists('.env'):
        print("Arquivo .env não encontrado. Criando com configurações padrão...")
        with open('.env', 'w') as f:
            f.write("""# Credenciais AWS para Amazon Textract
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
S3_BUCKET_NAME=
""")
        print("Arquivo .env criado. Por favor, edite-o com suas credenciais AWS antes de usar a funcionalidade de extração de PDF.")
    else:
        # Verificar se as credenciais estão configuradas
        load_dotenv()
        
        aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        s3_bucket = os.getenv('S3_BUCKET_NAME')
        
        if not (aws_access_key and aws_secret_key and s3_bucket):
            print("AVISO: Credenciais AWS incompletas no arquivo .env.")
            print("Por favor, configure corretamente as credenciais para usar a funcionalidade de extração de PDF.")

if __name__ == '__main__':
    # Verificar o arquivo .env
    verificar_env()
    
    # Criar arquivos estáticos necessários
    criar_arquivos_estaticos()
    
    # Iniciar navegador em uma thread separada apenas se for a primeira execução
    if not servidor_em_execucao():
        threading.Thread(target=abrir_navegador).start()
    
    # Iniciar servidor Flask
    app.run(debug=True) 