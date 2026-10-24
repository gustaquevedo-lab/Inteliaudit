# Especificación de Diseño: Sub-sistema de Ingesta Directa DNIT (SIFEN + Marangatú REA)

**Fecha:** 2026-10-24  
**Estado:** Aprobado  
**Objetivo:** Reemplazar la automatización por navegador (Playwright) por un sub-sistema de ingesta directa vía HTTP (Reverse Engineering API de Marangatú) y verificación de comprobantes electrónicos SIFEN con persistencia en caché, maximizando la velocidad de auditoría (< 1s por lote) y reduciendo el consumo de memoria en el dev-server a cero sobrecarga de Chromium.

---

## 1. Contexto y Justificación del Negocio

En la promesa comercial de Inteliaudit ("Auditoría impositiva que se hace sola", cruce RG 90 × SIFEN × HECHAUKA), la dependencia de un navegador headless virtual (Chromium) genera tres puntos de fricción:
1. **Lentitud:** Iniciar un navegador y esperar renderizados de DOM toma entre 45 y 120 segundos.
2. **Consumo de recursos:** Cada sesión de Chromium consume ~500 MB de RAM en el servidor.
3. **Fragilidad ante cambios de UI:** Cambios menores en la maquetación web de la DNIT rompen selectores CSS.

Dado que el portal moderno de Marangatú es una Single Page Application (SPA) que interactúa con endpoints REST/JSON internos, y que SIFEN cuenta con servicios web y endpoints de consulta para Códigos de Control (CDC), este diseño implementa un **cliente HTTP asíncrono nativo (`httpx`)** que interactúa directamente a nivel de protocolo, complementado con un **Bookmarklet conector de 1-clic** para el auditor.

---

## 2. Arquitectura del Sub-sistema

```
┌────────────────────────────────────────────────────────┐
│                      AUDITOR                           │
│  [Opción A: Bookmarklet 1-Clic en Marangatú]            │
│  [Opción B: Pega Cookie/Token en pestaña Automatización]│
└──────────────────────────┬─────────────────────────────┘
                           │ POST /api/auditorias/{id}/marangatu/sync
                           ▼
┌────────────────────────────────────────────────────────┐
│           CLIENTE HTTP MARANGATÚ (REA)                 │
│  • Petición directa a endpoints internos de la DNIT   │
│  • Consulta talones RG 90 (compras y ventas)          │
│  • Descarga el payload / Excel en ~300ms               │
│  • Ingesta inmediata en `rg90_registros`               │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│            VERIFICADOR SIFEN (Asíncrono)               │
│  1. Validación instantánea: CDC 44 dígitos + Módulo 11 │
│  2. Consulta en segundo plano a Web Service DNIT       │
│  3. Tabla `sifen_cache`: CDC, estado, RUC emisor, IVA  │
│  4. Si SIFEN rechaza o no existe → Genera Hallazgo      │
└────────────────────────────────────────────────────────┘
```

---

## 3. Modelo de Datos & Persistencia de Caché

### Tabla `sifen_cache`
Almacena el resultado de validación de cada CDC consultado para evitar peticiones redundantes entre distintas auditorías de la misma o diferentes firmas:

```python
class SifenCache(Base):
    __tablename__ = "sifen_cache"

    cdc = Column(String(44), primary_key=True, index=True)
    estado_sifen = Column(String(50), nullable=False)  # 'APROBADO', 'NO_EXISTE', 'RECHAZADO', 'CANCELADO'
    ruc_emisor = Column(String(20), nullable=True, index=True)
    razon_social = Column(String(200), nullable=True)
    timbrado = Column(String(20), nullable=True)
    fecha_emision = Column(DateTime, nullable=True)
    total_comprobante = Column(Numeric(18, 2), nullable=True)
    iva_10 = Column(Numeric(18, 2), nullable=True)
    iva_5 = Column(Numeric(18, 2), nullable=True)
    es_valido = Column(Boolean, default=True, nullable=False)
    respuesta_raw = Column(JSON, nullable=True)
    consultado_en = Column(DateTime, default=func.now(), nullable=False)
```

---

## 4. Componentes Backend

### 4.1. Validador y Cliente SIFEN (`ingesta/sifen_client.py`)
- **Algoritmo Módulo 11:** Valida instantáneamente si el dígito verificador del CDC de 44 dígitos coincide con el peso ponderado oficial de la DNIT (base 2 a 11).
- **Extracción de Metadatos del CDC:**
  - Posición 1-2: Tipo de comprobante (ej: 01 = Factura electrónica, 04 = Autofactura, 05 = Nota de crédito).
  - Posición 3-10: RUC del emisor.
  - Posición 11: Dígito verificador del RUC.
  - Posición 12-14: Tipo de contribuyente.
  - Posición 15-21: Código de establecimiento y punto de expedición.
  - Posición 22-28: Número de comprobante.
  - Posición 29-36: Timbrado.
  - Posición 37-43: Código de seguridad aleatorio.
  - Posición 44: Dígito verificador general del CDC.
- **Consulta HTTP en Background:** Concurrencia controlada (`asyncio.Semaphore(5)`) con fallback a cache local.

### 4.2. Cliente HTTP Marangatú (`ingesta/marangatu_http.py`)
- Simula cabeceras de navegación estándar:
  - `User-Agent: Mozilla/5.0 ...`
  - `Referer: https://marangatu.dnit.gov.py/`
  - `Accept: application/json, text/plain, */*`
- Métodos:
  - `verificar_conexion_sesion(cookie: str) -> dict`: retorna `{ "valida": True, "ruc": "...", "nombre": "..." }`.
  - `obtener_talones_declarados(cookie: str, ruc: str, periodo: str) -> list[dict]`: lista los talones de presentación de compras y ventas de la RG 90.
  - `descargar_talon_rg90(cookie: str, id_talon: str) -> bytes`: obtiene el archivo oficial de detalle de comprobantes.

### 4.3. Rutas de API (`api/routers/marangatu_sync.py`)
- `POST /api/auditorias/{id}/marangatu/verificar`: valida el token/cookie provisto.
- `POST /api/auditorias/{id}/marangatu/sync`: sincroniza automáticamente los comprobantes del período seleccionado, los inserta en `rg90_registros` e invoca la auditoría.
- `GET /api/sifen/verificar-cdc/{cdc}`: consulta o valida el estado de un CDC puntual.

---

## 5. Experiencia de Usuario & Frontend

### 5.1. Pestaña de Automatización (`TabAutomatizacion.tsx`)
1. **Conector Rápido (Bookmarklet):**
   - Enlace arrastrable que contiene el JavaScript empaquetado:
     ```javascript
     javascript:(function(){
       /* Extrae cookie/token y redirige a la auditoria de Inteliaudit */
     })();
     ```
2. **Conexión Directa por Sesión:**
   - Campo para pegar el valor de `JSESSIONID` o token.
   - Selector de período (ej. `2024-03`) y tipo (`Compras`, `Ventas` o `Ambos`).
   - Botón *"Sincronizar y Auditar Lote"*.

### 5.2. Visualización en `EvidenceExplorer.tsx` y `TabArchivos.tsx`
- Indicador visual sobre cada factura electrónica con CDC:
  - Badge verde: `SIFEN: APROBADO`
  - Badge rojo: `SIFEN: NO REGISTRADO / CDC INVÁLIDO`
  - Badge gris: `Factura Tradicional (Pre-impresa)`

---

## 6. Plan de Pruebas y Validación

1. **Test del Validador SIFEN:** Comprobar CDCs válidos con algoritmo Módulo 11 y CDCs alterados o truncados.
2. **Test de Caché SIFEN:** Comprobar que una segunda consulta al mismo CDC no realiza llamadas HTTP externas.
3. **Test del Parser/Cliente Marangatú:** Probar respuestas mock de la API interna y extracción correcta de registros RG 90.
4. **Verificación en Dev-Server:** Desplegar y probar los endpoints vía curl y en el frontend.
