@echo off
REM ==========================================================================
REM  iniciar_aplicacao_schulz.bat - Projeto Aplicado III (AV05) - Grupo 6
REM  MVP de automacao de certificados de calibracao - Schulz S.A.
REM
REM  Etapas: 1) verifica Python 3.10+ no PATH   2) cria e ativa o venv
REM          3) instala o requirements.txt       4) inicia a API backend e
REM             abre a interface no navegador padrao
REM
REM  Uso:  iniciar_aplicacao_schulz.bat          (acesso somente nesta maquina)
REM        iniciar_aplicacao_schulz.bat rede     (celulares na mesma rede Wi-Fi
REM                                              podem ler o QR Code)
REM ==========================================================================
setlocal EnableExtensions
title Schulz MVP - Inicializacao
cd /d "%~dp0"

set "MODO=%~1"
set "VENV=.venv"
set "VENV_PY=%CD%\%VENV%\Scripts\python.exe"
set "PORTA_INICIAL=5000"

echo.
echo  ===============================================================
echo   MVP Schulz S.A. - Certificados de Calibracao (Grupo 6 - AV05)
echo  ===============================================================
echo.

if not exist "app.py" goto :erro_pasta
if not exist "requirements.txt" goto :erro_pasta

REM --------------------------------------------------------------------------
echo [1/4] Verificando o Python 3.10+ no PATH do sistema...
set "PY="
where python >nul 2>&1
if not errorlevel 1 (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if not errorlevel 1 set "PY=python"
)
if not defined PY (
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
        if not errorlevel 1 set "PY=py -3"
    )
)
if not defined PY goto :erro_python
for /f "delims=" %%v in ('%PY% -c "import sys; print(sys.version.split()[0])"') do set "PY_VERSAO=%%v"
echo       OK - Python %PY_VERSAO% encontrado (comando: %PY%)
echo.

REM --------------------------------------------------------------------------
echo [2/4] Preparando o ambiente virtual (%VENV%)...
if exist "%VENV_PY%" (
    "%VENV_PY%" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if errorlevel 1 (
        echo       Ambiente virtual antigo ou corrompido. Recriando...
        rmdir /s /q "%VENV%"
    )
)
if not exist "%VENV_PY%" (
    %PY% -m venv "%VENV%"
    if errorlevel 1 goto :erro_venv
    echo       Ambiente virtual criado.
) else (
    echo       Ambiente virtual ja existente.
)
call "%VENV%\Scripts\activate.bat"
if not defined VIRTUAL_ENV goto :erro_venv
echo       OK - ambiente virtual ativado ("%VIRTUAL_ENV%").
echo.

REM --------------------------------------------------------------------------
echo [3/4] Instalando as bibliotecas do requirements.txt...
if exist "%VENV%\requirements.instalado" (
    fc /b "requirements.txt" "%VENV%\requirements.instalado" >nul 2>&1
    if not errorlevel 1 (
        echo       OK - bibliotecas ja instaladas e atualizadas.
        goto :iniciar
    )
)
"%VENV_PY%" -m pip install -r requirements.txt --disable-pip-version-check
if errorlevel 1 goto :erro_pip
copy /y "requirements.txt" "%VENV%\requirements.instalado" >nul
echo       OK - bibliotecas instaladas.

:iniciar
echo.
REM --------------------------------------------------------------------------
echo [4/4] Iniciando a API backend e a interface web...
set "PORTA="
REM "python" aqui e o do ambiente virtual ativado (sem aspas, evita problemas do for /f com espacos)
for /f "delims=" %%p in ('python app.py --porta-livre %PORTA_INICIAL%') do set "PORTA=%%p"
if not defined PORTA goto :erro_porta
if not "%PORTA%"=="%PORTA_INICIAL%" echo       Porta %PORTA_INICIAL% ocupada; usando a porta %PORTA%.

set "ARGS=--porta %PORTA%"
if /i "%MODO%"=="rede" set "ARGS=%ARGS% --rede"
start "Schulz MVP - API backend (feche esta janela para encerrar)" "%VENV_PY%" app.py %ARGS% --pausar-em-erro

set "URL=http://127.0.0.1:%PORTA%/"
echo       Aguardando o servidor responder em %URL%api/status ...
"%VENV_PY%" app.py --aguardar "%URL%api/status" --timeout 90
if errorlevel 1 goto :erro_servidor
start "" "%URL%"

echo.
echo  ===============================================================
echo   Aplicacao em execucao:  %URL%
echo   API (status):           %URL%api/status
echo   Validacao de QR Code:   %URL%validar
if /i "%MODO%"=="rede" echo   Modo rede ativo: o endereco do QR Code aparece na janela da API.
echo.
echo   Usuarios de demonstracao (senha local: senha123)
echo     executor1    importa a planilha (.xlsx)
echo     emissor1     analisa e finaliza o certificado
echo     signatario1  analisa e finaliza o certificado
echo     auditor1     somente consulta      admin  cadastra padroes
echo.
echo   Planilhas de exemplo: pasta samples\ (01_valida_aprovada.xlsx)
echo   Para encerrar: feche a janela "Schulz MVP - API backend".
echo  ===============================================================
echo.
pause
endlocal
exit /b 0

REM ======================== mensagens de erro ================================
:erro_pasta
echo [ERRO] Execute este script na raiz do repositorio (onde estao app.py e
echo        requirements.txt). Se baixou o .zip do GitHub, extraia-o antes.
goto :falha

:erro_python
echo [ERRO] Python 3.10 ou superior nao foi encontrado no PATH.
echo        1. Baixe em https://www.python.org/downloads/
echo        2. Na instalacao, marque "Add python.exe to PATH".
echo        3. Feche e abra o terminal e execute este script novamente.
echo        Obs.: o atalho "python" da Microsoft Store nao e um Python instalado.
goto :falha

:erro_venv
echo [ERRO] Nao foi possivel criar ou ativar o ambiente virtual em %VENV%.
echo        Verifique a permissao de escrita nesta pasta e tente novamente.
goto :falha

:erro_pip
echo [ERRO] Falha ao instalar as bibliotecas do requirements.txt.
echo        Verifique a conexao com a internet (ou proxy) e execute novamente.
goto :falha

:erro_porta
echo [ERRO] Nao foi possivel encontrar uma porta TCP livre a partir de %PORTA_INICIAL%.
goto :falha

:erro_servidor
echo [ERRO] O servidor nao respondeu em 90 segundos.
echo        Veja a mensagem na janela "Schulz MVP - API backend".
goto :falha

:falha
echo.
pause
endlocal
exit /b 1
