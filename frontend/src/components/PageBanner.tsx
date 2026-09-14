import { Link } from 'react-router'

interface Crumb {
  label: string
  to?: string
}

/** Light title band with breadcrumbs, used at the top of inner pages. */
export function PageBanner({ title, crumbs }: { title: string; crumbs: Crumb[] }) {
  return (
    <section className="relative overflow-hidden bg-sand">
      <DotCluster className="absolute top-6 left-[12%]" />
      <DotCluster className="absolute right-[10%] bottom-5" />
      <div className="mx-auto max-w-7xl px-4 py-12 text-center sm:px-6">
        <h1 className="text-3xl font-medium sm:text-4xl">{title}</h1>
        <nav aria-label="Breadcrumb" className="mt-3 text-sm text-muted">
          {crumbs.map((crumb, i) => (
            <span key={crumb.label}>
              {i > 0 && <span className="mx-2">/</span>}
              {crumb.to ? (
                <Link to={crumb.to} className="hover:text-brown">
                  {crumb.label}
                </Link>
              ) : (
                <span className="text-ink">{crumb.label}</span>
              )}
            </span>
          ))}
        </nav>
      </div>
    </section>
  )
}

/** The small scattered-dot texture from the design. */
export function DotCluster({ className = '' }: { className?: string }) {
  return (
    <svg width="64" height="24" viewBox="0 0 64 24" aria-hidden className={`text-brown/25 ${className}`}>
      {[0, 1, 2].flatMap((row) =>
        [0, 1, 2, 3, 4, 5, 6].map((col) => (
          <circle key={`${row}-${col}`} cx={4 + col * 9 + (row % 2) * 4} cy={4 + row * 8} r="1.6" fill="currentColor" />
        )),
      )}
    </svg>
  )
}
