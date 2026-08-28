import { RouteObject } from 'react-router-dom';
import KYCHome from './pages/KYCHome';
import KYCRepos from './pages/KYCRepos';
import KYCRepoDetail from './pages/KYCRepoDetail';
import KYCQuestionAndAnswer from './pages/KYCQuestionAndAnswer';
import KYCArchitecture from './pages/KYCArchitecture';
import KYCOnboarding from './pages/KYCOnboarding';

// Children of the host's protected /app route (DashboardLayout + auth gate). Paths are relative.
export const kycRoutes: RouteObject[] = [
  { path: 'legend',                element: <KYCHome /> },
  { path: 'legend/repos',          element: <KYCRepos /> },
  { path: 'legend/repos/:id',      element: <KYCRepoDetail /> },
  { path: 'legend/repos/:id/qa',   element: <KYCQuestionAndAnswer /> },
  { path: 'legend/repos/:id/arch', element: <KYCArchitecture /> },
  { path: 'legend/repos/:id/tour', element: <KYCOnboarding /> },
];
