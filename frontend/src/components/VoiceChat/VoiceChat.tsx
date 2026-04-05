import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
    Box,
    Button,
    Paper,
    Typography,
    IconButton,
    CircularProgress,
    Chip,
    Alert,
    Container,
    TextField
} from '@mui/material';
import {
    Mic,
    MicOff,
    VolumeUp,
    Send,
    Chat as ChatIcon,
    Add as AddIcon
} from '@mui/icons-material';
import { useVoice } from '../../hooks/useVoice';
import { useNoiseCancellation } from '../../hooks/useNoiseCancellation';

interface Message {
    role: 'user' | 'assistant';
    content: string;
}

interface VoiceChatProps {
    conversationId: string | null;
    onConversationChange?: (id: string | null) => void;
    onNewChat?: () => void;
}

const VoiceChat: React.FC<VoiceChatProps> = ({
    conversationId,
    onConversationChange,
    onNewChat,
}) => {
    const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    // Toggle between 'llm-query' (prototype with Gemini) and 'hybrid-query' (local hybrid)
    const QUERY_ENDPOINT = '/qa/llm-query'; // Use '/qa/hybrid-query' for local hybrid
    const [isRecording, setIsRecording] = useState(false);
    const [messages, setMessages] = useState<Message[]>([]);
    const [isProcessing, setIsProcessing] = useState(false);
    const [textInput, setTextInput] = useState('');
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [health, setHealth] = useState<{ status: string; ollama_connected: boolean; gemini_available: boolean } | null>(null);
    const [feedbackType, setFeedbackType] = useState<'up' | 'down' | null>(null);
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [llmMode, setLlmMode] = useState(true); // Toggle for prototype

    const voice = useVoice({ language: 'en-US' });
    const noiseCanceller = useNoiseCancellation({
        enabled: true,
        noiseGateThreshold: -45,
        highPassFrequency: 120,
        noiseReduction: 0.4
    });

    useEffect(() => {
        if (!isSpeaking) return;
        if (isRecording && (voice.transcript || voice.interimTranscript)) {
            console.log('Barge-in detected! Stopping playback.');
            stopSpeaking();
        }
    }, [voice.transcript, voice.interimTranscript, isSpeaking, isRecording]);

    useEffect(() => {
        return () => {
            noiseCanceller.cleanup();
        };
    }, [noiseCanceller]);

    // Load conversation messages when conversationId changes
    useEffect(() => {
        if (conversationId) {
            loadConversationMessages(conversationId);
        } else {
            setMessages([]);
        }
    }, [conversationId]);

    // Load health status
    useEffect(() => {
        const loadHealth = async () => {
            try {
                const res = await fetch(`${API_BASE}/qa/health`);
                if (res.ok) {
                    const data = await res.json();
                    setHealth(data);
                }
            } catch (e) {
                setHealth(null);
            }
        };
        loadHealth();
    }, [API_BASE]);

    const loadConversationMessages = async (convId: string) => {
        try {
            const res = await fetch(`${API_BASE}/conversations/${convId}`);
            if (res.ok) {
                const data = await res.json();
                const loadedMessages: Message[] = data.messages.map((m: { role: string; content: string }) => ({
                    role: m.role as 'user' | 'assistant',
                    content: m.content,
                }));
                setMessages(loadedMessages);
            }
        } catch (error) {
            console.error('Error loading conversation:', error);
        }
    };

    const audioQueueRef = useRef<string[]>([]);
    const isPlayingRef = useRef(false);

    const playNextInQueue = useCallback(async () => {
        if (audioQueueRef.current.length === 0) {
            isPlayingRef.current = false;
            setIsSpeaking(false);
            return;
        }

        isPlayingRef.current = true;
        setIsSpeaking(true);
        const nextUrl = audioQueueRef.current.shift();

        if (nextUrl) {
            const audio = new Audio(nextUrl);
            audio.onended = () => playNextInQueue();
            audio.onerror = () => playNextInQueue();
            await audio.play();
        }
    }, []);

    const addToAudioQueue = useCallback((url: string) => {
        audioQueueRef.current.push(url);
        if (!isPlayingRef.current) {
            playNextInQueue();
        }
    }, [playNextInQueue]);

    const speakAnswer = useCallback(async (text: string) => {
        if (!text.trim()) return;

        try {
            audioQueueRef.current = [];
            setIsSpeaking(true);

            const res = await fetch(`${API_BASE}/qa/tts`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text: text,
                    session_id: sessionId || "default"
                }),
            });

            if (res.ok) {
                const data = await res.json();
                const audioUrl = `${API_BASE}${data.audio_url}`;
                addToAudioQueue(audioUrl);
            } else {
                console.error("TTS generation failed");
                setIsSpeaking(false);
            }
        } catch (error) {
            console.error('Error in speakAnswer:', error);
            setIsSpeaking(false);
        }
    }, [sessionId, API_BASE, addToAudioQueue]);

    const stopSpeaking = useCallback(() => {
        setIsSpeaking(false);
    }, []);

    const startRecording = async () => {
        if (isProcessing) return;

        try {
            setIsRecording(true);
            await voice.startRecording();
        } catch (error) {
            console.error('Error starting recording:', error);
            setIsRecording(false);
        }
    };

    // Function to submit query
    const handleQuery = async (queryText?: string) => {
        const textToSend = queryText || textInput;
        if (!textToSend.trim() || isProcessing) return;

        setIsProcessing(true);
        setIsSpeaking(false);
        audioQueueRef.current = [];

        // Add user message to UI immediately
        const userMessage: Message = { role: 'user', content: textToSend };
        setMessages(prev => [...prev, userMessage]);

        if (!queryText) setTextInput('');

        try {
            // Use LLM endpoint for prototype, hybrid for local
            const endpoint = llmMode ? '/qa/llm-query' : '/qa/hybrid-query';
            const res = await fetch(`${API_BASE}${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    message: textToSend,
                    conversation_id: conversationId
                }),
            });

            if (res.ok) {
                const data = await res.json();
                const answer = data.answer;

                // Add assistant message to UI
                const assistantMessage: Message = { role: 'assistant', content: answer };
                setMessages(prev => [...prev, assistantMessage]);

                // Notify parent of conversation change
                if (data.conversation_id && data.conversation_id !== conversationId) {
                    onConversationChange?.(data.conversation_id);
                }

                // Auto-speak if voice input
                if (queryText) {
                    speakAnswer(answer);
                }
            } else {
                const errorMsg = 'Error: Could not process your request. Please try again.';
                setMessages(prev => [...prev, { role: 'assistant', content: errorMsg }]);
            }
        } catch (error) {
            console.error('Error processing query:', error);
            setMessages(prev => [...prev, { role: 'assistant', content: 'Error: Could not process your request. Please try again.' }]);
        } finally {
            setIsProcessing(false);
        }
    };

    const stopRecording = () => {
        setIsRecording(false);
        voice.stopRecording();

        const spokenText = voice.transcript || voice.interimTranscript;
        if (spokenText && spokenText.trim()) {
            handleQuery(spokenText);
        }
    };

    const handleNewChat = () => {
        setMessages([]);
        onNewChat?.();
    };

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 160px)' }}>
            {/* Header */}
            <Box sx={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'space-between',
                p: 2,
                borderBottom: '1px solid #e0e0e0'
            }}>
                <Typography variant="h5" sx={{ fontWeight: 600 }}>
                    BCREC Voice Assistant
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Chip
                        label={health?.gemini_available ? "Gemini Active (Prototype)" : "Gemini Not Configured"}
                        color={health?.gemini_available ? "info" : "warning"}
                        size="small"
                        sx={{ fontSize: '0.7rem' }}
                    />
                    <Chip
                        label={health?.ollama_connected ? "Ollama OK" : "Ollama Offline"}
                        color={health?.ollama_connected ? "success" : "error"}
                        size="small"
                        sx={{ fontSize: '0.7rem' }}
                    />
                    <Button
                        variant="outlined"
                        size="small"
                        startIcon={<AddIcon />}
                        onClick={handleNewChat}
                    >
                        New Chat
                    </Button>
                </Box>
            </Box>

            {/* Messages Area */}
            <Box sx={{ 
                flexGrow: 1, 
                overflow: 'auto', 
                p: 3,
                display: 'flex',
                flexDirection: 'column',
                gap: 2
            }}>
                {messages.length === 0 && !isProcessing && (
                    <Box sx={{ 
                        flexGrow: 1, 
                        display: 'flex', 
                        flexDirection: 'column',
                        alignItems: 'center', 
                        justifyContent: 'center',
                        textAlign: 'center',
                        color: '#666'
                    }}>
                        <ChatIcon sx={{ fontSize: 64, mb: 2, opacity: 0.3 }} />
                        <Typography variant="h6" gutterBottom>
                            Welcome to BCREC Voice Assistant
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                            Ask me about admissions, fees, placements, hostel, courses, and more!
                        </Typography>
                    </Box>
                )}

                {messages.map((msg, index) => (
                    <Box
                        key={index}
                        sx={{
                            display: 'flex',
                            justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                        }}
                    >
                        <Paper
                            elevation={1}
                            sx={{
                                p: 2,
                                maxWidth: '80%',
                                bgcolor: msg.role === 'user' ? '#1a237e' : '#f5f5f5',
                                color: msg.role === 'user' ? 'white' : 'text.primary',
                                borderRadius: 2,
                            }}
                        >
                            <Typography variant="body1">
                                {msg.content}
                            </Typography>
                            {msg.role === 'assistant' && (
                                <Box sx={{ mt: 1, textAlign: 'right' }}>
                                    <IconButton
                                        size="small"
                                        onClick={() => speakAnswer(msg.content)}
                                        disabled={isSpeaking}
                                        sx={{ color: '#666' }}
                                    >
                                        <VolumeUp fontSize="small" />
                                    </IconButton>
                                </Box>
                            )}
                        </Paper>
                    </Box>
                ))}

                {isProcessing && (
                    <Box sx={{ display: 'flex', justifyContent: 'flex-start' }}>
                        <Paper sx={{ p: 2, bgcolor: '#f5f5f5', borderRadius: 2 }}>
                            <CircularProgress size={20} />
                            <Typography variant="body2" sx={{ ml: 2, display: 'inline' }}>
                                Processing...
                            </Typography>
                        </Paper>
                    </Box>
                )}
            </Box>

            {/* Input Area */}
            <Box sx={{ 
                p: 2, 
                borderTop: '1px solid #e0e0e0',
                bgcolor: 'white'
            }}>
                {/* Voice Support Warning */}
                {!voice.isSupported && (
                    <Alert severity="warning" sx={{ mb: 2 }}>
                        Voice recognition not supported. Please use Chrome, Edge, or Safari.
                    </Alert>
                )}

                <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                    {/* Mic Button */}
                    <IconButton
                        onClick={isRecording ? stopRecording : startRecording}
                        disabled={!voice.isSupported || isProcessing}
                        sx={{
                            bgcolor: isRecording ? '#d32f2f' : '#1a237e',
                            color: 'white',
                            '&:hover': { bgcolor: isRecording ? '#b71c1c' : '#0d47a1' },
                            width: 56,
                            height: 56,
                        }}
                    >
                        {isRecording ? <MicOff /> : <Mic />}
                    </IconButton>

                    {/* Text Input */}
                    <TextField
                        fullWidth
                        placeholder="Type your question..."
                        value={textInput}
                        onChange={(e) => setTextInput(e.target.value)}
                        onKeyPress={(e) => e.key === 'Enter' && handleQuery()}
                        variant="outlined"
                        disabled={isProcessing}
                        sx={{
                            '& .MuiOutlinedInput-root': { 
                                borderRadius: 3,
                                bgcolor: '#f9fafb'
                            }
                        }}
                    />

                    {/* Send Button */}
                    <Button
                        variant="contained"
                        onClick={() => handleQuery()}
                        disabled={!textInput.trim() || isProcessing}
                        sx={{ 
                            borderRadius: 3, 
                            px: 3,
                            minWidth: 100,
                            height: 56
                        }}
                    >
                        Send <Send sx={{ ml: 1 }} />
                    </Button>
                </Box>

                {/* Live Transcript */}
                {(voice.transcript || voice.interimTranscript) && (
                    <Box sx={{ mt: 2, p: 2, bgcolor: '#fff3e0', borderRadius: 2 }}>
                        <Typography variant="caption" color="text.secondary">
                            Listening: 
                        </Typography>
                        <Typography variant="body2">
                            {voice.transcript}
                            <span style={{ color: '#999' }}>{voice.interimTranscript}</span>
                        </Typography>
                    </Box>
                )}
            </Box>
        </Box>
    );
};

export default VoiceChat;
