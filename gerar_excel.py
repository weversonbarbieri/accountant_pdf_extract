import json
import sys
import os
import pandas as pd
from datetime import datetime
import logging
from typing import Dict, List, Any, Tuple, Optional
from collections import defaultdict
from analisar_json import AnalisadorJSON
import glob

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
                                if texto.strip() and len(texto.strip()) > 1:  # Reduzido para 1 caractere
                                    # Obter coordenadas do bloco
                                    geometry = b.get('Geometry', {})
                                    bbox = geometry.get('BoundingBox', {})
                                    top = bbox.get('Top', 0)
                                    left = bbox.get('Left', 0)
                                    
                                    # Verificar se a linha contém separadores de chave-valor
                                    if ':' in texto or '=' in texto:
                                        partes = texto.split(':' if ':' in texto else '=', 1)
                                        if len(partes) == 2:
                                            chave, valor = partes[0].strip(), partes[1].strip()
                                            if chave and valor:  # Ambos não vazios
                                                self.chave_valor_por_pagina[pagina_num].append({
                                                    'chave': chave,
                                                    'valor': valor,
                                                    'confianca': confianca,
                                                    'top': top,
                                                    'left': left,
                                                    'tipo': 'linha_composta'
                                                })
                                                continue
                                    
                                    self.texto_por_pagina[pagina_num].append({
                                        'texto': texto,
                                        'confianca': confianca,
                                        'top': top,
                                        'left': left
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
                                
                                # Procurar texto próximo que possa ser a chave
                                texto_proximo = self._encontrar_texto_proximo(pagina_num, top, left)
                                
                                # Adicionar como um par chave-valor
                                texto = '[X]' if selection_status == 'SELECTED' else '[ ]'
                                self.chave_valor_por_pagina[pagina_num].append({
                                    'chave': texto_proximo if texto_proximo else '',
                                    'valor': texto,
                                    'confianca': confianca,
                                    'top': top,
                                    'left': left,
                                    'tipo': 'checkbox'
                                })
                                break
            
            # Agora, associar chaves e valores com base nos relacionamentos
            pares_chave_valor = self._associar_chaves_valores(chaves, valores)
            
            # Adicionar os pares à lista da página
            for par in pares_chave_valor:
                self.chave_valor_por_pagina[pagina_num].append(par)
            
            # Ordenar todos os pares da página por posição vertical
            if pagina_num in self.chave_valor_por_pagina:
                self.chave_valor_por_pagina[pagina_num].sort(key=lambda x: (x['top'], x['left']))
    
    def _encontrar_texto_proximo(self, pagina_num: int, top: float, left: float, margem: float = 0.05) -> str:
        """Encontra o texto mais próximo de uma posição específica"""
        texto_mais_proximo = ""
        menor_distancia = float('inf')
        
        # Procurar em texto_por_pagina
        for texto in self.texto_por_pagina.get(pagina_num, []):
            dist_vertical = abs(texto['top'] - top)
            dist_horizontal = abs(texto['left'] - left)
            
            # Calcular distância euclidiana
            distancia = (dist_vertical ** 2 + dist_horizontal ** 2) ** 0.5
            
            if distancia < menor_distancia and distancia < margem:
                menor_distancia = distancia
                texto_mais_proximo = texto['texto']
        
        return texto_mais_proximo
    
    def _associar_chaves_valores(self, chaves: Dict, valores: Dict) -> List[Dict]:
        """Associa chaves e valores com base nos relacionamentos e posicionamento"""
        pares = []
        
        # Aproveitar os relacionamentos diretos e indiretos do analisador
        relacionamentos_diretos = self.analisador.relacionamentos_diretos
        relacionamentos_indiretos = self.analisador.relacionamentos_indiretos
        
        # Detectar padrões nos dados
        padroes = self._detectar_padrao_relacionamento(
            [{'texto': data['texto'], 'left': data['left'], 'top': data['top']} for _, data in chaves.items()],
            [{'texto': data['texto'], 'left': data['left'], 'top': data['top']} for _, data in valores.items()]
        )
        
        # Criar um mapa de IDs para facilitar a busca
        mapa_ids = {}
        for key_id, key_data in chaves.items():
            mapa_ids[key_id] = ('chave', key_data)
        for value_id, value_data in valores.items():
            mapa_ids[value_id] = ('valor', value_data)
        
        # Primeiro, identificar todos os números identificadores e textos especiais
        identificadores = {}
        textos_especiais = {}
        for key_id, key_data in chaves.items():
            texto = key_data['texto'].strip()
            # Verificar se é um número identificador (um ou dois dígitos)
            if texto.isdigit() and len(texto) <= 2:
                identificadores[key_id] = {
                    'numero': texto,
                    'top': key_data['top'],
                    'left': key_data['left']
                }
            # Identificar textos que podem ser parte de um par chave-valor
            elif ':' in texto or '=' in texto:
                partes = texto.split(':' if ':' in texto else '=', 1)
                if len(partes) == 2:
                    textos_especiais[key_id] = {
                        'chave': partes[0].strip(),
                        'valor': partes[1].strip(),
                        'top': key_data['top'],
                        'left': key_data['left'],
                        'confianca': key_data['confianca']
                    }
        
        # Processar textos especiais primeiro
        for key_id, dados in textos_especiais.items():
            pares.append({
                'chave': dados['chave'],
                'valor': dados['valor'],
                'confianca': dados['confianca'],
                'top': dados['top'],
                'left': dados['left'],
                'numero_identificador': '',
                'tipo': 'texto_especial',
                'distancia': 0.0
            })
        
        # Processar cada chave
        for key_id, key_data in chaves.items():
            # Pular se já foi processado como texto especial
            if key_id in textos_especiais:
                continue
            
            chave_texto = key_data['texto']
            chave_confianca = key_data['confianca']
            chave_top = key_data['top']
            chave_left = key_data['left']
            
            # Lista para armazenar todos os valores candidatos
            valores_candidatos = []
            
            # 1. Coletar valores por relacionamento direto
            if key_id in relacionamentos_diretos:
                for value_id in relacionamentos_diretos[key_id]:
                    if value_id in valores:
                        valor = valores[value_id]
                        distancia = self.analisador._verificar_proximidade(
                            {'Geometry': {'BoundingBox': {'Top': chave_top, 'Left': chave_left}}},
                            {'Geometry': {'BoundingBox': {'Top': valor['top'], 'Left': valor['left']}}}
                        )
                        valores_candidatos.append({
                            'texto': valor['texto'],
                            'confianca': valor['confianca'],
                            'top': valor['top'],
                            'left': valor['left'],
                            'distancia': distancia,
                            'tipo': 'relacionamento_direto'
                        })
            
            # 2. Se não encontrou por relacionamento direto, tentar relacionamentos indiretos
            if not valores_candidatos and key_id in relacionamentos_indiretos:
                for value_id in relacionamentos_indiretos[key_id]:
                    if value_id in valores:
                        valor = valores[value_id]
                        distancia = self.analisador._verificar_proximidade(
                            {'Geometry': {'BoundingBox': {'Top': chave_top, 'Left': chave_left}}},
                            {'Geometry': {'BoundingBox': {'Top': valor['top'], 'Left': valor['left']}}}
                        )
                        valores_candidatos.append({
                            'texto': valor['texto'],
                            'confianca': valor['confianca'],
                            'top': valor['top'],
                            'left': valor['left'],
                            'distancia': distancia,
                            'tipo': 'relacionamento_indireto'
                        })
            
            # 3. Se ainda não encontrou, procurar por proximidade espacial
            if not valores_candidatos:
                margem_vertical = 0.12  # 12% da altura da página
                margem_horizontal = 0.20  # 20% da largura da página
                
                for value_id, value_data in valores.items():
                    # Verificar se o valor está próximo da chave
                    if (abs(value_data['top'] - chave_top) < margem_vertical):
                        distancia = self.analisador._verificar_proximidade(
                            {'Geometry': {'BoundingBox': {'Top': chave_top, 'Left': chave_left}}},
                            {'Geometry': {'BoundingBox': {'Top': value_data['top'], 'Left': value_data['left']}}}
                        )
                        
                        if distancia < margem_horizontal:
                            valores_candidatos.append({
                                'texto': value_data['texto'],
                                'confianca': value_data['confianca'],
                                'top': value_data['top'],
                                'left': value_data['left'],
                                'distancia': distancia,
                                'tipo': 'proximidade_espacial'
                            })
            
            # 4. Resolver ambiguidades se houver múltiplos candidatos
            if valores_candidatos:
                valor_selecionado = self._resolver_ambiguidade({
                    'texto': chave_texto,
                    'top': chave_top,
                    'left': chave_left
                }, valores_candidatos, padroes)
                
                if valor_selecionado:
                    # Procurar número identificador associado
                    numero_identificador = ''
                    for id_data in identificadores.values():
                        # Verificar se o identificador está próximo da chave ou do valor
                        if (abs(id_data['top'] - chave_top) < 0.08 or  # 8% margem vertical
                            abs(id_data['top'] - valor_selecionado['top']) < 0.08):
                            if (abs(id_data['left'] - chave_left) < 0.15 or  # 15% margem horizontal
                                abs(id_data['left'] - valor_selecionado['left']) < 0.15):
                                numero_identificador = id_data['numero']
                                break
                    
                    # Adicionar o par encontrado
                    pares.append({
                        'chave': chave_texto,
                        'valor': valor_selecionado['texto'],
                        'confianca': min(chave_confianca, valor_selecionado['confianca']),
                        'top': min(chave_top, valor_selecionado['top']),
                        'left': min(chave_left, valor_selecionado['left']),
                        'numero_identificador': numero_identificador,
                        'tipo': valor_selecionado['tipo'],
                        'distancia': valor_selecionado['distancia']
                    })
        
        # Ordenar pares por confiança e remover duplicatas
        pares.sort(key=lambda x: (-x['confianca'], x.get('distancia', 0)))
        pares_unicos = []
        chaves_processadas = set()
        
        for par in pares:
            chave_valor = (par['chave'], par['valor'])
            if chave_valor not in chaves_processadas:
                chaves_processadas.add(chave_valor)
                pares_unicos.append(par)
        
        return pares_unicos
    
    def _extrair_texto_chave_valor(self, bloco: Dict) -> str:
        """Extrai o texto de um bloco chave-valor com melhor tratamento de casos especiais"""
        texto = ""
        palavras = []
        
        # Verificar relacionamentos para encontrar o texto
        for rel in bloco.get('Relationships', []):
            if rel['Type'] == 'CHILD':
                for child_id in rel.get('Ids', []):
                    # Encontrar o bloco filho
                    for pagina in self.analisador.dados:
                        for b in pagina.get('Blocks', []):
                            if b.get('Id') == child_id:
                                if b.get('BlockType') == 'WORD':
                                    # Armazenar palavra com sua posição
                                    geometry = b.get('Geometry', {}).get('BoundingBox', {})
                                    palavras.append({
                                        'texto': b.get('Text', ''),
                                        'left': geometry.get('Left', 0),
                                        'top': geometry.get('Top', 0)
                                    })
                                elif b.get('BlockType') == 'SELECTION_ELEMENT':
                                    # Adicionar indicador de seleção
                                    selection_status = b.get('SelectionStatus', '')
                                    palavras.append({
                                        'texto': '[X]' if selection_status == 'SELECTED' else '[ ]',
                                        'left': b.get('Geometry', {}).get('BoundingBox', {}).get('Left', 0),
                                        'top': b.get('Geometry', {}).get('BoundingBox', {}).get('Top', 0)
                                    })
        
        # Se encontrou palavras, ordenar por posição
        if palavras:
            # Primeiro, agrupar palavras por linha (usando tolerância vertical)
            tolerancia_vertical = 0.01  # 1% da altura da página
            linhas = {}
            
            for palavra in palavras:
                linha_encontrada = False
                for top in linhas.keys():
                    if abs(palavra['top'] - top) < tolerancia_vertical:
                        linhas[top].append(palavra)
                        linha_encontrada = True
                        break
                
                if not linha_encontrada:
                    linhas[palavra['top']] = [palavra]
            
            # Para cada linha, ordenar palavras da esquerda para direita
            texto_final = []
            for top in sorted(linhas.keys()):
                linha = linhas[top]
                linha.sort(key=lambda x: x['left'])
                texto_linha = ' '.join(p['texto'] for p in linha)
                texto_final.append(texto_linha)
            
            # Juntar linhas com espaço apropriado
            texto = ' '.join(texto_final)
        
        # Limpar espaços extras
        texto = ' '.join(texto.split())
        
        # Verificar se o texto contém caracteres especiais que podem indicar separação chave-valor
        if ':' in texto or '=' in texto:
            # Preservar a separação original
            texto = texto.replace(' :', ':').replace(' = ', '=')
        
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
                try:
                    # Converter confiança para porcentagem e arredondar para 2 casas decimais
                    confianca_percentual = round(par.get('confianca', 0) * 100, 2)
                    
                    # Preparar o valor para exibição
                    valor = par.get('valor', '')
                    chave = par.get('chave', '')
                    
                    # Adicionar identificador se existir
                    if par.get('numero_identificador'):
                        identificador = par['numero_identificador']
                    else:
                        # Tentar extrair identificador do texto
                        identificador = self._extrair_identificador(chave) or self._extrair_identificador(valor)
                    
                    # Determinar o tipo de par
                    tipo_par = par.get('tipo', 'chave_valor')
                    
                    # Calcular posições relativas em porcentagem
                    pos_vertical = round(par.get('top', 0) * 100, 2)
                    pos_horizontal = round(par.get('left', 0) * 100, 2)
                    
                    # Calcular distância se disponível
                    distancia = round(par.get('distancia', 0), 4) if 'distancia' in par else None
                    
                    # Adicionar informações ao CSV
                    dados_csv.append({
                        'Página': pagina_num,
                        'Chave': chave,
                        'Valor': valor,
                        'Identificador': identificador,
                        'Tipo': tipo_par,
                        'Confiança (%)': confianca_percentual,
                        'Posição Vertical (%)': pos_vertical,
                        'Posição Horizontal (%)': pos_horizontal,
                        'Distância': distancia if distancia is not None else ''
                    })
                except Exception as e:
                    self.logger.warning(f"Erro ao processar par na página {pagina_num}: {str(e)}")
                    self.logger.warning(f"Par problemático: {par}")
                    continue
        
        # Criar DataFrame e salvar como CSV
        if dados_csv:
            try:
                df_csv = pd.DataFrame(dados_csv)
                
                # Ordenar primeiro por página, depois por posição vertical
                df_csv = df_csv.sort_values(
                    by=['Página', 'Posição Vertical (%)', 'Posição Horizontal (%)'],
                    ascending=[True, True, True]
                )
                
                # Remover duplicatas mantendo a primeira ocorrência
                df_csv = df_csv.drop_duplicates(subset=['Página', 'Chave', 'Valor'], keep='first')
                
                # Salvar como CSV
                csv_path = f"{output_dir}/{base_name}_{timestamp}.csv"
                df_csv.to_csv(csv_path, index=False, encoding='utf-8-sig')
                self.logger.info(f"Arquivo CSV gerado com sucesso: {csv_path}")
                
                # Gerar estatísticas
                self._gerar_estatisticas_extracao(df_csv)
            except Exception as e:
                self.logger.error(f"Erro ao gerar CSV: {str(e)}")
                raise
        else:
            self.logger.warning("Nenhum par chave-valor encontrado para gerar o CSV.")
    
    def _extrair_identificador(self, texto: str) -> str:
        """Extrai possível identificador numérico do texto"""
        if not texto:
            return ''
        
        # Procurar por padrões comuns de identificadores
        import re
        
        # Padrão 1: Número no início do texto
        padrao1 = r'^\d{1,3}'
        match = re.match(padrao1, texto.strip())
        if match:
            return match.group()
        
        # Padrão 2: Número entre parênteses
        padrao2 = r'\((\d{1,3})\)'
        match = re.search(padrao2, texto)
        if match:
            return match.group(1)
        
        # Padrão 3: Número seguido de ponto ou traço
        padrao3 = r'^\d{1,3}[.-]'
        match = re.match(padrao3, texto.strip())
        if match:
            return match.group().rstrip('.-')
        
        return ''

    def _detectar_padrao_relacionamento(self, chaves: List[Dict], valores: List[Dict]) -> Dict:
        """Detecta padrões comuns nos relacionamentos entre chaves e valores"""
        self.logger.info("Iniciando detecção de padrões de relacionamento...")
        
        padroes = {
            'espacial': defaultdict(int),
            'formatacao': defaultdict(int),
            'semantico': defaultdict(int),
            'estrutural': defaultdict(list)
        }
        
        # Análise de padrões espaciais e formatação
        for chave in chaves:
            for valor in valores:
                # Padrões espaciais
                diff_horizontal = round(abs(chave.get('left', 0) - valor.get('left', 0)), 2)
                diff_vertical = round(abs(chave.get('top', 0) - valor.get('top', 0)), 2)
                
                padrao_espacial = f"h:{diff_horizontal}_v:{diff_vertical}"
                padroes['espacial'][padrao_espacial] += 1
                
                # Padrões de formatação
                chave_texto = chave.get('texto', '').strip()
                valor_texto = valor.get('texto', '').strip()
                
                # Verificar separadores
                if ':' in chave_texto:
                    padroes['formatacao']['separador_dois_pontos'] += 1
                if '=' in chave_texto:
                    padroes['formatacao']['separador_igual'] += 1
                
                # Verificar capitalização
                if chave_texto.isupper() and valor_texto.isupper():
                    padroes['formatacao']['ambos_maiusculos'] += 1
                elif chave_texto.istitle() and valor_texto.istitle():
                    padroes['formatacao']['ambos_titulo'] += 1
                
                # Padrões estruturais
                if len(chave_texto.split()) == 1 and len(valor_texto.split()) > 1:
                    padroes['estrutural']['chave_simples_valor_composto'].append({
                        'chave': chave_texto,
                        'valor': valor_texto
                    })
        
        # Calcular estatísticas dos padrões
        self._calcular_estatisticas_padroes(padroes)
        
        return padroes
    
    def _calcular_estatisticas_padroes(self, padroes: Dict) -> None:
        """Calcula estatísticas sobre os padrões detectados"""
        self.logger.info("Calculando estatísticas dos padrões...")
        
        # Estatísticas espaciais
        if padroes['espacial']:
            padrao_mais_comum = max(padroes['espacial'].items(), key=lambda x: x[1])
            total_espacial = sum(padroes['espacial'].values())
            self.logger.info(f"Padrão espacial mais comum: {padrao_mais_comum[0]} ({(padrao_mais_comum[1]/total_espacial)*100:.2f}%)")
        
        # Estatísticas de formatação
        if padroes['formatacao']:
            total_formatacao = sum(padroes['formatacao'].values())
            for tipo, contagem in padroes['formatacao'].items():
                percentual = (contagem/total_formatacao)*100
                self.logger.info(f"Padrão de formatação '{tipo}': {percentual:.2f}%")
    
    def _resolver_ambiguidade(self, chave: Dict, valores_candidatos: List[Dict], padroes: Dict) -> Optional[Dict]:
        """Resolve ambiguidades entre múltiplos valores candidatos para uma chave"""
        self.logger.info(f"Resolvendo ambiguidade para chave: {chave.get('texto', '')}")
        
        if not valores_candidatos:
            return None
        
        if len(valores_candidatos) == 1:
            return valores_candidatos[0]
        
        # Sistema de pontuação para cada candidato
        valores_pontuados = []
        for valor in valores_candidatos:
            pontos = 0.0
            
            # 1. Proximidade espacial (40% do peso)
            diff_horizontal = round(abs(chave.get('left', 0) - valor.get('left', 0)), 2)
            diff_vertical = round(abs(chave.get('top', 0) - valor.get('top', 0)), 2)
            padrao_atual = f"h:{diff_horizontal}_v:{diff_vertical}"
            
            # Verificar se o padrão espacial é comum
            if padrao_atual in padroes['espacial']:
                total_padroes = sum(padroes['espacial'].values())
                frequencia_padrao = padroes['espacial'][padrao_atual] / total_padroes
                pontos += frequencia_padrao * 0.4
            
            # 2. Confiança do valor (30% do peso)
            confianca = valor.get('confianca', 0)
            pontos += confianca * 0.3
            
            # 3. Análise de formatação (30% do peso)
            chave_texto = chave.get('texto', '').strip()
            valor_texto = valor.get('texto', '').strip()
            
            # Verificar padrões de formatação
            if ':' in chave_texto and padroes['formatacao'].get('separador_dois_pontos', 0) > 0:
                pontos += 0.15  # 15% por seguir o padrão de formatação comum
            
            if chave_texto.isupper() == valor_texto.isupper():
                pontos += 0.15  # 15% por manter consistência na capitalização
            
            valores_pontuados.append((valor, pontos))
            self.logger.info(f"Valor candidato: {valor_texto} - Pontuação: {pontos:.2f}")
        
        # Selecionar o valor com maior pontuação
        melhor_valor = max(valores_pontuados, key=lambda x: x[1])
        self.logger.info(f"Valor selecionado: {melhor_valor[0].get('texto', '')} com pontuação {melhor_valor[1]:.2f}")
        
        return melhor_valor[0]

    def _gerar_estatisticas_extracao(self, df: pd.DataFrame) -> None:
        """Gera e loga estatísticas sobre a extração"""
        self.logger.info("\nEstatísticas da Extração:")
        
        # Total de pares por página
        pares_por_pagina = df['Página'].value_counts().sort_index()
        self.logger.info("\nPares por página:")
        for pagina, total in pares_por_pagina.items():
            self.logger.info(f"Página {pagina}: {total} pares")
        
        # Distribuição por tipo
        tipos = df['Tipo'].value_counts()
        self.logger.info("\nDistribuição por tipo:")
        for tipo, total in tipos.items():
            self.logger.info(f"{tipo}: {total} pares")
        
        # Estatísticas de confiança
        confianca_media = df['Confiança (%)'].mean()
        confianca_mediana = df['Confiança (%)'].median()
        confianca_min = df['Confiança (%)'].min()
        confianca_max = df['Confiança (%)'].max()
        
        self.logger.info("\nEstatísticas de Confiança:")
        self.logger.info(f"Média: {confianca_media:.2f}%")
        self.logger.info(f"Mediana: {confianca_mediana:.2f}%")
        self.logger.info(f"Mínima: {confianca_min:.2f}%")
        self.logger.info(f"Máxima: {confianca_max:.2f}%")
        
        # Identificadores encontrados
        total_com_id = df['Identificador'].notna().sum()
        self.logger.info(f"\nPares com identificador: {total_com_id} ({(total_com_id/len(df)*100):.2f}%)")
    
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