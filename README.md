# DP - Ferramentas & Utilidades

Aplicativo desktop para centralizar ferramentas, automações e documentos do Departamento Pessoal.

## Estado atual

O repositório foi inicializado em 17/09/2026. O desenvolvimento ocorre em branch própria antes da validação no Windows.

## Objetivo

Disponibilizar uma central instalada no Windows capaz de:

- abrir ferramentas HTML, Python, executáveis, planilhas e páginas web;
- representar fluxos integrados entre projetos;
- validar se cada ferramenta está disponível na máquina;
- concentrar atalhos para documentação, logs e configurações;
- preservar dados operacionais, certificados, credenciais, planilhas reais e relatórios somente no computador do usuário.

## Primeiro fluxo integrado

1. **Leitor PDF Extrato Mensal — Poligonal** gera a planilha XLSX.
2. **FGTS por Obra / Poligonal** importa a planilha e executa a emissão das guias.

## Ambiente previsto

- Windows 10 ou 11;
- Python 3.11 para desenvolvimento;
- distribuição futura em EXE/SETUP sem exigir Python na máquina de uso;
- clonagem prevista em `C:\Users\Cezar.CONTALEX\Desktop\GitHub\DP-Ferramentas-e-Utilidades`.

## Segurança

Não versionar certificados, senhas, cookies, sessões autenticadas, planilhas reais, relatórios fiscais, documentos de empregados ou logs contendo dados pessoais.
