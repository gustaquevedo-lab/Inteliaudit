import { useState } from 'react'
import { api } from '../../api/client'
import { useToast } from '../../components/Toaster'
import Modal from '../../components/Modal'
import type { Hallazgo, TipoImpuesto, NivelRiesgo } from '../../api/types'

const IMPUESTOS: TipoImpuesto[] = ['IVA', 'IRE', 'IRP', 'IDU', 'RET_IVA', 'RET_IRE', 'OTRO']
const RIESGOS: NivelRiesgo[] = ['alto', 'medio', 'bajo']
const MESES = Array.from({length:12},(_,i)=>String(i+1).padStart(2,'0'))
const ANOS = Array.from({length:6},(_,i)=>String(new Date().getFullYear()-i))

const TIPOS_HALLAZGO = [
  'Crédito fiscal con RUC inactivo/cancelado',
  'Comprobante sin CDC en SIFEN (posible apócrifo)',
  'Factura electrónica recibida no declarada en RG90',
  'Diferencia entre RG90 y Form. 120',
  'Gasto sin comprobante legal',
  'Depreciación que supera tasas máximas (Dcto. 3107)',
  'Gasto personal cargado a la empresa',
  'Retención no practicada',
  'Retención practicada no depositada',
  'Diferencia RG90 vs HECHAUKA',
  'Ingreso no declarado',
  'Otro hallazgo',
]

const ARTICULOS_SUGERIDOS: Record<string, string> = {
  'Crédito fiscal con RUC inactivo/cancelado': 'Art. 103 Ley 6380/2019 — Requisitos crédito fiscal IVA',
  'Comprobante sin CDC en SIFEN (posible apócrifo)': 'Art. 6 RG 69/2020 — Obligatoriedad validez e-Kuatia',
  'Factura electrónica recibida no declarada en RG90': 'Art. 2 RG 90/2021 — Obligación de informar comprobantes',
  'Diferencia entre RG90 y Form. 120': 'Art. 102 Ley 6380/2019 — Determinación IVA',
  'Gasto sin comprobante legal': 'Art. 16 inc. d) Ley 6380/2019 — Gastos no deducibles IRE',
  'Depreciación que supera tasas máximas (Dcto. 3107)': 'Art. 14 Decreto 3107/2019 — Tasas de depreciación',
  'Gasto personal cargado a la empresa': 'Art. 16 inc. e) Ley 6380/2019 — Gastos no deducibles',
  'Retención no practicada': 'Art. 175 Ley 125/1991 — Multa por omisión de retención',
  'Retención practicada no depositada': 'Art. 175 Ley 125/1991 — Omisión de depositar retención',
  'Diferencia RG90 vs HECHAUKA': 'Art. 2 RG 90/2021 — Consistencia declaración IVA',
  'Ingreso no declarado': 'Art. 8 Ley 6380/2019 — Renta bruta IRE',
}

interface Props {
  open: boolean
  onClose: () => void
  auditoriaId: string
  onCreated: (h: Hallazgo) => void
}

export default function NuevoHallazgoModal({ open, onClose, auditoriaId, onCreated }: Props) {
  const { success, error } = useToast()
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    impuesto: 'IVA' as TipoImpuesto,
    anio: String(new Date().getFullYear() - 1),
    mes: '01',
    tipo_hallazgo: TIPOS_HALLAZGO[0],
    descripcion: '',
    articulo_legal: ARTICULOS_SUGERIDOS[TIPOS_HALLAZGO[0]] ?? '',
    descripcion_tecnica: '',
    base_ajuste: '',
    impuesto_omitido: '',
    fecha_omision: '',
    nivel_riesgo: 'medio' as NivelRiesgo,
    notas_auditor: '',
  })

  const set = <K extends keyof typeof form>(k: K, v: typeof form[K]) => setForm(f => ({ ...f, [k]: v }))

  const setTipo = (tipo: string) => {
    setForm(f => ({ ...f, tipo_hallazgo: tipo, articulo_legal: ARTICULOS_SUGERIDOS[tipo] ?? f.articulo_legal }))
  }

  const crear = async () => {
    if (!form.descripcion || !form.tipo_hallazgo) return
    setSaving(true)
    try {
      const h = await api.post<Hallazgo>(`/auditorias/${auditoriaId}/hallazgos`, {
        impuesto: form.impuesto,
        periodo: `${form.anio}-${form.mes}`,
        tipo_hallazgo: form.tipo_hallazgo,
        descripcion: form.descripcion,
        articulo_legal: form.articulo_legal,
        descripcion_tecnica: form.descripcion_tecnica || undefined,
        base_ajuste: Number(form.base_ajuste) || 0,
        impuesto_omitido: Number(form.impuesto_omitido) || 0,
        fecha_omision: form.fecha_omision || undefined,
        nivel_riesgo: form.nivel_riesgo,
        notas_auditor: form.notas_auditor || undefined,
      })
      success('Hallazgo creado correctamente')
      onCreated(h)
      onClose()
    } catch (e: unknown) {
      error(e instanceof Error ? e.message : 'Error al crear hallazgo')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Nuevo hallazgo manual" size="lg"
      footer={
        <>
          <button className="btn-outline" onClick={onClose}>Cancelar</button>
          <button className="btn-primary" onClick={crear} disabled={saving || !form.descripcion}>
            {saving ? <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> : 'Crear hallazgo'}
          </button>
        </>
      }
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-h-[65vh] overflow-y-auto pr-1">
        {/* Impuesto + Período */}
        <div>
          <label className="input-label label-required">Impuesto</label>
          <select className="input-field" value={form.impuesto} onChange={e => set('impuesto', e.target.value as TipoImpuesto)}>
            {IMPUESTOS.map(i => <option key={i} value={i}>{i.replace('_',' ')}</option>)}
          </select>
        </div>
        <div>
          <label className="input-label label-required">Período</label>
          <div className="grid grid-cols-2 gap-2">
            <select className="input-field" value={form.mes} onChange={e => set('mes', e.target.value)}>
              {MESES.map(m => <option key={m} value={m}>{new Date(2024,Number(m)-1).toLocaleString('es-PY',{month:'short'})}</option>)}
            </select>
            <select className="input-field" value={form.anio} onChange={e => set('anio', e.target.value)}>
              {ANOS.map(a => <option key={a}>{a}</option>)}
            </select>
          </div>
        </div>

        {/* Tipo hallazgo */}
        <div className="sm:col-span-2">
          <label className="input-label label-required">Tipo de hallazgo</label>
          <select className="input-field" value={form.tipo_hallazgo} onChange={e => setTipo(e.target.value)}>
            {TIPOS_HALLAZGO.map(t => <option key={t}>{t}</option>)}
          </select>
        </div>

        {/* Descripción */}
        <div className="sm:col-span-2">
          <label className="input-label label-required">Descripción del hallazgo</label>
          <textarea className="input-field resize-none" rows={3} placeholder="Describí el hallazgo en términos claros para el cliente..." value={form.descripcion} onChange={e => set('descripcion', e.target.value)} />
        </div>

        {/* Marco legal */}
        <div className="sm:col-span-2">
          <label className="input-label label-required">Marco legal aplicable</label>
          <input className="input-field" placeholder="Art. 103 Ley 6380/2019..." value={form.articulo_legal} onChange={e => set('articulo_legal', e.target.value)} />
        </div>

        {/* Montos */}
        <div>
          <label className="input-label">Base de ajuste (₲)</label>
          <input className="input-field font-mono" type="number" min="0" placeholder="0" value={form.base_ajuste} onChange={e => set('base_ajuste', e.target.value)} />
        </div>
        <div>
          <label className="input-label">Impuesto omitido (₲)</label>
          <input className="input-field font-mono" type="number" min="0" placeholder="0" value={form.impuesto_omitido} onChange={e => set('impuesto_omitido', e.target.value)} />
        </div>

        <div>
          <label className="input-label">Fecha de omisión</label>
          <input className="input-field" type="date" value={form.fecha_omision} onChange={e => set('fecha_omision', e.target.value)} />
          <p className="text-[10px] text-gray-400 mt-1">Para calcular intereses moratorios (1% mensual)</p>
        </div>
        <div>
          <label className="input-label">Nivel de riesgo</label>
          <div className="grid grid-cols-3 gap-2">
            {RIESGOS.map(r => (
              <button key={r} type="button" onClick={() => set('nivel_riesgo', r)}
                className={`py-2 rounded-xl border-2 text-xs font-bold capitalize transition-all ${
                  form.nivel_riesgo === r
                    ? r === 'alto' ? 'border-red-500 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400'
                      : r === 'medio' ? 'border-amber-500 bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400'
                      : 'border-green-500 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400'
                    : 'border-gray-200 dark:border-gray-700 text-gray-500'
                }`}
              >{r}</button>
            ))}
          </div>
        </div>

        {/* Descripción técnica */}
        <div className="sm:col-span-2">
          <label className="input-label">Descripción técnica (interno)</label>
          <textarea className="input-field resize-none font-mono text-xs" rows={2} placeholder="Detalle técnico para el archivo de trabajo..." value={form.descripcion_tecnica} onChange={e => set('descripcion_tecnica', e.target.value)} />
        </div>

        {/* Notas */}
        <div className="sm:col-span-2">
          <label className="input-label">Notas del auditor</label>
          <textarea className="input-field resize-none" rows={2} placeholder="Observaciones adicionales..." value={form.notas_auditor} onChange={e => set('notas_auditor', e.target.value)} />
        </div>
      </div>
    </Modal>
  )
}
