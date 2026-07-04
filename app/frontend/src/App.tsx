import { Routes, Route, Navigate } from 'react-router-dom';
import AppLayout from './layouts/AppLayout';
import Home from './pages/Home/Home';
import Overview from './pages/Overview/Overview';
import Timeline from './pages/Timeline/Timeline';
import Files from './pages/Files/Files';
import Diagrams from './pages/Diagrams/Diagrams';
import ApiDb from './pages/ApiDb/ApiDb';
import Ask from './pages/Ask/Ask';
import Track from './pages/Track/Track';
import Intel from './pages/Intel/Intel';
import Settings from './pages/Settings/Settings';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<AppLayout />}>
        <Route index element={<Home />} />
        <Route path="repos/:repoId/overview"  element={<Overview />} />
        <Route path="repos/:repoId/timeline"  element={<Timeline />} />
        <Route path="repos/:repoId/files"     element={<Files />} />
        <Route path="repos/:repoId/diagrams"  element={<Diagrams />} />
        <Route path="repos/:repoId/api-db"    element={<ApiDb />} />
        <Route path="repos/:repoId/ask"       element={<Ask />} />
        <Route path="repos/:repoId/track"     element={<Track />} />
        <Route path="repos/:repoId/intel"     element={<Intel />} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
