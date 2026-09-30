export const num = (n) => (n === null || n === undefined || Number.isNaN(n) ? '–' : Number(n).toLocaleString('en-US'))

export function bytes(n) {
  if (!n && n !== 0) return '–'
  if (n < 1024) return `${n} B`
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 ** 2).toFixed(1)} MB`
}

export function dateTime(iso) {
  if (!iso) return '–'
  const d = new Date(iso)
  return d.toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}

export function time(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function ago(iso) {
  if (!iso) return '–'
  const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 45) return 'just now'
  if (s < 3600) return `${Math.round(s / 60)} min ago`
  if (s < 86400) return `${Math.round(s / 3600)} h ago`
  return `${Math.round(s / 86400)} d ago`
}

export function duration(start, end) {
  if (!start) return '–'
  const s = Math.max(0, Math.round(((end ? new Date(end) : new Date()) - new Date(start)) / 1000))
  if (s < 60) return `${s}s`
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`
}

export const pct = (a, b) => (b ? Math.round((a / b) * 100) : 0)

export const shortRun = (id) => (id ? id.replace('RUN-MARC-', '').replace(/^(\d{8})T(\d{4})\d{2}-/, '$1 $2 · ') : '')
