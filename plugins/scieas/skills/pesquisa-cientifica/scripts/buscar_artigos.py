#!/usr/bin/env python3
"""
buscar_artigos.py  (versão 1.1 — várias bases)
----------------------------------------------
Busca artigos científicos REAIS em várias bases, junta os resultados sem
repetir (usando o DOI), e monta uma tabela com dados verificáveis.

BASES DISPONÍVEIS (parâmetro --fontes):
    crossref          gratuita, sem chave            (ligada por padrão)
    semanticscholar   gratuita, sem chave            (ligada por padrão)
    openalex          gratuita, mas exige chave      variável OPENALEX_API_KEY
    scopus            exige chave de API da Elsevier variável SCOPUS_API_KEY
    wos               exige chave de API da Clarivate variável WOS_API_KEY

Scopus e Web of Science: o acesso depende da assinatura da instituição (UFSM).
Rode o programa conectado à rede da UFSM (ou VPN) para as bases pagas.
Se a chave não estiver definida, essas bases são simplesmente ignoradas.

COMO USAR (exemplos):
    python buscar_artigos.py "deep learning forest inventory"
    python buscar_artigos.py "remote sensing biomass" --desde 2022 --max 15
    python buscar_artigos.py "UAV forestry" --fontes crossref,scopus,wos
    python buscar_artigos.py "UAV forestry" --apenas-lista

O QUE O PROGRAMA FAZ, PASSO A PASSO:
 1. Lê o tema e as opções.
 2. Carrega o revistas.csv como um "conjunto" de ISSNs (permite perguntar
    "este ISSN está na lista?" instantaneamente).
 3. Para cada base escolhida, existe uma função que faz a consulta e devolve os
    artigos num formato único (título, autor, revista, ISSN, ano, DOI, citações).
    Se uma base falhar (sem chave, sem internet, limite de uso), o programa
    avisa e segue com as outras.
 4. Junta tudo: artigos com o mesmo DOI viram uma só linha, e a coluna "Fontes"
    mostra em quais bases ele apareceu.
 5. Imprime a tabela em Markdown.

IMPORTANTE: o programa NÃO informa o Fator de Impacto (JCR) e não o inventa.
Esse número é da Clarivate; confira no JCR/Portal CAPES.
"""
import argparse
import csv
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent.parent / "references" / "revistas.csv"
PADRAO = "crossref,semanticscholar"


# --------------------------------------------------------------------------
# Ferramentas de apoio
# --------------------------------------------------------------------------
def carregar_issns() -> set:
    """Lê o CSV e devolve o conjunto de todos os ISSNs da lista."""
    with open(CSV_PATH, newline="", encoding="utf-8") as arquivo:
        return {linha["ISSN"].upper() for linha in csv.DictReader(arquivo)}


def pedir_json(url: str, cabecalhos: dict = None):
    """Faz um pedido HTTP e devolve a resposta já convertida de JSON para Python."""
    h = {"User-Agent": "SciEAS-plugin/1.1", "Accept": "application/json"}
    h.update(cabecalhos or {})
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30) as r:
        return json.load(r)


def normalizar_issn(valor) -> str:
    """Padroniza para o formato 1234-567X (alguns serviços mandam sem hífen)."""
    s = re.sub(r"[^0-9Xx]", "", str(valor or "")).upper()
    return f"{s[:4]}-{s[4:]}" if len(s) == 8 else ""


def normalizar_doi(valor) -> str:
    """Deixa o DOI em minúsculas e sem o prefixo https://doi.org/."""
    d = str(valor or "").strip().lower()
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", d)


def novo(titulo, autor, revista, issns, ano, doi, citacoes, fonte) -> dict:
    """Todas as bases devolvem artigos neste mesmo formato (um dicionário)."""
    return {
        "titulo": titulo or "(sem título)",
        "autor": autor or "—",
        "revista": revista or "—",
        "issns": [i for i in (normalizar_issn(x) for x in issns) if i],
        "ano": ano or "—",
        "doi": normalizar_doi(doi),
        "citacoes": citacoes if isinstance(citacoes, int) else None,
        "fontes": {fonte},
    }


def limpar(texto) -> str:
    """Evita que '|' ou quebras de linha estraguem a tabela Markdown."""
    return " ".join(html.unescape(str(texto)).replace("|", "/").split())


# --------------------------------------------------------------------------
# Uma função por base de dados
# --------------------------------------------------------------------------
def buscar_crossref(tema, desde, n):
    p = {
        "query.bibliographic": tema,
        "filter": f"type:journal-article,from-pub-date:{desde}",
        "rows": n,
        "select": "title,author,container-title,ISSN,issued,DOI,is-referenced-by-count",
    }
    if os.environ.get("CROSSREF_MAILTO"):
        p["mailto"] = os.environ["CROSSREF_MAILTO"]
    itens = pedir_json("https://api.crossref.org/works?" + urllib.parse.urlencode(p))["message"]["items"]
    saida = []
    for it in itens:
        a = (it.get("author") or [{}])[0]
        autor = f"{a.get('given', '')} {a.get('family', a.get('name', ''))}".strip()
        partes = it.get("issued", {}).get("date-parts", [[None]])
        saida.append(novo((it.get("title") or [""])[0], autor, (it.get("container-title") or [""])[0],
                          it.get("ISSN", []), partes[0][0] if partes and partes[0] else None,
                          it.get("DOI"), it.get("is-referenced-by-count"), "Crossref"))
    return saida


def buscar_semanticscholar(tema, desde, n):
    p = {
        "query": tema, "year": f"{desde}-", "limit": min(n, 100),
        "fields": "title,authors,venue,year,externalIds,citationCount,journal",
    }
    cab = {}
    if os.environ.get("S2_API_KEY"):  # opcional; aumenta o limite de uso
        cab["x-api-key"] = os.environ["S2_API_KEY"]
    dados = pedir_json("https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode(p), cab)
    saida = []
    for it in dados.get("data", []):
        autores = it.get("authors") or [{}]
        revista = (it.get("journal") or {}).get("name") or it.get("venue")
        saida.append(novo(it.get("title"), autores[0].get("name"), revista, [], it.get("year"),
                          (it.get("externalIds") or {}).get("DOI"), it.get("citationCount"),
                          "Semantic Scholar"))
    return saida


def buscar_openalex(tema, desde, n):
    chave = os.environ.get("OPENALEX_API_KEY")
    if not chave:
        raise RuntimeError("defina OPENALEX_API_KEY (chave gratuita em openalex.org)")
    p = {
        "search": tema, "per-page": min(n, 100), "api_key": chave,
        "filter": f"from_publication_date:{desde}-01-01,type:article",
    }
    dados = pedir_json("https://api.openalex.org/works?" + urllib.parse.urlencode(p))
    saida = []
    for it in dados.get("results", []):
        fonte = (it.get("primary_location") or {}).get("source") or {}
        autores = it.get("authorships") or [{}]
        saida.append(novo(it.get("title"), (autores[0].get("author") or {}).get("display_name"),
                          fonte.get("display_name"), fonte.get("issn") or [], it.get("publication_year"),
                          it.get("doi"), it.get("cited_by_count"), "OpenAlex"))
    return saida


def buscar_scopus(tema, desde, n):
    chave = os.environ.get("SCOPUS_API_KEY")
    if not chave:
        raise RuntimeError("defina SCOPUS_API_KEY (chave da Elsevier; usar na rede da UFSM)")
    p = {
        "query": f"TITLE-ABS-KEY({tema}) AND PUBYEAR > {desde - 1} AND DOCTYPE(ar)",
        "count": min(n, 25), "apiKey": chave,
    }
    dados = pedir_json("https://api.elsevier.com/content/search/scopus?" + urllib.parse.urlencode(p))
    saida = []
    for it in dados.get("search-results", {}).get("entry", []):
        if "error" in it:  # a Scopus devolve uma "entrada de erro" quando não há resultados
            continue
        ano = (it.get("prism:coverDate") or "")[:4]
        cit = it.get("citedby-count")
        saida.append(novo(it.get("dc:title"), it.get("dc:creator"), it.get("prism:publicationName"),
                          [it.get("prism:issn"), it.get("prism:eIssn")], int(ano) if ano.isdigit() else None,
                          it.get("prism:doi"), int(cit) if str(cit).isdigit() else None, "Scopus"))
    return saida


def buscar_wos(tema, desde, n):
    chave = os.environ.get("WOS_API_KEY")
    if not chave:
        raise RuntimeError("defina WOS_API_KEY (chave da Clarivate; usar na rede da UFSM)")
    p = {
        "q": f"TS=({tema}) AND PY=({desde}-{date.today().year}) AND DT=(Article)",
        "db": "WOS", "limit": min(n, 50), "page": 1,
    }
    dados = pedir_json("https://api.clarivate.com/apis/wos-starter/v1/documents?" + urllib.parse.urlencode(p),
                       {"X-ApiKey": chave})
    saida = []
    for it in dados.get("hits", []):
        autores = (it.get("names") or {}).get("authors") or [{}]
        fonte = it.get("source") or {}
        ident = it.get("identifiers") or {}
        cit = (it.get("citations") or [{}])[0].get("count")
        saida.append(novo(it.get("title"), autores[0].get("displayName"), fonte.get("sourceTitle"),
                          [ident.get("issn"), ident.get("eissn")], fonte.get("publishYear"),
                          ident.get("doi"), cit, "Web of Science"))
    return saida


BASES = {
    "crossref": buscar_crossref,
    "semanticscholar": buscar_semanticscholar,
    "openalex": buscar_openalex,
    "scopus": buscar_scopus,
    "wos": buscar_wos,
}


# --------------------------------------------------------------------------
# Programa principal
# --------------------------------------------------------------------------
def juntar(listas: list) -> list:
    """Une artigos repetidos: mesmo DOI (ou, sem DOI, mesmo título) vira uma linha só."""
    unicos = {}
    for artigo in (a for lista in listas for a in lista):
        chave = artigo["doi"] or re.sub(r"[^a-z0-9]", "", artigo["titulo"].lower())
        if chave not in unicos:
            unicos[chave] = artigo
            continue
        existente = unicos[chave]
        existente["fontes"] |= artigo["fontes"]
        existente["issns"] = list(dict.fromkeys(existente["issns"] + artigo["issns"]))
        if existente["revista"] == "—":
            existente["revista"] = artigo["revista"]
        cits = [c for c in (existente["citacoes"], artigo["citacoes"]) if c is not None]
        existente["citacoes"] = max(cits) if cits else None
    return list(unicos.values())


def main() -> int:
    ap = argparse.ArgumentParser(description="Busca artigos em várias bases")
    ap.add_argument("tema", help="assunto da busca (de preferência em inglês)")
    ap.add_argument("--desde", type=int, default=date.today().year - 5, help="ano inicial")
    ap.add_argument("--max", type=int, default=20, help="máximo de artigos na tabela")
    ap.add_argument("--fontes", default=PADRAO,
                    help=f"bases separadas por vírgula: {', '.join(BASES)} (padrão: {PADRAO})")
    ap.add_argument("--apenas-lista", action="store_true",
                    help="mostra só artigos de revistas presentes no revistas.csv")
    args = ap.parse_args()

    escolhidas = [f.strip().lower() for f in args.fontes.split(",") if f.strip()]
    desconhecidas = [f for f in escolhidas if f not in BASES]
    if desconhecidas:
        print(f"Base(s) desconhecida(s): {', '.join(desconhecidas)}. Opções: {', '.join(BASES)}", file=sys.stderr)
        return 1

    issns_lista = carregar_issns()
    pedir = min(args.max * 5, 100) if args.apenas_lista else args.max

    resultados, funcionaram, falharam = [], [], []
    for nome in escolhidas:
        try:
            resultados.append(BASES[nome](args.tema, args.desde, pedir))
            funcionaram.append(nome)
        except Exception as erro:  # sem chave, sem internet, limite de uso etc.
            falharam.append(f"{nome}: {erro}")

    artigos = juntar(resultados)
    # Quem apareceu em mais bases vem primeiro (a ordem original é mantida em empates).
    artigos.sort(key=lambda a: -len(a["fontes"]))

    linhas = []
    for a in artigos:
        na_lista = any(i in issns_lista for i in a["issns"])
        if args.apenas_lista and not na_lista:
            continue
        linhas.append((
            limpar(a["titulo"]), limpar(a["autor"]), limpar(a["revista"]),
            ", ".join(a["issns"]) or "—", "Sim" if na_lista else "Não", a["ano"],
            a["citacoes"] if a["citacoes"] is not None else "—",
            ", ".join(sorted(a["fontes"])),
            f"https://doi.org/{a['doi']}" if a["doi"] else "—",
        ))
        if len(linhas) >= args.max:
            break

    if linhas:
        print("| Título | Autor principal | Revista | ISSN | Na lista | Ano | Citações* | Fontes | Link |")
        print("|---|---|---|---|---|---|---|---|---|")
        for linha in linhas:
            print("| " + " | ".join(str(c) for c in linha) + " |")
        print("\n*Citações: maior valor entre as bases (cada base conta de um jeito).")
        print("Fator de Impacto (JCR): não incluído — conferir no JCR/Web of Science.")
    else:
        print("Nenhum artigo encontrado com esses critérios.")

    print(f"\nBases consultadas com sucesso: {', '.join(funcionaram) or 'nenhuma'}", file=sys.stderr)
    for f in falharam:
        print(f"Base ignorada -> {f}", file=sys.stderr)
    return 0 if funcionaram else 1


if __name__ == "__main__":
    sys.exit(main())
