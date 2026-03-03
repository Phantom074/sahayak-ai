import React, { useState, useRef, useEffect } from 'react';
import { useLanguage } from '../contexts/LanguageContext';
import { FaMicrophone, FaStop, FaPlay, FaPause, FaVolumeUp } from 'react-icons/fa';
import '../styles/VoiceInput.css';

const VoiceInput = ({ onTranscript, language, disabled }) => {
  const { language: contextLanguage } = useLanguage();
  const [isRecording, setIsRecording] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [audioUrl, setAudioUrl] = useState(null);
  const [recordingTime, setRecordingTime] = useState(0);
  const [permissionDenied, setPermissionDenied] = useState(false);
  
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerRef = useRef(null);
  const audioRef = useRef(null);

  const texts = {
    en: {
      record: 'Hold to Record',
      stop: 'Release to Stop',
      play: 'Play Response',
      pause: 'Pause',
      error: 'Microphone access denied. Please enable microphone permission in your browser settings.',
      unavailable: 'Speech recognition not supported in this browser.'
    },
    hi: {
      record: 'रकड करने के लिए दबाएंरखें',
      stop: 'रोकने केलिए छोड़ं',
      play: 'प्रतिक्रिया चलाएं',
      pause: 'रोकं',
      error: 'माइक्रोफोन एकसस असवीकृत। कृपया अपने ब्राउज़र सेटिंगसं माइक्रोफोन अनुमति सक्षम करें।',
      unavailable: 'इस ब्राउज़र में स्पीच रिकग्निशन समरथितनहीं है।'
    }
  };

  const currentText = texts[language || contextLanguage] || texts.en;

  // Check if speech recognition is supported
  const isSpeechRecognitionSupported = () => {
    return 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;
  };

  // Initialize speech recognition
  const initializeSpeechRecognition = () => {
    if (!isSpeechRecognitionSupported()) {
      alert(currentText.unavailable);
      return null;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = language === 'hi' ? 'hi-IN' : 'en-IN';

    return recognition;
  };

  // Handle recording start
  const startRecording = async () => {
    if (disabled) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (event) => {
        audioChunksRef.current.push(event.data);
      };

      mediaRecorderRef.current.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        const audioUrl = URL.createObjectURL(audioBlob);
        setAudioUrl(audioUrl);

        // Perform speech recognition
        const recognition = initializeSpeechRecognition();
        if (recognition) {
          recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            onTranscript(transcript);
          };

          recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            if (event.error === 'no-speech' || event.error === 'audio-capture') {
              onTranscript(language === 'hi' ? 'कया आप किसी योजना के बारे में जाननाचाहते हैं?' : 'Do you want to know about any scheme?');
            }
          };

          recognition.start();
        } else {
          onTranscript(language === 'hi' ? 'आवाज़ से संबंधित कमांड संसाधित कया जा रहा है' : 'Processing voice command');
        }

        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorderRef.current.start();
      setIsRecording(true);
      
      // Start timer
      setRecordingTime(0);
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);
    } catch (err) {
      console.error('Error accessing microphone:', err);
      if (err.name === 'NotAllowedError') {
        setPermissionDenied(true);
      }
    }
  };

  // Handle recording stop
  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
  };

  // Handle play/pause of response audio
  const togglePlayback = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
        setIsPlaying(false);
      } else {
        audioRef.current.play();
        setIsPlaying(true);
      }
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, []);

  // Format time for display
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="voice-input-container">
      {permissionDenied && (
        <div className="permission-error">
          {currentText.error}
        </div>
      )}
      
      <div className="voice-controls">
        <button
          className={`record-button ${isRecording ? 'recording pulse' : ''} ${disabled ? 'disabled' : ''}`}
          onMouseDown={startRecording}
          onMouseUp={stopRecording}
          onMouseLeave={stopRecording}
          onTouchStart={startRecording}
          onTouchEnd={stopRecording}
          disabled={disabled || !isSpeechRecognitionSupported()}
          title={isRecording ? currentText.stop : currentText.record}
        >
          {isRecording ? (
            <>
              <FaStop className="stop-icon" /> 
              <span className="recording-time">{formatTime(recordingTime)}</span>
            </>
          ) : (
            <FaMicrophone className="mic-icon" />
          )}
        </button>
        
        {audioUrl && (
          <button
            className={`playback-button ${isPlaying ? 'playing' : ''}`}
            onClick={togglePlayback}
            title={isPlaying ? currentText.pause : currentText.play}
          >
            {isPlaying ? <FaPause /> : <FaPlay />}
          </button>
        )}
      </div>
      
      {/* Hidden audio element for playback */}
      {audioUrl && (
        <audio
          ref={audioRef}
          src={audioUrl}
          onEnded={() => setIsPlaying(false)}
          preload="metadata"
        />
      )}
    </div>
  );
};

export default VoiceInput;