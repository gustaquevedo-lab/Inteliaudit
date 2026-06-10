"""
Sistema de emails transaccionales para Inteliaudit.
Usa Resend (free: 100 emails/dia) o Brevo (free: 300/dia).
"""
import asyncio
from datetime import datetime
from typing import Optional

from config.settings import settings

TEMPLATES = {
    "bienvenida": {
        "asunto": "Bienvenido a Inteliaudit",
        "template": "bienvenida",
    },
    "trial_por_vencer": {
        "asunto": "Tu trial Pro vence en 3 dias",
        "template": "trial_por_vencer",
    },
    "trial_expirado": {
        "asunto": "Tu trial ha expirado",
        "template": "trial_expirado",
    },
    "auditoria_completada": {
        "asunto": "Auditoria de {cliente} finalizada",
        "template": "auditoria_completada",
    },
    "invitacion_usuario": {
        "asunto": "{firma} te invito a Inteliaudit",
        "template": "invitacion_usuario",
    },
}


def _template_html(template_name: str, **data) -> str:
    """Genera HTML del email usando templates inline."""
    ctx = {
        "logo_url": "https://inteliaudit.com/favicon.svg",
        "anio": datetime.now().year,
        **data,
    }

    cuerpo = _render_cuerpo(template_name, ctx)

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:32px 16px;">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);">

<!-- Header navy -->
<tr><td style="background:#091624;padding:24px 32px;text-align:center;">
  <table cellpadding="0" cellspacing="0"><tr><td style="vertical-align:middle;">
    <span style="font-size:22px;font-weight:700;color:#2E84F0;">Inteli</span>
    <span style="font-size:22px;font-weight:300;color:#22C47E;">audit</span>
  </td></tr></table>
  <p style="color:#6B7A90;font-size:12px;margin:4px 0 0 0;">Auditoria impositiva inteligente para Paraguay</p>
</td></tr>

<!-- Body -->
<tr><td style="padding:32px;">
{cuerpo}
</td></tr>

<!-- Footer -->
<tr><td style="background:#f8fafc;padding:20px 32px;text-align:center;border-top:1px solid #e2e8f0;">
  <p style="font-size:11px;color:#94a3b8;margin:0 0 4px 0;">
    Inteliaudit — Auditoria impositiva inteligente para Paraguay
  </p>
  <p style="font-size:10px;color:#cbd5e1;margin:0;">
    Este es un mensaje automatico. No respondas a este correo.
  </p>
</td></tr>

</table>
</td></tr></table>
</body>
</html>"""


def _render_cuerpo(template_name: str, ctx: dict) -> str:
    t = template_name
    if t == "bienvenida":
        return f"""
<h1 style="font-size:20px;font-weight:700;color:#091624;margin:0 0 16px 0;">Bienvenido a Inteliaudit</h1>
<p style="font-size:14px;color:#475569;line-height:1.6;margin:0 0 16px 0;">Hola <strong>{ctx.get('nombre','')}</strong>,</p>
<p style="font-size:14px;color:#475569;line-height:1.6;margin:0 0 16px 0;">Tu firma <strong>{ctx.get('firma','')}</strong> ha sido creada correctamente. Ya podes empezar a auditar.</p>
<table cellpadding="0" cellspacing="0" style="margin:24px 0;"><tr>
  <td style="background:#2E84F0;border-radius:8px;padding:12px 24px;">
    <a href="{ctx.get('dashboard_url','#')}" style="color:#fff;font-size:14px;font-weight:700;text-decoration:none;">Ir al dashboard &rarr;</a>
  </td>
</tr></table>
<div style="background:#f8fafc;border-radius:8px;padding:16px;margin:16px 0;">
  <p style="font-size:13px;font-weight:700;color:#091624;margin:0 0 8px 0;">Tus proximos pasos:</p>
  <ol style="font-size:13px;color:#475569;margin:0;padding-left:20px;">
    <li style="margin-bottom:4px;">Crea tu primer cliente</li>
    <li style="margin-bottom:4px;">Subi archivos RG90 y HECHAUKA</li>
    <li>Ejecuta el analisis automatico</li>
  </ol>
</div>
<p style="font-size:13px;color:#94a3b8;">Trial Pro: 7 dias gratis. <a href="{ctx.get('planes_url','#')}" style="color:#2E84F0;">Ver planes</a></p>"""

    if t == "trial_por_vencer":
        return f"""
<h1 style="font-size:20px;font-weight:700;color:#091624;margin:0 0 16px 0;">Tu trial Pro vence en 3 dias</h1>
<p style="font-size:14px;color:#475569;line-height:1.6;margin:0 0 16px 0;">Hola <strong>{ctx.get('nombre','')}</strong>,</p>
<p style="font-size:14px;color:#475569;line-height:1.6;margin:0 0 16px 0;">Tu periodo de prueba gratuita de Inteliaudit esta por vencer. No pierdas acceso a los datos de tus auditorias.</p>
<table cellpadding="0" cellspacing="0" style="margin:24px 0;"><tr>
  <td style="background:#2E84F0;border-radius:8px;padding:12px 24px;">
    <a href="{ctx.get('planes_url','#')}" style="color:#fff;font-size:14px;font-weight:700;text-decoration:none;">Ver planes &rarr;</a>
  </td>
</tr></table>
<p style="font-size:13px;color:#94a3b8;">Si ya elegiste un plan, ignora este mensaje.</p>"""

    if t == "trial_expirado":
        return f"""
<h1 style="font-size:20px;font-weight:700;color:#E53E3E;margin:0 0 16px 0;">Tu trial ha expirado</h1>
<p style="font-size:14px;color:#475569;line-height:1.6;margin:0 0 16px 0;">Hola <strong>{ctx.get('nombre','')}</strong>,</p>
<p style="font-size:14px;color:#475569;line-height:1.6;margin:0 0 16px 0;">Tu periodo de prueba ha finalizado. Tus datos estan seguros, pero necesitas elegir un plan para seguir usando Inteliaudit.</p>
<table cellpadding="0" cellspacing="0" style="margin:24px 0;"><tr>
  <td style="background:#2E84F0;border-radius:8px;padding:12px 24px;">
    <a href="{ctx.get('planes_url','#')}" style="color:#fff;font-size:14px;font-weight:700;text-decoration:none;">Elegi un plan &rarr;</a>
  </td>
</tr></table>"""

    if t == "auditoria_completada":
        return f"""
<h1 style="font-size:20px;font-weight:700;color:#091624;margin:0 0 16px 0;">Auditoria completada</h1>
<p style="font-size:14px;color:#475569;line-height:1.6;margin:0 0 16px 0;">La auditoria de <strong>{ctx.get('cliente','')}</strong> ha finalizado.</p>
<div style="background:#f8fafc;border-radius:8px;padding:16px;margin:16px 0;">
  <p style="font-size:13px;color:#475569;margin:0 0 4px 0;">Hallazgos encontrados: <strong>{ctx.get('hallazgos',0)}</strong></p>
  <p style="font-size:13px;color:#475569;margin:0 0 4px 0;">Contingencia total: <strong>Gs. {ctx.get('contingencia',0):,}</strong></p>
  <p style="font-size:13px;color:#475569;margin:0;">Periodo: {ctx.get('periodo_desde','')} a {ctx.get('periodo_hasta','')}</p>
</div>
<table cellpadding="0" cellspacing="0" style="margin:16px 0;"><tr>
  <td style="background:#2E84F0;border-radius:8px;padding:12px 24px;">
    <a href="{ctx.get('auditoria_url','#')}" style="color:#fff;font-size:14px;font-weight:700;text-decoration:none;">Ver resultados &rarr;</a>
  </td>
</tr></table>"""

    if t == "invitacion_usuario":
        return f"""
<h1 style="font-size:20px;font-weight:700;color:#091624;margin:0 0 16px 0;">Te invitaron a Inteliaudit</h1>
<p style="font-size:14px;color:#475569;line-height:1.6;margin:0 0 16px 0;">Hola,</p>
<p style="font-size:14px;color:#475569;line-height:1.6;margin:0 0 16px 0;"><strong>{ctx.get('firma','')}</strong> te ha invitado a unirte a su equipo en Inteliaudit.</p>
<table cellpadding="0" cellspacing="0" style="margin:24px 0;"><tr>
  <td style="background:#2E84F0;border-radius:8px;padding:12px 24px;">
    <a href="{ctx.get('activate_url','#')}" style="color:#fff;font-size:14px;font-weight:700;text-decoration:none;">Activar cuenta &rarr;</a>
  </td>
</tr></table>
<p style="font-size:13px;color:#94a3b8;">El link de activacion expira en 7 dias.</p>"""

    return f"<p>Template no encontrado: {template_name}</p>"


async def enviar_email(
    to: str,
    template: str,
    subject_extra: Optional[str] = None,
    **data,
) -> dict:
    """
    Envia un email transaccional usando Resend.

    Args:
        to: Email del destinatario
        template: Nombre del template (bienvenida, trial_por_vencer, etc.)
        subject_extra: Texto adicional para el asunto
        **data: Variables para el template

    Returns:
        Dict con resultado del envio
    """
    if not settings.resend_api_key:
        return {"ok": False, "error": "RESEND_API_KEY no configurada"}

    tmpl = TEMPLATES.get(template)
    if not tmpl:
        return {"ok": False, "error": f"Template '{template}' no encontrado"}

    asunto = tmpl["asunto"]
    if subject_extra:
        asunto = asunto.format(**subject_extra)

    html = _template_html(template, **data)

    try:
        import resend
        resend.api_key = settings.resend_api_key
        response = resend.Emails.send({
            "from": settings.email_from,
            "to": [to],
            "subject": asunto,
            "html": html,
        })
        _log_email(to, template, "enviado", response.get("id", ""))
        return {"ok": True, "id": response.get("id", "")}
    except Exception as e:
        _log_email(to, template, "error", str(e))
        return {"ok": False, "error": str(e)}


def enviar_email_sync(
    to: str,
    template: str,
    subject_extra: Optional[str] = None,
    **data,
) -> dict:
    """Version sincrona de enviar_email (para usar en endpoints sync)."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(enviar_email(to, template, subject_extra, **data))
    finally:
        loop.close()


def _log_email(to: str, template: str, status: str, detalle: str):
    """Logea el envio de email (a archivo o consola por ahora)."""
    from datetime import datetime
    ts = datetime.now().isoformat()
    log_line = f"[{ts}] {status.upper()} | to={to} | template={template} | {detalle}\n"
    try:
        from pathlib import Path
        log_file = Path(__file__).parent.parent / "logs" / "email.log"
        log_file.parent.mkdir(exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception:
        import sys
        print(log_line, file=sys.stderr)
