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
    return glob.glob("*.json")

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
        # Verificar se o arquivo existe antes de processar
        if not os.path.isfile(arquivo):
            resultados.append({
                'arquivo': arquivo,
                'status': 'Erro',
                'mensagem': 'Arquivo não encontrado',
                'tipo_erro': 'arquivo_nao_encontrado'
            })
            continue
                
        # Processar arquivo com captura de saída
        resultado = processar_com_captura(arquivo)
        resultados.append(resultado)
    
    return jsonify({'resultados': resultados})

# Rota para servir arquivos estáticos
@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory(STATIC_FOLDER, path)

# Criar os arquivos estáticos necessários
def criar_arquivos_estaticos():
    # Criar HTML
    with open(os.path.join(TEMPLATE_FOLDER, 'index.html'), 'w', encoding='utf-8') as f:
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
        </main>
        
        <footer>
            <p>Processamento de arquivos JSON para extração de texto e pares chave-valor</p>
        </footer>
    </div>
    
    <script src="/static/js/script.js"></script>
</body>
</html>''')
    
    # Criar CSS
    with open(os.path.join(STATIC_FOLDER, 'css', 'style.css'), 'w', encoding='utf-8') as f:
        f.write('''/* Variáveis globais */
:root {
    --primary-color: #3498db;
    --primary-dark: #2980b9;
    --secondary-color: #2ecc71;
    --secondary-dark: #27ae60;
    --error-color: #e74c3c;
    --warning-color: #f39c12;
    --dark-color: #2c3e50;
    --light-color: #ecf0f1;
    --border-color: #ddd;
    --hover-color: #f5f5f5;
    --card-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
    --transition-speed: 0.3s;
}

/* Estilos gerais */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background-color: var(--light-color);
    color: var(--dark-color);
    line-height: 1.6;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

header {
    text-align: center;
    margin-bottom: 30px;
    padding: 20px 0;
}

header h1 {
    color: var(--primary-color);
    margin-bottom: 10px;
    font-size: 2.2rem;
}

header p {
    color: var(--dark-color);
    font-size: 1.1rem;
}

/* Cards */
.card {
    background: white;
    border-radius: 8px;
    box-shadow: var(--card-shadow);
    padding: 25px;
    margin-bottom: 30px;
    transition: box-shadow 0.3s ease;
}

.card:hover {
    box-shadow: 0 5px 15px rgba(0, 0, 0, 0.15);
}

.card h2 {
    color: var(--dark-color);
    margin-bottom: 20px;
    padding-bottom: 15px;
    border-bottom: 1px solid var(--border-color);
    display: flex;
    align-items: center;
    font-size: 1.5rem;
}

.card h2 i {
    margin-right: 10px;
    color: var(--primary-color);
}

/* Dropzone */
.dropzone {
    border: 2px dashed var(--border-color);
    border-radius: 8px;
    padding: 20px;
    text-align: center;
    transition: all var(--transition-speed) ease;
    margin-bottom: 20px;
    background-color: #fbfbfb;
}

.dropzone.highlight {
    border-color: var(--primary-color);
    background-color: rgba(52, 152, 219, 0.05);
}

.dropzone-content {
    padding: 30px 20px;
}

.dropzone i {
    font-size: 3rem;
    color: var(--primary-color);
    margin-bottom: 15px;
}

.dropzone p {
    font-size: 1.2rem;
    margin-bottom: 10px;
    color: var(--dark-color);
}

.dropzone span {
    display: block;
    margin: 10px 0;
    color: #777;
}

.file-preview {
    margin-top: 20px;
    padding-top: 20px;
    border-top: 1px dashed var(--border-color);
    display: none;
}

.file-preview.active {
    display: block;
}

.file-item-preview {
    display: flex;
    align-items: center;
    padding: 10px;
    margin-bottom: 8px;
    background-color: #f9f9f9;
    border-radius: 4px;
    justify-content: space-between;
}

.file-item-preview .file-name {
    display: flex;
    align-items: center;
}

.file-item-preview .file-name i {
    font-size: 1.2rem;
    margin-right: 10px;
    color: var(--primary-color);
}

.file-remove {
    background: none;
    border: none;
    color: var(--error-color);
    cursor: pointer;
    font-size: 1.2rem;
    transition: color var(--transition-speed) ease;
}

.file-remove:hover {
    color: #c0392b;
}

.upload-controls {
    display: flex;
    justify-content: center;
    gap: 15px;
    margin-top: 10px;
}

/* Lista de arquivos */
.file-list {
    max-height: 300px;
    overflow-y: auto;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    margin-bottom: 20px;
    background-color: white;
}

.file-list-header {
    display: flex;
    padding: 12px 15px;
    background-color: #f9f9f9;
    border-bottom: 1px solid var(--border-color);
    font-weight: bold;
}

.file-select-all {
    width: 30px;
    margin-right: 10px;
}

.file-name-header {
    flex: 1;
}

.file-actions-header {
    width: 80px;
    text-align: center;
}

.file-item {
    display: flex;
    padding: 12px 15px;
    border-bottom: 1px solid var(--border-color);
    align-items: center;
    transition: background-color var(--transition-speed) ease;
}

.file-item:last-child {
    border-bottom: none;
}

.file-item:hover {
    background-color: var(--hover-color);
}

.file-item input[type="checkbox"] {
    margin-right: 10px;
}

.file-label {
    flex: 1;
    cursor: pointer;
}

.file-actions {
    display: flex;
    justify-content: flex-end;
    width: 80px;
}

.btn-icon {
    background: none;
    border: none;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all var(--transition-speed) ease;
    color: var(--dark-color);
}

.btn-icon:hover {
    background-color: rgba(0, 0, 0, 0.05);
    color: var(--error-color);
}

.delete-file {
    color: #777;
}

.delete-file:hover {
    color: var(--error-color);
}

.no-files, .no-results {
    padding: 25px;
    text-align: center;
    color: #777;
    font-style: italic;
}

/* Botões */
.btn {
    padding: 10px 18px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
    transition: all var(--transition-speed) ease;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-weight: 500;
}

.btn i {
    margin-right: 8px;
}

.primary {
    background-color: var(--primary-color);
    color: white;
}

.primary:hover {
    background-color: var(--primary-dark);
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.secondary {
    background-color: var(--secondary-color);
    color: white;
}

.secondary:hover {
    background-color: var(--secondary-dark);
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.actions {
    display: flex;
    justify-content: center;
    gap: 15px;
    margin-top: 20px;
}

/* Resultados */
.results-card {
    min-height: 200px;
}

#processing-indicator {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 30px;
}

.spinner {
    border: 4px solid rgba(0, 0, 0, 0.1);
    width: 40px;
    height: 40px;
    border-radius: 50%;
    border-left-color: var(--primary-color);
    animation: spin 1s linear infinite;
    margin-bottom: 15px;
}

.result-item {
    padding: 18px;
    margin-bottom: 15px;
    border-radius: 8px;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05);
    transition: transform var(--transition-speed) ease;
}

.result-item:hover {
    transform: translateY(-2px);
}

.result-success {
    background-color: rgba(46, 204, 113, 0.1);
    border-left: 4px solid var(--secondary-color);
}

.result-error {
    background-color: rgba(231, 76, 60, 0.1);
    border-left: 4px solid var(--error-color);
}

.result-warning {
    background-color: rgba(243, 156, 18, 0.1);
    border-left: 4px solid var(--warning-color);
}

.status-badge {
    display: inline-block;
    padding: 5px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: bold;
    color: white;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.badge-success {
    background-color: var(--secondary-color);
}

.badge-error {
    background-color: var(--error-color);
}

.badge-warning {
    background-color: var(--warning-color);
}

.error-details {
    margin-top: 12px;
    padding: 12px;
    background-color: #f9f9f9;
    border-radius: 6px;
    font-size: 13px;
    box-shadow: inset 0 0 5px rgba(0, 0, 0, 0.05);
}

/* Modal de confirmação */
.modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    opacity: 0;
    visibility: hidden;
    transition: all 0.3s ease;
}

.modal-backdrop.active {
    opacity: 1;
    visibility: visible;
}

.modal {
    background-color: white;
    border-radius: 8px;
    box-shadow: 0 5px 20px rgba(0, 0, 0, 0.2);
    width: 90%;
    max-width: 500px;
    padding: 25px;
    transform: translateY(-20px);
    transition: all 0.3s ease;
}

.modal-backdrop.active .modal {
    transform: translateY(0);
}

.modal-header {
    display: flex;
    align-items: center;
    margin-bottom: 15px;
}

.modal-header i {
    color: var(--warning-color);
    font-size: 24px;
    margin-right: 15px;
}

.modal-header h3 {
    font-size: 1.2rem;
    color: var(--dark-color);
}

.modal-body {
    margin-bottom: 20px;
    color: #555;
}

.modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
}

.btn-modal-cancel {
    background-color: #f1f1f1;
    color: #555;
    padding: 8px 16px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s ease;
}

.btn-modal-cancel:hover {
    background-color: #e1e1e1;
}

.btn-modal-confirm {
    background-color: var(--error-color);
    color: white;
    padding: 8px 16px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s ease;
}

.btn-modal-confirm:hover {
    background-color: #c0392b;
}

/* Utilitários */
.hidden {
    display: none !important;
}

/* Animações */
@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

/* Footer */
footer {
    text-align: center;
    margin-top: 40px;
    padding-top: 20px;
    border-top: 1px solid var(--border-color);
    color: #777;
}

/* Responsivo */
@media (max-width: 768px) {
    .container {
        padding: 15px;
    }
    
    .card {
        padding: 15px;
    }
    
    .actions {
        flex-direction: column;
    }
    
    .btn {
        width: 100%;
        margin-bottom: 10px;
    }
    
    .result-item {
        flex-direction: column;
    }
    
    .result-item > div:last-child {
        margin-top: 10px;
    }
}''')
    
    # Criar JavaScript
    with open(os.path.join(STATIC_FOLDER, 'js', 'script.js'), 'w', encoding='utf-8') as f:
        f.write('''document.addEventListener('DOMContentLoaded', function() {
    // Elementos da interface
    const selectAllCheckbox = document.getElementById('select-all');
    const fileCheckboxes = document.querySelectorAll('.file-checkbox');
    const processButton = document.getElementById('process-button');
    const refreshButton = document.getElementById('refresh-button');
    const uploadButton = document.getElementById('upload-button');
    const clearButton = document.getElementById('clear-button');
    const fileUpload = document.getElementById('file-upload');
    const processingIndicator = document.getElementById('processing-indicator');
    const resultsContainer = document.getElementById('results');
    const dropArea = document.getElementById('drop-area');
    const filePreview = document.getElementById('file-preview');
    const deleteButtons = document.querySelectorAll('.delete-file');
    
    // Criar modal de confirmação
    const modalHTML = `
        <div class="modal-backdrop" id="confirm-modal">
            <div class="modal">
                <div class="modal-header">
                    <i class="fas fa-exclamation-triangle"></i>
                    <h3>Confirmar exclusão</h3>
                </div>
                <div class="modal-body">
                    <p>Tem certeza que deseja excluir o arquivo <strong id="filename-to-delete"></strong>?</p>
                    <p>Esta ação não pode ser desfeita.</p>
                </div>
                <div class="modal-footer">
                    <button class="btn-modal-cancel" id="cancel-delete">Cancelar</button>
                    <button class="btn-modal-confirm" id="confirm-delete">Excluir</button>
                </div>
            </div>
        </div>
    `;
    
    // Adicionar modal ao body
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    
    const confirmModal = document.getElementById('confirm-modal');
    const filenameToDelete = document.getElementById('filename-to-delete');
    const cancelDeleteBtn = document.getElementById('cancel-delete');
    const confirmDeleteBtn = document.getElementById('confirm-delete');
    
    let currentFileToDelete = '';
    
    // Array para armazenar os arquivos selecionados para upload
    let selectedFiles = [];
    
    // Funções para Drag and Drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
    });
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });
    
    function highlight() {
        dropArea.classList.add('highlight');
    }
    
    function unhighlight() {
        dropArea.classList.remove('highlight');
    }
    
    // Manipulador para soltar arquivos
    dropArea.addEventListener('drop', handleDrop, false);
    
    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }
    
    // Manipulador para selecionar arquivos manualmente
    fileUpload.addEventListener('change', function() {
        handleFiles(this.files);
    });
    
    // Adicionar evento de exclusão a todos os botões de exclusão
    deleteButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const filename = this.getAttribute('data-filename');
            currentFileToDelete = filename;
            filenameToDelete.textContent = filename;
            confirmModal.classList.add('active');
        });
    });
    
    // Função para excluir arquivo
    function deleteFile(filename) {
        fetch('/excluir-arquivo', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ arquivo: filename })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Recarregar a página para atualizar a lista
                window.location.reload();
            } else {
                alert('Erro ao excluir arquivo: ' + data.message);
            }
        })
        .catch(error => {
            alert('Erro ao excluir arquivo: ' + error.message);
            console.error('Erro:', error);
        });
    }
    
    // Eventos do modal de confirmação
    cancelDeleteBtn.addEventListener('click', function() {
        confirmModal.classList.remove('active');
        currentFileToDelete = '';
    });
    
    confirmDeleteBtn.addEventListener('click', function() {
        if (currentFileToDelete) {
            deleteFile(currentFileToDelete);
            confirmModal.classList.remove('active');
        }
    });
    
    // Clicar fora do modal para fechar
    confirmModal.addEventListener('click', function(e) {
        if (e.target === confirmModal) {
            confirmModal.classList.remove('active');
            currentFileToDelete = '';
        }
    });
    
    // Processar arquivos selecionados para upload
    function handleFiles(files) {
        // Filtrar apenas arquivos JSON
        const jsonFiles = Array.from(files).filter(file => file.name.endsWith('.json'));
        
        if (jsonFiles.length === 0) {
            alert('Por favor, selecione apenas arquivos JSON.');
            return;
        }
        
        // Adicionar à lista de arquivos selecionados
        selectedFiles = [...selectedFiles, ...jsonFiles];
        
        // Atualizar a pré-visualização
        updateFilePreview();
    }
    
    // Atualizar a pré-visualização dos arquivos
    function updateFilePreview() {
        if (selectedFiles.length > 0) {
            filePreview.innerHTML = '';
            filePreview.classList.add('active');
            
            selectedFiles.forEach((file, index) => {
                const fileItem = document.createElement('div');
                fileItem.className = 'file-item-preview';
                fileItem.innerHTML = `
                    <div class="file-name">
                        <i class="fas fa-file-code"></i>
                        ${file.name} (${formatFileSize(file.size)})
                    </div>
                    <button type="button" class="file-remove" data-index="${index}">
                        <i class="fas fa-times"></i>
                    </button>
                `;
                filePreview.appendChild(fileItem);
            });
            
            // Adicionar eventos para remover arquivos
            document.querySelectorAll('.file-remove').forEach(button => {
                button.addEventListener('click', function() {
                    const index = parseInt(this.getAttribute('data-index'));
                    selectedFiles.splice(index, 1);
                    updateFilePreview();
                });
            });
        } else {
            filePreview.classList.remove('active');
            filePreview.innerHTML = '';
        }
    }
    
    // Formatar tamanho do arquivo
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    // Limpar seleção de arquivos
    clearButton.addEventListener('click', function() {
        selectedFiles = [];
        fileUpload.value = '';
        updateFilePreview();
    });
    
    // Evento para selecionar/desselecionar todos os arquivos
    selectAllCheckbox.addEventListener('change', function() {
        const isChecked = this.checked;
        fileCheckboxes.forEach(checkbox => {
            checkbox.checked = isChecked;
        });
    });
    
    // Evento para processar arquivos selecionados
    processButton.addEventListener('click', function() {
        const selectedFiles = Array.from(document.querySelectorAll('.file-checkbox:checked'))
            .map(checkbox => checkbox.getAttribute('data-filename'));
        
        if (selectedFiles.length === 0) {
            alert('Por favor, selecione pelo menos um arquivo para processar.');
            return;
        }
        
        // Mostrar indicador de processamento
        processingIndicator.classList.remove('hidden');
        resultsContainer.innerHTML = '';
        
        // Enviar requisição para processar os arquivos
        fetch('/processar', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ arquivos: selectedFiles })
        })
        .then(response => response.json())
        .then(data => {
            // Ocultar indicador de processamento
            processingIndicator.classList.add('hidden');
            
            // Exibir resultados
            if (data.resultados && data.resultados.length > 0) {
                const resultadosHTML = data.resultados.map(resultado => {
                    // Determinar a classe CSS com base no status
                    let classeResultado = 'result-success';
                    let badgeClass = 'badge-success';
                    let iconClass = 'fas fa-check-circle';
                    
                    if (resultado.status === 'Erro') {
                        classeResultado = 'result-error';
                        badgeClass = 'badge-error';
                        iconClass = 'fas fa-exclamation-circle';
                    }
                    
                    // Renderizar mensagens específicas para tipos de erro
                    let detalhesErro = '';
                    if (resultado.tipo_erro === 'sem_dados') {
                        detalhesErro = `
                            <div class="error-details">
                                <p><strong>Problema:</strong> O arquivo JSON não contém dados suficientes para gerar planilhas.</p>
                                <p><strong>Solução:</strong> Verifique se o arquivo JSON contém blocos de texto válidos com pares chave-valor.</p>
                            </div>
                        `;
                    } else if (resultado.tipo_erro === 'sem_blocos') {
                        detalhesErro = `
                            <div class="error-details">
                                <p><strong>Problema:</strong> Não foram encontrados blocos de texto no arquivo.</p>
                                <p><strong>Solução:</strong> O arquivo JSON parece estar vazio ou não contém o formato esperado.</p>
                            </div>
                        `;
                    } else if (resultado.tipo_erro === 'json_invalido') {
                        detalhesErro = `
                            <div class="error-details">
                                <p><strong>Problema:</strong> O arquivo JSON está em formato inválido.</p>
                                <p><strong>Solução:</strong> Verifique a sintaxe do arquivo JSON ou gere-o novamente.</p>
                            </div>
                        `;
                    } else if (resultado.tipo_erro === 'arquivo_nao_encontrado') {
                        detalhesErro = `
                            <div class="error-details">
                                <p><strong>Problema:</strong> O arquivo não foi encontrado no servidor.</p>
                                <p><strong>Solução:</strong> Verifique se o arquivo existe ou tente fazer upload novamente.</p>
                            </div>
                        `;
                    }
                    
                    return `
                        <div class="result-item ${classeResultado}">
                            <div>
                                <strong><i class="${iconClass}"></i> ${resultado.arquivo}</strong>
                                <p>${resultado.mensagem}</p>
                                ${detalhesErro}
                            </div>
                            <div>
                                <span class="status-badge ${badgeClass}">${resultado.status}</span>
                            </div>
                        </div>
                    `;
                }).join('');
                
                resultsContainer.innerHTML = resultadosHTML;
            } else {
                resultsContainer.innerHTML = '<p class="no-results">Nenhum resultado obtido.</p>';
            }
        })
        .catch(error => {
            processingIndicator.classList.add('hidden');
            resultsContainer.innerHTML = `
                <div class="result-item result-error">
                    <div>
                        <p><i class="fas fa-exclamation-triangle"></i> Erro ao processar arquivos: ${error.message}</p>
                        <div class="error-details">
                            <p>Ocorreu um erro na comunicação com o servidor. Por favor, tente novamente mais tarde.</p>
                        </div>
                    </div>
                    <div>
                        <span class="status-badge badge-error">Erro</span>
                    </div>
                </div>
            `;
            console.error('Erro:', error);
        });
    });
    
    // Evento para atualizar a lista de arquivos
    refreshButton.addEventListener('click', function() {
        window.location.reload();
    });
    
    // Evento para upload de novos arquivos
    uploadButton.addEventListener('click', function() {
        if (selectedFiles.length === 0) {
            alert('Por favor, selecione pelo menos um arquivo para upload.');
            return;
        }
        
        const formData = new FormData();
        selectedFiles.forEach(file => {
            formData.append('files[]', file);
        });
        
        // Mostrar indicador de carregamento
        uploadButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Enviando...';
        uploadButton.disabled = true;
        
        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Resetar o formulário
                selectedFiles = [];
                fileUpload.value = '';
                updateFilePreview();
                
                // Exibir mensagem de sucesso
                alert('Arquivos enviados com sucesso!');
                
                // Recarregar a página para mostrar os novos arquivos
                window.location.reload();
            } else {
                alert('Erro ao enviar arquivos: ' + data.message);
                
                // Restaurar o botão
                uploadButton.innerHTML = '<i class="fas fa-upload"></i> Enviar arquivos';
                uploadButton.disabled = false;
            }
        })
        .catch(error => {
            alert('Erro ao enviar arquivos: ' + error.message);
            console.error('Erro:', error);
            
            // Restaurar o botão
            uploadButton.innerHTML = '<i class="fas fa-upload"></i> Enviar arquivos';
            uploadButton.disabled = false;
        });
    });
});''')

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

if __name__ == '__main__':
    # Criar arquivos estáticos necessários
    criar_arquivos_estaticos()
    
    # Iniciar navegador em uma thread separada apenas se for a primeira execução
    if not servidor_em_execucao():
        threading.Thread(target=abrir_navegador).start()
    
    # Iniciar servidor Flask
    app.run(debug=True) 