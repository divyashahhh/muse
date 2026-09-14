import { BrowserRouter, Route, Routes } from 'react-router'

import { Layout } from './components/Layout'
import { LibraryProvider } from './library/LibraryContext'
import { HomePage } from './pages/HomePage'
import { ItemPage } from './pages/ItemPage'
import { RecentsPage } from './pages/RecentsPage'
import { WishlistPage } from './pages/WishlistPage'

export default function App() {
  return (
    <BrowserRouter>
      <LibraryProvider>
        <Layout>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/items/:id" element={<ItemPage />} />
            <Route path="/recents" element={<RecentsPage />} />
            <Route path="/wishlist" element={<WishlistPage />} />
            <Route
              path="*"
              element={<p className="mx-auto max-w-7xl px-6 py-16 text-muted">Page not found.</p>}
            />
          </Routes>
        </Layout>
      </LibraryProvider>
    </BrowserRouter>
  )
}
