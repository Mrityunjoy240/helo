import { lazy, Suspense, useState, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route, Link as RouterLink, useLocation } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { CssBaseline, AppBar, Toolbar, Button, Box, CircularProgress, Container, Typography } from '@mui/material';
import logo from './assets/logo.svg';
import Sidebar from './components/Sidebar';
import VoiceChat from './components/VoiceChat/VoiceChat';

const AdminDashboard = lazy(() => import('./components/Admin/AdminDashboard'));

function Navigation() {
    const location = useLocation();
    const isActive = (path: string) => location.pathname === path;

    return (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Button
                component={RouterLink}
                to="/"
                variant={isActive('/') ? 'contained' : 'text'}
                color={isActive('/') ? 'primary' : 'inherit'}
                sx={{ 
                    px: 3, 
                    py: 1,
                    color: isActive('/') ? 'white' : '#333',
                    fontSize: '1rem'
                }}
            >
                Voice Chat
            </Button>
            <Button
                component={RouterLink}
                to="/admin"
                variant={isActive('/admin') ? 'contained' : 'text'}
                color={isActive('/admin') ? 'primary' : 'inherit'}
                sx={{ 
                    px: 3, 
                    py: 1,
                    color: isActive('/admin') ? 'white' : '#333',
                    fontSize: '1rem'
                }}
            >
                Admin
            </Button>
        </Box>
    );
}

const theme = createTheme({
    palette: {
        mode: 'light',
        primary: {
            main: '#1a237e',
        },
        secondary: {
            main: '#d32f2f',
        },
        background: {
            default: '#f3f4f6',
            paper: '#ffffff',
        },
    },
    typography: {
        fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
        h4: {
            fontFamily: '"Times New Roman", Times, serif',
            fontWeight: 700,
        },
        h5: {
            fontFamily: '"Times New Roman", Times, serif',
            fontWeight: 700,
        },
        h6: {
            fontFamily: '"Times New Roman", Times, serif',
            fontWeight: 700,
        },
    },
    components: {
        MuiButton: {
            styleOverrides: {
                root: {
                    textTransform: 'none',
                    borderRadius: '8px',
                },
            },
        },
        MuiPaper: {
            styleOverrides: {
                root: {
                    borderRadius: '16px',
                },
            },
        },
    },
});

function App() {
    const [conversationId, setConversationId] = useState<string | null>(null);
    const [sidebarOpen, setSidebarOpen] = useState(true);

    const handleSelectConversation = useCallback((id: string | null) => {
        setConversationId(id);
    }, []);

    const handleNewConversation = useCallback(() => {
        setConversationId(null);
    }, []);

    return (
        <ThemeProvider theme={theme}>
            <CssBaseline />
            <Router>
                <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
                    {/* Header */}
                    <AppBar position="static" color="transparent" elevation={0} sx={{ bgcolor: 'white', borderBottom: '1px solid #e0e0e0' }}>
                        <Container maxWidth="xl">
                            <Toolbar disableGutters sx={{ justifyContent: 'space-between', height: 80 }}>
                                {/* Logo */}
                                <Box component={RouterLink} to="/" sx={{ display: 'flex', alignItems: 'center', textDecoration: 'none' }}>
                                    <img src={logo} alt="Dr. B.C. Roy Engineering College" style={{ height: 50 }} />
                                </Box>

                                {/* Navigation */}
                                <Navigation />
                            </Toolbar>
                        </Container>
                    </AppBar>

                    {/* Main Content */}
                    <Box component="main" sx={{ flexGrow: 1, display: 'flex' }}>
                        <Suspense fallback={
                            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4, width: '100%' }}>
                                <CircularProgress />
                            </Box>
                        }>
                            <Routes>
                                <Route path="/" element={
                                    <Box sx={{ display: 'flex', width: '100%', height: 'calc(100vh - 140px)' }}>
                                        {/* Sidebar */}
                                        <Sidebar 
                                            currentConversationId={conversationId}
                                            onSelectConversation={handleSelectConversation}
                                            onNewConversation={handleNewConversation}
                                        />
                                        
                                        {/* Chat Area */}
                                        <Box sx={{ flexGrow: 1, overflow: 'hidden' }}>
                                            <VoiceChat 
                                                conversationId={conversationId}
                                                onConversationChange={handleSelectConversation}
                                                onNewChat={handleNewConversation}
                                            />
                                        </Box>
                                    </Box>
                                } />
                                <Route path="/admin" element={<AdminDashboard />} />
                            </Routes>
                        </Suspense>
                    </Box>

                    {/* Footer */}
                    <Box component="footer" sx={{ py: 3, textAlign: 'center', color: '#666', bgcolor: '#f3f4f6', borderTop: '1px solid #e0e0e0' }}>
                        <Typography variant="body2">
                            © 2025 DR. B.C. Roy Engineering College. All rights reserved.
                        </Typography>
                    </Box>
                </Box>
            </Router>
        </ThemeProvider>
    );
}

export default App;
