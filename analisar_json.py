import json
import sys
from collections import defaultdict
from typing import Dict, List, Any, Tuple
import statistics
import math

class AnalisadorJSON:
    def __init__(self, arquivo_json: str):
        self.arquivo_json = arquivo_json
        self.dados = None
        self.blocos_por_pagina = defaultdict(int)
        self.tipos_por_pagina = defaultdict(lambda: defaultdict(int))
        self.posicoes_por_pagina = defaultdict(list)
        self.relacionamentos_por_pagina = defaultdict(lambda: defaultdict(list))
        self.hierarquia_por_pagina = defaultdict(dict)
        self.estatisticas = {}
        
        # Novas estruturas de dados
        self.confianca_minima = float('inf')
        self.confianca_maxima = float('-inf')
        self.sobreposicoes_por_pagina = defaultdict(list)
        self.relacionamentos_diretos = defaultdict(list)
        self.relacionamentos_indiretos = defaultdict(list)
        self.padroes_por_pagina = defaultdict(list)
        self.metricas_qualidade = defaultdict(dict)
        self.hierarquia_completa = defaultdict(dict)
        self.erros_validacao = []
    
    def carregar_dados(self) -> None:
        """Carrega os dados do arquivo JSON"""
        try:
            with open(self.arquivo_json, 'r', encoding='utf-8') as f:
                self.dados = json.load(f)
            print(f"\nArquivo JSON carregado com sucesso: {self.arquivo_json}")
        except Exception as e:
            print(f"Erro ao carregar o arquivo JSON: {str(e)}")
            sys.exit(1)
    
    def _verificar_sobreposicoes(self, pagina_num: int, bloco_id: str, bbox: Dict) -> None:
        """Verifica sobreposições entre blocos"""
        for posicao in self.posicoes_por_pagina[pagina_num]:
            if posicao['id'] != bloco_id:
                outro_bbox = {
                    'Top': posicao['top'],
                    'Left': posicao['left'],
                    'Width': posicao['width'],
                    'Height': posicao['height']
                }
                if self._tem_sobreposicao(bbox, outro_bbox):
                    self.sobreposicoes_por_pagina[pagina_num].append({
                        'bloco1_id': bloco_id,
                        'bloco2_id': posicao['id'],
                        'area_sobreposicao': self._calcular_area_sobreposicao(bbox, outro_bbox)
                    })
    
    def _tem_sobreposicao(self, bbox1: Dict, bbox2: Dict) -> bool:
        """Verifica se há sobreposição entre dois bounding boxes"""
        return not (
            bbox1['Left'] + bbox1['Width'] < bbox2['Left'] or
            bbox2['Left'] + bbox2['Width'] < bbox1['Left'] or
            bbox1['Top'] + bbox1['Height'] < bbox2['Top'] or
            bbox2['Top'] + bbox2['Height'] < bbox1['Top']
        )
    
    def _calcular_area_sobreposicao(self, bbox1: Dict, bbox2: Dict) -> float:
        """Calcula a área de sobreposição entre dois bounding boxes"""
        x_left = max(bbox1['Left'], bbox2['Left'])
        y_top = max(bbox1['Top'], bbox2['Top'])
        x_right = min(bbox1['Left'] + bbox1['Width'], bbox2['Left'] + bbox2['Width'])
        y_bottom = min(bbox1['Top'] + bbox1['Height'], bbox2['Top'] + bbox2['Height'])
        
        if x_right < x_left or y_bottom < y_top:
            return 0.0
        
        return (x_right - x_left) * (y_bottom - y_top)
    
    def _verificar_proximidade(self, bloco1: Dict, bloco2: Dict) -> float:
        """Calcula a proximidade entre dois blocos"""
        bbox1 = bloco1['Geometry']['BoundingBox']
        bbox2 = bloco2['Geometry']['BoundingBox']
        
        # Calcular distância vertical e horizontal
        dist_vertical = abs(bbox1['Top'] - bbox2['Top'])
        dist_horizontal = abs(bbox1['Left'] - bbox2['Left'])
        
        # Retornar distância euclidiana normalizada
        return math.sqrt(dist_vertical ** 2 + dist_horizontal ** 2)
    
    def analisar_blocos(self) -> None:
        """Analisa os blocos em cada página com métricas adicionais"""
        for pagina in self.dados:
            for bloco in pagina.get('Blocks', []):
                pagina_num = bloco.get('Page', 0)
                tipo = bloco.get('BlockType', 'UNKNOWN')
                bloco_id = bloco.get('Id', '')
                confianca = bloco.get('Confidence', 0)
                
                # Atualizar confiança min/max
                self.confianca_minima = min(self.confianca_minima, confianca)
                self.confianca_maxima = max(self.confianca_maxima, confianca)
                
                # Contagem de blocos
                self.blocos_por_pagina[pagina_num] += 1
                
                # Contagem de tipos
                self.tipos_por_pagina[pagina_num][tipo] += 1
                
                # Armazenar posições e verificar sobreposições
                if 'Geometry' in bloco:
                    bbox = bloco['Geometry'].get('BoundingBox', {})
                    self.posicoes_por_pagina[pagina_num].append({
                        'id': bloco_id,
                        'tipo': tipo,
                        'top': bbox.get('Top', 0),
                        'left': bbox.get('Left', 0),
                        'width': bbox.get('Width', 0),
                        'height': bbox.get('Height', 0),
                        'confianca': confianca
                    })
                    self._verificar_sobreposicoes(pagina_num, bloco_id, bbox)
                
                # Analisar relacionamentos
                self._analisar_relacionamentos_bloco(pagina_num, bloco)
    
    def _analisar_relacionamentos_bloco(self, pagina_num: int, bloco: Dict) -> None:
        """Analisa os relacionamentos de um bloco específico"""
        bloco_id = bloco.get('Id', '')
        print(f"\nAnalisando relacionamentos do bloco {bloco_id} (Página {pagina_num}):")
        
        for relacionamento in bloco.get('Relationships', []):
            rel_tipo = relacionamento.get('Type', '')
            rel_ids = relacionamento.get('Ids', [])
            
            # Armazenar relacionamento
            self.relacionamentos_por_pagina[pagina_num][bloco_id].append({
                'tipo': rel_tipo,
                'ids': rel_ids
            })
            
            print(f"  - Tipo: {rel_tipo}")
            print(f"    IDs relacionados: {', '.join(rel_ids)}")
            
            # Classificar relacionamentos
            if rel_tipo in ['VALUE', 'KEY']:
                self.relacionamentos_diretos[bloco_id].extend(rel_ids)
                print(f"    Relacionamento direto encontrado")
            elif rel_tipo == 'CHILD':
                self.relacionamentos_indiretos[bloco_id].extend(rel_ids)
                print(f"    Relacionamento indireto encontrado")
            
            # Analisar relacionamentos em cadeia
            self._analisar_relacionamentos_em_cadeia(bloco_id, rel_ids)
    
    def _analisar_relacionamentos_em_cadeia(self, bloco_id: str, rel_ids: List[str]) -> None:
        """Analisa relacionamentos em cadeia para identificar conexões indiretas"""
        print(f"  Analisando relacionamentos em cadeia para bloco {bloco_id}:")
        
        for rel_id in rel_ids:
            for pagina in self.dados:
                for bloco in pagina.get('Blocks', []):
                    if bloco.get('Id') == rel_id:
                        for rel in bloco.get('Relationships', []):
                            if rel['Type'] in ['VALUE', 'KEY']:
                                self.relacionamentos_indiretos[bloco_id].extend(rel['Ids'])
                                print(f"    - Encontrada conexão indireta: {rel_id} -> {rel['Ids']}")
    
    def analisar_padroes(self) -> None:
        """Analisa padrões comuns em documentos"""
        for pagina in self.dados:
            pagina_num = pagina.get('Page', 0)
            blocos = pagina.get('Blocks', [])
            
            # Identificar padrões de layout
            self._identificar_padroes_layout(pagina_num, blocos)
            
            # Identificar estruturas tabulares
            self._identificar_estruturas_tabulares(pagina_num, blocos)
    
    def _identificar_padroes_layout(self, pagina_num: int, blocos: List[Dict]) -> None:
        """Identifica padrões comuns de layout na página"""
        # Agrupar blocos por tipo
        blocos_por_tipo = defaultdict(list)
        for bloco in blocos:
            blocos_por_tipo[bloco.get('BlockType', 'UNKNOWN')].append(bloco)
        
        # Identificar padrões de formulário
        self._identificar_padrao_formulario(pagina_num, blocos_por_tipo)
        
        # Identificar padrões de lista
        self._identificar_padrao_lista(pagina_num, blocos_por_tipo)
    
    def _identificar_padrao_formulario(self, pagina_num: int, blocos_por_tipo: Dict) -> None:
        """Identifica padrões de formulário (campos chave-valor)"""
        key_blocks = blocos_por_tipo.get('KEY_VALUE_SET', [])
        for key_block in key_blocks:
            if 'KEY' in key_block.get('EntityTypes', []):
                self.padroes_por_pagina[pagina_num].append({
                    'tipo': 'FORM_FIELD',
                    'bloco_id': key_block.get('Id', ''),
                    'confianca': key_block.get('Confidence', 0)
                })
    
    def _identificar_padrao_lista(self, pagina_num: int, blocos_por_tipo: Dict) -> None:
        """Identifica padrões de lista (itens em sequência)"""
        line_blocks = blocos_por_tipo.get('LINE', [])
        line_blocks.sort(key=lambda x: x['Geometry']['BoundingBox']['Top'])
        
        for i in range(len(line_blocks) - 1):
            if self._eh_item_lista(line_blocks[i], line_blocks[i + 1]):
                self.padroes_por_pagina[pagina_num].append({
                    'tipo': 'LIST_ITEM',
                    'bloco_id': line_blocks[i].get('Id', ''),
                    'proximo_id': line_blocks[i + 1].get('Id', '')
                })
    
    def _eh_item_lista(self, bloco1: Dict, bloco2: Dict) -> bool:
        """Verifica se dois blocos parecem ser itens de lista"""
        bbox1 = bloco1['Geometry']['BoundingBox']
        bbox2 = bloco2['Geometry']['BoundingBox']
        
        # Verificar alinhamento vertical e espaçamento consistente
        alinhamento_horizontal = abs(bbox1['Left'] - bbox2['Left']) < 0.02
        espacamento_vertical = 0.01 < abs(bbox2['Top'] - bbox1['Top']) < 0.05
        
        return alinhamento_horizontal and espacamento_vertical
    
    def _identificar_estruturas_tabulares(self, pagina_num: int, blocos: List[Dict]) -> None:
        """Identifica estruturas que parecem tabelas"""
        # Filtrar blocos que podem ser células de tabela
        celulas_potenciais = [
            b for b in blocos
            if b.get('BlockType') in ['CELL', 'LINE', 'KEY_VALUE_SET']
        ]
        
        if not celulas_potenciais:
            return
        
        # Ordenar por posição
        celulas_potenciais.sort(key=lambda x: (
            x['Geometry']['BoundingBox']['Top'],
            x['Geometry']['BoundingBox']['Left']
        ))
        
        # Identificar linhas e colunas
        linhas = self._agrupar_em_linhas(celulas_potenciais)
        if len(linhas) > 1:
            self.padroes_por_pagina[pagina_num].append({
                'tipo': 'TABLE',
                'linhas': len(linhas),
                'colunas': self._estimar_numero_colunas(linhas)
            })
    
    def _agrupar_em_linhas(self, blocos: List[Dict]) -> List[List[Dict]]:
        """Agrupa blocos em linhas baseado na posição vertical"""
        linhas = []
        linha_atual = []
        ultima_posicao_y = None
        
        for bloco in blocos:
            pos_y = bloco['Geometry']['BoundingBox']['Top']
            
            if ultima_posicao_y is None:
                linha_atual.append(bloco)
            elif abs(pos_y - ultima_posicao_y) < 0.02:  # Tolerância de 2%
                linha_atual.append(bloco)
            else:
                if linha_atual:
                    linhas.append(linha_atual)
                linha_atual = [bloco]
            
            ultima_posicao_y = pos_y
        
        if linha_atual:
            linhas.append(linha_atual)
        
        return linhas
    
    def _estimar_numero_colunas(self, linhas: List[List[Dict]]) -> int:
        """Estima o número de colunas baseado no número médio de blocos por linha"""
        if not linhas:
            return 0
        return round(statistics.mean([len(linha) for linha in linhas]))
    
    def calcular_estatisticas(self) -> None:
        """Calcula estatísticas dos blocos"""
        blocos = list(self.blocos_por_pagina.values())
        
        if not blocos:
            print("Aviso: Nenhum bloco encontrado para calcular estatísticas")
            return
        
        self.estatisticas = {
            'total_paginas': len(self.dados),
            'total_blocos': sum(blocos),
            'media_blocos': statistics.mean(blocos),
            'mediana_blocos': statistics.median(blocos),
            'min_blocos': min(blocos),
            'max_blocos': max(blocos),
            'desvio_padrao': statistics.stdev(blocos) if len(blocos) > 1 else 0
        }
        
        print("\nEstatísticas calculadas:")
        print(f"Total de páginas: {self.estatisticas['total_paginas']}")
        print(f"Total de blocos: {self.estatisticas['total_blocos']}")
        print(f"Média de blocos por página: {self.estatisticas['media_blocos']:.2f}")
        print(f"Mediana de blocos por página: {self.estatisticas['mediana_blocos']}")
        print(f"Mínimo de blocos em uma página: {self.estatisticas['min_blocos']}")
        print(f"Máximo de blocos em uma página: {self.estatisticas['max_blocos']}")
        print(f"Desvio padrão: {self.estatisticas['desvio_padrao']:.2f}")

    def analisar_distribuicao_espacial(self) -> None:
        """Analisa a distribuição espacial dos blocos em cada página"""
        print("\nAnálise da distribuição espacial dos blocos:")
        
        for pagina_num, posicoes in sorted(self.posicoes_por_pagina.items()):
            print(f"\nPágina {pagina_num}:")
            
            if not posicoes:
                print("  Nenhuma posição encontrada nesta página")
                continue
            
            # Análise vertical
            tops = [p['top'] for p in posicoes]
            print(f"  Distribuição vertical:")
            print(f"    - Topo mínimo: {min(tops):.3f}")
            print(f"    - Topo máximo: {max(tops):.3f}")
            
            # Análise horizontal
            lefts = [p['left'] for p in posicoes]
            print(f"  Distribuição horizontal:")
            print(f"    - Esquerda mínima: {min(lefts):.3f}")
            print(f"    - Esquerda máxima: {max(lefts):.3f}")
            
            # Análise de sobreposições
            if pagina_num in self.sobreposicoes_por_pagina:
                sobreposicoes = self.sobreposicoes_por_pagina[pagina_num]
                print(f"  Sobreposições detectadas: {len(sobreposicoes)}")
                for s in sobreposicoes:
                    print(f"    - Entre blocos {s['bloco1_id']} e {s['bloco2_id']}")
                    print(f"      Área de sobreposição: {s['area_sobreposicao']:.4f}")

    def analisar_qualidade(self) -> None:
        """Analisa a qualidade dos blocos extraídos"""
        print("\nAnalisando qualidade dos blocos:")
        
        for pagina in self.dados:
            pagina_num = pagina.get('Page', 0)
            blocos = pagina.get('Blocks', [])
            
            # Calcular métricas de qualidade
            confiancas = [b.get('Confidence', 0) for b in blocos]
            if confiancas:
                self.metricas_qualidade[pagina_num] = {
                    'confianca_media': statistics.mean(confiancas),
                    'confianca_mediana': statistics.median(confiancas),
                    'confianca_std': statistics.stdev(confiancas) if len(confiancas) > 1 else 0,
                    'total_blocos_baixa_confianca': sum(1 for c in confiancas if c < 90)
                }
                
                print(f"\nPágina {pagina_num}:")
                print(f"  Confiança média: {self.metricas_qualidade[pagina_num]['confianca_media']:.2f}%")
                print(f"  Confiança mediana: {self.metricas_qualidade[pagina_num]['confianca_mediana']:.2f}%")
                print(f"  Desvio padrão: {self.metricas_qualidade[pagina_num]['confianca_std']:.2f}")
                print(f"  Blocos com baixa confiança: {self.metricas_qualidade[pagina_num]['total_blocos_baixa_confianca']}")

    def validar_dados(self) -> None:
        """Valida a integridade dos dados extraídos"""
        print("\nValidando integridade dos dados:")
        
        for pagina in self.dados:
            pagina_num = pagina.get('Page', 0)
            blocos = pagina.get('Blocks', [])
            
            print(f"\nPágina {pagina_num}:")
            
            # Validar IDs únicos
            ids = [b.get('Id') for b in blocos]
            if len(ids) != len(set(ids)):
                erro = f"IDs duplicados na página {pagina_num}"
                self.erros_validacao.append(erro)
                print(f"  ERRO: {erro}")
            else:
                print("  ✓ IDs únicos validados")
            
            # Validar relacionamentos
            self._validar_relacionamentos(pagina_num, blocos)
            
            # Validar geometria
            self._validar_geometria(pagina_num, blocos)

    def _validar_relacionamentos(self, pagina_num: int, blocos: List[Dict]) -> None:
        """Valida a integridade dos relacionamentos"""
        ids_validos = {b.get('Id') for b in blocos}
        
        print("  Validando relacionamentos:")
        tem_erro = False
        
        for bloco in blocos:
            for rel in bloco.get('Relationships', []):
                for rel_id in rel.get('Ids', []):
                    if rel_id not in ids_validos:
                        erro = f"Relacionamento inválido na página {pagina_num}: ID {rel_id} não encontrado"
                        self.erros_validacao.append(erro)
                        print(f"    ERRO: {erro}")
                        tem_erro = True
        
        if not tem_erro:
            print("    ✓ Todos os relacionamentos são válidos")

    def _validar_geometria(self, pagina_num: int, blocos: List[Dict]) -> None:
        """Valida a geometria dos blocos"""
        print("  Validando geometria:")
        tem_erro = False
        
        for bloco in blocos:
            if 'Geometry' in bloco:
                bbox = bloco['Geometry'].get('BoundingBox', {})
                
                # Verificar valores dentro dos limites esperados
                for chave, valor in [
                    ('Top', bbox.get('Top', 0)),
                    ('Left', bbox.get('Left', 0)),
                    ('Width', bbox.get('Width', 0)),
                    ('Height', bbox.get('Height', 0))
                ]:
                    if not (0 <= valor <= 1):
                        erro = f"Geometria inválida na página {pagina_num}: {chave}={valor} fora do intervalo [0,1]"
                        self.erros_validacao.append(erro)
                        print(f"    ERRO: {erro}")
                        tem_erro = True
        
        if not tem_erro:
            print("    ✓ Toda a geometria é válida")

    def analisar(self) -> None:
        """Executa a análise completa com todas as melhorias"""
        print("\nIniciando análise completa...")
        
        self.carregar_dados()
        print("\nAnalisando blocos...")
        self.analisar_blocos()
        
        print("\nCalculando estatísticas...")
        self.calcular_estatisticas()
        
        print("\nAnalisando distribuição espacial...")
        self.analisar_distribuicao_espacial()
        
        print("\nAnalisando padrões...")
        self.analisar_padroes()
        
        print("\nAnalisando qualidade...")
        self.analisar_qualidade()
        
        print("\nValidando dados...")
        self.validar_dados()
        
        print("\nGerando relatório final...")
        self.imprimir_resultados()
        
        print("\nAnálise completa finalizada.")
    
    def imprimir_resultados(self) -> None:
        """Imprime os resultados da análise com informações adicionais"""
        print("\nEstatísticas Gerais:")
        print(f"Total de páginas: {self.estatisticas['total_paginas']}")
        print(f"Total de blocos: {self.estatisticas['total_blocos']}")
        print(f"Média de blocos por página: {self.estatisticas['media_blocos']:.2f}")
        print(f"Mediana de blocos por página: {self.estatisticas['mediana_blocos']:.2f}")
        print(f"Mínimo de blocos em uma página: {self.estatisticas['min_blocos']}")
        print(f"Máximo de blocos em uma página: {self.estatisticas['max_blocos']}")
        print(f"Desvio padrão: {self.estatisticas['desvio_padrao']:.2f}")
        
        print("\nMétricas de Qualidade:")
        for pagina_num, metricas in self.metricas_qualidade.items():
            print(f"\nPágina {pagina_num}:")
            print(f"  Confiança média: {metricas['confianca_media']:.2f}%")
            print(f"  Confiança mediana: {metricas['confianca_mediana']:.2f}%")
            print(f"  Desvio padrão da confiança: {metricas['confianca_std']:.2f}")
            print(f"  Blocos com baixa confiança: {metricas['total_blocos_baixa_confianca']}")
        
        print("\nPadrões Identificados:")
        for pagina_num, padroes in self.padroes_por_pagina.items():
            print(f"\nPágina {pagina_num}:")
            tipos_padroes = defaultdict(int)
            for padrao in padroes:
                tipos_padroes[padrao['tipo']] += 1
            for tipo, count in tipos_padroes.items():
                print(f"  {tipo}: {count}")
        
        if self.erros_validacao:
            print("\nErros de Validação Encontrados:")
            for erro in self.erros_validacao:
                print(f"- {erro}")

def main():
    if len(sys.argv) > 1:
        arquivo_json = sys.argv[1]
    else:
        arquivo_json = 'of_analysis.json'
    
    print(f"Iniciando análise do arquivo: {arquivo_json}")
    
    analisador = AnalisadorJSON(arquivo_json)
    analisador.analisar()

if __name__ == "__main__":
    main() 