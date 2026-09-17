# DP - Ferramentas & Utilidades

Aplicativo desktop para centralizar ferramentas, automações e documentos do Departamento Pessoal.

## O que já funciona

- painel desktop com pesquisa e categorias;
- cartões que abrem projetos HTML, Python, executáveis, scripts, arquivos, pastas e páginas web;
- indicação quando o caminho de uma ferramenta ainda não existe no computador;
- fluxo visual integrado entre o Leitor PDF e o FGTS por Obra / Poligonal;
- catálogo local personalizável e logs de execução.

## Fluxo integrado — FGTS Poligonal

1. **Leitor PDF Extrato Mensal — Poligonal** gera a planilha XLSX.
2. **FGTS por Obra / Poligonal** importa a planilha e continua a automação.

## Testar no Windows

Abra o PowerShell na pasta do projeto e execute:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\instalar.ps1
.\scripts\executar.bat
```

Na primeira execução, o catálogo será copiado para:

```text
%APPDATA%\DP Ferramentas e Utilidades\tools.json
```

Edite esse arquivo para ajustar os caminhos reais das ferramentas sem alterar o código.

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
