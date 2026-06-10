"""Fix roadmap-state.json indices and add missing tasks."""
import json

PATH = "C:\\Users\\Gustavo Quevedo\\OneDrive\\Dev\\Inteliaudit\\roadmap-state.json"

with open(PATH, "r", encoding="utf-8") as f:
    state = json.load(f)

# Fix 2.1__4 briefing (was describing task 5)
state["2.1__4"]["briefing"] = "Implementada logica de trial expirado: middleware en api/main.py bloquea endpoints de escritura (POST/PUT/PATCH/DELETE) cuando trial_hasta < now. GET y rutas auth/portal/health no bloqueadas. Retorna 403."

# Add missing 2.1__5
state["2.1__5"] = {"completed": True, "briefing": "Botones de landing page actualizados: hero CTA y pricing cards apuntan a /app/registro. Ruta /registro agregada en App.tsx como publica.", "timestamp": "2026-06-10T21:00:30.000Z"}

# Fix 2.5__3 briefing (was describing task 4)
state["2.5__3"]["briefing"] = "Gate por plan Enterprise en portal.py: verifica plan_cfg.tiene_portal_cliente antes de generar link. Solo admin/auditor_senior."

# Add missing 2.5__4
state["2.5__4"] = {"completed": True, "briefing": "PortalCliente.tsx completado con diseno profesional: header logo Inteliaudit + nombre firma, hero cliente, KPIs, lista hallazgos, descarga PDF, footer legal. Sin sidebar.", "timestamp": "2026-06-10T21:01:00.000Z"}

# Add missing 2.5__5
state["2.5__5"] = {"completed": True, "briefing": "Boton Compartir con cliente en TabInformes.tsx con modal: select hallazgos, config expiracion, generar link JWT, copiar al portapapeles.", "timestamp": "2026-06-10T21:02:00.000Z"}

# Fix 3.1__2 briefing (was describing task 1)
state["3.1__2"]["briefing"] = "Rate limiting mensual: 50 llamadas/mes Pro, ilimitado Enterprise. analisis/rate_limiter.py en memoria. Verificacion en endpoints IA. HTTP 429 si excede."

# Add missing 3.1__5
state["3.1__5"] = {"completed": True, "briefing": "Edicion post-generacion: textarea editable para narrativa IA. Badge Generado por IA con icono Sparkles.", "timestamp": "2026-06-10T21:03:00.000Z"}

# Add missing 3.1__6
state["3.1__6"] = {"completed": True, "briefing": "Contador uso mensual IA en Configuracion: periodo, llamadas, limite, plan. Endpoint GET /api/auth/ia-usage. Componente IaUsageCard.", "timestamp": "2026-06-10T21:04:00.000Z"}

# Add missing 3.2__5
state["3.2__5"] = {"completed": True, "briefing": "Endpoint POST /auditorias/{id}/tareas para crear tareas desde sugerencias. Boton Agregar en frontend.", "timestamp": "2026-06-10T21:06:00.000Z"}

# Add missing 3.3__4
state["3.3__4"] = {"completed": True, "briefing": "Verificada inclusion resumen ejecutivo en informes: primera seccion en HTML preview. Integrado en _template_basico() de render.py.", "timestamp": "2026-06-10T21:07:00.000Z"}

state["_lastSaved"] = "2026-06-10T21:07:00.000Z"

with open(PATH, "w", encoding="utf-8") as f:
    json.dump(state, f, indent=2, ensure_ascii=False)
print("OK: roadmap-state.json fixed -", len(state), "entries")
