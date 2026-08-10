import { Outlet } from 'react-router-dom'

import { Header } from '@/components/layout/header'
import { Sidebar } from '@/components/layout/sidebar'

export function AppLayout() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-950">
      <Sidebar />
      <div className="lg:pl-64">
        <Header />
        <main className="px-5 py-8 lg:px-8"><Outlet /></main>
      </div>
    </div>
  )
}
