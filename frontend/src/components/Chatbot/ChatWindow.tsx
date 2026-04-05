import React, { useState, useRef, useEffect } from 'react';
import {
    Box,
    Paper,
    Typography,
    IconButton,
    TextField,
    Avatar,
    Fade,
    Chip,
    Collapse,
} from '@mui/material';
import {
    Close,
    Send as SendIcon,
    Phone,
    School,
} from '@mui/icons-material';
import { Message } from './types';
import { COLLEGE_INFO } from './config';

interface ChatWindowProps {
    messages: Message[];
    isOpen: boolean;
    isLoading: boolean;
    onClose: () => void;
    onSendMessage: (message: string) => void;
    onQuickReply: (message: string) => void;
    quickReplies: string[];
    messagesEndRef: React.RefObject<HTMLDivElement>;
}

const ChatWindow: React.FC<ChatWindowProps> = ({
    messages,
    isOpen,
    isLoading,
    onClose,
    onSendMessage,
    onQuickReply,
    quickReplies,
    messagesEndRef,
}) => {
    const [inputValue, setInputValue] = useState('');
    const inputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        if (isOpen && inputRef.current) {
            inputRef.current.focus();
        }
    }, [isOpen]);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (inputValue.trim() && !isLoading) {
            onSendMessage(inputValue.trim());
            setInputValue('');
        }
    };

    const formatTime = (date: Date) => {
        return new Date(date).toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    return (
        <Fade in={isOpen}>
            <Paper
                elevation={8}
                sx={{
                    position: 'fixed',
                    bottom: 100,
                    right: 24,
                    width: { xs: 'calc(100vw - 48px)', sm: 380 },
                    height: { xs: 'calc(100vh - 160px)', sm: 550 },
                    maxHeight: 550,
                    display: 'flex',
                    flexDirection: 'column',
                    borderRadius: 3,
                    overflow: 'hidden',
                    zIndex: 9999,
                }}
            >
                <Box
                    sx={{
                        bgcolor: 'primary.main',
                        color: 'white',
                        p: 2,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                    }}
                >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                        <Avatar sx={{ bgcolor: 'white', color: 'primary.main', width: 40, height: 40 }}>
                            <School />
                        </Avatar>
                        <Box>
                            <Typography variant="subtitle1" fontWeight={600}>
                                College Assistant
                            </Typography>
                            <Typography variant="caption" sx={{ opacity: 0.9 }}>
                                Here to help 24/7
                            </Typography>
                        </Box>
                    </Box>
                    <IconButton onClick={onClose} size="small" sx={{ color: 'white' }}>
                        <Close />
                    </IconButton>
                </Box>

                <Box
                    sx={{
                        flex: 1,
                        overflowY: 'auto',
                        p: 2,
                        bgcolor: '#f8fafc',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 2,
                    }}
                >
                    {messages.map((message) => (
                        <Box
                            key={message.id}
                            sx={{
                                display: 'flex',
                                justifyContent: message.sender === 'user' ? 'flex-end' : 'flex-start',
                                animation: 'fadeIn 0.3s ease',
                                '@keyframes fadeIn': {
                                    from: { opacity: 0, transform: 'translateY(10px)' },
                                    to: { opacity: 1, transform: 'translateY(0)' },
                                },
                            }}
                        >
                            <Box
                                sx={{
                                    maxWidth: '80%',
                                    display: 'flex',
                                    flexDirection: message.sender === 'user' ? 'row-reverse' : 'row',
                                    alignItems: 'flex-end',
                                    gap: 1,
                                }}
                            >
                                {message.sender === 'bot' && (
                                    <Avatar sx={{ width: 28, height: 28, bgcolor: 'primary.main', fontSize: 14 }}>
                                        <School fontSize="small" />
                                    </Avatar>
                                )}
                                <Box>
                                    <Box
                                        sx={{
                                            px: 2,
                                            py: 1.5,
                                            borderRadius: message.sender === 'user'
                                                ? '18px 18px 4px 18px'
                                                : '18px 18px 18px 4px',
                                            bgcolor: message.sender === 'user' ? 'primary.main' : 'white',
                                            color: message.sender === 'user' ? 'white' : 'text.primary',
                                            boxShadow: 1,
                                        }}
                                    >
                                        <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>
                                            {message.text}
                                        </Typography>
                                    </Box>
                                    <Typography
                                        variant="caption"
                                        sx={{
                                            display: 'block',
                                            mt: 0.5,
                                            color: 'text.disabled',
                                            textAlign: message.sender === 'user' ? 'right' : 'left',
                                        }}
                                    >
                                        {formatTime(message.timestamp)}
                                    </Typography>
                                </Box>
                            </Box>
                        </Box>
                    ))}

                    {isLoading && (
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, ml: 1 }}>
                            <Avatar sx={{ width: 28, height: 28, bgcolor: 'primary.main', fontSize: 14 }}>
                                <School fontSize="small" />
                            </Avatar>
                            <Box
                                sx={{
                                    px: 2,
                                    py: 1.5,
                                    borderRadius: '18px 18px 18px 4px',
                                    bgcolor: 'white',
                                    boxShadow: 1,
                                    display: 'flex',
                                    gap: 0.5,
                                }}
                            >
                                <Box
                                    sx={{
                                        width: 8,
                                        height: 8,
                                        borderRadius: '50%',
                                        bgcolor: 'primary.main',
                                        animation: 'bounce 1.4s infinite ease-in-out',
                                        '@keyframes bounce': {
                                            '0%, 80%, 100%': { transform: 'scale(0)' },
                                            '40%': { transform: 'scale(1)' },
                                        },
                                    }}
                                />
                                <Box
                                    sx={{
                                        width: 8,
                                        height: 8,
                                        borderRadius: '50%',
                                        bgcolor: 'primary.main',
                                        animation: 'bounce 1.4s infinite ease-in-out 0.16s',
                                    }}
                                />
                                <Box
                                    sx={{
                                        width: 8,
                                        height: 8,
                                        borderRadius: '50%',
                                        bgcolor: 'primary.main',
                                        animation: 'bounce 1.4s infinite ease-in-out 0.32s',
                                    }}
                                />
                            </Box>
                        </Box>
                    )}

                    <div ref={messagesEndRef} />
                </Box>

                <Collapse in={messages.length <= 2 && !isLoading}>
                    <Box sx={{ px: 2, pb: 1, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                        {quickReplies.map((reply) => (
                            <Chip
                                key={reply}
                                label={reply}
                                onClick={() => onQuickReply(reply)}
                                size="small"
                                sx={{
                                    bgcolor: 'primary.light',
                                    color: 'white',
                                    '&:hover': { bgcolor: 'primary.main' },
                                    cursor: 'pointer',
                                }}
                            />
                        ))}
                    </Box>
                </Collapse>

                <Box sx={{ p: 2, borderTop: '1px solid', borderColor: 'divider', bgcolor: 'white' }}>
                    <Box sx={{ display: 'flex', gap: 1, mb: 1.5 }}>
                        <Phone sx={{ fontSize: 16, color: 'text.secondary', mt: 0.75 }} />
                        <Typography variant="body2" color="text.secondary">
                            Call us: {COLLEGE_INFO.phone}
                        </Typography>
                    </Box>
                    <Box component="form" onSubmit={handleSubmit} sx={{ display: 'flex', gap: 1 }}>
                        <TextField
                            inputRef={inputRef}
                            fullWidth
                            size="small"
                            placeholder="Type your message..."
                            value={inputValue}
                            onChange={(e) => setInputValue(e.target.value)}
                            disabled={isLoading}
                            sx={{
                                '& .MuiOutlinedInput-root': {
                                    borderRadius: 3,
                                    bgcolor: '#f8fafc',
                                },
                            }}
                        />
                        <IconButton
                            type="submit"
                            disabled={!inputValue.trim() || isLoading}
                            sx={{
                                bgcolor: 'primary.main',
                                color: 'white',
                                '&:hover': { bgcolor: 'primary.dark' },
                                '&:disabled': { bgcolor: 'grey.300' },
                            }}
                        >
                            <SendIcon />
                        </IconButton>
                    </Box>
                </Box>
            </Paper>
        </Fade>
    );
};

export default ChatWindow;
