@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ============================================
echo   Strovo — регистрация протокола strovo://
echo ============================================
echo.

REM Ищем Strovo.exe рядом со скриптом, в Program Files, в текущей папке
set "EXE="
if exist "%~dp0Strovo.exe" set "EXE=%~dp0Strovo.exe"
if exist "%~dp0Strovo-Setup.exe" set "EXE=%~dp0Strovo-Setup.exe"
if exist "%LocalAppData%\Strovo\Strovo.exe" set "EXE=%LocalAppData%\Strovo\Strovo.exe"
if exist "%ProgramFiles%\Strovo\Strovo.exe" set "EXE=%ProgramFiles%\Strovo\Strovo.exe"
if exist "%ProgramFiles(x86)%\Strovo\Strovo.exe" set "EXE=%ProgramFiles(x86)%\Strovo\Strovo.exe"
if exist "C:\strovo\Strovo.exe" set "EXE=C:\strovo\Strovo.exe"
if exist "C:\Strovo\Strovo.exe" set "EXE=C:\Strovo\Strovo.exe"

if "%EXE%"=="" (
    echo [!] Strovo.exe не найден автоматически.
    echo.
    set /p EXE=Укажи полный путь к Strovo.exe: 
    if not exist "!EXE!" (
        echo [ОШИБКА] Файл не найден: !EXE!
        pause
        exit /b 1
    )
)

echo Найден клиент:
echo   %EXE%
echo.

REM Папка логов
if not exist "C:\strovo-log" mkdir "C:\strovo-log"

REM Регистрация протокола strovo:// в HKCU (не нужен админ)
set "EXE_ESC=%EXE:\=\\%"

reg add "HKCU\Software\Classes\strovo" /ve /d "URL:Strovo Protocol" /f >nul
reg add "HKCU\Software\Classes\strovo" /v "URL Protocol" /d "" /f >nul
reg add "HKCU\Software\Classes\strovo\DefaultIcon" /ve /d "\"%EXE%\",0" /f >nul
reg add "HKCU\Software\Classes\strovo\shell\open\command" /ve /d "\"%EXE%\" \"%%1\"" /f >nul

if errorlevel 1 (
    echo [ОШИБКА] Не удалось записать в реестр.
    pause
    exit /b 1
)

echo [OK] Протокол strovo:// зарегистрирован.
echo.
echo Теперь в браузере ссылки вида:
echo   strovo://play?id=...
echo будут открывать клиент.
echo.
echo Логи: C:\strovo-log
echo.
echo Проверка: открой в проводнике или Win+R:
echo   strovo://play?id=test
echo.
pause
