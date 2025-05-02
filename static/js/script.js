document.addEventListener('DOMContentLoaded', function() {
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
});