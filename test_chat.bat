@echo off
echo Starting TAAFT Chat Test Server
echo.
echo This will run the server in TEST_MODE, which uses an in-memory database
echo instead of MongoDB for testing purposes.
echo.
set TEST_MODE=true
python -m uvicorn app.main:app --reload 