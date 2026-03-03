import React from 'react';
import { useLanguage } from '../contexts/LanguageContext';
import LanguageSelector from './LanguageSelector';
import '../styles/Header.css';

const Header = () => {
  const { language } = useLanguage();
  
  const texts = {
    en: {
      title: 'Sahayak AI',
      subtitle: 'Government Scheme Assistant'
    },
    hi: {
      title: 'सहयकएआई',
      subtitle: 'सरकारी योजना सहयता'
    }
  };

  const currentText = texts[language] || texts.hi;

  return (
    <header className="modern-header fade-in">
      <div className="header-logo">
        <div className="logo-circle">
          <span className="logo-text">SA</span>
        </div>
        <div className="header-text">
          <h1 className="header-title">{currentText.title}</h1>
          <p className="header-subtitle">{currentText.subtitle}</p>
        </div>
      </div>
      <LanguageSelector />
    </header>
  );
};

export default Header;