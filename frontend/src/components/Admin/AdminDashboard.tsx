import React, { useState, useEffect } from 'react';
import {
    Box,
    Paper,
    Typography,
    Container,
    Button,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    IconButton,
    Alert,
    LinearProgress,
    Chip
} from '@mui/material';
import { Delete as DeleteIcon, CloudUpload as UploadIcon } from '@mui/icons-material';

const AdminDashboard: React.FC = () => {
    const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const [files, setFiles] = useState<any[]>([]);
    const [uploadFile, setUploadFile] = useState<File | null>(null);
    const [uploadProgress, setUploadProgress] = useState<number | null>(null);
    const [uploadStatus, setUploadStatus] = useState<{type: 'success' | 'error', message: string} | null>(null);
    const [loading, setLoading] = useState(true);

    // Load files from backend
    useEffect(() => {
        loadFiles();
    }, []);

    const loadFiles = async () => {
        try {
            setLoading(true);
            const res = await fetch(`${API_BASE}/admin/files/`);
            if (res.ok) {
                const data = await res.json();
                setFiles(data.files || []);
            }
        } catch (error) {
            console.error('Error loading files:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            setUploadFile(e.target.files[0]);
        }
    };

    const handleUpload = async () => {
        if (!uploadFile) return;

        const formData = new FormData();
        formData.append('file', uploadFile);

        try {
            setUploadProgress(0);
            setUploadStatus(null);

            // Simulate upload progress
            const interval = setInterval(() => {
                setUploadProgress(prev => {
                    if (prev === null) return 0;
                    const newProgress = prev + 10;
                    if (newProgress >= 100) {
                        clearInterval(interval);
                        return 100;
                    }
                    return newProgress;
                });
            }, 200);

            const res = await fetch(`${API_BASE}/admin/upload`, {
                method: 'POST',
                body: formData,
            });

            clearInterval(interval);
            
            if (res.ok) {
                const result = await res.json();
                setUploadStatus({ type: 'success', message: result.message || 'File uploaded successfully!' });
                setUploadFile(null);
                loadFiles(); // Refresh file list
            } else {
                const error = await res.json();
                setUploadStatus({ type: 'error', message: error.detail || 'Upload failed' });
            }
        } catch (error) {
            console.error('Upload error:', error);
            setUploadStatus({ type: 'error', message: 'Upload failed: ' + (error as Error).message });
        } finally {
            setTimeout(() => setUploadProgress(null), 2000);
        }
    };

    const handleDelete = async (filename: string) => {
        try {
            const res = await fetch(`${API_BASE}/admin/files/${filename}`, {
                method: 'DELETE',
            });

            if (res.ok) {
                setFiles(files.filter(file => file.filename !== filename));
                setUploadStatus({ type: 'success', message: 'File deleted successfully' });
            } else {
                const error = await res.json();
                setUploadStatus({ type: 'error', message: error.detail || 'Delete failed' });
            }
        } catch (error) {
            console.error('Delete error:', error);
            setUploadStatus({ type: 'error', message: 'Delete failed: ' + (error as Error).message });
        }
    };

    return (
        <Container maxWidth="lg" sx={{ py: 4 }}>
            <Paper elevation={3} sx={{ p: 4, borderRadius: 4 }}>
                <Typography variant="h4" component="h1" gutterBottom sx={{ mb: 4, fontFamily: '"Times New Roman", Times, serif', fontWeight: 'bold' }}>
                    Admin Dashboard
                </Typography>

                {/* Upload Section */}
                <Paper elevation={1} sx={{ p: 3, mb: 4, bgcolor: '#f9f9f9' }}>
                    <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
                        Upload Documents
                    </Typography>
                    
                    <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2 }}>
                        <Button
                            variant="contained"
                            component="label"
                            startIcon={<UploadIcon />}
                        >
                            Select File
                            <input
                                type="file"
                                hidden
                                accept=".pdf,.txt,.md,.xlsx,.csv"
                                onChange={handleFileChange}
                            />
                        </Button>
                        
                        {uploadFile && (
                            <Box sx={{ flex: 1 }}>
                                <Typography variant="body2">
                                    Selected: {uploadFile.name} ({(uploadFile.size / 1024 / 1024).toFixed(2)} MB)
                                </Typography>
                            </Box>
                        )}
                        
                        {uploadFile && (
                            <Button
                                variant="contained"
                                color="primary"
                                onClick={handleUpload}
                                disabled={!!uploadProgress}
                            >
                                Upload
                            </Button>
                        )}
                    </Box>
                    
                    {uploadProgress !== null && (
                        <Box sx={{ mb: 2 }}>
                            <LinearProgress variant="determinate" value={uploadProgress} />
                            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                                Uploading... {uploadProgress}%
                            </Typography>
                        </Box>
                    )}
                    
                    {uploadStatus && (
                        <Alert 
                            severity={uploadStatus.type === 'success' ? 'success' : 'error'} 
                            sx={{ mt: 2 }}
                        >
                            {uploadStatus.message}
                        </Alert>
                    )}
                </Paper>

                {/* Files List */}
                <Paper elevation={1} sx={{ p: 3 }}>
                    <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
                        Uploaded Documents
                    </Typography>
                    
                    {loading ? (
                        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                            <LinearProgress sx={{ width: '100%' }} />
                        </Box>
                    ) : files.length === 0 ? (
                        <Typography variant="body1" color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
                            No documents uploaded yet.
                        </Typography>
                    ) : (
                        <TableContainer>
                            <Table>
                                <TableHead>
                                    <TableRow>
                                        <TableCell>File Name</TableCell>
                                        <TableCell>Size</TableCell>
                                        <TableCell>Status</TableCell>
                                        <TableCell>Uploaded</TableCell>
                                        <TableCell align="right">Actions</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {files.map((file, index) => (
                                        <TableRow key={index}>
                                            <TableCell>
                                                <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                                                    {file.filename}
                                                </Typography>
                                            </TableCell>
                                            <TableCell>
                                                <Typography variant="body2">
                                                    {(file.size / 1024 / 1024).toFixed(2)} MB
                                                </Typography>
                                            </TableCell>
                                            <TableCell>
                                                <Chip 
                                                    label={file.processed ? "Processed" : "Pending"} 
                                                    color={file.processed ? "success" : "warning"} 
                                                    size="small"
                                                />
                                            </TableCell>
                                            <TableCell>
                                                <Typography variant="body2">
                                                    {new Date(file.uploaded_at).toLocaleDateString()}
                                                </Typography>
                                            </TableCell>
                                            <TableCell align="right">
                                                <IconButton
                                                    color="error"
                                                    onClick={() => handleDelete(file.filename)}
                                                    size="small"
                                                >
                                                    <DeleteIcon />
                                                </IconButton>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    )}
                </Paper>

                {/* System Info */}
                <Paper elevation={1} sx={{ p: 3, mt: 4 }}>
                    <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
                        System Information
                    </Typography>
                    <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 2 }}>
                        <Box>
                            <Typography variant="body2" color="text.secondary">Total Documents</Typography>
                            <Typography variant="h6">{files.length}</Typography>
                        </Box>
                        <Box>
                            <Typography variant="body2" color="text.secondary">Processed</Typography>
                            <Typography variant="h6">{files.filter(f => f.processed).length}</Typography>
                        </Box>
                        <Box>
                            <Typography variant="body2" color="text.secondary">Pending</Typography>
                            <Typography variant="h6">{files.filter(f => !f.processed).length}</Typography>
                        </Box>
                    </Box>
                </Paper>
            </Paper>
        </Container>
    );
};

export default AdminDashboard;