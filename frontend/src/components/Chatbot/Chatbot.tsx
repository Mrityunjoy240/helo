import React from 'react';
import { Badge, Fab, Zoom } from '@mui/material';
import { Chat as ChatIcon } from '@mui/icons-material';
import ChatWindow from './ChatWindow';
import { useChat } from './hooks/useChat';

const Chatbot: React.FC = () => {
    const {
        messages,
        isOpen,
        isLoading,
        toggleChat,
        closeChat,
        sendMessage,
        quickReplies,
        messagesEndRef,
    } = useChat();

    return (
        <>
            <ChatWindow
                messages={messages}
                isOpen={isOpen}
                isLoading={isLoading}
                onClose={closeChat}
                onSendMessage={sendMessage}
                onQuickReply={sendMessage}
                quickReplies={quickReplies}
                messagesEndRef={messagesEndRef as React.RefObject<HTMLDivElement>}
            />

            <Zoom in>
                <Badge
                    badgeContent=""
                    color="error"
                    sx={{
                        '& .MuiBadge-badge': {
                            width: 12,
                            height: 12,
                            borderRadius: '50%',
                        },
                    }}
                >
                    <Fab
                        onClick={toggleChat}
                        sx={{
                            position: 'fixed',
                            bottom: 24,
                            right: 24,
                            bgcolor: 'primary.main',
                            color: 'white',
                            width: 64,
                            height: 64,
                            boxShadow: '0 4px 20px rgba(26, 35, 126, 0.4)',
                            '&:hover': {
                                bgcolor: 'primary.dark',
                                transform: 'scale(1.05)',
                            },
                            transition: 'all 0.3s ease',
                        }}
                    >
                        <ChatIcon sx={{ fontSize: 32 }} />
                    </Fab>
                </Badge>
            </Zoom>
        </>
    );
};

export default Chatbot;
