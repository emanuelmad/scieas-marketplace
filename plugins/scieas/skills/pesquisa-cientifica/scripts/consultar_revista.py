#!/usr/bin/env python3
"""
consultar_revista.py
--------------------
Consulta a lista de revistas (references/revistas.csv) por ISSN ou por parte do nome.

COMO USAR (exemplos):
    python3 consultar_revista.py 0034-4257
    python3 consultar_revista.py "remote sensing"

O QUE O PROGRAMA FAZ, PASSO A PASSO:
 1. Lê o texto que você digitou na linha de comando.
 2. Abre o arquivo revistas.csv (uma tabela com duas colunas: ISSN e Titulo).
 3. Se o texto parece um ISSN (formato 1234-567X), procura a revista exata.
    Caso contrário, procura revistas cujo nome contenha o texto (sem diferenciar
    maiúsculas/minúsculas nem acentos).
 4. Mostra até 25 resultados.
"""
import csv
import re
import sys
import unicodedata
from pathlib import Path

# Caminho do CSV: está na pasta "references", ao lado da pasta "scripts".
CSV_PATH = Path(__file__).resolve().parent.parent / "references" / "revistas.csv"
LIMITE = 25


def normalizar(texto: str) -> str:
    """Tira acentos e deixa em minúsculas, para comparar 'Ciência' com 'ciencia'."""
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return sem_acento.lower()


def main() -> int:
    if len(sys.argv) < 2:
        print("Uso: consultar_revista.py <ISSN ou parte do nome>")
        return 1

    consulta = " ".join(sys.argv[1:]).strip()
    eh_issn = re.fullmatch(r"\d{4}-?\d{3}[\dXx]", consulta) is not None

    if eh_issn:
        # Garante o hífen no meio: 00344257 -> 0034-4257
        issn = consulta.replace("-", "").upper()
        issn = f"{issn[:4]}-{issn[4:]}"
    else:
        alvo = normalizar(consulta)

    achados = []
    with open(CSV_PATH, newline="", encoding="utf-8") as arquivo:
        for linha in csv.DictReader(arquivo):  # cada linha vira um dicionário
            if eh_issn:
                if linha["ISSN"] == issn:
                    achados.append(linha)
            elif alvo in normalizar(linha["Titulo"]):
                achados.append(linha)

    if not achados:
        print("Nenhuma revista encontrada na lista.")
        return 0

    print(f"{len(achados)} resultado(s) (mostrando até {LIMITE}):")
    for linha in achados[:LIMITE]:
        print(f"  {linha['ISSN']}  {linha['Titulo']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
