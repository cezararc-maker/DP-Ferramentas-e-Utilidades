# DP - Ferramentas & Utilidades

Aplicativo desktop para centralizar ferramentas, automações, documentos e o acompanhamento dos projetos do Departamento Pessoal.

## O que já funciona

- painel desktop com pesquisa e categorias;
- cartões que abrem projetos HTML, Python, executáveis, scripts, arquivos, pastas e páginas web;
- indicação quando o caminho de uma ferramenta ainda não existe no computador;
- fluxo visual integrado entre o Leitor PDF e o FGTS por Obra / Poligonal;
- catálogo local personalizável e logs de execução;
- tema claro/escuro;
- **Organizador de Seguro-Desemprego**: identifica SD/CD, agrupa por requerimento, valida nome/CPF e gera um PDF por colaborador sem alterar o original;
- **painel oficial de projetos** com status, progresso estimado, última atualização, último commit local, bloqueio, próxima tarefa e dependências;
- filtros de projetos por `ATIVO`, `BLOQUEADO`, `PAUSADO`, `PLANEJADO` e `FINALIZADO`;
- ações por projeto para abrir a pasta local, abrir o GitHub e executar quando houver comando configurado.

## Organizador de Seguro-Desemprego

Na categoria **Documentos**, abra **Seguro-Desemprego — Organizar SD/CD**.

Fluxo:

1. selecione um ou mais PDFs emitidos pelo portal do MTE;
2. a ferramenta identifica cada página como Requerimento SD ou Comunicação de Dispensa CD;
3. o agrupamento usa o número do requerimento como chave principal;
4. nome e CPF são usados como validações adicionais;
5. somente conjuntos com exatamente 1 SD + 1 CD e dados compatíveis são liberados para geração;
6. por padrão, a ferramenta cria uma pasta com o nome completo de cada colaborador e salva dentro dela `SD - NOME DO COLABORADOR.pdf`;
7. alternativamente, é possível selecionar a pasta principal das rescisões e distribuir os PDFs diretamente nas pastas já existentes;
8. no modo de distribuição direta, a busca tenta primeiro o nome exato e, se necessário, compara novamente ignorando `DE`, `DA`, `DO`, `DAS` e `DOS`;
9. a distribuição direta só ocorre quando existe uma única pasta correspondente; ausências ou ambiguidades são registradas como advertência e nenhum arquivo é colocado automaticamente naquele caso;
10. o PDF original nunca é alterado e arquivos existentes não são sobrescritos silenciosamente.

O processamento é local. PDFs protegidos por senha ou páginas que não possam ser identificadas são apontados como advertência/erro para revisão.

## Painel de projetos

A seção **Projetos** foi criada para organizar o portfólio sem misturá-lo ao catálogo de ferramentas executáveis.

Os dados iniciais são copiados na primeira execução para:

```text
%APPDATA%\DP Ferramentas e Utilidades\projects.json
```

Esse arquivo pode ser ajustado conforme o andamento real de cada projeto. O campo `progress` é um indicador operacional de 0 a 100 e não é calculado automaticamente.

Quando a pasta local cadastrada é um repositório Git, o aplicativo tenta mostrar o último commit diretamente do Git local. Se não conseguir, usa o valor informado no catálogo.

## Fluxo integrado - FGTS Poligonal

1. **Leitor PDF Extrato Mensal - Poligonal** gera a planilha XLSX.
2. **FGTS por Obra / Poligonal** importa a planilha e continua a automação.

## Testar no Windows

Abra o PowerShell na pasta do projeto e execute:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\instalar.ps1
.\scripts\executar.bat
```

Na primeira execução, os catálogos serão copiados para:

```text
%APPDATA%\DP Ferramentas e Utilidades\tools.json
%APPDATA%\DP Ferramentas e Utilidades\projects.json
```

## Gerar o executável

```powershell
.\scripts\build.ps1
```

O resultado ficará em `dist\DP_Ferramentas_Utilidades`.

## Ambiente previsto

- Windows 10 ou 11;
- Python 3.11 para desenvolvimento;
- distribuição futura em EXE/SETUP sem exigir Python na máquina de uso;
- clonagem prevista em `C:\Users\Cezar.CONTALEX\Desktop\GitHub\DP-Ferramentas-e-Utilidades`.

## Segurança

Não versionar certificados, senhas, cookies, sessões autenticadas, planilhas reais, relatórios fiscais, documentos de empregados ou logs contendo dados pessoais.
