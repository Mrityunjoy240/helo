export interface Message {
    id: string;
    text: string;
    sender: 'user' | 'bot';
    timestamp: Date;
}

export interface ChatState {
    messages: Message[];
    isOpen: boolean;
    isLoading: boolean;
    error: string | null;
}
