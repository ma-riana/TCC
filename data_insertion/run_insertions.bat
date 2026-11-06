@echo off
setlocal
cd /d "%~dp0"

set SCRIPTS=polyglot_insertion.py graph_insertion.py multimodel_insertion.py

for %%S in (%SCRIPTS%) do (
    python %%S
    if errorlevel 1 (
        echo.
        echo [ERRO] %%S falhou com codigo %errorlevel%. Interrompendo.
        exit /b 1
    )
    echo [OK] %%S concluido
)

echo.
echo Todas as insercoes foram concluidas com sucesso.
endlocal