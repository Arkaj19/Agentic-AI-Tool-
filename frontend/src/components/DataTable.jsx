import { ArrowDown, ArrowUp } from 'lucide-react'

// Scrollable table with a sticky header. columns: [{ key, label, sub?, align?, render? }]
export default function DataTable({ columns, rows, sort, onSort, rowKey = (_, i) => i, rowClass, maxHeight = '60vh',
  dense = true, empty = 'No rows', blank = '·' }) {
  return (
    <div className="overflow-auto rounded-lg border border-slate-200 scroll-thin" style={{ maxHeight }}>
      <table className="min-w-full border-separate border-spacing-0 text-left text-[13px]">
        <thead>
          <tr>
            {columns.map((c) => {
              const active = sort?.key === c.key
              return (
                <th key={c.key}
                  onClick={onSort && c.sortable !== false ? () => onSort(c.key) : undefined}
                  className={`sticky top-0 z-10 whitespace-nowrap border-b border-slate-200 bg-slate-50 px-3 py-2 font-semibold text-slate-700 ${onSort && c.sortable !== false ? 'cursor-pointer select-none hover:bg-slate-100' : ''} ${c.align === 'right' ? 'text-right' : ''}`}>
                  <div className={`flex items-center gap-1 ${c.align === 'right' ? 'justify-end' : ''}`}>
                    <span>{c.label}</span>
                    {active && (sort.desc ? <ArrowDown className="h-3 w-3" /> : <ArrowUp className="h-3 w-3" />)}
                  </div>
                  {c.sub !== undefined && (
                    <div className={`mono font-normal ${c.sub ? 'text-brand-700' : 'text-slate-300'}`}>{c.sub || '—'}</div>
                  )}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr><td colSpan={columns.length} className="px-3 py-10 text-center text-slate-500">{empty}</td></tr>
          )}
          {rows.map((r, i) => (
            <tr key={rowKey(r, i)} className={`group ${rowClass ? rowClass(r, i) : ''}`}>
              {columns.map((c, ci) => {
                const v = c.render ? c.render(r, i) : (Array.isArray(r) ? r[ci] : r[c.key])
                return (
                  <td key={c.key}
                    className={`whitespace-nowrap border-b border-slate-100 px-3 ${dense ? 'py-1.5' : 'py-2.5'} group-hover:bg-navy-50/60 ${c.align === 'right' ? 'text-right tabular-nums' : ''} ${typeof c.className === 'function' ? c.className(r) : (c.className || '')}`}>
                    {v === '' || v === null || v === undefined ? (blank && <span className="text-slate-300">{blank}</span>) : v}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
