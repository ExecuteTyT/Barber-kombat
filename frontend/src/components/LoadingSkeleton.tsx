interface LoadingSkeletonProps {
  lines?: number
  circle?: boolean
  className?: string
}

export default function LoadingSkeleton({
  lines = 3,
  circle,
  className = '',
}: LoadingSkeletonProps) {
  if (circle) {
    return <div className={`bk-skeleton h-12 w-12 rounded-full ${className}`} />
  }

  return (
    <div className={`space-y-3 ${className}`}>
      {Array.from({ length: lines }, (_, i) => (
        <div
          key={i}
          className="bk-skeleton h-4 rounded"
          style={{ width: i === lines - 1 ? '60%' : '100%' }}
        />
      ))}
    </div>
  )
}
