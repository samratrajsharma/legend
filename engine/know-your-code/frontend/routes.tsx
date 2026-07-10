import { RouteObject } from 'react-router-dom';
import KYCHome from './pages/KYCHome';
import KYCRepos from './pages/KYCRepos';
import KYCRepoDetail from './pages/KYCRepoDetail';
import KYCQuestionAndAnswer from './pages/KYCQuestionAndAnswer';
import KYCArchitecture from './pages/KYCArchitecture';
import KYCOnboarding from './pages/KYCOnboarding';

// Children of the host's protected /app route (DashboardLayout + auth gate). Paths are relative.
export const kycRoutes: RouteObject[] = [
  { path: 'know-your-code',                element: <KYCHome /> },
  { path: 'know-your-code/repos',          element: <KYCRepos /> },
  { path: 'know-your-code/repos/:id',      element: <KYCRepoDetail /> },
  { path: 'know-your-code/repos/:id/qa',   element: <KYCQuestionAndAnswer /> },
  { path: 'know-your-code/repos/:id/arch', element: <KYCArchitecture /> },
  { path: 'know-your-code/repos/:id/tour', element: <KYCOnboarding /> },
];
