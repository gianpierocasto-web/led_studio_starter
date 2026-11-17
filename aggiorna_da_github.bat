@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "BLEND=LED_Studio.blend"
set "SCRIPT=scripts\led_starter.py"
set "BLENDER=E:\blender\blender.exe"

if defined BLENDER_EXE if exist "%BLENDER_EXE%" set "BLENDER=%BLENDER_EXE%"
if not exist "%BLENDER%" if exist "C:\Program Files\Blender Foundation\Blender 5.3\blender.exe" set "BLENDER=C:\Program Files\Blender Foundation\Blender 5.3\blender.exe"
if not exist "%BLENDER%" (
    for /f "delims=" %%I in ('where blender 2^>nul') do if not exist "%BLENDER%" set "BLENDER=%%I"
)

where git >nul 2>&1
if errorlevel 1 (
    echo [ERRORE] Git non trovato nel PATH. Installa Git per usare l'aggiornamento da GitHub.
    pause
    exit /b 1
)
if not exist ".git\" (
    echo [ERRORE] Questa cartella non e un repository Git ^(.git mancante^).
    pause
    exit /b 1
)
if not exist "%BLEND%" (
    echo [ERRORE] File non trovato: "%CD%\%BLEND%"
    pause
    exit /b 1
)
if not exist "%BLENDER%" (
    echo [ERRORE] Blender 5.3 non trovato in "E:\blender\blender.exe", in Program Files ne nel PATH.
    pause
    exit /b 1
)

call :is_blender_running
if %errorlevel% equ 0 (
    call :ask_and_close_blender
    if errorlevel 2 exit /b 0
    if errorlevel 1 (
        pause
        exit /b 1
    )
)

echo.
echo [1/3] Scarico gli aggiornamenti da GitHub ^(origin/main^)...
git fetch origin
if errorlevel 1 (
    echo [ERRORE] Connessione a GitHub fallita durante "git fetch origin".
    pause
    exit /b 1
)

echo [2/3] Aggiorno script e guide ^(preservando %BLEND% e gli asset locali^)...
set "SKIP_SELF=0"
for /f "usebackq delims=" %%F in (`git ls-tree -r --name-only origin/main`) do (
    if /I "%%F"=="%BLEND%" (
        echo   - salto %%F ^(preservato^)
    ) else if /I "%%F"=="aggiorna_da_github.bat" (
        set "SKIP_SELF=1"
    ) else (
        echo   - aggiorno %%F
        git checkout origin/main -- "%%F"
        if errorlevel 1 (
            echo [ERRORE] Impossibile aggiornare "%%F".
            pause
            exit /b 1
        )
    )
)

if not exist "%SCRIPT%" (
    echo [ERRORE] Script mancante dopo il fetch: "%CD%\%SCRIPT%"
    pause
    exit /b 1
)

echo.
echo [3/3] Aggiorno i soli Geometry Nodes e Render Passes dentro "%BLEND%"...
"%BLENDER%" -b "%BLEND%" --python "%SCRIPT%" -- --upgrade-inplace
set "EXIT_CODE=%errorlevel%"

if exist "%BLEND%1" if exist "archivio\" (
    move /Y "%BLEND%1" "archivio\" >nul 2>&1
)

echo.
if %EXIT_CODE% neq 0 (
    echo [ERRORE] Aggiornamento nodi non riuscito ^(codice %EXIT_CODE%^).
    pause
    exit /b %EXIT_CODE%
)

echo Aggiornamento completato: script e guide aggiornati da GitHub; luci, camera e asset locali intatti.
if "%SKIP_SELF%"=="1" (
    (goto) 2>nul & git checkout origin/main -- aggiorna_da_github.bat >nul 2>&1 & pause & exit /b 0
)
pause
exit /b 0

:is_blender_running
tasklist /FI "IMAGENAME eq blender.exe" 2>nul | find /I "blender.exe" >nul
exit /b %errorlevel%

:ask_and_close_blender
echo.
echo ============================================================================
echo  ATTENZIONE: Blender e attualmente aperto.
echo  Prima di proseguire, salva il tuo lavoro in Blender ^(Ctrl+S^).
echo ============================================================================
echo.
choice /C SN /N /M "Hai salvato tutti i file? Premere [S] per chiudere Blender e aggiornare, [N] per annullare: "
if errorlevel 2 (
    echo Operazione annullata. Blender resta aperto.
    exit /b 2
)

echo Chiusura di Blender in corso...
taskkill /IM blender.exe >nul 2>&1
set /a tries=0

:wait_close
call :is_blender_running
if %errorlevel% neq 0 exit /b 0
set /a tries+=1
if %tries% lss 6 (
    timeout /t 1 /nobreak >nul
    goto wait_close
)

echo Blender non si e chiuso in tempo. Chiusura forzata in corso...
taskkill /F /IM blender.exe >nul 2>&1
timeout /t 1 /nobreak >nul
call :is_blender_running
if %errorlevel% equ 0 (
    echo [ERRORE] Impossibile chiudere blender.exe. Chiudilo manualmente e riprova.
    exit /b 1
)
exit /b 0
