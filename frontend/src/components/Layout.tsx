import type { ReactNode } from 'react'
import { Link, NavLink } from 'react-router'

import { useLibrary } from '../library/LibraryContext'
import { ClockIcon, HeartIcon, HomeIcon, SearchIcon } from './Icons'

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-svh flex-col">
      <AnnouncementBar />
      <Header />
      <main className="flex-1 pb-28 md:pb-0">{children}</main>
      <Footer />
      <MobileTabBar />
    </div>
  )
}

function AnnouncementBar() {
  return (
    <div className="bg-brown text-xs text-white/85">
      <div className="mx-auto flex max-w-7xl items-center justify-center gap-2 px-4 py-2.5 sm:justify-between sm:px-6">
        <span className="hidden sm:inline">Real listings from retailers &amp; resellers</span>
        <span>
          Prices verified by AI.{' '}
          <Link to="/" className="font-medium text-mustard underline underline-offset-2">
            Search an item
          </Link>
        </span>
      </div>
    </div>
  )
}

export function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2" aria-label="Muse home">
      <span className="flex size-9 items-center justify-center rounded-full bg-brown text-lg font-semibold text-white">
        M
      </span>
      <span className="text-2xl font-semibold tracking-tight">
        Muse<span className="text-mustard">.</span>
      </span>
    </Link>
  )
}

const NAV = [
  { to: '/', label: 'Home', end: true },
  { to: '/recents', label: 'Recents' },
  { to: '/wishlist', label: 'Wishlist' },
]

function Header() {
  const { wishlist, recents } = useLibrary()
  const navClass = ({ isActive }: { isActive: boolean }) =>
    `text-sm transition ${isActive ? 'font-semibold text-brown' : 'text-ink/80 hover:text-brown'}`

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6">
        <Logo />
        <nav className="hidden items-center gap-9 md:flex">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className={navClass}>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="flex items-center gap-1">
          <IconLink to="/" label="Search">
            <SearchIcon />
          </IconLink>
          <IconLink to="/recents" label="Recents" count={recents.length}>
            <ClockIcon />
          </IconLink>
          <IconLink to="/wishlist" label="Wishlist" count={wishlist.length}>
            <HeartIcon />
          </IconLink>
        </div>
      </div>
    </header>
  )
}

function IconLink({
  to,
  label,
  count,
  children,
}: {
  to: string
  label: string
  count?: number
  children: ReactNode
}) {
  return (
    <Link
      to={to}
      aria-label={count ? `${label} (${count})` : label}
      className="relative flex size-10 items-center justify-center rounded-full text-ink hover:bg-cream"
    >
      {children}
      {Boolean(count) && (
        <span className="absolute top-1 right-0.5 flex min-w-4 items-center justify-center rounded-full bg-brown px-1 text-[10px] leading-4 font-medium text-white">
          {count}
        </span>
      )}
    </Link>
  )
}

function MobileTabBar() {
  const tab = ({ isActive }: { isActive: boolean }) =>
    `flex size-12 items-center justify-center rounded-full transition ${
      isActive ? 'bg-white text-brown' : 'text-white/80'
    }`
  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-4 z-40 mx-auto flex w-fit items-center gap-3 rounded-full bg-ink p-2 shadow-[var(--shadow-card)] md:hidden"
    >
      <NavLink to="/" end className={tab} aria-label="Home">
        <HomeIcon />
      </NavLink>
      <NavLink to="/recents" className={tab} aria-label="Recents">
        <ClockIcon />
      </NavLink>
      <NavLink to="/wishlist" className={tab} aria-label="Wishlist">
        <HeartIcon />
      </NavLink>
    </nav>
  )
}

function Footer() {
  return (
    <footer className="mt-20 bg-brown text-white/80">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-12 sm:px-6 md:grid-cols-[2fr_1fr_1fr]">
        <div>
          <p className="text-2xl font-semibold text-white">
            Muse<span className="text-mustard">.</span>
          </p>
          <p className="mt-3 max-w-sm text-sm leading-relaxed">
            Show us one item. We find where it&rsquo;s cheapest and a whole marketplace of pieces
            in the same style.
          </p>
        </div>
        <div className="text-sm">
          <p className="mb-3 font-medium text-white">Explore</p>
          <ul className="space-y-2">
            <li><Link to="/" className="hover:text-white">Search</Link></li>
            <li><Link to="/recents" className="hover:text-white">Recents</Link></li>
            <li><Link to="/wishlist" className="hover:text-white">Wishlist</Link></li>
          </ul>
        </div>
        <p className="text-xs leading-relaxed">
          Muse links to listings on third-party retailers and resellers. Prices and availability
          are set by those sites and may change.
        </p>
      </div>
    </footer>
  )
}
