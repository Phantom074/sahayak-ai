import React, { createContext, useContext, useState, useEffect } from 'react';

const LanguageContext = createContext();

export const useLanguage = () => {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
};

export const LanguageProvider = ({ children }) => {
  const [language, setLanguage] = useState('hi'); // Default to Hindi

  // Load saved language preference from localStorage
  useEffect(() => {
    const savedLanguage = localStorage.getItem('sahayak-lang');
    if (savedLanguage) {
      setLanguage(savedLanguage);
    } else {
      // Detect user's language preference
      const browserLang = navigator.language.substring(0, 2);
      if (browserLang === 'hi' || browserLang === 'en') {
        setLanguage(browserLang);
      }
    }
  }, []);

  // Save language preference to localStorage
  useEffect(() => {
    localStorage.setItem('sahayak-lang', language);
    
    // Update document language attribute
    document.documentElement.lang = language;
  }, [language]);

  const value = {
    language,
    setLanguage,
    isHindi: language === 'hi',
    isEnglish: language === 'en'
  };

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
};