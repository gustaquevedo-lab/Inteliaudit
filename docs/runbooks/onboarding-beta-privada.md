# Runbook Operativo: Onboarding de Clientes en Beta Privada

> **Público:** Equipo fundador / SuperAdmin de Inteliaudit.  
> **Objetivo:** Dar de alta un estudio contable o firma auditora en menos de 2 minutos, entregarle sus accesos con contraseña temporal y garantizar un primer valor instantáneo.

---

## 1. Datos Requeridos de la Firma Auditora

Antes de dar el alta, solicita al cliente o socio responsable los siguientes 4 datos básicos:
1. **Razón Social de la Firma:** (ej. *Auditoría & Consultoría Guaraní S.R.L.*)
2. **RUC de la Firma:** (ej. *80098765-4*)
3. **Nombre del Socio / Administrador:** (ej. *Lic. Carlos Benítez*)
4. **Email del Administrador:** (ej. *carlos.benitez@guaraniaudit.com.py*)
5. **Plan Contratado:** Starter (5 clientes / 3 usuarios), Pro (15 clientes / 8 usuarios + IA Qwen) o Enterprise (Ilimitado).

---

## 2. Aprovisionamiento en la Consola SuperAdmin

1. Ingresa a la plataforma con tu usuario superadministrador:  
   👉 **URL:** `https://inteliaudit.intellihouse.lat/admin/superadmin`
2. En la pestaña **Tenants**, haz clic en el botón superior **`+ Nueva Firma`**.
3. Completa el formulario modal:
   * **Nombre de la Firma:** Razón social del cliente.
   * **RUC de la Firma:** RUC paraguayo (con o sin guión).
   * **Email del Admin:** Correo del socio responsable.
   * **Nombre del Admin:** Nombre del profesional.
   * **Plan Inicial:** Selecciona `starter`, `pro` o `enterprise`.
4. Haz clic en **"Crear Firma y Usuario"**.
5. **IMPORTANTE:** Aparecerá una tarjeta destacada con la **Contraseña Temporal Generada**. Haz clic en **Copiar Contraseña** antes de cerrar el modal.

---

## 3. Plantilla de Entrega de Accesos (WhatsApp / Email)

Copia y personaliza el siguiente mensaje para enviárselo directamente al socio o contador responsable:

```text
Estimado/a [Nombre del Socio],

¡Bienvenido/a a Inteliaudit! Ya hemos habilitado el espacio de trabajo exclusivo para [Nombre de la Firma].

Tus credenciales de acceso inicial son:
🌐 Plataforma: https://inteliaudit.intellihouse.lat/login
👤 Usuario: [email@cliente.com]
🔑 Contraseña Temporal: [CONTRASEÑA_TEMPORAL]

🔒 Seguridad: En tu primer inicio de sesión, el sistema te solicitará establecer tu propia contraseña personal definitiva.

Pasos recomendados para tu primera prueba en 5 minutos:
1. Inicia sesión y define tu contraseña personal.
2. Ve a "Clientes" y registra a tu primer contribuyente.
3. En la pestaña "Archivos", sube el Excel de Compras o Ventas de tu RG90.
4. En la pestaña "Análisis", haz clic en "Ejecutar Análisis" para auditar en segundos las diferencias de IVA, SIFEN y retenciones.

Quedamos a tu entera disposición para cualquier consulta.
Atentamente,
Equipo de Inteliaudit Paraguay
```

---

## 4. Experiencia del Cliente en el Primer Ingreso

1. **Ingreso:** El cliente accede a `/login` con su email y contraseña temporal.
2. **Forzado de Cambio de Clave:** El sistema detecta el flag `debe_cambiar_password = true` y bloquea la navegación hasta que ingrese y confirme su nueva contraseña segura.
3. **Activación Automática:** Una vez cambiada la clave, el flag se desactiva y el cliente accede directamente a su Dashboard de trabajo.

---

## 5. Monitoreo Proactivo desde SuperAdmin

* **Impersonación para Soporte:** Si el cliente tiene alguna duda sobre un archivo o cruce, puedes ir a `/admin/superadmin` $\to$ buscar su firma $\to$ hacer clic en **"Impersonar"**. Verás la pantalla exactamente como la ve el cliente para guiarlo en tiempo real.
* **Telemetría de Errores (Sentry-Lite):** Si el cliente carga un formato atípico de Excel o surge una excepción, ve a la pestaña **Sentry-Lite**. El error aparecerá agrupado con su stack trace completo y podrás presionar **"Copiar Reporte para Agente AI"** para intervenirlo inmediatamente.
