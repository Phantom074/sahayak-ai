import { useState, useEffect, useCallback } from 'react';

const useSpeechSynthesis = () => {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [voices, setVoices] = useState([]);
  const [currentVoice, setCurrentVoice] = useState(null);
  const [volume, setVolume] = useState(1);
  const [rate, setRate] = useState(1);
  const [pitch, setPitch] = useState(1);

  // Load available voices
  useEffect(() => {
    const loadVoices = () => {
      const availableVoices = window.speechSynthesis.getVoices();
      setVoices(availableVoices);

      // Try to find appropriate voices for Hindi and English
      const hindiVoice = availableVoices.find(voice => 
        voice.lang.includes('hi') || voice.name.toLowerCase().includes('hindi')
      );
      const englishVoice = availableVoices.find(voice => 
        voice.lang.includes('en') || voice.name.toLowerCase().includes('english')
      );

      // Set default voice (prefer Hindi if available, otherwise English)
      setCurrentVoice(hindiVoice || englishVoice || availableVoices[0]);
    };

    // Initial load
    loadVoices();

    // Chrome loads voices asynchronously
    window.speechSynthesis.onvoiceschanged = loadVoices;

    return () => {
      window.speechSynthesis.onvoiceschanged = null;
    };
  }, []);

  // Speak function
  const speak = useCallback((text, lang = 'hi-IN') => {
    if (!window.speechSynthesis) {
      console.warn('Speech synthesis not supported in this browser');
      return;
    }

    // Cancel any ongoing speech
    if (window.speechSynthesis.speaking) {
      window.speechSynthesis.cancel();
    }

    if (!text || typeof text !== 'string') {
      return;
    }

    const utterance = new SpeechSynthesisUtterance(text);
    
    // Set language
    utterance.lang = lang;
    
    // Set voice
    if (currentVoice) {
      utterance.voice = currentVoice;
    }
    
    // Set speech parameters
    utterance.volume = volume;
    utterance.rate = rate;
    utterance.pitch = pitch;

    // Event handlers
    utterance.onstart = () => {
      setIsSpeaking(true);
    };

    utterance.onend = () => {
      setIsSpeaking(false);
    };

    utterance.onerror = (event) => {
      console.error('Speech synthesis error:', event);
      setIsSpeaking(false);
    };

    // Speak the text
    window.speechSynthesis.speak(utterance);
  }, [currentVoice, volume, rate, pitch]);

  // Pause function
  const pause = useCallback(() => {
    if (window.speechSynthesis.speaking) {
      window.speechSynthesis.pause();
      setIsSpeaking(false);
    }
  }, []);

  // Resume function
  const resume = useCallback(() => {
    if (window.speechSynthesis.paused) {
      window.speechSynthesis.resume();
      setIsSpeaking(true);
    }
  }, []);

  // Cancel function
  const cancel = useCallback(() => {
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
  }, []);

  // Change voice function
  const setVoice = useCallback((voiceName) => {
    const voice = voices.find(v => v.name === voiceName);
    if (voice) {
      setCurrentVoice(voice);
    }
  }, [voices]);

  return {
    isSpeaking,
    voices,
    currentVoice,
    volume,
    rate,
    pitch,
    speak,
    pause,
    resume,
    cancel,
    setVoice,
    setVolume,
    setRate,
    setPitch
  };
};

export default useSpeechSynthesis;