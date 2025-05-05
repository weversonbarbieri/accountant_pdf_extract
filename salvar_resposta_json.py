import os
import boto3
import json
import time
import logging
import glob
import re
from dotenv import load_dotenv
import sys

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('textract-json-response')

# Carregar variáveis de ambiente
load_dotenv()

# Configuração AWS
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')

# Inicializar clientes S3 e Textract
s3 = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

textract = boto3.client(
    'textract',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

def upload_to_s3(file_path):
    """Faz upload de um arquivo para o bucket S3"""
    logger.info(f"=== Iniciando upload para S3 ===")
    s3_object_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path) / (1024 * 1024)  # Tamanho em MB
    
    try:
        logger.info(f"Enviando arquivo '{file_path}' (tamanho: {file_size:.2f} MB) para '{S3_BUCKET_NAME}/{s3_object_name}'")
        start_time = time.time()
        s3.upload_file(file_path, S3_BUCKET_NAME, s3_object_name)
        elapsed_time = time.time() - start_time
        logger.info(f"Upload concluído com sucesso em {elapsed_time:.2f} segundos")
        return s3_object_name
    except Exception as e:
        logger.error(f"Erro ao fazer upload para S3: {str(e)}", exc_info=True)
        return None

def start_document_analysis(document_name):
    """Inicia análise assíncrona de documento"""
    try:
        logger.info(f"Iniciando análise de documento para: {document_name}")
        response = textract.start_document_analysis(
            DocumentLocation={
                'S3Object': {
                    'Bucket': S3_BUCKET_NAME,
                    'Name': document_name
                }
            },
            FeatureTypes=['TABLES', 'FORMS']
        )
        job_id = response['JobId']
        logger.info(f"Job de análise iniciado com ID: {job_id}")
        return job_id
    except Exception as e:
        logger.error(f"Erro ao iniciar análise de documento: {e}")
        return None

def check_job_status(job_id):
    """Verifica o status de um job"""
    try:
        response = textract.get_document_analysis(JobId=job_id)
        status = response['JobStatus']
        logger.info(f"Status do job {job_id}: {status}")
        return status
    except Exception as e:
        logger.error(f"Erro ao verificar status do job: {e}")
        return None

def wait_for_job_completion(job_id, max_time=300):
    """Aguarda a conclusão de um job, com timeout"""
    logger.info(f"=== Iniciando monitoramento de job para {job_id} ===")
    start_time = time.time()
    status = check_job_status(job_id)
    
    progress_interval = 30  # Log de progresso a cada 30 segundos
    last_progress_time = start_time
    
    while status in ['SUBMITTED', 'IN_PROGRESS']:
        # Verificar timeout
        current_time = time.time()
        elapsed = current_time - start_time
        
        if elapsed > max_time:
            logger.warning(f"Timeout aguardando conclusão do job após {elapsed:.2f} segundos")
            return False
        
        # Log de progresso periódico
        if current_time - last_progress_time > progress_interval:
            logger.info(f"Job {job_id} ainda em progresso... ({elapsed:.2f} segundos decorridos, {(elapsed/max_time)*100:.1f}% do timeout)")
            last_progress_time = current_time
            
        # Aguardar e verificar novamente
        wait_time = 5
        logger.debug(f"Job em progresso. Verificando novamente em {wait_time} segundos...")
        time.sleep(wait_time)
        status = check_job_status(job_id)
    
    total_time = time.time() - start_time
    if status == 'SUCCEEDED':
        logger.info(f"Job {job_id} concluído com sucesso em {total_time:.2f} segundos")
    else:
        logger.error(f"Job {job_id} falhou com status: {status} após {total_time:.2f} segundos")
    
    return status == 'SUCCEEDED'

def get_complete_results(job_id):
    """Obtém todos os resultados de um job, incluindo todas as páginas"""
    logger.info(f"=== Obtendo resultados completos para o job {job_id} ===")
    get_results_function = textract.get_document_analysis
    
    # Obter primeira página de resultados
    start_time = time.time()
    logger.info(f"Obtendo primeira página de resultados para o job {job_id}")
    response = get_results_function(JobId=job_id)
    
    # Coletar todas as páginas de resultados
    all_responses = [response]
    next_token = response.get('NextToken')
    
    page_count = 1
    while next_token:
        page_count += 1
        logger.info(f"Obtendo página {page_count} de resultados...")
        response = get_results_function(JobId=job_id, NextToken=next_token)
        all_responses.append(response)
        next_token = response.get('NextToken')
    
    elapsed_time = time.time() - start_time
    logger.info(f"Resultados completos obtidos em {elapsed_time:.2f} segundos ({len(all_responses)} páginas de resultado)")
    
    # Adicionar mais detalhes sobre os dados obtidos
    doc_metadata = response.get('DocumentMetadata', {})
    if doc_metadata:
        logger.info(f"Metadados do documento: {doc_metadata}")
    
    return all_responses

def save_json_response(responses, output_file):
    """Salva as respostas em formato JSON"""
    try:
        # Salvar em formato JSON (indentado para legibilidade)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(responses, f, indent=2, default=str)
        
        logger.info(f"Resposta salva em: {output_file}")
        
        # Informações adicionais
        num_blocks = sum(len(response.get('Blocks', [])) for response in responses)
        logger.info(f"Número total de blocos na resposta: {num_blocks}")
        
        # Contagem de tipos de blocos
        block_types = {}
        for response in responses:
            for block in response.get('Blocks', []):
                block_type = block.get('BlockType', 'UNKNOWN')
                block_types[block_type] = block_types.get(block_type, 0) + 1
        
        logger.info("Tipos de blocos encontrados:")
        for block_type, count in block_types.items():
            logger.info(f"  - {block_type}: {count}")
        
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar resposta JSON: {e}")
        return False

def process_document(file_path):
    """Processa um documento e salva apenas o JSON de análise"""
    logger.info(f"========================================")
    logger.info(f"=== INICIANDO PROCESSAMENTO DE DOCUMENTO ===")
    logger.info(f"========================================")
    logger.info(f"Arquivo: {file_path}")
    
    # Verificar se o arquivo já foi processado
    output_dir = os.path.dirname(file_path)
    base_filename = os.path.splitext(os.path.basename(file_path))[0]
    analysis_output = os.path.join(output_dir, f"{base_filename}_analysis.json")
    
    if os.path.exists(analysis_output):
        logger.info(f"Arquivo de análise já existe: {analysis_output}")
        logger.info(f"Pulando processamento para evitar duplicação.")
        return True
    
    process_start_time = time.time()
    
    # Upload para S3
    s3_object_name = upload_to_s3(file_path)
    if not s3_object_name:
        logger.error("Falha ao fazer upload para S3")
        return False
    
    # Obter o diretório onde o arquivo está localizado para salvar resultados
    logger.info(f"Nome base do arquivo: {base_filename}")
    logger.info(f"Salvando resultados em: {output_dir}")
    
    # Iniciar apenas o job de análise de documento
    logger.info("=== Iniciando job no Textract ===")
    analysis_job_id = start_document_analysis(s3_object_name)
    
    if not analysis_job_id:
        logger.error("Falha ao iniciar job de análise")
        return False
    
    success = True
    
    # Processamento de análise de documento (tabelas, formulários)
    logger.info("=== Processando job de análise de documento ===")
    if wait_for_job_completion(analysis_job_id):
        analysis_responses = get_complete_results(analysis_job_id)
        if not save_json_response(analysis_responses, analysis_output):
            success = False
    else:
        logger.error("Job de análise de documento falhou ou expirou")
        success = False
    
    total_process_time = time.time() - process_start_time
    logger.info(f"========================================")
    logger.info(f"=== FIM DO PROCESSAMENTO DE DOCUMENTO ===")
    logger.info(f"Tempo total de processamento: {total_process_time:.2f} segundos ({total_process_time/60:.2f} minutos)")
    logger.info(f"Status: {'Sucesso' if success else 'Falha'}")
    logger.info(f"========================================")
    
    return success

def process_all_folders():
    """Processa todos os arquivos PDF seguindo o padrão [número]_Bula.pdf em subdiretórios"""
    logger.info("Iniciando processamento de todas as pastas...")
    
    # Obter lista de diretórios (excluindo os especiais)
    root_dir = os.getcwd()
    dirs = [d for d in os.listdir(root_dir) 
            if os.path.isdir(os.path.join(root_dir, d)) 
            and not d.startswith('.') 
            and d not in ['venv', 'html_output', 'resultados_json', 'resultados_async']]
    
    logger.info(f"Encontradas {len(dirs)} pastas para processar")
    
    successful_dirs = 0
    failed_dirs = 0
    skipped_dirs = 0
    
    for dir_name in dirs:
        dir_path = os.path.join(root_dir, dir_name)
        logger.info(f"Processando pasta: {dir_name}")
        
        # Procurar arquivos seguindo o padrão [número]_Bula.pdf
        pdf_pattern = os.path.join(dir_path, "*_Bula.pdf")
        matching_files = glob.glob(pdf_pattern)
        
        if not matching_files:
            logger.warning(f"Nenhum arquivo encontrado com padrão '*_Bula.pdf' em {dir_name}")
            skipped_dirs += 1
            continue
        
        if len(matching_files) > 1:
            logger.warning(f"Múltiplos arquivos encontrados em {dir_name}, usando o primeiro: {matching_files}")
            
        pdf_file = matching_files[0]
        logger.info(f"Arquivo encontrado: {pdf_file}")
        
        # Verificar se o JSON de análise já existe para evitar reprocessamento
        base_filename = os.path.splitext(os.path.basename(pdf_file))[0]
        analysis_json = os.path.join(dir_path, f"{base_filename}_analysis.json")
        
        if os.path.exists(analysis_json):
            logger.info(f"Arquivo JSON de análise já existe para {base_filename}, pulando processamento")
            skipped_dirs += 1
            continue
        
        # Processar documento
        if process_document(pdf_file):
            successful_dirs += 1
            logger.info(f"Processamento de {dir_name} concluído com sucesso")
        else:
            failed_dirs += 1
            logger.error(f"Falha ao processar {dir_name}")
    
    logger.info("=== RESUMO DO PROCESSAMENTO ===")
    logger.info(f"Total de pastas: {len(dirs)}")
    logger.info(f"Processadas com sucesso: {successful_dirs}")
    logger.info(f"Falha no processamento: {failed_dirs}")
    logger.info(f"Pastas puladas: {skipped_dirs}")
    
    return successful_dirs > 0 and failed_dirs == 0

def main():
    # Se um arquivo específico for fornecido, processar apenas ele
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if not os.path.exists(file_path):
            logger.error(f"Arquivo não encontrado: {file_path}")
            return False
        return process_document(file_path)
    
    # Caso contrário, processar todas as pastas
    return process_all_folders()

if __name__ == "__main__":
    success = main()
    if success:
        print("Processamento concluído com sucesso!")
    else:
        print("Ocorreram erros durante o processamento.")
        sys.exit(1) 