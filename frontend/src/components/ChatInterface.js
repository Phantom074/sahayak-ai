import React, { useState, useRef, useEffect } from 'react';
import { useLanguage } from '../contexts/LanguageContext';
import Message from './Message';
import TextInput from './TextInput';
import VoiceInput from './VoiceInput';
import ApiService from '../utils/ApiService';
import '../styles/ChatInterface.css';

const ChatInterface = ({ userProfile, setUserProfile }) => {
  const { language } = useLanguage();
  const [messages, setMessages] = useState([
    {
      id: 1,
      text: language === 'hi' 
        ? 'नमस्ते! मैं सहायक एआई हूं। मैं आपको सरकारी योजनाओं के बारे में जानकारी देने में मदद कर सकता हूं। क्या आप किसी विशेष योजना के बारे में जानना चाहते हैं?' 
        : 'Hello! I am Sahayak AI. I can help you with information about government schemes. Would you like to know about any specific scheme?',
      sender: 'bot',
      timestamp: new Date()
    }
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Initialize session when component mounts
  useEffect(() => {
    const initializeSession = async () => {
      try {
        const sessionData = await ApiService.startNewSession({
          language_preference: language,
          channel: 'web'
        });
        setSessionId(sessionData.session_id);
      } catch (error) {
        console.error('Error initializing session:', error);
      }
    };

    initializeSession();
  }, [language]);

  const handleSendMessage = async (text) => {
    if (!text.trim()) return;

    // Add user message
    const userMessage = {
      id: Date.now(),
      text: text,
      sender: 'user',
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    try {
      // Call the backend API
      const response = await ApiService.sendMessage(text, language, sessionId);
      
      // Add bot response
      const botResponse = {
        id: Date.now() + 1,
        text: response.response_text,
        sender: 'bot',
        timestamp: new Date(),
        scheme_details: response.scheme_details,
        suggested_schemes: response.suggested_schemes
      };
      
      setMessages(prev => [...prev, botResponse]);
    } catch (error) {
      const errorMessage = {
        id: Date.now() + 1,
        text: language === 'hi'
          ? 'क्षमा करें, आपकी जांच पूरी करने में समस्या हुई। कृपया पुनः प्रयास करें।'
          : 'Sorry, there was an issue processing your request. Please try again.',
        sender: 'bot',
        timestamp: new Date(),
        isError: true
      };
      
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleVoiceMessage = async (transcript) => {
    if (!transcript.trim()) return;
    
    // Add user message
    const userMessage = {
      id: Date.now(),
      text: transcript,
      sender: 'user',
      timestamp: new Date(),
      isVoice: true
    };
    
    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    try {
      // Call the backend API with the voice transcript
      const response = await ApiService.sendMessage(transcript, language, sessionId);
      
      // Add bot response
      const botResponse = {
        id: Date.now() + 1,
        text: response.response_text,
        sender: 'bot',
        timestamp: new Date(),
        scheme_details: response.scheme_details,
        suggested_schemes: response.suggested_schemes
      };
      
      setMessages(prev => [...prev, botResponse]);
    } catch (error) {
      const errorMessage = {
        id: Date.now() + 1,
        text: language === 'hi'
          ? 'क्षमा करें, आपकी जांच पूरी करने में समस्या हुई। कृपया पुनः प्रयास करें।'
          : 'Sorry, there was an issue processing your request. Please try again.',
        sender: 'bot',
        timestamp: new Date(),
        isError: true
      };
      
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="chat-interface glass-container fade-in">
      <div className="chat-messages">
        {messages.map((message) => (
          <Message 
            key={message.id} 
            message={message} 
            language={language} 
          />
        ))}
        {isLoading && (
          <div className="loading-message slide-in">
            <div className="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
            <div className="typing-text">
              {language === 'hi' ? 'एआई सोच रहा है...' : 'AI is thinking...'}
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      <div className="chat-input-section">
        <VoiceInput 
          onTranscript={handleVoiceMessage} 
          language={language}
          disabled={isLoading}
        />
        <TextInput 
          onSend={handleSendMessage} 
          language={language}
          disabled={isLoading}
        />
      </div>
    </div>
  );
};

export default ChatInterface;