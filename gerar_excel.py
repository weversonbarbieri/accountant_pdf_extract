import json
import sys
import os
import pandas as pd
from datetime import datetime
import logging
from typing import Dict, List, Any, Tuple
from collections import defaultdict
from analisar_json import AnalisadorJSON
import glob
import numpy as np
class GeradorExcel:
    def __init__(self, arquivo_json: str):
        self.arquivo_json = arquivo_json
        self.analisador = AnalisadorJSON(arquivo_json)
        self.texto_por_pagina = defaultdict(list)
        self.chave_valor_por_pagina = defaultdict(list)
        self.setup_logging()
    
    def setup_logging(self):
        """Configura o sistema de logging"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f"log_excel_generator_{timestamp}.txt"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger('excel_generator')
        self.logger.info(f"Iniciando processamento - Log salvo em: {log_file}")
    
    def carregar_dados(self) -> None:
        """Carrega os dados do arquivo JSON usando o AnalisadorJSON"""
        self.analisador.carregar_dados()
        self.analisador.analisar_blocos()
        self.analisador.calcular_estatisticas()
        self.logger.info(f"Arquivo JSON carregado e analisado com sucesso: {self.arquivo_json}")
    
    def _normalizar_confianca(self, valor: float) -> float:
        """Normaliza o valor de confiança para estar entre 0 e 1"""
        # Se o valor for maior que 1, assume que está em porcentagem e divide por 100
        if valor > 1.0:
            valor = valor / 100.0
        return min(1.0, max(0.0, valor))

    def extrair_texto_e_chave_valor(self) -> None:
        """Extrai texto e pares chave-valor do JSON usando os dados já analisados"""
        # Extrair texto das linhas
        for pagina_num, blocos in self.analisador.posicoes_por_pagina.items():
            # Dicionário para armazenar chaves e valores por ID
            chaves = {}
            valores = {}
            
            # Primeiro, identificar todos os blocos de chave e valor
            for bloco in blocos:
                if bloco['tipo'] == 'LINE':
                    # Encontrar o bloco original para obter o texto e confiança
                    for pagina in self.analisador.dados:
                        for b in pagina.get('Blocks', []):
                            if b.get('Id') == bloco['id']:
                                texto = b.get('Text', '')
                                confianca_bruta = float(b.get('Confidence', 0))
                                confianca = self._normalizar_confianca(confianca_bruta)
                                self.logger.info(f"Confiança bruta (LINE): {confianca_bruta}, Normalizada: {confianca}")
                                
                                # Filtrar linhas vazias ou com muito pouco conteúdo
                                if texto.strip() and len(texto.strip()) > 2:
                                    # Obter coordenadas do bloco
                                    geometry = b.get('Geometry', {})
                                    bbox = geometry.get('BoundingBox', {})
                                    top = bbox.get('Top', 0)
                                    
                                    self.texto_por_pagina[pagina_num].append({
                                        'texto': texto,
                                        'confianca': confianca,
                                        'top': top
                                    })
                                break
                
                elif bloco['tipo'] == 'KEY_VALUE_SET':
                    # Encontrar o bloco original para obter informações de chave-valor
                    for pagina in self.analisador.dados:
                        for b in pagina.get('Blocks', []):
                            if b.get('Id') == bloco['id']:
                                # Verificar se é uma chave ou um valor
                                entity_types = b.get('EntityTypes', [])
                                bloco_id = b.get('Id', '')
                                confianca_bruta = float(b.get('Confidence', 0))
                                confianca = self._normalizar_confianca(confianca_bruta)
                                self.logger.info(f"Confiança bruta (KEY_VALUE_SET): {confianca_bruta}, Normalizada: {confianca}")
                                
                                # Extrair o texto do bloco
                                texto = self._extrair_texto_chave_valor(b)
                                if not texto:
                                    continue
                                
                                # Obter coordenadas do bloco
                                geometry = b.get('Geometry', {})
                                bbox = geometry.get('BoundingBox', {})
                                top = bbox.get('Top', 0)
                                left = bbox.get('Left', 0)
                                
                                # Verificar relacionamentos para encontrar o par chave-valor
                                relacionamentos = b.get('Relationships', [])
                                
                                if 'KEY' in entity_types:
                                    chaves[bloco_id] = {
                                        'texto': texto,
                                        'confianca': confianca,
                                        'relacionamentos': relacionamentos,
                                        'top': top,
                                        'left': left
                                    }
                                elif 'VALUE' in entity_types:
                                    valores[bloco_id] = {
                                        'texto': texto,
                                        'confianca': confianca,
                                        'relacionamentos': relacionamentos,
                                        'top': top,
                                        'left': left
                                    }
                                break
                
                elif bloco['tipo'] == 'SELECTION_ELEMENT':
                    # Encontrar o bloco original para obter informações de seleção
                    for pagina in self.analisador.dados:
                        for b in pagina.get('Blocks', []):
                            if b.get('Id') == bloco['id']:
                                selection_status = b.get('SelectionStatus', '')
                                confianca_bruta = float(b.get('Confidence', 0))
                                confianca = self._normalizar_confianca(confianca_bruta)
                                self.logger.info(f"Confiança bruta (SELECTION_ELEMENT): {confianca_bruta}, Normalizada: {confianca}")
                                
                                # Obter coordenadas do bloco
                                geometry = b.get('Geometry', {})
                                bbox = geometry.get('BoundingBox', {})
                                top = bbox.get('Top', 0)
                                left = bbox.get('Left', 0)
                                
                                # Adicionar como um par chave-valor especial
                                texto = '[X]' if selection_status == 'SELECTED' else '[ ]'
                                self.chave_valor_por_pagina[pagina_num].append({
                                    'chave': '',
                                    'valor': texto,
                                    'confianca': confianca,
                                    'top': top,
                                    'left': left
                                })
                                break
            
            # Agora, associar chaves e valores com base nos relacionamentos
            pares_chave_valor = self._associar_chaves_valores(chaves, valores)
            
            # Ordenar os pares por posição na página (top, left)
            pares_chave_valor.sort(key=lambda x: (x['top'], x['left']))
            
            # Adicionar os pares à lista da página
            for par in pares_chave_valor:
                self.chave_valor_por_pagina[pagina_num].append(par)
    
    def _associar_chaves_valores(self, chaves: Dict, valores: Dict) -> List[Dict]:
        """Associa chaves e valores com base nos relacionamentos e posicionamento"""
        pares = []
        
        # Criar um mapa de IDs para facilitar a busca
        mapa_ids = {}
        for key_id, key_data in chaves.items():
            mapa_ids[key_id] = ('chave', key_data)
        for value_id, value_data in valores.items():
            mapa_ids[value_id] = ('valor', value_data)
        
        # Primeiro, identificar todos os números identificadores
        identificadores = {}
        for key_id, key_data in chaves.items():
            texto = key_data['texto'].strip()
            # Verificar se é um número identificador (geralmente um único dígito)
            if texto.isdigit() and len(texto) <= 2:
                identificadores[key_id] = {
                    'numero': texto,
                    'top': key_data['top'],
                    'left': key_data['left']
                }
        
        # Processar relacionamentos para associar chaves e valores
        for key_id, key_data in chaves.items():
            chave_texto = key_data['texto']
            chave_confianca = key_data['confianca']
            chave_top = key_data['top']
            chave_left = key_data['left']
            valor_texto = ''
            valor_confianca = 0
            valor_top = 0
            valor_left = 0
            numero_identificador = ''
            
            # Procurar o valor associado à chave
            for rel in key_data['relacionamentos']:
                if rel['Type'] == 'VALUE':
                    for value_id in rel.get('Ids', []):
                        if value_id in valores:
                            valor_texto = valores[value_id]['texto']
                            valor_confianca = valores[value_id]['confianca']
                            valor_top = valores[value_id]['top']
                            valor_left = valores[value_id]['left']
                            break
            
            # Se não encontrou o valor pelo relacionamento direto, procurar por proximidade espacial
            if not valor_texto:
                # Procurar por checkboxes próximas
                for value_id, value_data in valores.items():
                    # Verificar se é uma checkbox
                    if value_data['texto'] in ['[X]', '[ ]']:
                        # Verificar se está próximo verticalmente (dentro de uma margem)
                        margem_vertical = 0.05  # 5% da altura da página
                        if abs(value_data['top'] - chave_top) < margem_vertical:
                            valor_texto = value_data['texto']
                            valor_confianca = value_data['confianca']
                            valor_top = value_data['top']
                            valor_left = value_data['left']
                            break
            
            # Procurar número identificador associado
            for id_id, id_data in identificadores.items():
                # Verificar se está próximo horizontalmente (à esquerda) ou verticalmente (acima)
                margem_horizontal = 0.1  # 10% da largura da página
                margem_vertical = 0.05   # 5% da altura da página
                
                if (abs(id_data['left'] - valor_left) < margem_horizontal and 
                    abs(id_data['top'] - valor_top) < margem_vertical):
                    numero_identificador = id_data['numero']
                    break
            
            # Adicionar o par à lista se tiver tanto chave quanto valor
            if chave_texto and valor_texto:
                confianca_final = max(chave_confianca, valor_confianca)
                pares.append({
                    'chave': chave_texto,
                    'valor': valor_texto,
                    'confianca': confianca_final,
                    'top': min(chave_top, valor_top),
                    'left': min(chave_left, valor_left),
                    'numero_identificador': numero_identificador
                })
        
        return pares
    
    def _extrair_texto_chave_valor(self, bloco: Dict) -> str:
        """Extrai o texto de um bloco chave-valor"""
        texto = ""
        
        # Verificar relacionamentos para encontrar o texto
        for rel in bloco.get('Relationships', []):
            if rel['Type'] == 'CHILD':
                for child_id in rel.get('Ids', []):
                    # Encontrar o bloco filho
                    for pagina in self.analisador.dados:
                        for b in pagina.get('Blocks', []):
                            if b.get('Id') == child_id:
                                if b.get('BlockType') == 'WORD':
                                    texto += b.get('Text', '') + ' '
                                elif b.get('BlockType') == 'SELECTION_ELEMENT':
                                    # Adicionar indicador de seleção
                                    selection_status = b.get('SelectionStatus', '')
                                    if selection_status == 'SELECTED':
                                        texto += '[X] '
                                    else:
                                        texto += '[ ] '
        
        return texto.strip()
    
    def gerar_csv(self) -> None:
        """Gera arquivo CSV com os pares chave-valor extraídos"""
        # Criar diretório de saída se não existir
        output_dir = "csv_output"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Gerar nome do arquivo baseado no arquivo JSON de entrada
        base_name = os.path.splitext(os.path.basename(self.arquivo_json))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Preparar dados para o CSV
        dados_csv = []
        
        # Adicionar pares chave-valor
        for pagina_num, pares in self.chave_valor_por_pagina.items():
            for par in pares:
                # Converter confiança para porcentagem e arredondar para 2 casas decimais
                confianca_percentual = round(par['confianca'] * 100, 2)
                
                # Preparar o valor para exibição
                valor = par['valor']
                if par.get('numero_identificador'):
                    valor = f"{par['numero_identificador']} {valor}"
                
                dados_csv.append({
                    'Página': pagina_num,
                    'Chave': par['chave'],
                    'Valor': valor,
                    'Confiança (%)': confianca_percentual,
                    'top': par['top'],
                    'left': par['left']
                })
        
        # Criar DataFrame e salvar como CSV
        if dados_csv:
            df_csv = pd.DataFrame(dados_csv)
            # Ordenar por página e posição vertical (top) em ordem crescente
            df_csv = df_csv.sort_values(by=['Página', 'top'], ascending=[True, True])
            # Remover as colunas 'top' e 'left' antes de salvar
            df_csv = df_csv.drop(columns=['top', 'left'])
            # Salvar como CSV
            csv_path = f"{output_dir}/{base_name}_{timestamp}.csv"
            df_csv.to_csv(csv_path, index=False, encoding='utf-8-sig')
            self.logger.info(f"Arquivo CSV gerado com sucesso: {csv_path}")
        else:
            self.logger.warning("Nenhum par chave-valor encontrado para gerar o CSV.")
    
    def gerar_excel(self) -> None:
        """Gera arquivos Excel com o texto e pares chave-valor extraídos"""
        # Criar diretório de saída se não existir
        output_dir = "excel_output"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Gerar nome do arquivo baseado no arquivo JSON de entrada
        base_name = os.path.splitext(os.path.basename(self.arquivo_json))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Criar arquivo Excel com múltiplas abas
        with pd.ExcelWriter(f"{output_dir}/{base_name}_{timestamp}.xlsx", engine='openpyxl') as writer:
            # Aba de estatísticas
            estatisticas = {
                'Métrica': [
                    'Total de Páginas',
                    'Total de Blocos',
                    'Média de Blocos por Página',
                    'Mediana de Blocos por Página',
                    'Mínimo de Blocos em uma Página',
                    'Máximo de Blocos em uma Página',
                    'Desvio Padrão'
                ],
                'Valor': [
                    self.analisador.estatisticas['total_paginas'],
                    self.analisador.estatisticas['total_blocos'],
                    self.analisador.estatisticas['media_blocos'],
                    self.analisador.estatisticas['mediana_blocos'],
                    self.analisador.estatisticas['min_blocos'],
                    self.analisador.estatisticas['max_blocos'],
                    self.analisador.estatisticas['desvio_padrao']
                ]
            }
            df_estatisticas = pd.DataFrame(estatisticas)
            df_estatisticas.to_excel(writer, sheet_name='Estatísticas', index=False)
            
            # Aba de distribuição de tipos por página
            tipos_por_pagina = []
            for pagina_num, tipos in self.analisador.tipos_por_pagina.items():
                for tipo, count in tipos.items():
                    tipos_por_pagina.append({
                        'Página': pagina_num,
                        'Tipo': tipo,
                        'Quantidade': count
                    })
            df_tipos = pd.DataFrame(tipos_por_pagina)
            df_tipos.to_excel(writer, sheet_name='Tipos_por_Página', index=False)
            
            # Aba de texto por página
            for pagina_num, textos in self.texto_por_pagina.items():
                if textos:  # Só criar aba se houver texto
                    df_texto = pd.DataFrame(textos)
                    # Ordenar por posição vertical em ordem crescente (do topo para baixo)
                    df_texto = df_texto.sort_values(by='top', ascending=True)
                    # Converter confiança para porcentagem
                    df_texto['confianca'] = df_texto['confianca'].apply(lambda x: round(x * 100, 2))
                    df_texto.rename(columns={'confianca': 'Confiança (%)'}, inplace=True)
                    # Remover a coluna 'top' antes de salvar
                    df_texto = df_texto.drop(columns=['top'])
                    df_texto.to_excel(writer, sheet_name=f'Texto_Página_{pagina_num}', index=False)
            
            # Aba de pares chave-valor por página
            for pagina_num, pares in self.chave_valor_por_pagina.items():
                if pares:  # Só criar aba se houver pares chave-valor
                    # Criar DataFrame apenas com as colunas chave e valor
                    df_pares = pd.DataFrame(pares)
                    # Ordenar por posição vertical em ordem decrescente
                    df_pares = df_pares.sort_values(by='top', ascending=False)
                    # Converter confiança para porcentagem
                    df_pares['confianca'] = df_pares['confianca'].apply(lambda x: round(x * 100, 2))
                    df_pares.rename(columns={'confianca': 'Confiança (%)'}, inplace=True)
                    df_pares.to_excel(writer, sheet_name=f'Chave_Valor_Página_{pagina_num}', index=False)
        
        self.logger.info(f"Arquivo Excel gerado com sucesso: {output_dir}/{base_name}_{timestamp}.xlsx")

def processar_arquivo(arquivo_json: str) -> None:
    """Processa um único arquivo JSON"""
    print(f"\nProcessando arquivo: {arquivo_json}")
    try:
        gerador = GeradorExcel(arquivo_json)
        gerador.carregar_dados()
        gerador.extrair_texto_e_chave_valor()
        gerador.gerar_csv()  # Gerar CSV com as 4 colunas
        gerador.gerar_excel()  # Manter a geração do Excel também
        print(f"Arquivo processado com sucesso: {arquivo_json}")
    except Exception as e:
        print(f"Erro ao processar o arquivo {arquivo_json}: {str(e)}")

def main():
    # Verificar se foi fornecido um arquivo específico como argumento
    if len(sys.argv) > 1:
        arquivo_json = sys.argv[1]
        processar_arquivo(arquivo_json)
    else:
        # Procurar todos os arquivos JSON com "_analysis.json" no nome
        arquivos_json = glob.glob("*_analysis.json")
        
        if not arquivos_json:
            print("Nenhum arquivo JSON com '_analysis.json' no nome foi encontrado.")
            print("Por favor, forneça o caminho do arquivo JSON como argumento ou coloque os arquivos no diretório atual.")
            sys.exit(1)
        
        print(f"Encontrados {len(arquivos_json)} arquivos JSON para processar:")
        for arquivo in arquivos_json:
            print(f"- {arquivo}")
        
        # Processar cada arquivo encontrado
        for arquivo_json in arquivos_json:
            processar_arquivo(arquivo_json)

if __name__ == "__main__":
    main() 