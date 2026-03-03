import React from 'react';
import { useLanguage } from '../contexts/LanguageContext';
import '../styles/LanguageSelector.css';

const LanguageSelector = ({ currentLanguage, onLanguageChange }) => {
  const { language, setLanguage } = useLanguage();
  const languages = [
    { code: 'hi', name: 'हिंदी', nativeName: 'Hindi' },
    { code: 'en', name: 'English', nativeName: 'English' },
    { code: 'bn', name: 'বাংলা', nativeName: 'Bengali' },
    { code: 'te', name: 'తెలుగు', nativeName: 'Telugu' },
    { code: 'ta', name: 'தமிழ்', nativeName: 'Tamil' },
    { code: 'mr', name: 'मराठी', nativeName: 'Marathi' },
    { code: 'gu', name: 'ગુજરાતી', nativeName: 'Gujarati' },
    { code: 'kn', name: 'ಕನ್ನಡ', nativeName: 'Kannada' },
    { code: 'ml', name: 'മലയാളം', nativeName: 'Malayalam' },
    { code: 'pa', name: 'ਪੰਜਾਬੀ', nativeName: 'Punjabi' }
  ];

  const currentLang = languages.find(lang => lang.code === language);

  const handleLanguageChange = (e) => {
    const newLanguage = e.target.value;
    setLanguage(newLanguage);
    if (onLanguageChange) {
      onLanguageChange(newLanguage);
    }
  };

  return (
    <div className="language-selector">
      <select 
        value={language} 
        onChange={handleLanguageChange}
        className="language-dropdown"
      >
        {languages.map((lang) => (
          <option key={lang.code} value={lang.code}>
            {lang.name} ({lang.nativeName})
          </option>
        ))}
      </select>
      <div className="current-language">
        {currentLang ? `${currentLang.name} (${currentLang.nativeName})` : 'Select Language'}
      </div>
    </div>
  );
};

export default LanguageSelector;