import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

// Force favicon refresh to prevent caching issues
const forceFaviconRefresh = () => {
  // Remove any existing favicon links that might be cached
  const existingFavicons = document.querySelectorAll('link[rel*="icon"]');
  existingFavicons.forEach(link => {
    if (link.getAttribute('href')?.includes('lovable.dev') ||
      link.getAttribute('href')?.includes('vite') ||
      link.getAttribute('href')?.includes('react')) {
      link.remove();
    }
  });

  // Force update all favicon links with timestamp
  const faviconLinks = document.querySelectorAll('link[rel*="icon"]');
  faviconLinks.forEach(link => {
    const href = link.getAttribute('href');
    if (href && href.includes('ella-favicon.svg')) {
      const newHref = href.split('?')[0] + '?v=' + Date.now();
      link.setAttribute('href', newHref);
    }
  });

  // Create new favicon link if none exists
  if (faviconLinks.length === 0) {
    const newFavicon = document.createElement('link');
    newFavicon.rel = 'icon';
    newFavicon.type = 'image/svg+xml';
    newFavicon.href = '/ella-favicon.svg?v=' + Date.now();
    document.head.appendChild(newFavicon);
  }
};

// Call on page load and after a delay
forceFaviconRefresh();
setTimeout(forceFaviconRefresh, 1000);
setTimeout(forceFaviconRefresh, 3000);

import { AuthProvider } from '@/context/AuthContext';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </React.StrictMode>,
)
