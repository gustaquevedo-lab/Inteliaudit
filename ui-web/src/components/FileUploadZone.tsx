import { useRef, useState, DragEvent } from 'react'
import { Upload, File } from 'lucide-react'
import { clsx } from 'clsx'

interface FileUploadZoneProps {
  accept?: string
  onFile: (file: File) => void
  label?: string
  hint?: string
  disabled?: boolean
}

export default function FileUploadZone({ accept, onFile, label = 'Subir archivo', hint, disabled }: FileUploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  const handle = (file: File | undefined) => {
    if (file && !disabled) onFile(file)
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    handle(e.dataTransfer.files[0])
  }

  return (
    <div
      className={clsx(
        'border-2 border-dashed rounded-2xl p-8 flex flex-col items-center gap-3 transition-all cursor-pointer',
        dragging ? 'border-primary bg-primary/5' : 'border-gray-200 dark:border-gray-700 hover:border-primary/40 hover:bg-gray-50 dark:hover:bg-gray-800/40',
        disabled && 'opacity-50 cursor-not-allowed',
      )}
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
    >
      <div className={clsx('p-3 rounded-xl', dragging ? 'bg-primary/10' : 'bg-gray-100 dark:bg-gray-800')}>
        <Upload size={22} className={dragging ? 'text-primary' : 'text-gray-400'} />
      </div>
      <div className="text-center">
        <p className="text-sm font-bold text-gray-700 dark:text-gray-300">{label}</p>
        {hint && <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{hint}</p>}
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Arrastrá el archivo o hacé clic</p>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={e => handle(e.target.files?.[0])}
        disabled={disabled}
      />
    </div>
  )
}
