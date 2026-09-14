import { Link } from 'react-router'

import { PageBanner } from '../components/PageBanner'
import { RecentCard } from '../components/RecentCard'
import { useLibrary } from '../library/LibraryContext'

export function RecentsPage() {
  const { recents, removeRecent, error } = useLibrary()

  return (
    <>
      <PageBanner title="Recents" crumbs={[{ label: 'Home', to: '/' }, { label: 'Recents' }]} />
      <section className="mx-auto max-w-7xl px-4 pt-10 sm:px-6">
        {error && <p className="mb-6 text-sm text-red-700">{error}</p>}
        {recents.length === 0 ? (
          <EmptyState />
        ) : (
          <>
            <p className="text-sm text-muted">
              {recents.length} item{recents.length === 1 ? '' : 's'} you searched on this browser
            </p>
            <div className="mt-6 grid grid-cols-2 gap-x-5 gap-y-10 md:grid-cols-3 lg:grid-cols-4">
              {recents.map((item) => (
                <RecentCard
                  key={item.id}
                  item={item}
                  onRemove={() => {
                    removeRecent(item.id).catch((e: Error) => alert(e.message))
                  }}
                />
              ))}
            </div>
          </>
        )}
      </section>
    </>
  )
}

function EmptyState() {
  return (
    <div className="mx-auto max-w-md py-16 text-center">
      <h2 className="text-2xl font-medium">No recent searches yet</h2>
      <p className="mt-2 text-muted">Items you look up with Muse will appear here.</p>
      <Link
        to="/"
        className="mt-6 inline-block rounded-full bg-brown px-7 py-3 font-medium text-white hover:bg-brown-light"
      >
        Search an item
      </Link>
    </div>
  )
}
