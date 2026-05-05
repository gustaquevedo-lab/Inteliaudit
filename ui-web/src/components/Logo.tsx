interface LogoProps {
  size?: 'sm' | 'md' | 'lg'
  showSlogan?: boolean
  dark?: boolean
}

const sizes = {
  sm: { icon: 24, text: 'text-base', slogan: 'text-[9px]' },
  md: { icon: 32, text: 'text-xl', slogan: 'text-[10px]' },
  lg: { icon: 42, text: 'text-3xl', slogan: 'text-xs' },
}

export default function Logo({ size = 'md', showSlogan = false, dark = false }: LogoProps) {
  const s = sizes[size]
  const textColor = dark ? 'text-white' : 'text-gray-900 dark:text-white'
  const sloganColor = dark ? 'text-blue-200/60' : 'text-gray-400 dark:text-blue-200/60'

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="flex items-center gap-2">
        {/* Isotipo: squircle con lupa + check */}
        <svg width={s.icon} height={s.icon} viewBox="0 0 40 40" fill="none">
          <rect width="40" height="40" rx="10" fill="url(#logoGrad)" />
          {/* Lupa */}
          <circle cx="17" cy="17" r="7" stroke="white" strokeWidth="2.5" fill="none" />
          <line x1="22" y1="22" x2="29" y2="29" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
          {/* Check verde */}
          <circle cx="29" cy="13" r="6" fill="#00a651" />
          <polyline points="26,13 28.5,15.5 32,11" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" fill="none" />
          <defs>
            <linearGradient id="logoGrad" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#256ebf" />
              <stop offset="100%" stopColor="#0a356b" />
            </linearGradient>
          </defs>
        </svg>
        {/* Wordmark */}
        <span className={`${s.text} font-black tracking-tighter leading-none ${textColor}`}>
          <span className="text-primary-light dark:text-blue-300">Inteli</span>
          <span className="text-secondary dark:text-secondary-light">audit</span>
        </span>
      </div>
      {showSlogan && (
        <p className={`${s.slogan} font-medium uppercase tracking-widest ${sloganColor}`}>
          Auditoría impositiva inteligente
        </p>
      )}
    </div>
  )
}
