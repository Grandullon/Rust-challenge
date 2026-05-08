@echo off
REM Lanzador del dashboard de tareas periodicas
REM Usa Bypass de la politica solo para esta ejecucion (no toca nada del sistema)
chcp 65001 > nul
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0actualizar-dashboard.ps1"
if errorlevel 1 (
  echo.
  echo Hubo un error. Revisa los mensajes anteriores.
  pause
)
