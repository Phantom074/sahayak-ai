import React, { useState } from 'react';
import { useLanguage } from '../contexts/LanguageContext';
import { FaPaperPlane } from 'react-icons/fa';
import '../styles/TextInput.css';

const TextInput = ({ onSend, language, disabled }) => {
  const { language: contextLanguage } = useLanguage();
  const [inputText, setInputText] = useState('');

  const texts = {
    en: {
      placeholder: 'Type your message...',
      send: 'Send'
    },
    hi: {
      placeholder: 'अपना संदेश लिखें...',
      send: 'भेजें'
    }
  };

  const currentText = texts[language || contextLanguage] || texts.en;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (inputText.trim() && !disabled) {
      onSend(inputText);
      setInputText('');
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form className="text-input-form" onSubmit={handleSubmit}>
      <div className="input-container">
        <textarea
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder={currentText.placeholder}
          disabled={disabled}
          className="text-input"
          rows="1"
        />
        <button 
          type="submit" 
          className="send-button"
          disabled={!inputText.trim() || disabled}
        >
          <FaPaperPlane />
        </button>
      </div>
    </form>
  );
};

export default TextInput;