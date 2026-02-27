interface LoadingSkeletonProps {
  lines?: number
  circle?: boolean
  className?: string
}

export default function LoadingSkeleton({ lines = 3, circle, className = '' }: LoadingSkeletonProps) {
  if (circle) {
    return (
      <div
        className={`h-12 w-12 animate-pulse rounded-full bg-[var(--tg-theme-secondary-bg-color)] ${className}`}
      />
    )
  }

  return (
    <div className={`space-y-3 ${className}`}>
      {Array.from({ length: lines }, (_, i) => (
        <div
          key={i}
          className="h-4 animate-pulse rounded bg-[var(--tg-theme-secondary-bg-color)]"
          style={{ width: i === lines - 1 ? '60%' : '100%' }}
        />
      ))}
    </div>
  )
}
