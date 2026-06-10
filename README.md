# Inteliaudit

![CI/CD Pipeline](https://github.com/gustaquevedo-lab/Inteliaudit/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.12-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)
![License](https://img.shields.io/badge/license-proprietary-red.svg)

**SaaS de automatización de auditoría impositiva para Paraguay**

Inteliaudit automatiza el trabajo del auditor impositivo desde la descarga de datos en Marangatú hasta la generación de informes finales firmables.

## 🎯 Características

- **Ingesta automática**: Scraping de Marangatú (portal SET) con Playwright
- **Análisis inteligente**: Cruces automáticos RG90 × SIFEN × HECHAUKA
- **Hallazgos con IA**: Generación de narrativas profesionales con Claude API
- **Informes profesionales**: Word/PDF con identidad visual de la firma
- **Multi-tenant**: Sistema SaaS con firmas, usuarios y planes
- **Portal del cliente**: Vista compartible con token para clientes auditados

## 🏗️ Stack Tecnológico

**Backend:**
- Python 3.12 + FastAPI
- SQLAlchemy 2.0 (async) + Alembic
- PostgreSQL (Railway) / SQLite (dev)
- Playwright (scraping)
- Anthropic Claude API (análisis IA)

**Frontend:**
- React 18 + TypeScript
- Vite 5
- Tailwind CSS
- Recharts (visualizaciones)

**Deploy:**
- Railway PRO (hosting + PostgreSQL)
- GitHub Actions (CI/CD)

## 📁 Estructura del Proyecto

```
inteliaudit/
├── api/                    # FastAPI endpoints
│   ├── routers/           # Auth, clientes, auditorías, hallazgos, informes
│   └── main.py            # App principal
├── db/                    # SQLAlchemy models + CRUD
│   ├── models.py          # 14 tablas (Firma, Usuario, Cliente, Auditoría, etc.)
│   └── db.py              # Operaciones CRUD
├── analisis/              # Lógica de auditoría
│   ├── iva.py             # 5 cruces IVA
│   ├── riesgo.py          # Cálculo de contingencias
│   └── claude_analisis.py # Narrativas con IA
├── ingesta/               # Descarga de datos
│   ├── marangatu.py       # Scraper Playwright
│   ├── sifen.py           # Cliente SIFEN (e-Kuatia)
│   └── parser_rg90.py     # Parser XLSX RG90
├── informes/              # Generación de informes
│   ├── word_profesional.py
│   └── pdf_profesional.py
├── ui-web/                # Frontend React
│   ├── src/
│   └── dist/              # Build output
├── tests/                 # Suite de tests (85 tests)
│   ├── test_iva.py        # 11 tests - cruces IVA
│   ├── test_riesgo.py     # 20 tests - contingencias
│   ├── test_auth.py       # 13 tests - JWT + permisos
│   ├── test_parser_rg90.py # 22 tests - parsing XLSX
│   └── test_sifen.py      # 15 tests - XML e-Kuatia
├── alembic/               # Migraciones DB
├── landing/               # Landing page HTML
└── config/                # Settings + planes
```

## 🚀 Inicio Rápido

### Desarrollo Local

```bash
# 1. Clonar repo
git clone https://github.com/gustaquevedo-lab/Inteliaudit.git
cd Inteliaudit

# 2. Crear venv e instalar
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e ".[dev]"

# 3. Configurar .env
cp .env.example .env
# Editar .env con tus variables

# 4. Inicializar DB
alembic upgrade head

# 5. Instalar Playwright
playwright install chromium

# 6. Ejecutar servidor
uvicorn api.main:app --reload --port 8000

# 7. Frontend (en otra terminal)
cd ui-web
npm install
npm run dev
```

### Tests

```bash
# Ejecutar todos los tests
pytest

# Con coverage
pytest --cov --cov-report=html

# Tests específicos
pytest tests/test_iva.py -v
```

### Build Frontend

```bash
cd ui-web
npm run build
```

## 🌐 Producción

**URL:** https://inteliaudit-production.up.railway.app

**Deploy automático:** Railway detecta pushes a `main` y redeploya automáticamente.

## 📊 Roadmap

Ver [ROADMAP.html](./ROADMAP.html) para el plan completo de implementación.

**Fases actuales:**
- ✅ **0.1** Migraciones Alembic
- ✅ **0.2** Tests fundamentales (85 tests)
- ⏳ **0.3** CI/CD con GitHub Actions
- ⏳ **0.4** Seed de datos realistas
- ⏳ **0.5** Migración Render → Railway (completada)
- ⏳ **1.x** Core funcional completo

## 🔐 Seguridad

- Credenciales Marangatú cifradas con Fernet (AES-128-CBC)
- JWT HS256 para autenticación
- Passwords con bcrypt
- CORS configurado para dominios permitidos
- Rate limiting (pendiente)

## 📝 Marco Legal

Inteliaudit opera bajo el marco legal paraguayo:
- Ley 6380/2019 (Modernización tributaria)
- RG 90/2021 (Detalle comprobantes IVA)
- RG 69/2020 (Factura electrónica e-Kuatia)

## 🤝 Contribución

Este es un proyecto privado. Para consultas o soporte, contactar al equipo de desarrollo.

## 📄 Licencia

Propietario - Todos los derechos reservados

---

**Desarrollado por Gustavo Quevedo** | Paraguay 🇵🇾
