import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Extraction from './pages/Extraction'
import Runs from './pages/Runs'
import Rulebook from './pages/Rulebook'
import Approvals from './pages/Approvals'
import Agents from './pages/Agents'
import Reports from './pages/Reports'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/extraction" replace />} />
        <Route path="/extraction" element={<Extraction />} />
        <Route path="/runs" element={<Runs />} />
        <Route path="/rulebook" element={<Rulebook />} />
        <Route path="/approvals" element={<Approvals />} />
        <Route path="/agents" element={<Agents />} />
        <Route path="/agents/:runId" element={<Agents />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/reports/:runId" element={<Reports />} />
        <Route path="*" element={<Navigate to="/extraction" replace />} />
      </Route>
    </Routes>
  )
}
