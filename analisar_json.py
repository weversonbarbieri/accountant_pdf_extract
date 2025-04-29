import json
import sys
from collections import defaultdict
from typing import Dict, List, Any
import statistics

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
    
    def carregar_dados(self) -> None:
        """Carrega os dados do arquivo JSON"""
        try:
            with open(self.arquivo_json, 'r', encoding='utf-8') as f:
                self.dados = json.load(f)
            print(f"\nArquivo JSON carregado com sucesso: {self.arquivo_json}")
        except Exception as e:
            print(f"Erro ao carregar o arquivo JSON: {str(e)}")
            sys.exit(1)
    
    def analisar_blocos(self) -> None:
        """Analisa os blocos em cada página"""
        for pagina in self.dados:
            for bloco in pagina.get('Blocks', []):
                pagina_num = bloco.get('Page', 0)
                tipo = bloco.get('BlockType', 'UNKNOWN')
                bloco_id = bloco.get('Id', '')
                
                # Contagem de blocos
                self.blocos_por_pagina[pagina_num] += 1
                
                # Contagem de tipos
                self.tipos_por_pagina[pagina_num][tipo] += 1
                
                # Armazenar posições dos blocos
                if 'Geometry' in bloco:
                    bbox = bloco['Geometry'].get('BoundingBox', {})
                    self.posicoes_por_pagina[pagina_num].append({
                        'id': bloco_id,
                        'tipo': tipo,
                        'top': bbox.get('Top', 0),
                        'left': bbox.get('Left', 0),
                        'width': bbox.get('Width', 0),
                        'height': bbox.get('Height', 0)
                    })
                
                # Analisar relacionamentos
                for relacionamento in bloco.get('Relationships', []):
                    rel_tipo = relacionamento.get('Type', '')
                    rel_ids = relacionamento.get('Ids', [])
                    self.relacionamentos_por_pagina[pagina_num][bloco_id].append({
                        'tipo': rel_tipo,
                        'ids': rel_ids
                    })
                
                # Construir hierarquia
                if tipo == 'PAGE':
                    self.hierarquia_por_pagina[pagina_num] = {
                        'id': bloco_id,
                        'tipo': tipo,
                        'filhos': []
                    }
                elif tipo in ['LINE', 'TABLE', 'KEY_VALUE_SET']:
                    if pagina_num in self.hierarquia_por_pagina:
                        self.hierarquia_por_pagina[pagina_num]['filhos'].append({
                            'id': bloco_id,
                            'tipo': tipo,
                            'filhos': []
                        })
    
    def calcular_estatisticas(self) -> None:
        """Calcula estatísticas dos blocos"""
        blocos = list(self.blocos_por_pagina.values())
        
        self.estatisticas = {
            'total_paginas': len(self.dados),
            'total_blocos': sum(blocos),
            'media_blocos': statistics.mean(blocos),
            'mediana_blocos': statistics.median(blocos),
            'min_blocos': min(blocos),
            'max_blocos': max(blocos),
            'desvio_padrao': statistics.stdev(blocos) if len(blocos) > 1 else 0
        }
    
    def analisar_distribuicao_espacial(self) -> None:
        """Analisa a distribuição espacial dos blocos em cada página"""
        print("\nAnálise da distribuição espacial dos blocos:")
        
        for pagina_num, posicoes in sorted(self.posicoes_por_pagina.items()):
            print(f"\nPágina {pagina_num}:")
            
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
    
    def analisar_relacionamentos(self) -> None:
        """Analisa os relacionamentos entre blocos"""
        print("\nAnálise de relacionamentos entre blocos:")
        
        for pagina_num, relacionamentos in sorted(self.relacionamentos_por_pagina.items()):
            print(f"\nPágina {pagina_num}:")
            
            # Contar tipos de relacionamentos
            tipos_rel = defaultdict(int)
            for bloco_id, rels in relacionamentos.items():
                for rel in rels:
                    tipos_rel[rel['tipo']] += 1
            
            print("  Tipos de relacionamentos:")
            for tipo, count in sorted(tipos_rel.items()):
                print(f"    - {tipo}: {count}")
            
            # Analisar hierarquia
            if pagina_num in self.hierarquia_por_pagina:
                print("\n  Estrutura hierárquica:")
                self._imprimir_hierarquia(self.hierarquia_por_pagina[pagina_num], "    ")
    
    def _imprimir_hierarquia(self, node: Dict, prefixo: str) -> None:
        """Imprime a estrutura hierárquica de forma recursiva"""
        print(f"{prefixo}- {node['tipo']} (ID: {node['id']})")
        for filho in node.get('filhos', []):
            self._imprimir_hierarquia(filho, prefixo + "  ")
    
    def imprimir_resultados(self) -> None:
        """Imprime os resultados da análise"""
        print("\nEstatísticas Gerais:")
        print(f"Total de páginas: {self.estatisticas['total_paginas']}")
        print(f"Total de blocos: {self.estatisticas['total_blocos']}")
        print(f"Média de blocos por página: {self.estatisticas['media_blocos']:.2f}")
        print(f"Mediana de blocos por página: {self.estatisticas['mediana_blocos']:.2f}")
        print(f"Mínimo de blocos em uma página: {self.estatisticas['min_blocos']}")
        print(f"Máximo de blocos em uma página: {self.estatisticas['max_blocos']}")
        print(f"Desvio padrão: {self.estatisticas['desvio_padrao']:.2f}")
        
        print("\nDistribuição de blocos por página:")
        for pagina_num, count in sorted(self.blocos_por_pagina.items()):
            print(f"\nPágina {pagina_num}: {count} blocos")
            print("Tipos de blocos:")
            for tipo, tipo_count in sorted(self.tipos_por_pagina[pagina_num].items()):
                percentual = (tipo_count / count) * 100
                print(f"  - {tipo}: {tipo_count} ({percentual:.2f}%)")
    
    def analisar(self) -> None:
        """Executa a análise completa"""
        self.carregar_dados()
        self.analisar_blocos()
        self.calcular_estatisticas()
        self.analisar_distribuicao_espacial()
        self.analisar_relacionamentos()
        self.imprimir_resultados()

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