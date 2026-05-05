Set-Location "C:\Users\Gustavo\OneDrive\Dev\Inteliaudit"
$env:DATABASE_URL = "sqlite+aiosqlite:///./inteliaudit.db"
& "venv\Scripts\python.exe" -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
