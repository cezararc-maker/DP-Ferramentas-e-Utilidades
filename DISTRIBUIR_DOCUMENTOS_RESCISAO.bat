@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "PYTHONUTF8=1"

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo O ambiente do programa nao foi encontrado.
    echo Execute primeiro: scripts\instalar.ps1
    echo.
    pause
    exit /b 2
)

set "ORIGEM=%~1"
if not defined ORIGEM (
    echo.
    echo Cole o caminho da pasta onde estao os Extratos FGTS e as Consultas do Consignado.
    set /p "ORIGEM=Pasta dos documentos: "
)
set "ORIGEM=%ORIGEM:"=%"

echo.
echo Cole o caminho da pasta principal das rescisoes.
echo Essa pasta deve conter uma subpasta para cada colaborador.
set /p "DESTINO=Pasta principal das rescisoes: "
set "DESTINO=%DESTINO:"=%"

if not defined ORIGEM (
    echo ERRO: a pasta dos documentos nao foi informada.
    pause
    exit /b 2
)
if not defined DESTINO (
    echo ERRO: a pasta principal das rescisoes nao foi informada.
    pause
    exit /b 2
)

echo.
".venv\Scripts\python.exe" -m dp_ferramentas.distribuir_documentos_cli --origem "%ORIGEM%" --destino "%DESTINO%"
set "RESULTADO=%ERRORLEVEL%"

echo.
if "%RESULTADO%"=="0" (
    echo Processo finalizado com sucesso.
) else (
    echo O processo terminou sem movimentar todos os arquivos.
    echo Revise as mensagens apresentadas acima.
)
echo.
pause
exit /b %RESULTADO%
