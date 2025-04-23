@echo off
REM Search Test Wrapper Script for Windows
REM This script makes it easier to run the NLP search tests

REM Set Python path to use the virtual environment if it exists
if exist venv\Scripts\python.exe (
    set PYTHON=venv\Scripts\python.exe
) else (
    set PYTHON=python
)

REM Check if help argument is present
if "%1"=="--help" (
    echo Usage: search_test.bat [query] [options]
    echo.
    echo Options:
    echo   --mock             Use mock data instead of real Algolia search
    echo   --process-only     Only process the query, don't search
    echo   --openai-key KEY   OpenAI API key to use for processing
    echo   --page NUMBER      Page number (default: 1)
    echo   --per-page NUMBER  Results per page (default: 10)
    echo.
    echo Examples:
    echo   search_test.bat "I need a free tool for writing blog posts" --mock
    echo   search_test.bat "Show me AI image generators" --openai-key YOUR_API_KEY
    echo.
    exit /b 0
)

REM Run the search test script with all provided arguments
%PYTHON% search_test.py %*

REM Pause at the end so results don't disappear if run by double-clicking
if not defined PROMPT pause 