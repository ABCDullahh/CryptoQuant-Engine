@echo off
echo ============================================================
echo   CryptoQuant Engine - Development Startup
echo ============================================================
echo.

docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running. Please start Docker Desktop.
    pause
    exit /b 1
)

echo [1/4] Starting TimescaleDB and Redis...
cd /d "%~dp0.."
docker compose up -d timescaledb redis

echo [2/4] Waiting for services to be ready...
ping -n 11 127.0.0.1 >nul

echo [3/4] Starting FastAPI backend...
start "CryptoQuant Backend" cmd /k "cd /d "%~dp0..\backend" && .venv\Scripts\activate && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

ping -n 6 127.0.0.1 >nul

echo [4/4] Starting Next.js frontend...
start "CryptoQuant Frontend" cmd /k "cd /d "%~dp0..\frontend" && npm run dev"

echo.
echo ============================================================
echo   All services started!
echo ============================================================
echo   Frontend:  http://localhost:3000
echo   Backend:   http://localhost:8000
echo   API Docs:  http://localhost:8000/docs
echo ============================================================
pause
