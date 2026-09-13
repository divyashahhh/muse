import { BrowserRouter, Link, NavLink, Route, Routes } from 'react-router'

import { HomePage } from './pages/HomePage'
import { ItemPage } from './pages/ItemPage'
import { SavedPage } from './pages/SavedPage'
import { SavedProvider, useSaved } from './saved/SavedContext'

export default function App() {
  return (
    <BrowserRouter>
      <SavedProvider>
        <div className="flex min-h-svh flex-col">
          <Header />
          <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-10 sm:py-16">
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/items/:id" element={<ItemPage />} />
              <Route path="/saved" element={<SavedPage />} />
              <Route path="*" element={<p className="text-muted">Page not found.</p>} />
            </Routes>
          </main>
          <footer className="border-t border-line">
            <p className="mx-auto max-w-6xl px-6 py-6 text-xs leading-relaxed text-muted">
              Muse links to listings on third-party retailers and resellers. Prices and availability
              are set by those sites and may change.
            </p>
          </footer>
        </div>
      </SavedProvider>
    </BrowserRouter>
  )
}

function Header() {
  const { items } = useSaved()
  const count = (list: string) => items.filter((s) => s.list === list).length
  const navClass = ({ isActive }: { isActive: boolean }) =>
    `text-sm ${isActive ? 'font-semibold' : 'text-muted hover:text-ink'}`

  return (
    <header className="border-b border-line">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <Link to="/" className="font-display text-2xl italic tracking-tight">
          muse
        </Link>
        <nav className="flex items-center gap-5">
          <NavLink to="/" end className={navClass}>
            Search
          </NavLink>
          <NavLink to="/saved?list=wishlist" className={navClass}>
            Wishlist ({count('wishlist')})
          </NavLink>
          <NavLink to="/saved?list=bag" className={navClass}>
            Bag ({count('bag')})
          </NavLink>
        </nav>
      </div>
    </header>
  )
}
