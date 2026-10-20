# SciEAS — plugin para o Claude Code

Versão para o Claude do seu GPT "SciEASGPT": busca estruturada de artigos científicos, com tabela inicial e análises cienciométricas.

## O que há dentro

```
scieas-marketplace/
├── .claude-plugin/marketplace.json      ← "catálogo" que permite instalar/compartilhar
└── plugins/scieas/
    ├── .claude-plugin/plugin.json       ← "documento de identidade" do plugin (nome, versão, autor)
    └── skills/pesquisa-cientifica/
        ├── SKILL.md                     ← as instruções (o antigo "Instructions" do GPT)
        ├── references/revistas.csv      ← sua planilha de revistas (31.337, sem repetições)
        └── scripts/
            ├── buscar_artigos.py        ← busca artigos reais no Crossref
            └── consultar_revista.py     ← consulta ISSN/nome na sua lista
```

## Instalar para uso próprio

No terminal (com o Claude Code instalado), dentro da pasta onde descompactou o zip:

```
claude plugin marketplace add ./scieas-marketplace
claude plugin install scieas@scieas-marketplace
```

Depois, em uma sessão do Claude Code, use `/scieas:pesquisa-cientifica` ou simplesmente peça: "busque artigos recentes sobre sensoriamento remoto em florestas".

## Compartilhar com outras pessoas

1. **Mais simples:** envie este zip. Quem receber descompacta e roda os dois comandos acima.
2. **Mais profissional:** suba a pasta `scieas-marketplace` para um repositório no GitHub. Qualquer pessoa instala com:
   ```
   claude plugin marketplace add SEU-USUARIO/scieas-marketplace
   claude plugin install scieas@scieas-marketplace
   ```
   O repositório pode ser privado (só quem tiver acesso instala) ou público.

## Limitações a conhecer

- O **Fator de Impacto (JCR)** é dado pago da Clarivate. O plugin não o inventa: a coluna fica "não verificado" até você conferir pelo Portal CAPES.
- A planilha `revistas.csv` traz só ISSN e título (sem fator de impacto nem Qualis).
- A busca usa o Crossref (gratuito, sem chave). Opcional: defina a variável de ambiente `CROSSREF_MAILTO` com seu e-mail para respostas mais rápidas.
