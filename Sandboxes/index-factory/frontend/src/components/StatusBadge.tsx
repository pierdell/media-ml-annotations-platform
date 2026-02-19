import { CheckCircle2, Clock, AlertCircle } from 'lucide-react'
import { clsx } from 'clsx'

interface Props {
  status: 'indexed' | 'pending' | 'error'
  size?: 'sm' | 'md'
}

export default function StatusBadge({ status, size = 'sm' }: Props) {
  const config = {
    indexed: {
      icon: CheckCircle2,
      label: 'Indexed',
      className: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
    },
    pending: {
      icon: Clock,
      label: 'Pending',
      className: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
    },
    error: {
      icon: AlertCircle,
      label: 'Error',
      className: 'bg-red-500/15 text-red-400 border-red-500/20',
    },
  }

  const { icon: Icon, label, className } = config[status]

  return (
    <span className={clsx(
      'inline-flex items-center gap-1 rounded-full border font-medium',
      size === 'sm' ? 'text-[10px] px-2 py-0.5' : 'text-xs px-2.5 py-1',
      className,
    )}>
      <Icon className={size === 'sm' ? 'w-2.5 h-2.5' : 'w-3 h-3'} />
      {label}
    </span>
  )
}
