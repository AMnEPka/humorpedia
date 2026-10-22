import React, { Suspense } from 'react';
import { Outlet } from 'react-router-dom';
import Header from './Header';
import { useHtmlPilotNavigation } from '../utils/htmlPilot';
import Footer from './Footer';

const CorrectionSuggestionButton = React.lazy(() => import('./CorrectionSuggestionButton'));

export default function Layout() {
  useHtmlPilotNavigation();
  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <Header />
      <main className="flex-1">
        <Outlet />
      </main>
      <Suspense fallback={null}>
        <CorrectionSuggestionButton />
      </Suspense>
      <Footer />
    </div>
  );
}
