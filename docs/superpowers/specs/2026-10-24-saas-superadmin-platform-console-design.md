# Design Spec — Consola de Operaciones y Plataforma SaaS de Clase Mundial (SuperAdmin)

**Fecha:** 2026-10-24  
**Alcance:** Consola SuperAdmin, Multi-tenant Atómico, Sentry-Lite Error Tracker, Health Vitals & Feature Matrix  
**Autor:** Antigravity AI + Dirección de Ingeniería  

---

## 1. Visión General y Objetivos

Inteliaudit opera como un SaaS multi-tenant para firmas auditoras y contables de Paraguay. Para lograr una gestión de clase mundial, transparente, coherente con las promesas de la landing page y con capacidad de respuesta inmediata ante incidentes técnicos, se diseña la **Consola Maestra de Operaciones y Plataforma**.

### Objetivos Clave:
1. **Alta Atómica de Tenants (Firmas):** Crear una nueva firma con su RUC, plan, período de prueba y su usuario administrador inicial con contraseña temporal visible en un solo paso.
2. **Control Estricto de Planes y Features:** Sincronizar de forma transparente las promesas comerciales de la landing page (Starter, Pro, Enterprise) con el backend, permitiendo personalizaciones/overrides por firma.
3. **Monitor de Errores "Sentry-Lite" Nativo:** Captura y deduplicación automática de excepciones $500$ y fallos en producción con stacktrace completo, contexto de la petición y botón de 1-clic para copiar el reporte formateado para el agente de IA.
4. **Consola de Salud del Sistema (Vitals):** Monitoreo en vivo de los 4 pilares: PostgreSQL, Cloudflare R2, Ollama (Qwen 14B) y SIFEN Cache.
5. **Impersonación Segura ("Login As"):** Capacidad del SuperAdmin de acceder al espacio de trabajo de cualquier tenant para dar soporte técnico directo sin requerir credenciales del cliente.

---

## 2. Modelo de Datos y Esquema

### 2.1. Modificación a `usuarios`
Añadir campo para forzar actualización de credenciales temporales:
- `debe_cambiar_password: bool` (default `False`). Cuando se genera un usuario desde la consola de SuperAdmin, se establece en `True`. Al autenticarse, si es `True`, la UI redirige a un modal de cambio obligatorio.

### 2.2. Modificación a `firmas`
Añadir campo para flexibilizar features por tenant:
- `features_override_json: Optional[str]` (Text, default `None`). Permite sobreescribir capacidades por firma (ej. activar IA a un cliente Starter o ampliar límite de clientes sin cambiar de plan).

### 2.3. Nueva Tabla: `errores_plataforma`
Almacena y deduplica incidentes no controlados:

| Columna | Tipo | Restricciones / Notas |
|---|---|---|
| `id` | `VARCHAR(36)` | PK (UUID v4) |
| `fingerprint` | `VARCHAR(64)` | Indexado (Hash SHA-256 de tipo de error + archivo + línea de fallo) |
| `tipo_error` | `VARCHAR(100)` | Ej: `ValueError`, `IntegrityError`, `KeyError` |
| `mensaje` | `TEXT` | Mensaje descriptivo de la excepción |
| `path` | `VARCHAR(255)` | Ruta HTTP donde ocurrió (ej: `/api/auditorias/...`) |
| `metodo` | `VARCHAR(10)` | Método HTTP (`GET`, `POST`, etc.) |
| `status_code` | `INTEGER` | Código HTTP emitido (por defecto `500`) |
| `stacktrace` | `TEXT` | Traceback completo de Python formateado |
| `contexto_json` | `TEXT` | Headers sanitizados, query params, IP del cliente |
| `firma_id` | `VARCHAR(36)` | Firma donde ocurrió el error (si estaba autenticado) |
| `usuario_email` | `VARCHAR(200)` | Email del usuario afectado |
| `ocurrencias` | `INTEGER` | Contador de veces que ocurrió el mismo fingerprint (default 1) |
| `primera_vez` | `DATETIME` | Timestamp de primera ocurrencia |
| `ultima_vez` | `DATETIME` | Timestamp de última ocurrencia |
| `resuelto` | `BOOLEAN` | Default `False` |
| `resuelto_en` | `DATETIME` | Nullable |
| `notas_resolucion` | `TEXT` | Nullable |

---

## 3. Arquitectura del Backend

### 3.1. Middleware de Telemetría y Errores ASGI (`api/middleware/error_tracker.py`)
- Intercepta excepciones en tiempo de ejecución.
- Si la excepción no fue capturada por la aplicación:
  1. Extrae `traceback.format_exc()`.
  2. Extrae el frame de código raíz.
  3. Genera el `fingerprint` determinista.
  4. En una sesión de base de datos aislada, busca si ya existe un `ErrorPlataforma` no resuelto con ese `fingerprint`.
     - Si existe: incrementa `ocurrencias` y actualiza `ultima_vez`.
     - Si no existe: crea nuevo registro.
  5. Devuelve al usuario un JSON estandarizado:
     ```json
     {
       "detail": "Error interno del servidor",
       "error_ref": "err_f8a92b3c",
       "mensaje": "El incidente ha sido registrado en la consola de soporte."
     }
     ```

### 3.2. Endpoints de la API SuperAdmin (`api/routers/superadmin.py`)

1. **Gestión de Tenants:**
   - `GET /api/superadmin/firmas`: Lista firmas con conteo de clientes, usuarios, plan y estado.
   - `POST /api/superadmin/firmas`: Alta atómica de firma + usuario admin inicial + contraseña temporal generada.
   - `PATCH /api/superadmin/firmas/{id}`: Actualización de plan, vigencia, features override y estado activo/inactivo.
   - `POST /api/superadmin/firmas/{id}/impersonate`: Genera JWT temporal para operar como la firma.

2. **Gestión de Usuarios Globales:**
   - `GET /api/superadmin/usuarios`: Lista todos los usuarios con su firma y último acceso.
   - `POST /api/superadmin/usuarios`: Alta de usuario en cualquier firma con validación de límites.
   - `PATCH /api/superadmin/usuarios/{id}`: Actualiza datos básicos y rol.
   - `PATCH /api/superadmin/usuarios/{id}/password`: Resetea contraseña.

3. **Monitor Sentry-Lite:**
   - `GET /api/superadmin/errores`: Listado paginado de errores con filtros (`resuelto=false`, búsqueda de texto).
   - `GET /api/superadmin/errores/{id}`: Detalle completo del stacktrace y contexto.
   - `POST /api/superadmin/errores/{id}/resolver`: Marca el error como resuelto.

4. **Salud del Sistema (Vitals):**
   - `GET /api/superadmin/vitals`:
     - **DB:** Ping a PostgreSQL y latencia en ms.
     - **Storage:** Prueba R2 / Cloudflare.
     - **AI Engine:** Ping a `http://localhost:11434/api/tags` verificando `inteliaudit-forense` / Qwen 14B.
     - **SIFEN:** Conteo de comprobantes en `sifen_cache`.
     - **Host:** Uptime, memoria libre y carga CPU.

---

## 4. Consola de Usuario en Frontend (`SuperAdminDashboard.tsx`)

La interfaz se estructura en 4 pestañas de clase mundial:

1. **Pestaña `🏢 Tenants & Firmas`:**
   - Métricas clave: MRR Estimado (Gs.), Firmas Activas, Firmas en Trial, Clientes Totales.
   - Botón destacado **"+ Nueva Firma / Tenant"**:
     - Modal con campos: Nombre del Estudio, RUC, Plan (Starter / Pro / Enterprise / Trial), Días de Trial, Email Admin y Nombre Admin.
     - Pantalla de éxito con tarjeta de credenciales: Email, Contraseña Temporal generada y botón "Copiar Credenciales".
   - Botón **"Ingresar como Firma" (Impersonación)** para soporte en vivo.
   - Switches de activación de features individuales.

2. **Pestaña `👥 Usuarios del Sistema`:**
   - Búsqueda en vivo por nombre, email o firma.
   - Botón **"+ Nuevo Usuario"** con selector de firma y rol (`admin`, `auditor_senior`, `auditor`).
   - Acciones: Reset de contraseña, Bloqueo de acceso, Edición de rol.

3. **Pestaña `⚡ Errores de Plataforma (Sentry-Lite)`:**
   - Tabla de incidentes con badges de severidad (Crítico / 500), método, ruta y contador de ocurrencias (ej: `× 42`).
   - Visor expandible del Stacktrace con tipografía monoespaciada oscura.
   - Botón **`[📋 Copiar Reporte para Agente AI]`**: copia al portapapeles un prompt estructurado en Markdown listo para resolver el bug.
   - Botón **`[✓ Resolver]`**.

4. **Pestaña `🩺 Salud del Sistema (Vitals)`:**
   - Tarjetas de estado con latencia y estado visual (🟢 Online / 🟡 Degradado / 🔴 Inactivo):
     - PostgreSQL Database.
     - Cloudflare R2 Storage.
     - Motor Forense Qwen 14B (Ollama).
     - SIFEN Cache Global.

---

## 5. Estrategia de Pruebas y Validación (TDD)

1. **Tests Backend:**
   - `tests/test_superadmin_tenants.py`: Creación atómica de firma con contraseña temporal y hash correcto.
   - `tests/test_superadmin_features.py`: Validación de límites de clientes y usuarios según plan.
   - `tests/test_error_tracker.py`: Middleware de captura, cálculo de fingerprint y deduplicación de incidentes.
   - `tests/test_superadmin_vitals.py`: Endpoint de diagnóstico de salud.
2. **Build de Frontend:**
   - Verificación con `npm run build` garantizando 0 errores en tipos y componentes.
3. **Despliegue y Validación en Vivo:**
   - Migración Alembic en PostgreSQL (`add_error_plataforma_table`).
   - Despliegue en `100.72.38.119`.
   - Verificación en vivo en `https://inteliaudit.intellihouse.lat/admin/superadmin`.
