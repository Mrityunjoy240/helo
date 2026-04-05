import { useState, useEffect, useCallback } from 'react';

interface UseVoiceOptions {
  language?: string;
}

interface UseVoiceReturn {
  isSupported: boolean;
  transcript: string;
  interimTranscript: string;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
}

export const useVoice = (options: UseVoiceOptions = {}): UseVoiceReturn => {
  const [isSupported, setIsSupported] = useState<boolean>(true);
  const [transcript, setTranscript] = useState<string>('');
  const [interimTranscript, setInterimTranscript] = useState<string>('');
  const [recognition, setRecognition] = useState<any>(null);

  useEffect(() => {
    // Check if browser supports speech recognition
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setIsSupported(false);
      return;
    }

    const recognitionInstance = new SpeechRecognition();
    recognitionInstance.continuous = true;
    recognitionInstance.interimResults = true;
    recognitionInstance.lang = options.language || 'en-US';

    recognitionInstance.onresult = (event: any) => {
      let finalTranscript = '';
      let interimTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          finalTranscript += result[0].transcript;
        } else {
          interimTranscript += result[0].transcript;
        }
      }

      if (finalTranscript) {
        setTranscript(prev => prev + finalTranscript);
        setInterimTranscript('');
      } else {
        setInterimTranscript(interimTranscript);
      }
    };

    recognitionInstance.onerror = (event: any) => {
      console.error('Speech recognition error', event.error);
    };

    recognitionInstance.onend = () => {
      // Recognition ended - do not auto-restart
      console.log('Speech recognition ended');
    };

    setRecognition(recognitionInstance);

    return () => {
      if (recognitionInstance) {
        recognitionInstance.stop();
      }
    };
  }, [options.language]);

  const startRecording = useCallback(async () => {
    if (!recognition) {
      console.error('Speech recognition not supported');
      return;
    }

    try {
      // Reset transcripts
      setTranscript('');
      setInterimTranscript('');

      recognition.start();
    } catch (error) {
      console.error('Error starting speech recognition:', error);
    }
  }, [recognition]);

  const stopRecording = useCallback(() => {
    if (recognition) {
      recognition.stop();
    }
  }, [recognition]);

  return {
    isSupported,
    transcript,
    interimTranscript,
    startRecording,
    stopRecording,
  };
};