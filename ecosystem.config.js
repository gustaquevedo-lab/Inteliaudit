module.exports = {
  apps: [
    {
      name: "inteliaudit-api",
      script: "/home/dev-server/apps/inteliaudit/.venv/bin/uvicorn",
      args: "api.main:app --host 0.0.0.0 --port 8001 --workers 2",
      cwd: "/home/dev-server/apps/inteliaudit",
      interpreter: "none",
      autorestart: true,
      watch: false,
      max_memory_restart: "1G",
      env: {
        PATH: "/home/dev-server/apps/inteliaudit/.venv/bin:" + process.env.PATH,
        PORT: "8001",
        DATABASE_URL: "postgresql://postgres:UAWS6rZmTinvcDOusJHp1Z76WWPWKOQXzXTNe29pRKXD9qkt3a2djWFxNd0c3lBk@10.0.1.7:5432/inteliaudit",
        SECRET_KEY: "gustavo-audit-prod-secure-key",
        ALLOWED_ORIGINS: "[\"https://inteliaudit.vercel.app\",\"https://inteliaudit.intellihouse.lat\",\"http://localhost:3000\",\"http://localhost:5173\",\"http://localhost:8001\"]",
        GEMINI_API_KEY: "AIzaSyD7_n4MFSx2VbfY_LAbknl_i81wHsFTh6M",
        R2_ACCESS_KEY: "56f844dc1a4bdceab25f3f31fa91a0b5",
        R2_SECRET_KEY: "e0d20fd460d7f84a32be5b5708ea01ee03bf6a01ef49ca1d0f801cc06fd1a9a7",
        R2_ACCOUNT_ID: "6367a26777aaf8d1363fc925dbb831b1",
        R2_BUCKET: "inteliaudit",
        STORAGE_PATH: "/home/dev-server/apps/inteliaudit/storage",
        PYTHONUNBUFFERED: "1"
      }
    }
  ]
};
