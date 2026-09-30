import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, FileSpreadsheet, FolderOpen, Search } from 'lucide-react'
import { PageHeader } from '../components/Layout'
import DataTable from '../components/DataTable'
import FilePicker from '../components/FilePicker'
import { Card, Empty, ErrorBox, Loading, Pager, Segmented } from '../components/ui'
import { api } from '../lib/api'
import { useAsync } from '../lib/hooks'
import { bytes, dateTime } from '../lib/format'
import { useApp } from '../lib/app-context'

function Preview({ path }) {
  const [offset, setOffset] = useState(0)
  const [cols, setCols] = useState('key')
  const [q, setQ] = useState('')
  const [query, setQuery] = useState('')
  const limit = 50
  useEffect(() => { const t = setTimeout(() => setQuery(q.trim()), 300); return () => clearTimeout(t) }, [q])
  useEffect(() => setOffset(0), [path, cols, query])
  const { data, loading, error, reload } = useAsync(() => api.table(path, { offset, limit, columns: cols, q: query }),
    [path, offset, cols, query])

  const columns = useMemo(() => (data?.columns || []).map((c, i) => ({
    key: c.label, label: c.label, sortable: false, render: (r) => r[i],
    className: c.field === 'MATNR' ? 'font-medium text-slate-900' : c.field === 'WERKS' ? 'font-semibold text-navy-800' : '',
  })), [data])

  if (error) return <ErrorBox error={error} onRetry={reload} />
  if (loading && !data) return <Loading label="Loading the file…" hint="The first time a file is opened it is downloaded from SharePoint, which can take about 20 seconds." />
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
          <input className="input w-56 pl-8" placeholder="Search material" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="ml-auto">
          <Segmented value={cols} onChange={setCols}
            options={[{ value: 'key', label: 'Main columns' }, { value: 'all', label: `All columns (${data.allColumns})` }]} />
        </div>
      </div>
      <div className={loading ? 'opacity-60 transition' : ''}>
        <DataTable columns={columns} rows={data.rows} maxHeight="60vh" />
        <div className="mt-2"><Pager offset={offset} limit={limit} total={data.total} onChange={setOffset} /></div>
      </div>
    </div>
  )
}

export default function Extraction() {
  const { marcFile, setMarcFile } = useApp()
  const [picker, setPicker] = useState(false)

  return (
    <>
      <PageHeader title="Data Extraction"
        actions={<>
          <button className="btn-outline" onClick={() => setPicker(true)}><FolderOpen className="h-4 w-4" />{marcFile ? 'Change file' : 'Select file'}</button>
          {marcFile && <Link to="/rulebook" className="btn-primary">Next: Rulebook <ArrowRight className="h-4 w-4" /></Link>}
        </>} />

      {!marcFile ? (
        <Card>
          <Empty icon={FolderOpen} title="Select the ECC file"
            action={<button className="btn-accent" onClick={() => setPicker(true)}><FolderOpen className="h-4 w-4" />Select from SharePoint</button>}>
            Pick the MARC extract from SharePoint to see a preview.
          </Empty>
        </Card>
      ) : (
        <Card bodyClass="p-0">
          <div className="flex items-center gap-3 border-b border-slate-100 px-5 py-3.5">
            <FileSpreadsheet className="h-5 w-5 text-emerald-600" />
            <div className="min-w-0">
              <div className="truncate font-semibold text-slate-900">{marcFile.name}</div>
              <div className="text-xs text-slate-500">{marcFile.path !== marcFile.name && <>{marcFile.path.slice(0, -marcFile.name.length - 1)} · </>}{bytes(marcFile.size)} · {dateTime(marcFile.modified)}</div>
            </div>
          </div>
          <div className="p-5"><Preview path={marcFile.path} /></div>
        </Card>
      )}

      <FilePicker open={picker} onClose={() => setPicker(false)} title="Select the ECC file"
        accept={['.xlsx', '.xls', '.xlsm', '.csv']} onPick={setMarcFile} />
    </>
  )
}
