import os
import boto3
import json
import time
import logging
import glob
import re
from dotenv import load_dotenv
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('textract-json-response')

# Load environment variables
load_dotenv()

# AWS Configuration
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')

# Initialize S3 and Textract clients
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
    """Uploads a file to the S3 bucket"""
    logger.info(f"=== Starting upload to S3 ===")
    s3_object_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path) / (1024 * 1024)  # Size in MB
    
    try:
        logger.info(f"Sending file '{file_path}' (size: {file_size:.2f} MB) to '{S3_BUCKET_NAME}/{s3_object_name}'")
        start_time = time.time()
        s3.upload_file(file_path, S3_BUCKET_NAME, s3_object_name)
        elapsed_time = time.time() - start_time
        logger.info(f"Upload completed successfully in {elapsed_time:.2f} seconds")
        return s3_object_name
    except Exception as e:
        logger.error(f"Error uploading to S3: {str(e)}", exc_info=True)
        return None

def start_document_analysis(document_name):
    """Starts asynchronous document analysis"""
    try:
        logger.info(f"Starting document analysis for: {document_name}")
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
        logger.info(f"Analysis job started with ID: {job_id}")
        return job_id
    except Exception as e:
        logger.error(f"Error starting document analysis: {e}")
        return None

def start_text_detection(document_name):
    """Starts asynchronous text detection"""
    try:
        logger.info(f"Starting text detection for: {document_name}")
        response = textract.start_document_text_detection(
            DocumentLocation={
                'S3Object': {
                    'Bucket': S3_BUCKET_NAME,
                    'Name': document_name
                }
            }
        )
        job_id = response['JobId']
        logger.info(f"Text detection job started with ID: {job_id}")
        return job_id
    except Exception as e:
        logger.error(f"Error starting text detection: {e}")
        return None

def check_job_status(job_id, job_type='ANALYSIS'):
    """Checks the status of a job"""
    try:
        if job_type == 'ANALYSIS':
            response = textract.get_document_analysis(JobId=job_id)
        else:  # TEXT_DETECTION
            response = textract.get_document_text_detection(JobId=job_id)
            
        status = response['JobStatus']
        logger.info(f"Status of job {job_id}: {status}")
        return status
    except Exception as e:
        logger.error(f"Error checking job status: {e}")
        return None

def wait_for_job_completion(job_id, job_type='ANALYSIS', max_time=300):
    """Waits for a job to complete, with timeout"""
    logger.info(f"=== Starting job monitoring for {job_id} ({job_type}) ===")
    start_time = time.time()
    status = check_job_status(job_id, job_type)
    
    progress_interval = 30  # Progress log every 30 seconds
    last_progress_time = start_time
    
    while status in ['SUBMITTED', 'IN_PROGRESS']:
        # Check timeout
        current_time = time.time()
        elapsed = current_time - start_time
        
        if elapsed > max_time:
            logger.warning(f"Timeout waiting for job completion after {elapsed:.2f} seconds")
            return False
        
        # Periodic progress log
        if current_time - last_progress_time > progress_interval:
            logger.info(f"Job {job_id} still in progress... ({elapsed:.2f} seconds elapsed, {(elapsed/max_time)*100:.1f}% of timeout)")
            last_progress_time = current_time
            
        # Wait and check again
        wait_time = 5
        logger.debug(f"Job in progress. Checking again in {wait_time} seconds...")
        time.sleep(wait_time)
        status = check_job_status(job_id, job_type)
    
    total_time = time.time() - start_time
    if status == 'SUCCEEDED':
        logger.info(f"Job {job_id} completed successfully in {total_time:.2f} seconds")
    else:
        logger.error(f"Job {job_id} failed with status: {status} after {total_time:.2f} seconds")
    
    return status == 'SUCCEEDED'

def get_complete_results(job_id, job_type='ANALYSIS'):
    """Gets all results from a job, including all pages"""
    logger.info(f"=== Getting complete results for job {job_id} ===")
    if job_type == 'ANALYSIS':
        get_results_function = textract.get_document_analysis
    else:  # TEXT_DETECTION
        get_results_function = textract.get_document_text_detection
    
    # Get first page of results
    start_time = time.time()
    logger.info(f"Getting first page of results for job {job_id}")
    response = get_results_function(JobId=job_id)
    
    # Collect all result pages
    all_responses = [response]
    next_token = response.get('NextToken')
    
    page_count = 1
    while next_token:
        page_count += 1
        logger.info(f"Getting page {page_count} of results...")
        response = get_results_function(JobId=job_id, NextToken=next_token)
        all_responses.append(response)
        next_token = response.get('NextToken')
    
    elapsed_time = time.time() - start_time
    logger.info(f"Complete results obtained in {elapsed_time:.2f} seconds ({len(all_responses)} result pages)")
    
    # Add more details about the obtained data
    doc_metadata = response.get('DocumentMetadata', {})
    if doc_metadata:
        logger.info(f"Document metadata: {doc_metadata}")
    
    return all_responses

def save_json_response(responses, output_file):
    """Saves the responses in JSON format"""
    try:
        # Save in JSON format (indented for readability)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(responses, f, indent=2, default=str)
        
        logger.info(f"Response saved to: {output_file}")
        
        # Additional information
        num_blocks = sum(len(response.get('Blocks', [])) for response in responses)
        logger.info(f"Total number of blocks in response: {num_blocks}")
        
        # Count block types
        block_types = {}
        for response in responses:
            for block in response.get('Blocks', []):
                block_type = block.get('BlockType', 'UNKNOWN')
                block_types[block_type] = block_types.get(block_type, 0) + 1
        
        logger.info("Found block types:")
        for block_type, count in block_types.items():
            logger.info(f"  - {block_type}: {count}")
        
        return True
    except Exception as e:
        logger.error(f"Error saving JSON response: {e}")
        return False

def process_document(file_path):
    """Processes a document and saves the JSON responses"""
    logger.info(f"========================================")
    logger.info(f"=== STARTING DOCUMENT PROCESSING ===")
    logger.info(f"========================================")
    logger.info(f"File: {file_path}")
    process_start_time = time.time()
    
    # Upload to S3
    s3_object_name = upload_to_s3(file_path)
    if not s3_object_name:
        logger.error("Failed to upload to S3")
        return False
    
    # Get the directory where the file is located to save results there
    output_dir = os.path.dirname(file_path)
    base_filename = os.path.splitext(os.path.basename(file_path))[0]
    logger.info(f"Base file name: {base_filename}")
    logger.info(f"Saving results to: {output_dir}")
    
    # Start jobs
    logger.info("=== Starting jobs in Textract ===")
    analysis_job_id = start_document_analysis(s3_object_name)
    text_job_id = start_text_detection(s3_object_name)
    
    if not analysis_job_id or not text_job_id:
        logger.error("Failed to start jobs")
        return False
    
    success = True
    
    # Document analysis (tables, forms)
    logger.info("=== Processing document analysis job ===")
    if wait_for_job_completion(analysis_job_id, 'ANALYSIS'):
        analysis_responses = get_complete_results(analysis_job_id, 'ANALYSIS')
        analysis_output = os.path.join(output_dir, f"{base_filename}_analysis.json")
        if not save_json_response(analysis_responses, analysis_output):
            success = False
    else:
        logger.error("Document analysis job failed or timed out")
        success = False
    
    # Text detection
    logger.info("=== Processing text detection job ===")
    if wait_for_job_completion(text_job_id, 'TEXT_DETECTION'):
        text_responses = get_complete_results(text_job_id, 'TEXT_DETECTION')
        text_output = os.path.join(output_dir, f"{base_filename}_text.json")
        if not save_json_response(text_responses, text_output):
            success = False
    else:
        logger.error("Text detection job failed or timed out")
        success = False
    
    total_process_time = time.time() - process_start_time
    logger.info(f"========================================")
    logger.info(f"=== END OF DOCUMENT PROCESSING ===")
    logger.info(f"Total processing time: {total_process_time:.2f} seconds ({total_process_time/60:.2f} minutes)")
    logger.info(f"Status: {'Success' if success else 'Failure'}")
    logger.info(f"========================================")
    
    return success

def process_all_folders():
    """Processes all PDF files following the pattern [number]_Bula.pdf in subdirectories"""
    logger.info("Starting processing of all folders...")
    
    # Get list of directories (excluding special ones)
    root_dir = os.getcwd()
    dirs = [d for d in os.listdir(root_dir) 
            if os.path.isdir(os.path.join(root_dir, d)) 
            and not d.startswith('.') 
            and d not in ['venv', 'html_output', 'resultados_json', 'resultados_async']]
    
    logger.info(f"Found {len(dirs)} folders to process")
    
    successful_dirs = 0
    failed_dirs = 0
    skipped_dirs = 0
    
    for dir_name in dirs:
        dir_path = os.path.join(root_dir, dir_name)
        logger.info(f"Processing folder: {dir_name}")
        
        # Look for files following the pattern [number]_Bula.pdf
        pdf_pattern = os.path.join(dir_path, "*_Bula.pdf")
        matching_files = glob.glob(pdf_pattern)
        
        if not matching_files:
            logger.warning(f"No files found with pattern '*_Bula.pdf' in {dir_name}")
            skipped_dirs += 1
            continue
        
        if len(matching_files) > 1:
            logger.warning(f"Multiple files found in {dir_name}, using the first: {matching_files}")
            
        pdf_file = matching_files[0]
        logger.info(f"File found: {pdf_file}")
        
        # Check if JSONs already exist to avoid reprocessing
        base_filename = os.path.splitext(os.path.basename(pdf_file))[0]
        analysis_json = os.path.join(dir_path, f"{base_filename}_analysis.json")
        text_json = os.path.join(dir_path, f"{base_filename}_text.json")
        
        if os.path.exists(analysis_json) and os.path.exists(text_json):
            logger.info(f"JSON files already exist for {base_filename}, skipping processing")
            skipped_dirs += 1
            continue
        
        # Process document
        if process_document(pdf_file):
            successful_dirs += 1
            logger.info(f"Processing of {dir_name} completed successfully")
        else:
            failed_dirs += 1
            logger.error(f"Failed to process {dir_name}")
    
    logger.info("=== PROCESSING SUMMARY ===")
    logger.info(f"Total folders: {len(dirs)}")
    logger.info(f"Processed successfully: {successful_dirs}")
    logger.info(f"Failed processing: {failed_dirs}")
    logger.info(f"Folders skipped: {skipped_dirs}")
    
    return successful_dirs > 0 and failed_dirs == 0

def main():
    # If a specific file is provided, process only it
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return False
        return process_document(file_path)
    
    # Otherwise, process all folders
    return process_all_folders()

if __name__ == "__main__":
    success = main()
    if success:
        print("Processing completed successfully!")
    else:
        print("Errors occurred during processing.")
        sys.exit(1) 