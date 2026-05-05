# Inteliaudit — Contexto maestro para Claude Code

## Qué es este proyecto

**Inteliaudit** es un SaaS de automatización completa de auditoría impositiva para el mercado paraguayo,
parte del ecosistema **Intelihouse**. Automatiza el trabajo del auditor impositivo desde la descarga
de datos en Marangatú hasta la generación de informes finales firmables.

**Principio de diseño central:**
Marangatú es la única fuente de verdad. Todo análisis parte de lo efectivamente presentado ante la SET.
Las demás fuentes (SIFEN, HECHAUKA, contabilidad, banco) se usan solo para contrastar.

---

## Stack tecnológico

```
Python 3.12
Playwright          → scraping Marangatú (no hay API pública)
SQLite / PostgreSQL → base de datos local por cliente/período
pdfplumber          → extracción texto de PDFs SET
openpyxl            → lectura archivos XLSX (RG90, HECHAUKA)
lxml / xmltodict    → parseo XML e-Kuatia (CDC)
Jinja2              → templates de reportes HTML
python-docx         → generación informes Word
WeasyPrint          → conversión HTML→PDF
anthropic           → Claude API para análisis inteligente
click               → CLI principal
rich                → output de terminal
```

---

## Marco legal vigente — Paraguay

### Leyes principales
- **Ley 6380/2019** — Modernización tributaria. Crea IRE, IRP, IDU, IRNR. Vigente desde 2020.
- **Ley 125/1991** y sus modificaciones — Código tributario base
- **Decreto 3107/2019** — Reglamentación del IRE
- **Decreto 3181/2019** — Reglamentación del IVA bajo Ley 6380
- **Ley 1034/1983** — Código Mercantil (registros contables)

### Resoluciones Generales SET clave
- **RG 24/2014** — Comprobantes de venta autorizados (pre-electrónicos)
- **RG 69/2020** — Implementación factura electrónica (e-Kuatia)
- **RG 80/2021** — Obligatoriedad e-Kuatia por tramos
- **RG 90/2021** — Detalle de comprobantes en declaración IVA (el "libro digital de IVA")
- **RG 108/2021** — Calendario de obligados a e-Kuatia

### Calendario tributario (vencimientos habituales)
- IVA (Form. 120): vence el mes siguiente según último dígito RUC
- IRE (Form. 500): vence en abril del año siguiente al ejercicio
- Retenciones (Forms. 800-830): vence el mes siguiente a la retención
- IRP (Form. 510): vence en marzo del año siguiente
- IDU (Form. 530): vence junto con IRE o en distribución

---

## Impuestos y formularios SET

### IVA — Impuesto al Valor Agregado
**Formulario:** 120
**Alícuotas Ley 6380:**
- 10% — operaciones generales (bienes y servicios)
- 5%  — bienes de la canasta básica familiar, servicios personales (médicos, educación), cesión de derechos
- 0%  — exportaciones (tasa cero, con derecho a crédito)
- Exento — algunos bienes expresamente listados en Ley 6380 Art. 100

**Cálculo IVA:**
```
Débito fiscal = suma IVA incluido en facturas emitidas del período
Crédito fiscal = suma IVA incluido en facturas recibidas del período
IVA a pagar = Débito fiscal - Crédito fiscal
Saldo a favor = Crédito fiscal - Débito fiscal (trasladable)
```

**Proporcionalidad del crédito fiscal:**
Si el contribuyente tiene operaciones gravadas Y exentas/no gravadas,
el crédito fiscal se prorratea: CF_admitido = CF_total × (ventas_gravadas / ventas_totales)

**RG 90 — Detalle de comprobantes:**
El contribuyente debe declarar comprobante por comprobante en su DJ IVA:
- RUC del emisor/receptor
- Número de comprobante
- CDC (si es electrónico)
- Fecha
- Monto gravado 10%, monto gravado 5%, monto exento
- IVA discriminado

**Hallazgos típicos IVA:**
1. Crédito fiscal con comprobantes de RUC inactivo o cancelado
2. Crédito fiscal con comprobantes sin CDC en SIFEN (posibles apócrifos)
3. Comprobantes electrónicos recibidos en SIFEN no declarados en RG90
4. Diferencia entre total RG90 y total Form. 120
5. Crédito fiscal de comprobantes de períodos anteriores fuera del plazo (prescripción 5 años)
6. Autoconsumo no facturado
7. Notas de crédito recibidas no descontadas del crédito
8. Exportaciones sin respaldo de DUA

---

### IRE — Impuesto a la Renta Empresarial
**Formulario:** 500
**Alícuota:** 10% sobre renta neta (Ley 6380 Art. 17)
**Ejercicio fiscal:** 1 enero al 31 diciembre
**Vencimiento DJ:** abril del año siguiente

**Base imponible:**
```
Renta bruta
- Costos y gastos deducibles
= Renta neta imponible × 10%
```

**Gastos NO deducibles (Ley 6380 Art. 16):**
- Multas, recargos e intereses pagados a SET
- Gastos personales del dueño/socios
- Retiros de socios
- Donaciones que superen el 1% de la renta bruta
- Gastos sin comprobante legal vigente
- Depreciaciones que superen tasas máximas reglamentarias
- Intereses a partes vinculadas que excedan tasa LIBOR + 3%
- Gastos de representación que superen el 1% de ingresos brutos

**Tasas de depreciación máximas (Decreto 3107):**
```
Inmuebles:          2.5% anual (40 años)
Maquinaria:         10%  anual (10 años)
Vehículos:          20%  anual (5 años)
Equipos informáticos: 33.3% anual (3 años)
Muebles y útiles:   10%  anual (10 años)
Instalaciones:      10%  anual (10 años)
```

**Partes vinculadas (Art. 35 Ley 6380):**
Obligación de precio de mercado (arm's length) en operaciones entre:
- Empresa y sus socios/accionistas con participación ≥ 50%
- Empresas del mismo grupo económico
- Empresa y sus directores/administradores

**Hallazgos típicos IRE:**
1. Gastos sin comprobante legal o con comprobante de RUC inactivo
2. Depreciaciones que superan tasas máximas
3. Gastos personales cargados como gastos de empresa
4. Diferencia entre resultado contable y base imponible declarada
5. Operaciones con vinculadas sin justificación de precio de mercado
6. Ingresos no declarados detectados por cruce bancario
7. Ventas de activos fijos no incluidas en renta
8. Dividendos distribuidos sin retención IDU

---

### Retenciones
**Formularios:** 800 al 830 según tipo

| Formulario | Concepto |
|-----------|---------|
| 800 | Retenciones IVA a contribuyentes del régimen general |
| 810 | Retenciones IVA a contribuyentes del régimen simplificado |
| 820 | Retenciones IRE a contribuyentes del régimen general |
| 830 | Retenciones IVA e IRE a contribuyentes pequeños |

**Tasas de retención principales:**
```
IVA sobre servicios personales:     30% del IVA (3% sobre precio)
IVA sobre compras a contrib. normal: 30% del IVA (3% sobre precio) — agentes designados
IRE sobre honorarios/servicios:     hasta 3% sobre importe bruto
Retención a pequeños contrib.:      30% IVA + 2.5% IRE sobre importe
```

**Agentes de retención obligatorios:**
- Organismos del Estado
- Empresas designadas por SET como agentes (lista en Marangatú)
- Cualquier contribuyente al contratar servicios personales

**Hallazgos típicos retenciones:**
1. Pago a proveedores sin practicar retención cuando correspondía
2. Retención practicada pero no declarada ni depositada a SET
3. Diferencia entre retenciones declaradas por agente vs retenciones recibidas según HECHAUKA
4. Retención sobre importes incorrectos (base de cálculo errónea)
5. Pagos fuera de plazo (multa automática: 0.1% por día hasta 20%)

---

### IDU — Impuesto a los Dividendos y Utilidades
**Formulario:** 530
**Alícuota:** 8% sobre dividendos distribuidos a residentes
           15% sobre dividendos distribuidos a no residentes
**Hecho generador:** distribución efectiva de utilidades a socios/accionistas

---

### IRP — Impuesto a la Renta Personal
**Formulario:** 510
**Alícuota:** 8% hasta 10 salarios mínimos de renta neta / 10% sobre excedente
**Contribuyentes:** personas físicas con ingresos > 36 salarios mínimos anuales

---

### IRNR — Impuesto a la Renta de No Residentes
**Formulario:** 520
**Alícuota:** 15% general sobre renta de fuente paraguaya

---

## Sistemas SET — cómo acceder

### Marangatú (portal principal)
**URL:** https://marangatu.set.gov.py
**Autenticación:** RUC + Clave de acceso SET
**Acceso técnico:** Playwright (no hay API). Login simulado, navegación por menús.

**Secciones relevantes para auditoría:**
```
Inicio > Mis Obligaciones          → obligaciones activas del contribuyente
Declaraciones > Mis Declaraciones  → lista todas las DJ presentadas con estado
Declaraciones > RG 90              → detalle comprobantes IVA (compras y ventas)
Estado de Cuenta                   → saldos, deuda, créditos, pagos
Datos del Contribuyente            → nombre, dirección, actividad, socios
HECHAUKA > Información Recibida    → lo que terceros declararon sobre este RUC
```

**Formatos de descarga:**
- Declaraciones juradas: PDF + datos parseables
- RG 90: XLSX (columnas fijas por resolución)
- HECHAUKA: XLSX
- Estado de cuenta: PDF

### SIFEN (facturación electrónica)
**URL:** https://sifen.set.gov.py
**Consulta pública de CDC:** https://ekuatia.set.gov.py/consultas/rest/faces/pages/main.xhtml
**Formato:** XML con estructura definida en RG 69/2020
**CDC:** Código de Control — hash SHA256 de 44 dígitos que identifica cada comprobante electrónico

**Estructura XML e-Kuatia mínima:**
```xml
<DE>
  <gTimb>
    <dTiDE>1</dTiDE>        <!-- Tipo: 1=Factura, 4=Autofactura, 5=NC, 6=ND, 7=Remisión -->
    <dNumTim>...</dNumTim>  <!-- Número de timbrado -->
    <dEst>001</dEst>        <!-- Establecimiento -->
    <dPunExp>001</dPunExp>  <!-- Punto de expedición -->
    <dNumDoc>0000001</dNumDoc><!-- Número de comprobante -->
    <dFeIniT>2024-01-01</dFeIniT>
  </gTimb>
  <gDatGralOpe>
    <dFeEmiDE>2024-03-15T10:30:00</dFeEmiDE>
    <gDatRec>
      <dRucRec>80012345-6</dRucRec>
      <dNomRec>EMPRESA SA</dNomRec>
    </gDatRec>
  </gDatGralOpe>
  <gTotSub>
    <dTotGravOp10>1000000</dTotGravOp10>  <!-- Base gravada 10% -->
    <dTotGravOp5>0</dTotGravOp5>           <!-- Base gravada 5% -->
    <dTotExe>0</dTotExe>                   <!-- Exento -->
    <dTotIVA>100000</dTotIVA>             <!-- IVA total -->
    <dTotGe>1100000</dTotGe>              <!-- Total comprobante -->
  </gTotSub>
  <Id>CDC_44_DIGITOS_AQUI</Id>
</DE>
```

---

## Estructura del proyecto

```
inteliaudit/
├── claude.md                    ← ESTE ARCHIVO (contexto permanente)
├── config/
│   └── cliente.yaml             ← RUC, período, impuestos en alcance, materialidad
├── ingesta/
│   ├── marangatu.py             ← Playwright scraper (descarga todo de Marangatú)
│   ├── sifen.py                 ← Parser XML e-Kuatia / consulta CDC
│   └── parser_rg90.py           ← Parser XLSX RG90 (compras y ventas)
├── analisis/
│   ├── iva.py                   ← Procedimientos IVA (cruce RG90 vs SIFEN vs HECHAUKA)
│   ├── ire.py                   ← Procedimientos IRE (conciliación contable-fiscal)
│   ├── retenciones.py           ← Procedimientos retenciones (cruce HECHAUKA)
│   ├── riesgo.py                ← Scoring, cuantificación ajustes, multas e intereses
│   └── claude_analisis.py       ← Análisis inteligente vía Claude API
├── papeles/
│   ├── cedulas.py               ← Generador cédulas analíticas
│   └── hallazgos.py             ← Registro hallazgos con evidencia
├── informes/
│   ├── templates/               ← Jinja2: informe auditoría, nota hallazgos, carta gerencia
│   └── render.py                ← Genera Word + PDF finales
├── db/
│   ├── schema.sql               ← Modelo de datos completo
│   └── db.py                    ← Capa de acceso a datos
├── ui/
│   └── dashboard/               ← Dashboard web (identidad visual Inteliaudit)
└── main.py                      ← CLI orquestador principal
```

---

## Modelo de datos (resumen)

```sql
-- Tablas principales
clientes          (ruc, razon_social, actividad, regimen, obligaciones_activas[])
periodos          (cliente_ruc, periodo, impuesto, estado_presentacion)
declaraciones     (id, cliente_ruc, formulario, periodo, fecha_presentacion, datos_json)
comprobantes_rg90 (id, cliente_ruc, periodo, tipo[compra/venta], ruc_contraparte,
                   nro_comprobante, cdc, fecha, base10, base5, exento, iva, fuente)
comprobantes_sifen(id, cdc, tipo_de, ruc_emisor, ruc_receptor, fecha, base10, base5,
                   exento, iva_total, total, estado_validez)
hechauka          (id, cliente_ruc, periodo, ruc_informante, tipo_operacion,
                   monto, retencion, fecha_declaracion_tercero)
hallazgos         (id, auditoria_id, impuesto, tipo_hallazgo, descripcion,
                   articulo_legal, evidencia_refs[], monto_ajuste,
                   multa_estimada, intereses_estimados, nivel_riesgo)
auditorias        (id, cliente_ruc, periodo_desde, periodo_hasta,
                   fecha_inicio, fecha_cierre, estado, auditor)
```

---

## Procedimientos de auditoría — lógica de negocio

### Cruce central IVA
```python
# Orden de ejecución obligatorio:
# 1. Descargar Form. 120 presentados de Marangatú
# 2. Descargar RG90 presentadas de Marangatú
# 3. Consultar SIFEN para validar CDCs de RG90
# 4. Descargar HECHAUKA recibido
# 5. Ejecutar cruces

def auditoria_iva(periodo):
    # Cruce 1: RG90 vs Form.120
    # ¿Los totales de RG90 cuadran con lo declarado en Form.120?
    
    # Cruce 2: RG90 compras vs SIFEN
    # ¿Cada comprobante con CDC en RG90 existe y es válido en SIFEN?
    # ¿Algún comprobante en RG90 no tiene CDC pero debería tenerlo?
    
    # Cruce 3: SIFEN recibidas vs RG90 compras
    # ¿Hay facturas electrónicas recibidas que NO están en RG90? (crédito omitido)
    
    # Cruce 4: RG90 ventas vs HECHAUKA
    # ¿Lo que los compradores declararon haberle comprado
    #  está en la RG90 ventas? (débito omitido)
    
    # Cruce 5: RUC de proveedores en RG90
    # ¿Algún proveedor tiene RUC inactivo/cancelado? (crédito inválido)
```

### Cuantificación de ajustes
```python
# Multas según Art. 175 Ley 125/1991
MULTA_OMISION_SIMPLE = 0.50   # 50% del impuesto omitido
MULTA_CONTUMACIA     = 1.00   # 100% si es reincidente

# Intereses moratorios
TASA_INTERES_MENSUAL = 0.01   # 1% mensual (verificar tasa vigente SET)

def calcular_contingencia(impuesto_omitido, fecha_omision, fecha_calculo):
    meses = diferencia_meses(fecha_omision, fecha_calculo)
    multa = impuesto_omitido * MULTA_OMISION_SIMPLE
    intereses = impuesto_omitido * TASA_INTERES_MENSUAL * meses
    return {
        "impuesto": impuesto_omitido,
        "multa": multa,
        "intereses": intereses,
        "total_contingencia": impuesto_omitido + multa + intereses
    }
```

---

## Identidad visual Inteliaudit

**Paleta:**
- Azul principal:   #2E84F0 / #1558B0 (gradiente — texto "Inteli", botones primarios)
- Verde audit:      #22C47E / #169058 (gradiente — texto "audit", éxito, hallazgos OK)
- Navy oscuro:      #091624 (fondos oscuros, sidebar)
- Gris texto:       #A8B4C8 (labels, secundario)
- Border:           #E4EAF4
- Background:       #F5F7FB (fondo general), #FFFFFF (cards)

**Tipografía:**
- Display/headings: Helvetica Neue Bold (700)
- Body: Helvetica Neue Regular (400)
- Datos/tablas: font-mono

**Logo:** isotipo squircle azul + lente magnifying glass + checkmark verde + punto verde "i"
Wordmark: `<span blue bold>Inteli</span><span green light>audit</span>`

**Niveles de riesgo (colores consistentes en toda la UI):**
- Alto:   #E53E3E (rojo)
- Medio:  #D97706 (ámbar)
- Bajo:   #22C47E (verde)
- Info:   #2E84F0 (azul)

---

## Reglas para Claude Code

1. **Siempre importar desde Marangatú** — nunca asumir datos del sistema contable del cliente
2. **Validar RUC** antes de cualquier análisis: dígito verificador + estado activo en SET
3. **Loggear toda decisión** en el trail de auditoría con timestamp
4. **No borrar datos crudos** — los archivos descargados de Marangatú se archivan siempre
5. **Citar el artículo legal** en cada hallazgo generado
6. **Montos siempre en Guaraníes** (PYG), sin decimales (la moneda paraguaya no usa centavos)
7. **Períodos en formato YYYY-MM** (ej: 2024-03 para marzo 2024)
8. **Formularios sin guiones** (ej: "120", "500", "800") al referenciarlos en código
9. **Toda la UI en español** — el producto es exclusivamente para el mercado paraguayo
10. **Identidad visual Inteliaudit** en todos los componentes UI (paleta y tipografía definidas arriba)
