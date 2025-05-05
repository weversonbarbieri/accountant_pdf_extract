import os
import logging
import sys
import time
import traceback
from salvar_resposta_json import process_document, logger

# Configuração de registro (logging)
def configure_logging():
    """Configura o logger para o módulo textract"""
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

def processar_pdf(arquivo_pdf):
    """
    Processa um arquivo PDF utilizando Amazon Textract e retorna o resultado.
    
    Args:
        arquivo_pdf (str): Caminho para o arquivo PDF a ser processado
        
    Returns:
        dict: Um dicionário contendo as informações sobre o processamento
              {
                'sucesso': bool,
                'mensagem': str,
                'arquivos_json': list,
                'tempo_processamento': float,
                'detalhes': str
              }
    """
    configure_logging()
    
    resultado = {
        'sucesso': False,
        'mensagem': '',
        'arquivos_json': [],
        'tempo_processamento': 0,
        'detalhes': ''
    }
    
    try:
        if not os.path.exists(arquivo_pdf):
            resultado['mensagem'] = f"Arquivo não encontrado: {arquivo_pdf}"
            return resultado
            
        if not arquivo_pdf.lower().endswith('.pdf'):
            resultado['mensagem'] = f"O arquivo {arquivo_pdf} não é um PDF"
            return resultado
        
        # Verificar se o arquivo já foi processado
        dir_pdf = os.path.dirname(arquivo_pdf)
        base_nome = os.path.splitext(os.path.basename(arquivo_pdf))[0]
        arquivo_analise = os.path.join(dir_pdf, f"{base_nome}_analysis.json")
        
        if os.path.exists(arquivo_analise):
            logger.info(f"Arquivo de análise já existe: {arquivo_analise}")
            resultado['sucesso'] = True
            resultado['mensagem'] = "Arquivo já processado anteriormente"
            resultado['arquivos_json'] = [arquivo_analise]
            return resultado
            
        # Capturar saída do logger
        import io
        log_capture = io.StringIO()
        log_handler = logging.StreamHandler(log_capture)
        log_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        logger.addHandler(log_handler)
        
        # Processar o documento
        inicio = time.time()
        sucesso = process_document(arquivo_pdf)
        tempo_total = time.time() - inicio
        
        # Remover o handler de captura após o processamento
        logger.removeHandler(log_handler)
        
        # Verificar os arquivos JSON gerados
        arquivos_gerados = []
        if os.path.exists(arquivo_analise):
            arquivos_gerados.append(arquivo_analise)
        
        # Construir resultado
        resultado['sucesso'] = sucesso
        resultado['tempo_processamento'] = tempo_total
        resultado['arquivos_json'] = arquivos_gerados
        resultado['detalhes'] = log_capture.getvalue()
        
        if sucesso:
            resultado['mensagem'] = f"PDF processado com sucesso em {tempo_total:.2f} segundos"
        else:
            resultado['mensagem'] = "Falha ao processar o PDF"
            
    except Exception as e:
        resultado['sucesso'] = False
        resultado['mensagem'] = f"Erro ao processar PDF: {str(e)}"
        resultado['detalhes'] = traceback.format_exc()
    
    return resultado

def verificar_configuracao_aws():
    """
    Verifica se as variáveis de ambiente para AWS estão configuradas.
    
    Returns:
        tuple: (bool, str) indicando sucesso e mensagem de status
    """
    from salvar_resposta_json import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_BUCKET_NAME
    
    faltando = []
    if not AWS_ACCESS_KEY_ID:
        faltando.append("AWS_ACCESS_KEY_ID")
    if not AWS_SECRET_ACCESS_KEY:
        faltando.append("AWS_SECRET_ACCESS_KEY")
    if not AWS_REGION:
        faltando.append("AWS_REGION")
    if not S3_BUCKET_NAME:
        faltando.append("S3_BUCKET_NAME")
    
    if faltando:
        return False, f"Configuração AWS incompleta. Variáveis de ambiente faltando: {', '.join(faltando)}"
    
    return True, "Configuração AWS válida" 