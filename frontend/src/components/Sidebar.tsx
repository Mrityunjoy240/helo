import React, { useState, useEffect } from 'react';
import {
    Box,
    Button,
    List,
    ListItem,
    ListItemButton,
    ListItemText,
    Typography,
    IconButton,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Paper,
    Divider,
} from '@mui/material';
import {
    Add as AddIcon,
    Delete as DeleteIcon,
    Chat as ChatIcon,
} from '@mui/icons-material';

interface Conversation {
    id: string;
    title: string;
    created_at: string;
    updated_at: string;
    message_count: number;
}

interface SidebarProps {
    currentConversationId: string | null;
    onSelectConversation: (id: string | null) => void;
    onNewConversation: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({
    currentConversationId,
    onSelectConversation,
    onNewConversation,
}) => {
    const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const [conversations, setConversations] = useState<Conversation[]>([]);
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [conversationToDelete, setConversationToDelete] = useState<string | null>(null);

    useEffect(() => {
        loadConversations();
    }, []);

    const loadConversations = async () => {
        try {
            const res = await fetch(`${API_BASE}/conversations`);
            if (res.ok) {
                const data = await res.json();
                setConversations(data);
            }
        } catch (error) {
            console.error('Error loading conversations:', error);
        }
    };

    const handleNewChat = async () => {
        try {
            const res = await fetch(`${API_BASE}/conversations`, {
                method: 'POST',
            });
            if (res.ok) {
                const data = await res.json();
                onSelectConversation(data.id);
                onNewConversation();
                loadConversations();
            }
        } catch (error) {
            console.error('Error creating conversation:', error);
        }
    };

    const handleDeleteClick = (e: React.MouseEvent, id: string) => {
        e.stopPropagation();
        setConversationToDelete(id);
        setDeleteDialogOpen(true);
    };

    const handleDeleteConfirm = async () => {
        if (!conversationToDelete) return;
        
        try {
            const res = await fetch(`${API_BASE}/conversations/${conversationToDelete}`, {
                method: 'DELETE',
            });
            if (res.ok) {
                if (currentConversationId === conversationToDelete) {
                    onSelectConversation(null);
                    onNewConversation();
                }
                loadConversations();
            }
        } catch (error) {
            console.error('Error deleting conversation:', error);
        }
        
        setDeleteDialogOpen(false);
        setConversationToDelete(null);
    };

    const formatDate = (dateString: string) => {
        const date = new Date(dateString);
        const now = new Date();
        const diff = now.getTime() - date.getTime();
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        
        if (days === 0) return 'Today';
        if (days === 1) return 'Yesterday';
        if (days < 7) return `${days} days ago`;
        return date.toLocaleDateString();
    };

    const truncateTitle = (title: string, maxLength: number = 25) => {
        if (title.length <= maxLength) return title;
        return title.substring(0, maxLength) + '...';
    };

    return (
        <>
            <Paper
                sx={{
                    width: 280,
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    borderRadius: 0,
                    borderRight: '1px solid #e0e0e0',
                }}
            >
                {/* Header */}
                <Box
                    sx={{
                        p: 2,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        borderBottom: '1px solid #e0e0e0',
                    }}
                >
                    <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1rem' }}>
                        Chat History
                    </Typography>
                    <IconButton
                        size="small"
                        onClick={handleNewChat}
                        sx={{
                            bgcolor: '#1a237e',
                            color: 'white',
                            '&:hover': { bgcolor: '#0d47a1' },
                        }}
                    >
                        <AddIcon />
                    </IconButton>
                </Box>

                {/* New Chat Button */}
                <Box sx={{ p: 1 }}>
                    <Button
                        fullWidth
                        variant="outlined"
                        startIcon={<AddIcon />}
                        onClick={handleNewChat}
                        sx={{
                            justifyContent: 'flex-start',
                            textTransform: 'none',
                            borderColor: '#e0e0e0',
                            color: '#333',
                            '&:hover': {
                                bgcolor: '#f5f5f5',
                                borderColor: '#ccc',
                            },
                        }}
                    >
                        New Chat
                    </Button>
                </Box>

                <Divider />

                {/* Conversation List */}
                <Box sx={{ flexGrow: 1, overflow: 'auto' }}>
                    <List dense>
                        {conversations.length === 0 ? (
                            <Box sx={{ p: 2, textAlign: 'center' }}>
                                <Typography variant="body2" color="text.secondary">
                                    No conversations yet
                                </Typography>
                            </Box>
                        ) : (
                            conversations.map((conv) => (
                                <ListItem
                                    key={conv.id}
                                    disablePadding
                                    secondaryAction={
                                        <IconButton
                                            edge="end"
                                            size="small"
                                            onClick={(e) => handleDeleteClick(e, conv.id)}
                                            sx={{
                                                opacity: 0.5,
                                                '&:hover': { opacity: 1 },
                                            }}
                                        >
                                            <DeleteIcon fontSize="small" />
                                        </IconButton>
                                    }
                                    sx={{
                                        bgcolor: currentConversationId === conv.id ? '#e8eaf6' : 'transparent',
                                    }}
                                >
                                    <ListItemButton
                                        onClick={() => onSelectConversation(conv.id)}
                                        sx={{
                                            py: 1.5,
                                            '&:hover': {
                                                bgcolor: '#f5f5f5',
                                            },
                                        }}
                                    >
                                        <ListItemText
                                            primary={
                                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                    <ChatIcon sx={{ fontSize: 18, color: '#666' }} />
                                                    <Typography
                                                        variant="body2"
                                                        sx={{
                                                            fontWeight: currentConversationId === conv.id ? 600 : 400,
                                                            color: currentConversationId === conv.id ? '#1a237e' : '#333',
                                                        }}
                                                    >
                                                        {truncateTitle(conv.title)}
                                                    </Typography>
                                                </Box>
                                            }
                                            secondary={
                                                <Typography
                                                    variant="caption"
                                                    sx={{ color: '#999', ml: 3.5 }}
                                                >
                                                    {formatDate(conv.updated_at)} • {conv.message_count} messages
                                                </Typography>
                                            }
                                        />
                                    </ListItemButton>
                                </ListItem>
                            ))
                        )}
                    </List>
                </Box>

                {/* Footer */}
                <Box
                    sx={{
                        p: 2,
                        borderTop: '1px solid #e0e0e0',
                        textAlign: 'center',
                    }}
                >
                    <Typography variant="caption" color="text.secondary">
                        Conversations are saved locally
                    </Typography>
                </Box>
            </Paper>

            {/* Delete Confirmation Dialog */}
            <Dialog
                open={deleteDialogOpen}
                onClose={() => setDeleteDialogOpen(false)}
            >
                <DialogTitle>Delete Conversation</DialogTitle>
                <DialogContent>
                    <Typography>
                        Are you sure you want to delete this conversation? This action cannot be undone.
                    </Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
                    <Button onClick={handleDeleteConfirm} color="error">
                        Delete
                    </Button>
                </DialogActions>
            </Dialog>
        </>
    );
};

export default Sidebar;
