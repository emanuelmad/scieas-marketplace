#!/usr/bin/env python3
"""
buscar_artigos.py
-----------------
Busca artigos científicos REAIS na base aberta Crossref e monta uma tabela com
dados verificáveis (título, autor, revista, ano, citações e link/DOI).
Também informa se a revista consta na lista revistas.csv do plugin.

COMO USAR (exemplos):
    python3 buscar_artigos.py "deep learning forest inventory"
    python3 buscar_artigos.py "remote sensing biomass" --desde 2022 --max 15
    python3 buscar_artigos.py "UAV forestry" --apenas-lista

O QUE O PROGRAMA FAZ, PASSO A PASSO:
 1. Lê o tema e as opções digitadas (ano inicial, quantidade, filtro).
 2. Carrega o revistas.csv na memória como um "conjunto" de ISSNs
    (um conjunto permite perguntar "este ISSN está aqui?" de forma instantânea).
 3. Faz uma consulta à API do Crossref (um serviço público e gratuito que
    cataloga artigos pelo DOI). A resposta vem em formato JSON.
 4. Para cada artigo: extrai os campos, confere se algum ISSN da revista está
    na sua lista e monta uma linha da tabela.
 5. Imprime a tabela em Markdown.

IMPORTANTE: o Crossref NÃO informa o Fator de Impacto (JCR). Esse número é
da Clarivate e precisa ser conferido por você (Portal CAPES/Web of Science).
O programa não inventa esse valor.
"""
import argparse
import csv
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent.parent / "references" / "revistas.csv"
API = "https://api.crossref.org/works"


def carregar_issns() -> set:
    """Lê o CSV e devolve o conjunto de todos os ISSNs da lista."""
    with open(CSV_PATH, newline="", encoding="utf-8") as arquivo:
        return {linha["ISSN"].upper() for linha in csv.DictReader(arquivo)}


def consultar_crossref(tema: str, desde: int, quantidade: int) -> list:
    """Pergunta ao Crossref e devolve a lista de artigos (já em formato Python)."""
    parametros = {
        "query.bibliographic": tema,
        "filter": f"type:journal-article,from-pub-date:{desde}",
        "rows": quantidade,
        "select": "title,author,container-title,ISSN,issued,DOI,is-referenced-by-count",
    }
    # O e-mail é opcional; ele só coloca você numa fila mais rápida do Crossref.
    email = os.environ.get("CROSSREF_MAILTO")
    if email:
        parametros["mailto"] = email

    url = API + "?" + urllib.parse.urlencode(parametros)
    pedido = urllib.request.Request(url, headers={"User-Agent": "SciEAS-plugin/1.0"})
    with urllib.request.urlopen(pedido, timeout=30) as resposta:
        return json.load(resposta)["message"]["items"]


def limpar(texto: str) -> str:
    """Evita que '|' ou quebras de linha estraguem a tabela Markdown."""
    return " ".join(str(texto).replace("|", "/").split())


def main() -> int:
    ap = argparse.ArgumentParser(description="Busca artigos no Crossref")
    ap.add_argument("tema", help="assunto da busca (de preferência em inglês)")
    ap.add_argument("--desde", type=int, default=date.today().year - 5,
                    help="ano inicial (padrão: 5 anos atrás)")
    ap.add_argument("--max", type=int, default=20, help="máximo de artigos na tabela")
    ap.add_argument("--apenas-lista", action="store_true",
                    help="mostra só artigos de revistas presentes no revistas.csv")
    args = ap.parse_args()

    issns_lista = carregar_issns()

    # Se for filtrar pela lista, pedimos mais resultados e descartamos depois.
    pedir = min(args.max * 5, 1000) if args.apenas_lista else args.max
    try:
        itens = consultar_crossref(args.tema, args.desde, pedir)
    except Exception as erro:  # sem internet, limite de uso etc.
        print(f"Erro ao consultar o Crossref: {erro}", file=sys.stderr)
        return 1

    linhas = []
    for item in itens:
        issns = [i.upper() for i in item.get("ISSN", [])]
        na_lista = any(i in issns_lista for i in issns)
        if args.apenas_lista and not na_lista:
            continue

        autores = item.get("author", [])
        principal = "—"
        if autores:
            a = autores[0]
            principal = f"{a.get('given', '')} {a.get('family', a.get('name', ''))}".strip()

        partes = item.get("issued", {}).get("date-parts", [[None]])
        ano = partes[0][0] if partes and partes[0] else "—"

        linhas.append((
            limpar((item.get("title") or ["(sem título)"])[0]),
            limpar(principal),
            limpar((item.get("container-title") or ["—"])[0]),
            ", ".join(issns) or "—",
            "Sim" if na_lista else "Não",
            ano,
            item.get("is-referenced-by-count", "—"),
            f"https://doi.org/{item['DOI']}" if item.get("DOI") else "—",
        ))
        if len(linhas) >= args.max:
            break

    if not linhas:
        print("Nenhum artigo encontrado com esses critérios.")
        return 0

    print("| Título | Autor principal | Revista | ISSN | Na lista | Ano | Citações (Crossref) | Link |")
    print("|---|---|---|---|---|---|---|---|")
    for linha in linhas:
        print("| " + " | ".join(str(c) for c in linha) + " |")
    print("\nFator de Impacto (JCR): não incluído — conferir no JCR/Web of Science.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
