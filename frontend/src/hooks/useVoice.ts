import { useState, useEffect, useCallback, useRef } from 'react';

interface UseVoiceOptions {
  language?: string;
  apiBase?: string;
  silenceTimeout?: number; // Time in ms to wait before auto-stopping (default 2000)
}

interface UseVoiceOptions {
  language?: string;
  apiBase?: string;
  silenceTimeout?: number;
  onTranscriptionComplete?: (result: { text: string; language: string }) => void;
}

interface UseVoiceReturn {
  isSupported: boolean;
  isRecording: boolean;
  transcript: string;
  interimTranscript: string;
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<{ text: string; language: string } | null>;
  error: string | null;
  volume: number;
}

export const useVoice = (options: UseVoiceOptions = {}): UseVoiceReturn => {
  const [isSupported, setIsSupported] = useState<boolean>(true);
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [transcript, setTranscript] = useState<string>('');
  const [interimTranscript, setInterimTranscript] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [volume, setVolume] = useState<number>(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const startTimeRef = useRef<number>(0);
  const activeMimeTypeRef = useRef<string>('audio/webm');

  // Silence Detection Refs
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const silenceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const isCurrentlyRecordingRef = useRef<boolean>(false);

  const stopResolverRef = useRef<((value: { text: string; language: string } | null) => void) | null>(null);

  const API_BASE = options.apiBase || import.meta.env.VITE_API_URL || 'http://localhost:8000';
  const SILENCE_THRESHOLD = 0.015; // Volume threshold for silence
  const SILENCE_DURATION = options.silenceTimeout || 2000; // 2 seconds of silence

  useEffect(() => {
    const isMediaRecorderSupported = !!window.MediaRecorder;
    const isGetUserMediaSupported = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);

    if (!isMediaRecorderSupported || !isGetUserMediaSupported) {
      setIsSupported(false);
    }
  }, []);

  const convertToWav = async (webmBlob: Blob): Promise<Blob> => {
    try {
      const arrayBuffer = await webmBlob.arrayBuffer();
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)({
        sampleRate: 16000
      });

      const decodePromise = audioContext.decodeAudioData(arrayBuffer);
      const timeoutPromise = new Promise((_, reject) => 
        setTimeout(() => reject(new Error('Audio decoding timed out')), 5000)
      );

      const audioBuffer = await Promise.race([decodePromise, timeoutPromise]) as AudioBuffer;
      const wavBuffer = audioBufferToWav(audioBuffer);
      audioContext.close();

      return new Blob([wavBuffer], { type: 'audio/wav' });
    } catch (err) {
      console.warn('WAV conversion failed, falling back to original blob:', err);
      return webmBlob;
    }
  };

  const audioBufferToWav = (buffer: AudioBuffer): ArrayBuffer => {
    const numChannels = buffer.numberOfChannels;
    const sampleRate = buffer.sampleRate;
    const format = 1;
    const bitDepth = 16;
    const bytesPerSample = bitDepth / 8;
    const blockAlign = numChannels * bytesPerSample;
    const byteRate = sampleRate * blockAlign;
    const dataSize = buffer.length * blockAlign;
    const headerSize = 44;
    const totalSize = headerSize + dataSize;

    const arrayBuffer = new ArrayBuffer(totalSize);
    const view = new DataView(arrayBuffer);

    const writeString = (offset: number, str: string) => {
      for (let i = 0; i < str.length; i++) {
        view.setUint8(offset + i, str.charCodeAt(i));
      }
    };

    writeString(0, 'RIFF');
    view.setUint32(4, totalSize - 8, true);
    writeString(8, 'WAVE');
    writeString(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, format, true);
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, byteRate, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, bitDepth, true);
    writeString(36, 'data');
    view.setUint32(40, dataSize, true);

    const channelData: Float32Array[] = [];
    for (let ch = 0; ch < numChannels; ch++) {
      channelData.push(buffer.getChannelData(ch));
    }

    let offset = 44;
    for (let i = 0; i < buffer.length; i++) {
      for (let ch = 0; ch < numChannels; ch++) {
        const sample = Math.max(-1, Math.min(1, channelData[ch][i]));
        view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7FFF, true);
        offset += 2;
      }
    }

    return arrayBuffer;
  };

  const processAudioData = async (audioBlob: Blob): Promise<{ text: string, language: string } | null> => {
    const duration = (Date.now() - startTimeRef.current) / 1000;

    if (duration < 0.5 || audioBlob.size < 1000) {
      setError('Recording too short. Please speak clearly.');
      setInterimTranscript('');
      return null;
    }

    try {
      setInterimTranscript('Optimizing audio...');
      const wavBlob = await convertToWav(audioBlob);

      const formData = new FormData();
      formData.append('audio', wavBlob, 'recording.wav');
      formData.append('language', options.language || 'auto');
      formData.append('model', 'saaras:v3');

      setInterimTranscript('Transcribing...');

      const response = await fetch(`${API_BASE}/qa/stt`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Transcription service error');
      }

      const data = await response.json();
      if (data.text && data.text.trim()) {
        const resultText = data.text.trim();
        const resultLang = data.language || 'en-IN';
        setTranscript(resultText);
        setInterimTranscript('');

        // Trigger callback if provided
        if (options.onTranscriptionComplete) {
          options.onTranscriptionComplete({ text: resultText, language: resultLang });
        }

        return { text: resultText, language: resultLang };
      } else {
        setError('No speech detected.');
        return null;
      }
    } catch (err: any) {
      setError('Processing failed.');
      return null;
    } finally {
      setInterimTranscript('');
      audioChunksRef.current = [];
    }
  };

  // Function to monitor volume and detect silence
  const monitorVolume = useCallback(() => {
    if (!analyserRef.current || !isCurrentlyRecordingRef.current) return;

    const dataArray = new Uint8Array(analyserRef.current.fftSize);
    analyserRef.current.getByteTimeDomainData(dataArray);

    // Calculate volume (RMS)
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
      const amplitude = (dataArray[i] - 128) / 128;
      sum += amplitude * amplitude;
    }
    const currentVolume = Math.sqrt(sum / dataArray.length);
    setVolume(currentVolume);

    // Silence detection logic
    if (currentVolume < SILENCE_THRESHOLD) {
      if (!silenceTimerRef.current) {
        silenceTimerRef.current = setTimeout(() => {
          stopRecording();
        }, SILENCE_DURATION);
      }
    } else {
      // User is speaking, reset the timer
      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current);
        silenceTimerRef.current = null;
      }
    }

    animationFrameRef.current = requestAnimationFrame(monitorVolume);
  }, []);

  const stopRecording = useCallback((): Promise<{ text: string, language: string } | null> => {
    return new Promise((resolve) => {
      if (!mediaRecorderRef.current || mediaRecorderRef.current.state === 'inactive') {
        resolve(null);
        return;
      }

      isCurrentlyRecordingRef.current = false;
      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current);
        silenceTimerRef.current = null;
      }
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }

      stopResolverRef.current = resolve;
      setIsRecording(false);
      setVolume(0);
      setInterimTranscript('Processing...');
      mediaRecorderRef.current.stop();
    });
  }, []);

  const startRecording = useCallback(async () => {
    setError(null);
    setTranscript('');
    setInterimTranscript('');
    audioChunksRef.current = [];

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: { echoCancellation: true, noiseSuppression: true, sampleRate: 16000 } 
      });

      streamRef.current = stream;

      // Initialize Audio Analysis for Silence Detection
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);

      audioContextRef.current = audioContext;
      analyserRef.current = analyser;

      let mimeType = 'audio/webm;codecs=opus';
      if (MediaRecorder.isTypeSupported('audio/webm')) mimeType = 'audio/webm';
      else if (MediaRecorder.isTypeSupported('audio/mp4')) mimeType = 'audio/mp4';

      activeMimeTypeRef.current = mimeType;
      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) audioChunksRef.current.push(event.data);
      };

      mediaRecorder.onstop = async () => {
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(track => track.stop());
          streamRef.current = null;
        }
        if (audioContextRef.current) {
          audioContextRef.current.close();
        }

        const audioBlob = new Blob(audioChunksRef.current, { type: activeMimeTypeRef.current });
        const result = await processAudioData(audioBlob);

        if (stopResolverRef.current) {
          stopResolverRef.current(result);
          stopResolverRef.current = null;
        }
      };

      mediaRecorder.start(100);
      startTimeRef.current = Date.now();
      setIsRecording(true);
      isCurrentlyRecordingRef.current = true;
      setInterimTranscript('Listening...');

      monitorVolume();

    } catch (err: any) {
      setError('Mic access denied.');
    }
  }, [monitorVolume]);

  useEffect(() => {
    return () => {
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
      if (audioContextRef.current) audioContextRef.current.close();
    };
  }, []);

  return {
    isSupported,
    isRecording,
    transcript,
    interimTranscript,
    startRecording,
    stopRecording,
    error,
    volume,
  };
};

