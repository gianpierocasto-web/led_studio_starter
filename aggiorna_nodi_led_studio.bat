@echo off
setlocal
cd /d "%~dp0"

set "BLEND=LED_Studio.blend"
set "SCRIPT=scripts\led_starter.py"
set "BLENDER=E:\blender\blender.exe"

if defined BLENDER_EXE if exist "%BLENDER_EXE%" set "BLENDER=%BLENDER_EXE%"
if not exist "%BLENDER%" (
    for /f "delims=" %%I in ('where blender 2^>nul') do if not exist "%BLENDER%" set "BLENDER=%%I"
)

if not exist "%BLEND%" (
    echo [ERRORE] File non trovato: "%CD%\%BLEND%"
    pause
    exit /b 1
)
if not exist "%SCRIPT%" (
    echo [ERRORE] Script non trovato: "%CD%\%SCRIPT%"
    pause
    exit /b 1
)
if not exist "%BLENDER%" (
    echo [ERRORE] Blender non trovato in "E:\blender\blender.exe" ne nel PATH.
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
echo Aggiornamento dei Geometry Nodes e del pannello in "%BLEND%"...
"%BLENDER%" -b "%BLEND%" --python "%SCRIPT%" -- --upgrade-inplace
set "EXIT_CODE=%errorlevel%"

if exist "%BLEND%1" if exist "archivio\" (
    move /Y "%BLEND%1" "archivio\" >nul 2>&1
)

echo.
if %EXIT_CODE% neq 0 (
    echo [ERRORE] Aggiornamento non riuscito ^(codice %EXIT_CODE%^).
    pause
    exit /b %EXIT_CODE%
)

echo Aggiornamento completato. Luci, camere e scene personalizzate sono rimaste intatte.
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
