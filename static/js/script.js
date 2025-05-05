/* Arquivo JavaScript criado pelo sistema - pode ser editado manualmente */

document.addEventListener('DOMContentLoaded', function() {
    // Inicialização de variáveis
    let selectedFiles = [];
    const pdfFileInput = document.getElementById('pdf-file-upload');
    const pdfFilePlaceholder = document.getElementById('pdf-filename');
    const pdfSelectBtn = document.getElementById('pdf-select-btn');
    const pdfProcessBtn = document.getElementById('pdf-process-btn');
    const pdfProcessingIndicator = document.getElementById('pdf-processing-indicator');
    const pdfResults = document.getElementById('pdf-results');
    const pdfProgressBar = document.getElementById('pdf-progress-bar');
    const jsonFilesFromPdf = document.getElementById('json-files-from-pdf');
    const pdfJsonFiles = document.getElementById('pdf-json-files');
    const pdfUploadForm = document.getElementById('pdf-upload-form');
    
    // Elementos da interface de JSON (tab alternativo)
    const dropArea = document.getElementById('drop-area');
    const fileUpload = document.getElementById('file-upload');
    const filePreview = document.getElementById('file-preview');
    const uploadButton = document.getElementById('upload-button');
    const clearButton = document.getElementById('clear-button');
    const processButton = document.getElementById('process-button');
    const refreshButton = document.getElementById('refresh-button');
    const processingIndicator = document.getElementById('processing-indicator');
    const results = document.getElementById('results');
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    // Funções de Utilidade
    function showElement(element) {
        if (element) element.classList.remove('hidden');
    }
    
    function hideElement(element) {
        if (element) element.classList.add('hidden');
    }
    
    function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `alert ${type}`;
        notification.innerHTML = `<i class="fas ${type === 'error' ? 'fa-times-circle' : 'fa-info-circle'}"></i><div><p>${message}</p></div>`;
        
        // Encontrar o primeiro card na tab ativa
        const activeTab = document.querySelector('.tab-content.active');
        if (activeTab) {
            const firstCard = activeTab.querySelector('.card');
            if (firstCard) {
                firstCard.insertBefore(notification, firstCard.firstChild);
                
                // Auto-remover após 5 segundos
                setTimeout(() => {
                    notification.remove();
                }, 5000);
            }
        }
    }
    
    // Evento para troca de tabs
    if (tabButtons && tabButtons.length > 0) {
        tabButtons.forEach(button => {
            button.addEventListener('click', function() {
                const targetTab = this.getAttribute('data-tab');
                
                // Remover classe ativa de todos os botões e conteúdos
                tabButtons.forEach(btn => btn.classList.remove('active'));
                tabContents.forEach(content => content.classList.remove('active'));
                
                // Adicionar classe ativa ao botão e conteúdo correspondente
                this.classList.add('active');
                document.getElementById(targetTab).classList.add('active');
            });
        });
    }
    
    // Função para exibir os arquivos selecionados
    function updatePdfFilenameDisplay() {
        if (pdfFileInput && pdfFileInput.files.length > 0) {
            const fileCount = pdfFileInput.files.length;
            
            if (fileCount === 1) {
                pdfFilePlaceholder.textContent = pdfFileInput.files[0].name;
            } else {
                pdfFilePlaceholder.textContent = `${fileCount} arquivos PDF selecionados`;
            }
            
            // Adicionar visualização detalhada dos arquivos selecionados
            const resultDiv = document.createElement('div');
            resultDiv.className = 'selected-pdf-list';
            
            const title = document.createElement('h4');
            title.innerHTML = '<i class="fas fa-file-pdf"></i> Arquivos selecionados:';
            resultDiv.appendChild(title);
            
            const filesList = document.createElement('ul');
            filesList.className = 'pdf-files-list';
            
            for (let i = 0; i < pdfFileInput.files.length; i++) {
                const listItem = document.createElement('li');
                listItem.textContent = pdfFileInput.files[i].name;
                filesList.appendChild(listItem);
            }
            
            resultDiv.appendChild(filesList);
            
            // Remover visualização anterior, se existir
            const existingPdfList = document.querySelector('.selected-pdf-list');
            if (existingPdfList) {
                existingPdfList.remove();
            }
            
            // Adicionar nova visualização após o formulário
            if (pdfUploadForm) {
                pdfUploadForm.appendChild(resultDiv);
            }
        } else {
            pdfFilePlaceholder.textContent = 'Nenhum arquivo selecionado';
            
            // Remover visualização anterior, se existir
            const existingPdfList = document.querySelector('.selected-pdf-list');
            if (existingPdfList) {
                existingPdfList.remove();
            }
        }
    }
    
    // Configurar os event listeners para o botão de seleção de PDFs
    if (pdfSelectBtn) {
        pdfSelectBtn.addEventListener('click', function() {
            if (pdfFileInput) {
                pdfFileInput.click();
            }
        });
    }
    
    // Event listener para quando arquivos são selecionados
    if (pdfFileInput) {
        pdfFileInput.addEventListener('change', function() {
            updatePdfFilenameDisplay();
        });
    }
    
    // Event listener para envio do formulário de PDFs
    if (pdfProcessBtn && pdfFileInput) {
        pdfProcessBtn.addEventListener('click', function(e) {
            e.preventDefault();
            
            if (pdfFileInput.files.length === 0) {
                showNotification('Por favor, selecione pelo menos um arquivo PDF para processar.', 'warning');
                return;
            }
            
            // Criar FormData e adicionar os arquivos
            const formData = new FormData();
            for (let i = 0; i < pdfFileInput.files.length; i++) {
                formData.append('pdf_files[]', pdfFileInput.files[i]);
            }
            
            // Mostrar indicador de processamento
            if (pdfUploadForm) hideElement(pdfUploadForm);
            showElement(pdfProcessingIndicator);
            pdfProgressBar.style.width = '0%';
            
            // Função de atualização de progresso simulado
            let progress = 0;
            const progressInterval = setInterval(function() {
                if (progress < 90) {
                    progress += 5;
                    pdfProgressBar.style.width = progress + '%';
                }
            }, 1000);
            
            // Enviar arquivos para processamento
            fetch('/processar-pdf', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                clearInterval(progressInterval);
                pdfProgressBar.style.width = '100%';
                
                // Resetar interface após um momento
                setTimeout(() => {
                    hideElement(pdfProcessingIndicator);
                    if (pdfUploadForm) showElement(pdfUploadForm);
                    
                    // Mostrar resultados
                    showElement(pdfResults);
                    pdfResults.innerHTML = renderPdfResults(data);
                    
                    // Se houver arquivos JSON gerados, mostrar a seção
                    if (data.sucesso && data.resultados && data.resultados.length > 0) {
                        const jsonFiles = data.resultados.flatMap(r => r.arquivos_disponiveis || []);
                        
                        if (jsonFiles && jsonFiles.length > 0) {
                            showElement(jsonFilesFromPdf);
                            renderJsonFilesFromPdf(jsonFiles);
                        }
                    }
                }, 500);
            })
            .catch(error => {
                clearInterval(progressInterval);
                hideElement(pdfProcessingIndicator);
                if (pdfUploadForm) showElement(pdfUploadForm);
                showNotification('Erro ao processar os arquivos: ' + error.message, 'error');
            });
        });
    }
    
    // Renderizar resultados do processamento PDF
    function renderPdfResults(data) {
        if (!data.sucesso) {
            return `
                <div class="pdf-result-item error">
                    <div class="pdf-result-header">
                        <i class="fas fa-times-circle"></i>
                        <h4>Erro no Processamento</h4>
                    </div>
                    <div class="pdf-result-body">
                        <p>${data.mensagem || 'Ocorreu um erro desconhecido.'}</p>
                    </div>
                </div>
            `;
        }
        
        let resultsHtml = `
            <h3>Resultado do Processamento (${data.total_processados} arquivos)</h3>
            <div class="pdf-results-list">
        `;
        
        data.resultados.forEach(resultado => {
            const statusClass = resultado.sucesso ? 'success' : 'error';
            const statusIcon = resultado.sucesso ? 'fa-check-circle' : 'fa-times-circle';
            
            resultsHtml += `
                <div class="pdf-result-item ${statusClass}">
                    <div class="pdf-result-header">
                        <i class="fas ${statusIcon}"></i>
                        <h4>${resultado.nome_arquivo}</h4>
                    </div>
                    <div class="pdf-result-body">
                        <p>${resultado.mensagem}</p>
                        ${resultado.sucesso && resultado.arquivos_disponiveis ? `
                            <p>Arquivos JSON gerados:</p>
                            <ul class="pdf-files-list">
                                ${resultado.arquivos_disponiveis.map(arquivo => `
                                    <li>${arquivo}</li>
                                `).join('')}
                            </ul>
                        ` : ''}
                        ${!resultado.sucesso && resultado.detalhes ? `
                            <div class="error-details">${resultado.detalhes}</div>
                        ` : ''}
                    </div>
                </div>
            `;
        });
        
        resultsHtml += '</div>';
        return resultsHtml;
    }
    
    // Renderizar arquivos JSON gerados a partir dos PDFs
    function renderJsonFilesFromPdf(files) {
        if (!pdfJsonFiles) return;
        
        pdfJsonFiles.innerHTML = '';
        
        files.forEach(file => {
            const fileItem = document.createElement('div');
            fileItem.className = 'file-item';
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'json-file-checkbox';
            checkbox.id = `json-file-${file.replace(/[^a-zA-Z0-9]/g, '-')}`;
            checkbox.dataset.filename = file;
            
            const label = document.createElement('label');
            label.className = 'file-label';
            label.htmlFor = checkbox.id;
            label.textContent = file;
            
            fileItem.appendChild(checkbox);
            fileItem.appendChild(label);
            
            pdfJsonFiles.appendChild(fileItem);
        });
    }
    
    // Event listener para processar os arquivos JSON gerados
    const processJsonBtn = document.getElementById('process-pdf-json-btn');
    if (processJsonBtn) {
        processJsonBtn.addEventListener('click', function() {
            const selectedJsonFiles = Array.from(document.querySelectorAll('.json-file-checkbox:checked'))
                .map(checkbox => checkbox.dataset.filename);
            
            if (selectedJsonFiles.length === 0) {
                showNotification('Por favor, selecione pelo menos um arquivo JSON para processar.', 'warning');
                return;
            }
            
            // Aqui você pode adicionar o código para processar os arquivos JSON selecionados
            showNotification(`Processando ${selectedJsonFiles.length} arquivos JSON.`, 'info');
            
            // Exemplo de chamada de processamento (substitua pelo seu endpoint real)
            fetch('/processar', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ arquivos: selectedJsonFiles })
            })
            .then(response => response.json())
            .then(data => {
                console.log('Resultado do processamento:', data);
                showNotification('Processamento concluído com sucesso!', 'info');
                
                // Exibir resultados detalhados
                const resultsDiv = document.getElementById('results');
                if (resultsDiv) {
                    let resultsHtml = '<h3>Resultados do Processamento</h3>';
                    
                    data.resultados.forEach(resultado => {
                        const nomeArquivo = resultado.arquivo_exibicao || resultado.arquivo;
                        const statusClass = resultado.status === 'Sucesso' ? 'result-success' : 'result-error';
                        const statusIcon = resultado.status === 'Sucesso' ? 'fa-check-circle' : 'fa-times-circle';
                        
                        resultsHtml += `
                            <div class="result-item ${statusClass}">
                                <div class="result-header">
                                    <i class="fas ${statusIcon}"></i>
                                    <h4>${nomeArquivo}</h4>
                                </div>
                                <div class="result-body">
                                    <p>${resultado.mensagem}</p>
                                    ${resultado.status !== 'Sucesso' && resultado.tipo_erro ? `
                                        <p>Tipo de erro: ${resultado.tipo_erro}</p>
                                    ` : ''}
                                </div>
                            </div>
                        `;
                    });
                    
                    resultsDiv.innerHTML = resultsHtml;
                }
            })
            .catch(error => {
                console.error('Erro ao processar:', error);
                showNotification('Erro ao processar os arquivos JSON.', 'error');
            });
        });
    }
});