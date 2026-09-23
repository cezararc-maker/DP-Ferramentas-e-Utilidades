# Arquitetura

O aplicativo é uma central desktop em Python 3.11 e PySide6. Ele não incorpora o código dos demais projetos: mantém catálogos locais e abre cada ferramenta/projeto pelo tipo e caminho configurados.

## Componentes

- **Interface:** navegação por categoria, pesquisa, cartões, tema e fluxo integrado.
- **Catálogo de ferramentas:** `tools.json` em AppData, responsável pelas ferramentas executáveis.
- **Catálogo de projetos:** `projects.json` em AppData, responsável pelo acompanhamento do portfólio.
- **Executor:** abre HTML, arquivos, pastas, executáveis, scripts, projetos Python e URLs.
- **Git local:** quando a pasta de um projeto contém `.git`, o painel tenta exibir o último commit local.
- **Logs:** gravados em AppData para facilitar suporte.

## Estados oficiais de projeto

- `ATIVO`: projeto na fila de trabalho atual.
- `BLOQUEADO`: existe uma dependência técnica/externa impedindo o avanço normal.
- `PAUSADO`: projeto existente, mas fora da fila ativa.
- `PLANEJADO`: ainda não deve consumir desenvolvimento relevante.
- `FINALIZADO`: entrega utilizável, sujeita apenas a manutenção.

## Fluxo FGTS Poligonal

1. Leitor PDF Extrato Mensal - Poligonal gera a planilha XLSX.
2. FGTS por Obra / Poligonal importa essa planilha e continua a automação.

Os campos `workflow` e `step` conectam visualmente ferramentas dependentes.

## Configuração local

Na primeira execução, o aplicativo cria:

- `%APPDATA%\DP Ferramentas e Utilidades\tools.json`
- `%APPDATA%\DP Ferramentas e Utilidades\projects.json`

Assim, os caminhos e os status podem ser ajustados sem alterar o código-fonte.

## Segurança

Credenciais, dados de clientes, PDFs e planilhas de produção não devem ser versionados. O GitHub contém apenas código, configuração de exemplo e documentação.
