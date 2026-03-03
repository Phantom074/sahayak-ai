import React, { useState, useEffect } from 'react';
import { LanguageProvider, useLanguage } from './contexts/LanguageContext';
import './App.css';
import ChatInterface from './components/ChatInterface';
import Header from './components/Header';
import LanguageSelector from './components/LanguageSelector';

// Wrapper component to access language context
const AppContent = () => {
  const { language, setLanguage } = useLanguage();
  const [userProfile, setUserProfile] = useState({
    name: '',
    phone: '',
    district: '',
    state: ''
  });

  return (
    <div className="App">
      <div className="app-container">
        <Header />
        <main className="main-content">
          <ChatInterface 
            userProfile={userProfile}
            setUserProfile={setUserProfile}
          />
        </main>
      </div>
    </div>
  );
};

function App() {
  return (
    <LanguageProvider>
      <AppContent />
    </LanguageProvider>
  );
}

export default App;