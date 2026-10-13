"""Gera planilhas sinteticas em samples/ (sem dados reais da Schulz)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.amostras import PONTOS_REPROVADO, gerar_xlsx  # noqa: E402

SAIDA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "samples")
os.makedirs(SAIDA, exist_ok=True)
arquivos = {
    "01_valida_aprovada.xlsx": gerar_xlsx(),
    "02_valida_reprovada.xlsx": gerar_xlsx(pontos=PONTOS_REPROVADO, meta={"Instrumento": "MP-0043"}),
    "03_invalida_plano_teste.xlsx": gerar_xlsx(meta={"Plano de medição": "703.1208_TESTE"}),
    "04_invalida_padrao_divergente.xlsx": gerar_xlsx(meta={"Padrão do relatório": "500011"}),
    "05_invalida_um_bloco.xlsx": gerar_xlsx(n_leituras=1),
    "06_invalida_data_sentinela.xlsx": gerar_xlsx(meta={"Data da medição": "00/00/0000"}),
    "07_desvio_divergente_aviso.xlsx": gerar_xlsx(meta={"Instrumento": "MP-0044"}, coluna_desvio=[0.0008, 0.0014, 0.0002, 0.5]),
}
for nome, conteudo in arquivos.items():
    with open(os.path.join(SAIDA, nome), "wb") as f:
        f.write(conteudo)
    print("gerado", nome)
