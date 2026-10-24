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
        PATH: "/home/dev-server/apps/inteliaudit/.venv/bin:" + (process.env.PATH || ""),
        PORT: "8001",
        PYTHONUNBUFFERED: "1"
      }
    }
  ]
};
