"""
Generador de informe PDF profesional — Inteliaudit.
Usa Jinja2 para el template HTML y WeasyPrint para la conversión a PDF.
"""
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Optional

from analisis.riesgo import formatear_pyg, resumir_contingencias

# ============================================================
#  Template HTML inline (sin archivos externos, portable)
# ============================================================

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<style>
  @page {
    size: A4;
    margin: 2cm 2cm 2.5cm 2cm;
    @bottom-center {
      content: "Inteliaudit — Informe Confidencial — Página " counter(page) " de " counter(pages);
      font-size: 8pt;
      color: #A8B4C8;
    }
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 10pt;
    color: #1a2332;
    line-height: 1.5;
  }

  /* ---- PORTADA ---- */
  .portada {
    height: 100vh;
    display: flex;
    flex-direction: column;
    justify-content: center;
    background: linear-gradient(135deg, #091624 0%, #1558B0 100%);
    color: white;
    padding: 3cm;
    page-break-after: always;
  }
  .portada .logo-text {
    font-size: 36pt;
    font-weight: 900;
    letter-spacing: -1px;
    margin-bottom: 0.5cm;
  }
  .portada .logo-text .green { color: #22C47E; }
  .portada .logo-text .blue { color: #2E84F0; }
  .portada h1 {
    font-size: 20pt;
    font-weight: 700;
    margin-bottom: 0.3cm;
    color: white;
  }
  .portada .meta {
    font-size: 11pt;
    opacity: 0.8;
    margin-bottom: 0.2cm;
  }
  .portada .confidencial {
    margin-top: 1.5cm;
    padding: 0.4cm 0.8cm;
    border: 1px solid rgba(255,255,255,0.3);
    display: inline-block;
    font-size: 8pt;
    font-weight: 700;
    letter-spacing: 3px;
    text-transform: uppercase;
    width: fit-content;
  }

  /* ---- ENCABEZADOS ---- */
  h2 {
    font-size: 14pt;
    font-weight: 900;
    color: #1558B0;
    border-bottom: 2px solid #2E84F0;
    padding-bottom: 0.3cm;
    margin: 0.8cm 0 0.4cm 0;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  h3 {
    font-size: 11pt;
    font-weight: 700;
    color: #091624;
    margin: 0.5cm 0 0.2cm 0;
  }

  /* ---- SECCIONES ---- */
  .section { margin-bottom: 0.8cm; }
  .page-break { page-break-before: always; }

  /* ---- INFO BOX ---- */
  .info-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.3cm;
    margin: 0.4cm 0;
  }
  .info-item {
    background: #F5F7FB;
    border: 1px solid #E4EAF4;
    border-radius: 6px;
    padding: 0.3cm 0.4cm;
  }
  .info-label {
    font-size: 7pt;
    font-weight: 700;
    color: #A8B4C8;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 0.1cm;
  }
  .info-value {
    font-size: 10pt;
    font-weight: 600;
    color: #091624;
  }

  /* ---- RESUMEN KPIs ---- */
  .kpi-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.4cm;
    margin: 0.5cm 0;
  }
  .kpi-card {
    border-radius: 8px;
    padding: 0.4cm;
    text-align: center;
  }
  .kpi-card.primary {
    background: linear-gradient(135deg, #2E84F0, #1558B0);
    color: white;
  }
  .kpi-card.danger { background: #FEF2F2; border: 1px solid #FECACA; }
  .kpi-card.warning { background: #FFFBEB; border: 1px solid #FDE68A; }
  .kpi-card.success { background: #F0FDF4; border: 1px solid #BBF7D0; }
  .kpi-label { font-size: 7pt; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; opacity: 0.7; margin-bottom: 0.15cm; }
  .kpi-value { font-size: 16pt; font-weight: 900; }
  .kpi-card.primary .kpi-label { color: rgba(255,255,255,0.8); }
  .kpi-card.primary .kpi-value { color: white; }
  .kpi-card.danger .kpi-value { color: #DC2626; }
  .kpi-card.warning .kpi-value { color: #D97706; }
  .kpi-card.success .kpi-value { color: #16A34A; }

  /* ---- TABLA HALLAZGOS ---- */
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 0.4cm 0;
    font-size: 9pt;
  }
  thead tr {
    background: #091624;
    color: white;
  }
  thead th {
    padding: 0.25cm 0.3cm;
    text-align: left;
    font-size: 7.5pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  tbody tr:nth-child(even) { background: #F5F7FB; }
  tbody td {
    padding: 0.2cm 0.3cm;
    border-bottom: 1px solid #E4EAF4;
    vertical-align: top;
  }
  .badge {
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 7pt;
    font-weight: 700;
    text-transform: uppercase;
  }
  .badge-alto { background: #FEE2E2; color: #DC2626; }
  .badge-medio { background: #FEF3C7; color: #D97706; }
  .badge-bajo { background: #D1FAE5; color: #059669; }

  /* ---- HALLAZGO DETALLE ---- */
  .hallazgo-card {
    border: 1px solid #E4EAF4;
    border-radius: 8px;
    margin-bottom: 0.6cm;
    overflow: hidden;
  }
  .hallazgo-header {
    padding: 0.3cm 0.4cm;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .hallazgo-alto .hallazgo-header { background: #FEF2F2; border-left: 4px solid #DC2626; }
  .hallazgo-medio .hallazgo-header { background: #FFFBEB; border-left: 4px solid #D97706; }
  .hallazgo-bajo .hallazgo-header { background: #F0FDF4; border-left: 4px solid #22C47E; }
  .hallazgo-body { padding: 0.4cm; }
  .hallazgo-title { font-size: 10pt; font-weight: 700; }
  .hallazgo-ref { font-size: 7.5pt; color: #A8B4C8; font-family: monospace; }
  .hallazgo-desc { font-size: 9pt; color: #4B5563; margin: 0.2cm 0; }
  .hallazgo-legal {
    background: #FFFBEB;
    border: 1px solid #FDE68A;
    border-radius: 6px;
    padding: 0.2cm 0.3cm;
    font-size: 8.5pt;
    font-style: italic;
    color: #92400E;
    margin: 0.2cm 0;
  }
  .contingencia-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 0.2cm;
    font-size: 9pt;
  }
  .contingencia-table td { padding: 0.15cm 0; border-bottom: 1px solid #F0F0F0; }
  .contingencia-table td:last-child { text-align: right; font-weight: 600; }
  .contingencia-total { font-weight: 900; color: #1558B0; font-size: 10pt; }

  /* ---- FIRMA ---- */
  .firma-section {
    margin-top: 2cm;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 2cm;
  }
  .firma-line {
    border-top: 1px solid #A8B4C8;
    padding-top: 0.2cm;
    font-size: 9pt;
    color: #6B7280;
    text-align: center;
  }

  /* ---- FOOTER ---- */
  .footer-disclaimer {
    margin-top: 1cm;
    padding: 0.4cm;
    background: #F5F7FB;
    border-radius: 6px;
    font-size: 8pt;
    color: #9CA3AF;
    text-align: center;
  }
</style>
</head>
<body>

<!-- PORTADA -->
<div class="portada">
  <div class="logo-text">
    <span class="blue">Inteli</span><span class="green">audit</span>
  </div>
  <h1>Informe de Auditoría Impositiva</h1>
  <p class="meta">{{ cliente.razon_social }} — RUC {{ cliente.ruc }}</p>
  <p class="meta">Período: {{ auditoria.periodo_desde }} al {{ auditoria.periodo_hasta }}</p>
  <p class="meta">Fecha de emisión: {{ fecha_emision }}</p>
  {% if auditoria.auditor %}
  <p class="meta">Auditor responsable: {{ auditoria.auditor }}</p>
  {% endif %}
  <div class="confidencial">Documento Confidencial</div>
</div>

<!-- 1. DATOS DEL ENCARGO -->
<div class="section">
  <h2>1. Datos del Encargo</h2>
  <div class="info-grid">
    <div class="info-item">
      <div class="info-label">Contribuyente Auditado</div>
      <div class="info-value">{{ cliente.razon_social }}</div>
    </div>
    <div class="info-item">
      <div class="info-label">RUC</div>
      <div class="info-value">{{ cliente.ruc }}</div>
    </div>
    <div class="info-item">
      <div class="info-label">Período de Auditoría</div>
      <div class="info-value">{{ auditoria.periodo_desde }} al {{ auditoria.periodo_hasta }}</div>
    </div>
    <div class="info-item">
      <div class="info-label">Impuestos en Alcance</div>
      <div class="info-value">{{ ", ".join(auditoria.impuestos) }}</div>
    </div>
    {% if cliente.regimen %}
    <div class="info-item">
      <div class="info-label">Régimen</div>
      <div class="info-value">{{ cliente.regimen }}</div>
    </div>
    {% endif %}
    {% if auditoria.materialidad %}
    <div class="info-item">
      <div class="info-label">Materialidad</div>
      <div class="info-value">Gs. {{ "{:,.0f}".format(auditoria.materialidad).replace(",", ".") }}</div>
    </div>
    {% endif %}
  </div>
</div>

<!-- 2. RESUMEN EJECUTIVO -->
<div class="section">
  <h2>2. Resumen Ejecutivo</h2>
  <div class="kpi-grid">
    <div class="kpi-card primary">
      <div class="kpi-label">Contingencia Total</div>
      <div class="kpi-value">Gs. {{ resumen.total_contingencia_fmt }}</div>
    </div>
    <div class="kpi-card danger">
      <div class="kpi-label">Impuesto Omitido</div>
      <div class="kpi-value">Gs. {{ resumen.total_impuesto_fmt }}</div>
    </div>
    <div class="kpi-card warning">
      <div class="kpi-label">Multas + Intereses</div>
      <div class="kpi-value">Gs. {{ resumen.total_sanciones_fmt }}</div>
    </div>
  </div>
  <div class="kpi-grid">
    <div class="kpi-card {{ 'danger' if resumen.alto > 0 else 'success' }}">
      <div class="kpi-label">Hallazgos Alto Riesgo</div>
      <div class="kpi-value">{{ resumen.alto }}</div>
    </div>
    <div class="kpi-card {{ 'warning' if resumen.medio > 0 else 'success' }}">
      <div class="kpi-label">Hallazgos Riesgo Medio</div>
      <div class="kpi-value">{{ resumen.medio }}</div>
    </div>
    <div class="kpi-card success">
      <div class="kpi-label">Hallazgos Riesgo Bajo</div>
      <div class="kpi-value">{{ resumen.bajo }}</div>
    </div>
  </div>
</div>

<!-- 3. TABLA RESUMEN HALLAZGOS -->
<div class="section page-break">
  <h2>3. Cuadro Resumen de Hallazgos</h2>
  <table>
    <thead>
      <tr>
        <th>#</th>
        <th>Tipo de Hallazgo</th>
        <th>Impuesto</th>
        <th>Período</th>
        <th>Riesgo</th>
        <th style="text-align:right">Contingencia (Gs.)</th>
      </tr>
    </thead>
    <tbody>
      {% for h in hallazgos %}
      <tr>
        <td>{{ loop.index }}</td>
        <td>{{ h.tipo_hallazgo.replace("_", " ") }}</td>
        <td>{{ h.impuesto }}</td>
        <td>{{ h.periodo }}</td>
        <td><span class="badge badge-{{ h.nivel_riesgo }}">{{ h.nivel_riesgo }}</span></td>
        <td style="text-align:right;font-weight:700">{{ "{:,.0f}".format(h.total_contingencia).replace(",", ".") }}</td>
      </tr>
      {% else %}
      <tr><td colspan="6" style="text-align:center;color:#9CA3AF;padding:1cm">Sin hallazgos registrados</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>

<!-- 4. HALLAZGOS DETALLADOS -->
{% if hallazgos %}
<div class="section page-break">
  <h2>4. Hallazgos Detallados</h2>
  {% for h in hallazgos %}
  <div class="hallazgo-card hallazgo-{{ h.nivel_riesgo }}">
    <div class="hallazgo-header">
      <div>
        <div class="hallazgo-ref">REF: {{ h.id[:8] }} | {{ h.impuesto }} — {{ h.periodo }}</div>
        <div class="hallazgo-title">{{ h.tipo_hallazgo.replace("_", " ") }}</div>
      </div>
      <span class="badge badge-{{ h.nivel_riesgo }}">{{ h.nivel_riesgo | upper }}</span>
    </div>
    <div class="hallazgo-body">
      <p class="hallazgo-desc">{{ h.descripcion }}</p>
      <div class="hallazgo-legal">{{ h.articulo_legal }}</div>
      <table class="contingencia-table">
        <tr>
          <td>Impuesto omitido</td>
          <td>Gs. {{ "{:,.0f}".format(h.impuesto_omitido).replace(",", ".") }}</td>
        </tr>
        <tr>
          <td>Multa estimada (50%)</td>
          <td>Gs. {{ "{:,.0f}".format(h.multa_estimada).replace(",", ".") }}</td>
        </tr>
        <tr>
          <td>Intereses estimados</td>
          <td>Gs. {{ "{:,.0f}".format(h.intereses_estimados).replace(",", ".") }}</td>
        </tr>
        <tr>
          <td class="contingencia-total">TOTAL CONTINGENCIA</td>
          <td class="contingencia-total">Gs. {{ "{:,.0f}".format(h.total_contingencia).replace(",", ".") }}</td>
        </tr>
      </table>
      {% if h.notas_auditor %}
      <p style="margin-top:0.3cm;font-size:8.5pt;color:#6B7280;font-style:italic">
        Nota del auditor: {{ h.notas_auditor }}
      </p>
      {% endif %}
    </div>
  </div>
  {% endfor %}
</div>
{% endif %}

<!-- 5. NOTAS ADICIONALES -->
{% if notas_auditor %}
<div class="section">
  <h2>5. Notas del Auditor</h2>
  <div style="padding:0.4cm;background:#F5F7FB;border-radius:8px;border:1px solid #E4EAF4">
    <p style="white-space:pre-wrap;font-size:9.5pt">{{ notas_auditor }}</p>
  </div>
</div>
{% endif %}

<!-- FIRMA Y CIERRE -->
<div class="firma-section">
  <div>
    <div class="firma-line">
      {{ auditoria.auditor or "Auditor Responsable" }}<br>
      <strong>Firma auditora</strong>
    </div>
  </div>
  <div>
    <div class="firma-line">
      Representante Legal<br>
      <strong>{{ cliente.razon_social }}</strong>
    </div>
  </div>
</div>

<div class="footer-disclaimer">
  Este informe ha sido generado por Inteliaudit y es de carácter confidencial.
  Su distribución está restringida al destinatario indicado.
  Los montos expresados están en Guaraníes (PYG) sin decimales.
  Las contingencias son estimadas y no constituyen deuda firme ante la SET.
</div>

</body>
</html>"""


def generar_informe_pdf(
    auditoria: dict,
    cliente: dict,
    hallazgos: list[dict],
    notas_auditor: Optional[str] = None,
) -> bytes:
    """
    Genera el informe de auditoría en PDF usando WeasyPrint + Jinja2.

    Args:
        auditoria: Dict con id, periodo_desde, periodo_hasta, impuestos, auditor, materialidad
        cliente: Dict con ruc, razon_social, nombre_fantasia, actividad_principal, regimen, direccion
        hallazgos: Lista de dicts de hallazgos serializados
        notas_auditor: Texto libre adicional

    Returns:
        bytes del PDF generado
    """
    try:
        from jinja2 import Environment, BaseLoader
        from weasyprint import HTML as WeasyprintHTML, CSS
    except ImportError as e:
        raise ImportError(
            f"PDF requiere jinja2 y weasyprint: pip install jinja2 weasyprint. Detalle: {e}"
        )

    # Calcular resumen
    res = resumir_contingencias(hallazgos)

    resumen = {
        "total_contingencia_fmt": formatear_pyg(res["total_contingencia"]),
        "total_impuesto_fmt": formatear_pyg(res["total_impuesto"]),
        "total_sanciones_fmt": formatear_pyg(res["total_multa"] + res["total_intereses"]),
        "alto": res["por_riesgo"].get("alto", 0),
        "medio": res["por_riesgo"].get("medio", 0),
        "bajo": res["por_riesgo"].get("bajo", 0),
    }

    env = Environment(loader=BaseLoader())
    template = env.from_string(_HTML_TEMPLATE)

    html_str = template.render(
        auditoria=auditoria,
        cliente=cliente,
        hallazgos=hallazgos,
        resumen=resumen,
        notas_auditor=notas_auditor,
        fecha_emision=date.today().strftime("%d/%m/%Y"),
    )

    buf = BytesIO()
    WeasyprintHTML(string=html_str, base_url=None).write_pdf(buf)
    return buf.getvalue()
