// Configuration
const API_BASE_URL = 'https://taaft-backend.onrender.com'; // Deployed backend URL
let currentSessionId = null;
let eventSource = null;

// DOM Elements
const chatMessages = document.getElementById('chat-messages');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const newChatBtn = document.getElementById('new-chat-btn');
const modelSelect = document.getElementById('model-select');
const streamToggle = document.getElementById('stream-toggle');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    createNewSession();

    // Event Listeners
    sendBtn.addEventListener('click', sendMessage);
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    newChatBtn.addEventListener('click', createNewSession);
});

// Create a new chat session
async function createNewSession() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/chat/sessions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: 'New Chat',
                model: modelSelect.value,
                user_id: 'user-' + Date.now() // Generate a temporary user ID
            })
        });

        if (!response.ok) {
            throw new Error(`Failed to create session: ${response.statusText}`);
        }

        const data = await response.json();
        currentSessionId = data.id;
        
        // Clear messages
        chatMessages.innerHTML = '';
        
        // Add system message
        addMessage('Welcome to the chat! How can I help you today?', 'assistant');
    } catch (error) {
        console.error('Error creating chat session:', error);
        addMessage('Failed to create a new chat session. Please try again.', 'assistant');
    }
}

// Send a message to the chat
async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message || !currentSessionId) return;

    // Add user message to the chat
    addMessage(message, 'user');
    messageInput.value = '';

    // Add loading indicator
    const loadingElement = document.createElement('div');
    loadingElement.className = 'loading';
    chatMessages.appendChild(loadingElement);

    // Determine whether to use streaming or non-streaming
    if (streamToggle.checked) {
        sendStreamingMessage(message, loadingElement);
    } else {
        sendNonStreamingMessage(message, loadingElement);
    }
}

// Send a non-streaming message
async function sendNonStreamingMessage(message, loadingElement) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/chat/sessions/${currentSessionId}/messages`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });

        if (!response.ok) {
            throw new Error(`Chat API error: ${response.statusText}`);
        }

        const data = await response.json();
        
        // Remove loading indicator
        loadingElement.remove();
        
        // Add assistant message
        addMessage(data.message, 'assistant', new Date(data.timestamp));
    } catch (error) {
        console.error('Error sending message:', error);
        loadingElement.remove();
        addMessage('Failed to get a response. Please try again.', 'assistant');
    }
}

// Send a streaming message
function sendStreamingMessage(message, loadingElement) {
    let assistantMessage = '';
    
    // Close any existing event source
    if (eventSource) {
        eventSource.close();
    }

    // Create a new EventSource
    const url = `${API_BASE_URL}/api/chat/sessions/${currentSessionId}/messages/stream`;
    
    // Instead of using EventSource directly, use fetch to post the message first
    fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Chat API error: ${response.statusText}`);
        }
        
        // Now set up the EventSource to receive the streaming response
        eventSource = new EventSource(url);
        
        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.event === 'chunk') {
                // Remove loading indicator on first chunk
                if (assistantMessage === '') {
                    loadingElement.remove();
                }
                
                assistantMessage += data.content;
                
                // Update or add the assistant message
                const existingMessage = document.querySelector('.assistant-message:last-child');
                if (existingMessage) {
                    existingMessage.textContent = assistantMessage;
                } else {
                    addMessage(assistantMessage, 'assistant');
                }
            } else if (data.event === 'end') {
                eventSource.close();
            }
        };
        
        eventSource.onerror = (error) => {
            console.error('Error with EventSource:', error);
            eventSource.close();
            loadingElement.remove();
            if (assistantMessage === '') {
                addMessage('Failed to get a streaming response. Please try again.', 'assistant');
            }
        };
    })
    .catch(error => {
        console.error('Error initiating streaming message:', error);
        loadingElement.remove();
        addMessage('Failed to start streaming. Please try again.', 'assistant');
    });
}

// Add a message to the chat
function addMessage(text, sender, timestamp = new Date()) {
    const messageElement = document.createElement('div');
    messageElement.className = `message ${sender}-message`;
    messageElement.textContent = text;
    
    const timeElement = document.createElement('div');
    timeElement.className = 'message-time';
    timeElement.textContent = formatTime(timestamp);
    
    messageElement.appendChild(timeElement);
    chatMessages.appendChild(messageElement);
    
    // Scroll to the bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Format timestamp to HH:MM
function formatTime(date) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
} 