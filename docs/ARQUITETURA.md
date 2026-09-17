# Arquitetura

O aplicativo é uma central desktop em Python 3.11 e PySide6. Ele não incorpora o código dos demais projetos: mantém um catálogo local e abre cada ferramenta pelo tipo e caminho configurados.

## Componentes

- Interface: navegação por categoria, pesquisa, cartões e fluxo integrado.
- Catálogo: arquivo tools.json mantido na pasta AppData do usuário.
- Executor: abre HTML, arquivos, pastas, executáveis, scripts, projetos Python e URLs.
- Logs: gravados em AppData para facilitar suporte.

## Fluxo FGTS Poligonal

1. Leitor PDF Extrato Mensal — Poligonal gera a planilha XLSX.
2. FGTS por Obra / Poligonal importa essa planilha e continua a automação.

Os campos workflow e step conectam visualmente ferramentas dependentes.

## Segurança

Credenciais, dados de clientes, PDFs e planilhas de produção não devem ser versionados. O GitHub contém apenas código, configuração de exemplo e documentação.
