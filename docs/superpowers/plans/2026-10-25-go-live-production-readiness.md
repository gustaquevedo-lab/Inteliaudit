# Plan de Salida a Producción y Beta Privada (Go-Live Readiness)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Completar el endurecimiento de producción (secretos criptográficos, blindaje legal con Secreto Fiscal Art. 190, backups automatizados de PostgreSQL a Cloudflare R2, y protocolo operativo de Onboarding B2B) para abrir la Beta Privada de Inteliaudit en `https://inteliaudit.intellihouse.lat`.

**Architecture:**
- **Entorno:** Dev-Server Docker + PM2 (`inteliaudit-api`) expuesto bajo Cloudflare Zero Trust Tunnel en `https://inteliaudit.intellihouse.lat`.
- **Billing:** Modo A (High-Touch B2B): Las firmas auditoras transfieren por SIPAP/banco; el SuperAdmin crea o aprueba la firma de forma atómica en 1-clic con contraseña temporal y forzado de cambio en primer login.
- **Seguridad:** Cifrado simétrico Fernet (AES-128-CBC + HMAC-SHA256) para credenciales Marangatú, JWT HS256 con `SECRET_KEY` criptográficamente segura, y validación estricta de arranque.
- **Backups:** Script diario automatizado `scripts/backup-postgres-r2.sh` que realiza `pg_dump`, comprime y respalda a Cloudflare R2 (`inteliaudit` bucket) con retención de 30 días.
- **Legal:** Actualización de Términos de Uso y Política de Privacidad citando el Secreto Fiscal (Art. 190 Ley 125/91), no cesión de datos y limitación de responsabilidad técnica vs dictamen profesional ante la DNIT.

---

### Task 1: Generador y Validador de Secretos Criptográficos de Producción

**Files:**
- Create: `scripts/generate_production_secrets.py`
- Modify: `api/main.py` (función `_validate_config`)
- Test: `tests/test_production_config_validation.py`

**Pasos:**
- [ ] Escribir test en `tests/test_production_config_validation.py` que verifique que `_validate_config()` lance error o bloquee el arranque en `debug=False` si `SECRET_KEY` es la por defecto o si `ENCRYPTION_KEY` no es una clave Fernet válida.
- [ ] Ejecutar pytest para verificar que el test falla.
- [ ] Crear `scripts/generate_production_secrets.py` que genere un `SECRET_KEY` seguro (64 caracteres hex) y un `ENCRYPTION_KEY` Fernet válido.
- [ ] Ajustar `_validate_config` en `api/main.py` para validar la integridad de `ENCRYPTION_KEY` (usando `Fernet(key)` en un `try/except`).
- [ ] Correr pytest y verificar que pasa al 100%.
- [ ] Commit: `git commit -m "feat(security): add production secret generator and fernet key validation on startup"`

---

### Task 2: Blindaje Legal en Landing y App (Secreto Fiscal Art. 190 y Responsabilidad)

**Files:**
- Modify: `landing/terminos-de-uso.html`
- Modify: `landing/politica-de-privacidad.html`
- Modify: `ui-web/public/landing/terminos-de-uso.html`
- Modify: `ui-web/public/landing/politica-de-privacidad.html`

**Pasos:**
- [ ] Enriquecer `terminos-de-uso.html` y `politica-de-privacidad.html` con las cláusulas regulatorias paraguayas:
  1. **Secreto de las Actuaciones Tributarias (Art. 190 Ley 125/91):** Garantía estricta de confidencialidad, no retención para fines ajenos a la auditoría del usuario, y prohibición de venta o cesión de información financiera.
  2. **Cifrado de Credenciales Marangatú:** Especificación técnica de que las claves de acceso de la SET/DNIT no se almacenan en texto plano, sino cifradas bajo estándar AES en base de datos protegida.
  3. **Delimitación del Dictamen Profesional:** Ratificación expresa de que Inteliaudit es una herramienta analítica de apoyo y que el dictamen impositivo ante la DNIT es responsabilidad indelegable del auditor matriculado.
- [ ] Sincronizar los archivos en `landing/` y `ui-web/public/landing/`.
- [ ] Compilar frontend con `npm run build` en `ui-web` para regenerar `dist/landing/`.
- [ ] Commit: `git commit -m "docs(legal): add Art 190 Ley 125/91 tax secrecy and credential encryption clauses"`

---

### Task 3: Script de Backups Automatizados de PostgreSQL a Cloudflare R2

**Files:**
- Create: `scripts/backup-postgres-r2.sh`
- Create: `scripts/test_backup_r2.py`
- Test: `tests/test_backup_script.py`

**Pasos:**
- [ ] Escribir test unitario que verifique que el módulo de subida a R2 utiliza las credenciales de `config.settings` (`r2_account_id`, `r2_access_key`, `r2_secret_key`, `r2_bucket`) para enviar el dump.
- [ ] Crear `scripts/backup-postgres-r2.sh`:
  - Extraer variables desde el `.env` o environment.
  - Ejecutar `pg_dump` de la base de datos `inteliaudit` en Docker/host.
  - Comprimir con `gzip -9` con nombre fechado `inteliaudit_backup_YYYYMMDD_HHMMSS.sql.gz`.
  - Subir el archivo al bucket R2 en el prefijo `backups/postgres/`.
  - Purgar volcados locales de más de 7 días.
- [ ] Probar la ejecución del script en modo dry-run y verificar que sube exitosamente a R2.
- [ ] Documentar la línea de crontab (`0 3 * * * /home/dev-server/apps/inteliaudit/scripts/backup-postgres-r2.sh`).
- [ ] Commit: `git commit -m "feat(ops): add automated postgres backup to cloudflare r2 script"`

---

### Task 4: Protocolo Operativo de Onboarding para Beta Privada (Runbook B2B)

**Files:**
- Create: `docs/runbooks/onboarding-beta-privada.md`
- Modify: `api/routers/superadmin.py` (agregar botón/campo de copia de credenciales de bienvenida si aplica)

**Pasos:**
- [ ] Crear la guía paso a paso `docs/runbooks/onboarding-beta-privada.md`:
  1. **Recepción del Interés:** Datos mínimos (Razón Social de la firma, RUC, Nombre del Socio/Admin, Email de contacto).
  2. **Alta en SuperAdmin:** Ingreso a `https://inteliaudit.intellihouse.lat/admin/superadmin`, clic en `+ Nueva Firma`, selección del Plan (Starter / Pro / Enterprise) y confirmación.
  3. **Entrega de Credencial:** Plantilla de mensaje de WhatsApp/Email con URL de acceso, usuario y contraseña temporal.
  4. **Primer Login del Cliente:** Flujo donde el cliente cambia su contraseña obligatoriamente y sube su primer cliente con su RG90.
  5. **Monitoreo:** El superadmin revisa la pestaña Sentry-Lite ante cualquier crash.
- [ ] Commit: `git commit -m "docs(ops): create beta privada onboarding runbook for B2B accounting firms"`

---

### Task 5: Despliegue al Dev-Server y Verificación Final de Producción

**Files:**
- Server: `100.72.38.119:/home/dev-server/apps/inteliaudit`

**Pasos:**
- [ ] Ejecutar suite completa de tests (`pytest -v`).
- [ ] Ejecutar `./scripts/deploy-devserver.sh`.
- [ ] Verificar live health check (`/api/health`), Open Graph tags y endpoints de landing (`/landing/terminos-de-uso.html`, `/landing/politica-de-privacidad.html`).
- [ ] Configurar el cron job de backup en el servidor.
