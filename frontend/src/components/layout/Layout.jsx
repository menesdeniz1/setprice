import './Layout.css';
import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import { Menu, Zap } from 'lucide-react';

export default function Layout({ sets, onCreateSet }) {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  return (
    <div className="sp-layout">
      {/* Mobile Header */}
      <div className="sp-layout__mobile-header">
        <div className="sp-layout__mobile-logo">
          <Zap size={20} className="text-gradient" />
          <span className="text-gradient font-bold">SetPrice</span>
        </div>
        <button 
          className="sp-layout__mobile-menu-btn"
          onClick={() => setIsMobileMenuOpen(true)}
        >
          <Menu size={24} />
        </button>
      </div>

      <Sidebar 
        sets={sets} 
        onCreateSet={onCreateSet} 
        isOpen={isMobileMenuOpen}
        onClose={() => setIsMobileMenuOpen(false)}
      />
      <main className="sp-layout__main">
        <Outlet />
      </main>
    </div>
  );
}
