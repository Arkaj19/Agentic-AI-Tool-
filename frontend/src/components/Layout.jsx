import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import {
  BookOpenText, Bot, Check, Database, FileBarChart2, History, Pencil, ShieldCheck,
} from 'lucide-react'
import { useApp } from '../lib/app-context'
import { Toasts } from './ui'

const NAV = [
  { to: '/extraction', label: 'Data Extraction', icon: Database },
  { to: '/runs', label: 'Runs', icon: History },
  { to: '/rulebook', label: 'Rulebook', icon: BookOpenText },
  { to: '/approvals', label: 'Approvals', icon: ShieldCheck, badge: 'pending' },
  { to: '/agents', label: 'Agents', icon: Bot },
  { to: '/reports', label: 'Reports', icon: FileBarChart2 },
]

function UserBox() {
  const { user, setUser } = useApp()
  const [edit, setEdit] = useState(false)
  const [val, setVal] = useState(user)
  if (edit) {
    return (
      <form className="flex gap-1" onSubmit={(e) => { e.preventDefault(); setUser(val.trim() || 'Consultant'); setEdit(false) }}>
        <input autoFocus value={val} onChange={(e) => setVal(e.target.value)}
          className="w-full rounded-md border border-white/20 bg-white/10 px-2 py-1 text-xs text-white outline-none" />
        <button className="rounded-md bg-white/15 px-2 text-white"><Check className="h-3.5 w-3.5" /></button>
      </form>
    )
  }
  return (
    <button onClick={() => { setVal(user); setEdit(true) }} className="group flex w-full items-center gap-2 text-left">
      <span className="flex h-7 w-7 items-center justify-center rounded-full bg-brand-500 text-xs font-bold text-white">
        {user.slice(0, 1).toUpperCase()}
      </span>
      <span className="min-w-0 flex-1 truncate text-xs text-white/80">{user}</span>
      <Pencil className="h-3 w-3 text-white/40 group-hover:text-white/80" />
    </button>
  )
}

function Sidebar() {
  const { pending } = useApp()
  return (
    <aside className="flex w-60 shrink-0 flex-col bg-navy-900 text-white">
      <div className="px-6 pb-6 pt-6">
        <div className="text-xl font-bold tracking-tight">GyanSys</div>
        <div className="text-[13px] font-semibold leading-tight text-brand-400">Agentic Migration<br />Tool</div>
      </div>
      <nav className="flex-1 space-y-1 px-3">
        {NAV.map(({ to, label, icon: Icon, badge }) => (
          <NavLink key={to} to={to}
            className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${isActive
              ? 'bg-navy-700 text-white shadow-inner' : 'text-white/75 hover:bg-white/5 hover:text-white'}`}>
            <Icon className="h-4 w-4 opacity-90" />
            <span className="flex-1">{label}</span>
            {badge === 'pending' && pending > 0 && (
              <span className="rounded-full bg-brand-500 px-1.5 py-px text-[11px] font-bold text-white">{pending}</span>
            )}
          </NavLink>
        ))}
      </nav>
      <div className="m-3 space-y-3 rounded-xl bg-navy-800 p-4">
        <div>
          <div className="text-[11px] text-white/60">Current client</div>
          <div className="mt-0.5 text-[15px] font-semibold">Client 1</div>
          <div className="text-[11px] font-medium text-brand-400">Mode B · Embedded</div>
        </div>
        <div className="border-t border-white/10 pt-3"><UserBox /></div>
      </div>
    </aside>
  )
}

export function PageHeader({ title, actions, children }) {
  return (
    <div className="mb-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <div className="text-[13px] text-slate-500">Client 1 · Material (MARC)</div>
          <h1 className="mt-0.5 text-[28px] font-bold tracking-tight text-navy-950">{title}</h1>
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {children}
    </div>
  )
}

export default function Layout() {
  return (
    <div className="flex h-full">
      <Sidebar />
      <main className="min-w-0 flex-1 overflow-y-auto scroll-thin">
        <div className="mx-auto max-w-[1440px] px-8 py-6">
          <Outlet />
        </div>
      </main>
      <Toasts />
    </div>
  )
}
