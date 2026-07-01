import './Layout.css';
import { useState } from 'react';
import { Outlet, Link } from 'react-router-dom';
import Sidebar from './Sidebar';
import { PanelLeftOpen, Zap } from 'lucide-react';

export default function Layout({ sets, onCreateSet }) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  return (
    <div className={`sp-layout ${!isSidebarOpen ? 'sp-layout--collapsed' : ''}`}>
      {isSidebarOpen ? (
        <Sidebar
          sets={sets}
          onCreateSet={onCreateSet}
          isOpen={isSidebarOpen}
          onClose={() => setIsSidebarOpen(false)}
        />
      ) : (
        <div className="sp-layout__rail">
          <Link to="/" className="sp-layout__rail-logo" title="Ana Sayfa">
            <Zap size={16} />
          </Link>
          <button
            className="sp-layout__rail-expand"
            onClick={() => setIsSidebarOpen(true)}
            title="Menüyü Aç"
          >
            <PanelLeftOpen size={16} />
          </button>
        </div>
      )}
      <main className="sp-layout__main">
        <Outlet />
      </main>
    </div>
  );
}
