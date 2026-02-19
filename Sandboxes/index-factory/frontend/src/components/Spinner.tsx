import { clsx } from 'clsx'

interface Props {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const sizes = {
  sm: 'w-4 h-4 border',
  md: 'w-8 h-8 border-2',
  lg: 'w-12 h-12 border-2',
}

export default function Spinner({ size = 'md', className }: Props) {
  return (
    <div className={clsx('rounded-full border-brand-500 border-t-transparent animate-spin', sizes[size], className)} />
  )
}
