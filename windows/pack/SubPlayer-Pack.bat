@echo off
rem ===========================================================================================
rem  SubPlayer-Pack.bat  -  carry SubPlayer to another PC (or give it to someone) on a flash drive
rem
rem  Put this file next to SubPlayer.exe and double-click it:
rem    [1] Pack for ME            program + everything of yours: words, review, lessons, subtitles,
rem                               settings, licence, dictionaries, Whisper models (+ Ollama, if you want)
rem    [2] Pack for SOMEONE ELSE  program + dictionaries + Whisper models (+ Ollama) - none of your
rem                               words, settings, sync token, licence or owner key
rem  On the flash drive the pack has this same file. On the new PC double-click it there:
rem    [3] Install on this PC     program, data, Ollama and its models, desktop shortcut
rem  The pack also runs straight from the flash drive: SubPlayer\SubPlayer.exe (portable).
rem ===========================================================================================
setlocal EnableExtensions
chcp 65001 >nul
title SubPlayer - carry it to another PC
set "HERE=%~dp0"
if "%HERE:~-1%"=="\" set "HERE=%HERE:~0,-1%"
set "RC=/E /R:1 /W:1 /NDL /NJH /NJS /NC /NS"
set "OMODELS=%USERPROFILE%\.ollama\models"
if defined OLLAMA_MODELS set "OMODELS=%OLLAMA_MODELS%"
set "OPROG=%LOCALAPPDATA%\Programs\Ollama"

:menu
cls
echo.
echo   ===============  SubPlayer: carry it to another PC  ===============
echo.
if exist "%HERE%\SubPlayer.exe" echo   [1] Pack for ME - program and all my data, dictionaries, Whisper, Ollama
if exist "%HERE%\SubPlayer.exe" echo   [2] Pack for SOMEONE ELSE - program, dictionaries, Whisper, Ollama only
if exist "%HERE%\SubPlayer\SubPlayer.exe" echo   [3] Install SubPlayer from this pack on THIS PC
echo   [Q] Quit
echo.
if not exist "%HERE%\SubPlayer.exe" if not exist "%HERE%\SubPlayer\SubPlayer.exe" (
  echo   This file must be next to SubPlayer.exe, or in a SubPlayer pack on a flash drive.
  echo.
)
set "CH="
set /p "CH=  Your choice: "
if /i "%CH%"=="Q" goto end
if "%CH%"=="1" if exist "%HERE%\SubPlayer.exe" goto pack_me
if "%CH%"=="2" if exist "%HERE%\SubPlayer.exe" goto pack_other
if "%CH%"=="3" if exist "%HERE%\SubPlayer\SubPlayer.exe" goto install
goto menu

rem ============================================================================== PACK
:pack_me
set "MODE=me"
goto pack
:pack_other
set "MODE=other"
:pack
tasklist /fi "imagename eq SubPlayer.exe" 2>nul | find /i "SubPlayer.exe" >nul
if not errorlevel 1 (
  echo.
  echo   SubPlayer is open. Close it first, so your words are copied completely.
  pause
  goto menu
)
echo.
echo   Where should the pack go? Type the flash drive letter, for example  E
echo   or a folder, for example  E:\Backup
set "DEST="
set /p "DEST=  Drive or folder: "
if not defined DEST goto menu
set "DEST=%DEST:"=%"
if "%DEST:~1%"=="" set "DEST=%DEST%:"
if "%DEST:~-1%"=="\" set "DEST=%DEST:~0,-1%"
if not exist "%DEST%\" (
  echo   %DEST% was not found.
  pause
  goto menu
)
set "FS="
set "FREE="
for /f "usebackq delims=" %%F in (`powershell -NoProfile -Command "(New-Object IO.DriveInfo '%DEST:~0,2%').DriveFormat"`) do set "FS=%%F"
for /f "usebackq delims=" %%F in (`powershell -NoProfile -Command "'{0:N1}' -f ((New-Object IO.DriveInfo '%DEST:~0,2%').AvailableFreeSpace/1GB)"`) do set "FREE=%%F"
if "%MODE%"=="me" (set "PACK=%DEST%\SubPlayer pack - mine") else (set "PACK=%DEST%\SubPlayer pack")

set "DATA=%APPDATA%\SubPlayer"
if exist "%HERE%\SubPlayer data\" set "DATA=%HERE%\SubPlayer data"
call :size "%HERE%" PSIZE
if "%MODE%"=="me" (call :size "%DATA%" DSIZE) else (call :size "%DATA%\assets" DSIZE)
echo.
echo   Program:                         %PSIZE% GB
if "%MODE%"=="me" echo   Your data, dictionaries, Whisper: %DSIZE% GB   from %DATA%
if "%MODE%"=="other" echo   Dictionaries and Whisper models:  %DSIZE% GB   from %DATA%\assets
echo   Free on %DEST:~0,2%                       %FREE% GB   - file system %FS%
if /i "%FS%"=="FAT32" (
  echo.
  echo   WARNING: this drive is FAT32 - it cannot hold files bigger than 4 GB, so large Ollama
  echo   models would fail. Better: back up the drive, then right-click it in Explorer, Format,
  echo   File system exFAT.
)
echo.
echo   The pack goes to: %PACK%
choice /c YN /m "  Start"
if errorlevel 2 goto menu

echo.
echo   [1/3] Copying the program ...
robocopy "%HERE%" "%PACK%\SubPlayer" %RC% /XD "SubPlayer data" >nul
if errorlevel 8 goto copy_failed

echo   [2/3] Copying data ...
if "%MODE%"=="other" goto pack_assets
set "SKIPKEY=N"
if exist "%DATA%\owner.key" (
  echo.
  echo   Your OWNER KEY - it makes activation codes - is on this PC.
  choice /c YN /m "  Put the owner key on the flash drive too - only if you need Owner tools on the new PC"
  if errorlevel 2 set "SKIPKEY=Y"
)
if "%SKIPKEY%"=="Y" (
  robocopy "%DATA%" "%PACK%\SubPlayer\SubPlayer data" %RC% /XF owner.key
) else (
  robocopy "%DATA%" "%PACK%\SubPlayer\SubPlayer data" %RC%
)
if errorlevel 8 goto copy_failed
goto pack_ollama
:pack_assets
if exist "%DATA%\assets\" robocopy "%DATA%\assets" "%PACK%\SubPlayer\SubPlayer data\assets" %RC%
if errorlevel 8 goto copy_failed
if not exist "%PACK%\SubPlayer\SubPlayer data\" mkdir "%PACK%\SubPlayer\SubPlayer data"

:pack_ollama
echo   [3/3] Ollama ...
if not exist "%OMODELS%\manifests\" (
  echo         no Ollama models on this PC - skipped
  goto pack_finish
)
call :size "%OMODELS%" OSIZE
echo.
echo   Ollama models on this PC: %OSIZE% GB  in %OMODELS%
echo   Tip: delete big models you don't use first, in Command Prompt e.g.   ollama rm deepseek-v2.5
choice /c YN /m "  Copy Ollama and these models too"
if errorlevel 2 goto pack_finish
echo   Copying Ollama models - this can take a while ...
robocopy "%OMODELS%" "%PACK%\Ollama\models" %RC%
if errorlevel 8 goto copy_failed
if exist "%OPROG%\ollama.exe" robocopy "%OPROG%" "%PACK%\Ollama\program" %RC% >nul
for %%I in ("%USERPROFILE%\Downloads\OllamaSetup*.exe") do copy /y "%%~fI" "%PACK%\Ollama\OllamaSetup.exe" >nul

:pack_finish
copy /y "%~f0" "%PACK%\SubPlayer-Pack.bat" >nul
> "%PACK%\READ ME.txt" (
  echo SubPlayer pack
  echo.
  echo On the new PC: double-click SubPlayer-Pack.bat and choose 3 - Install.
  echo Or run SubPlayer straight from here: SubPlayer\SubPlayer.exe - everything stays in "SubPlayer data".
  echo.
  echo A new PC has its own device code. The owner makes an activation code for it - Settings shows the code.
  echo Videos are not in the pack: copy them separately, with the same file names.
)
echo.
echo   ===============================================================
echo   Done: %PACK%
if "%MODE%"=="me" echo   It holds your words and settings, including the sync token - keep the flash drive safe.
echo   On the new PC: open that folder and double-click SubPlayer-Pack.bat, then 3.
echo   ===============================================================
pause
goto end

rem ============================================================================== INSTALL
:install
set "TARGET=%LOCALAPPDATA%\Programs\SubPlayer"
echo.
echo   SubPlayer will be installed to:  %TARGET%
echo   Press Enter to accept, or type another folder.
set "T2="
set /p "T2=  Folder: "
if defined T2 set "TARGET=%T2:"=%"
tasklist /fi "imagename eq SubPlayer.exe" 2>nul | find /i "SubPlayer.exe" >nul
if not errorlevel 1 (
  echo   SubPlayer is open on this PC. Close it first.
  pause
  goto menu
)
echo.
echo   [1/3] Copying the program ...
robocopy "%HERE%\SubPlayer" "%TARGET%" %RC% /XD "SubPlayer data" >nul
if errorlevel 8 goto copy_failed

echo   [2/3] Copying data ...
set "PDATA=%HERE%\SubPlayer\SubPlayer data"
set "UDATA=%APPDATA%\SubPlayer"
if not exist "%PDATA%\" goto inst_ollama
if not exist "%PDATA%\words.db" goto inst_assets
if not exist "%UDATA%\words.db" goto inst_alldata
echo.
echo   This PC already has SubPlayer words in %UDATA%.
echo     R = replace them with the words from the pack - a backup of this PC's words is kept
echo     K = keep this PC's words - only dictionaries and Whisper models are added
choice /c RK /m "  R or K"
if errorlevel 2 goto inst_assets
set "STAMP=old"
for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmm"`) do set "STAMP=%%D"
robocopy "%UDATA%" "%UDATA%-backup-%STAMP%" %RC% /XD assets >nul
echo         backup: %UDATA%-backup-%STAMP%
:inst_alldata
robocopy "%PDATA%" "%UDATA%" %RC%
if errorlevel 8 goto copy_failed
goto inst_ollama
:inst_assets
if exist "%PDATA%\assets\" robocopy "%PDATA%\assets" "%UDATA%\assets" %RC%
if errorlevel 8 goto copy_failed

:inst_ollama
echo   [3/3] Ollama ...
if not exist "%HERE%\Ollama\models\" (
  echo         not in this pack - skipped
  goto inst_shortcut
)
if exist "%OPROG%\ollama.exe" goto inst_models
if exist "%HERE%\Ollama\OllamaSetup.exe" (
  echo   Installing Ollama - click Install in its window, then wait ...
  start "" /wait "%HERE%\Ollama\OllamaSetup.exe"
  goto inst_models
)
if not exist "%HERE%\Ollama\program\ollama.exe" (
  echo   Ollama itself is not in the pack: install it from https://ollama.com/download - the models are copied now.
  goto inst_models
)
robocopy "%HERE%\Ollama\program" "%OPROG%" %RC% >nul
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup')+'\Ollama.lnk'); $s.TargetPath='%OPROG%\ollama app.exe'; $s.WorkingDirectory='%OPROG%'; $s.Save()"
start "" "%OPROG%\ollama app.exe"
:inst_models
echo   Copying Ollama models - this can take a while ...
robocopy "%HERE%\Ollama\models" "%OMODELS%" %RC%
if errorlevel 8 goto copy_failed

:inst_shortcut
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\SubPlayer.lnk'); $s.TargetPath='%TARGET%\SubPlayer.exe'; $s.WorkingDirectory='%TARGET%'; $s.Save()"
echo.
echo   ===============================================================
echo   Done. SubPlayer is in %TARGET% - there is a SubPlayer icon on the desktop.
echo   Its data is in %UDATA%.
echo   If Settings asks for activation: send the device code it shows to the owner.
echo   ===============================================================
pause
goto end

rem ============================================================================== helpers
:size
set "%~2=?"
for /f "usebackq delims=" %%S in (`powershell -NoProfile -Command "$t=0; foreach($f in (Get-ChildItem -LiteralPath '%~1' -Recurse -File -Force -ErrorAction SilentlyContinue)){$t+=$f.Length}; '{0:N1}' -f ($t/1GB)"`) do set "%~2=%%S"
exit /b

:copy_failed
echo.
echo   Some files could not be copied - is the drive full or was it removed? Nothing was deleted;
echo   you can run this again, it continues where it stopped.
pause

:end
endlocal
