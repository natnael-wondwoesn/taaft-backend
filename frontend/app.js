// Configuration
const API_BASE_URL = 'https://taaft-backend.onrender.com'; // Deployed backend URL
let currentSessionId = null;
let eventSource = null;
let authToken = null;
let currentUser = null;

// DOM Elements
const loginContainer = document.getElementById('login-container');
const chatContainer = document.getElementById('chat-container');
const chatMessages = document.getElementById('chat-messages');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const newChatBtn = document.getElementById('new-chat-btn');
const modelSelect = document.getElementById('model-select');
const streamToggle = document.getElementById('stream-toggle');
const usernameInput = document.getElementById('username-input');
const passwordInput = document.getElementById('password-input');
const loginBtn = document.getElementById('login-btn');
const loginError = document.getElementById('login-error');
const userDisplay = document.getElementById('user-display');
const logoutBtn = document.getElementById('logout-btn');
const authTitle = document.getElementById('auth-title');
const authToggleBtn = document.getElementById('auth-toggle-btn');
const authToggleText = document.getElementById('auth-toggle-text');
const registerFields = document.getElementById('register-fields');
const confirmPasswordInput = document.getElementById('confirm-password-input');
const emailInput = document.getElementById('email-input');

// Auth mode: 'login' or 'register'
let authMode = 'login';

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Check if a token exists in localStorage
    const savedToken = localStorage.getItem('authToken');
    const savedUser = localStorage.getItem('username');
    
    if (savedToken && savedUser) {
        // Auto login with saved token
        authToken = savedToken;
        currentUser = savedUser;
        showChatInterface();
        createNewSession();
    }

    // Event Listeners
    loginBtn.addEventListener('click', handleAuth);
    authToggleBtn.addEventListener('click', toggleAuthMode);
    logoutBtn.addEventListener('click', logout);
    sendBtn.addEventListener('click', sendMessage);
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    newChatBtn.addEventListener('click', createNewSession);
});

// Toggle between login and register modes
function toggleAuthMode() {
    authMode = authMode === 'login' ? 'register' : 'login';
    
    if (authMode === 'register') {
        authTitle.textContent = 'Register';
        loginBtn.textContent = 'Register';
        authToggleText.textContent = 'Already have an account?';
        authToggleBtn.textContent = 'Login';
        registerFields.style.display = 'flex';
    } else {
        authTitle.textContent = 'Login';
        loginBtn.textContent = 'Login';
        authToggleText.textContent = 'Don\'t have an account?';
        authToggleBtn.textContent = 'Register';
        registerFields.style.display = 'none';
    }
    
    // Clear error message when switching modes
    loginError.textContent = '';
}

// Handle authentication (both login and register)
async function handleAuth() {
    if (authMode === 'login') {
        login();
    } else {
        register();
    }
}

// Register function
async function register() {
    const username = usernameInput.value.trim();
    const password = passwordInput.value.trim();
    const confirmPassword = confirmPasswordInput.value.trim();
    const email = emailInput.value.trim();
    
    // Validate input
    if (!username || !password) {
        loginError.textContent = 'Please enter both username and password';
        return;
    }
    
    if (password !== confirmPassword) {
        loginError.textContent = 'Passwords do not match';
        return;
    }
    
    try {
        // Try registering with the /api/auth/register endpoint
        const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                username, 
                password,
                email: email || undefined // Only include email if provided
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Registration failed. Please try again.');
        }
        
        // Registration successful, auto login
        loginError.textContent = '';
        authMode = 'login';
        toggleAuthMode();
        
        // Show success message
        loginError.style.color = '#28a745';
        loginError.textContent = 'Registration successful! You can now login.';
        
    } catch (error) {
        console.error('Registration error:', error);
        loginError.textContent = error.message || 'Registration failed. Please try again.';
    }
}

// Login function
async function login() {
    const username = usernameInput.value.trim();
    const password = passwordInput.value.trim();
    
    if (!username || !password) {
        loginError.textContent = 'Please enter both username and password';
        return;
    }
    
    try {
        // First attempt: Try the direct token endpoint
        const response = await fetch(`${API_BASE_URL}/api/auth/token`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                username, 
                password,
                grant_type: 'password'
            })
        });
        
        if (!response.ok) {
            // If that fails, try a standard login endpoint as fallback
            const loginResponse = await fetch(`${API_BASE_URL}/api/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            
            if (!loginResponse.ok) {
                throw new Error('Invalid username or password');
            }
            
            const loginData = await loginResponse.json();
            handleSuccessfulLogin(loginData, username);
            return;
        }
        
        const data = await response.json();
        handleSuccessfulLogin(data, username);
        
    } catch (error) {
        console.error('Login error:', error);
        loginError.textContent = error.message || 'Login failed. Please try again.';
    }
}

// Handle successful login data
function handleSuccessfulLogin(data, username) {
    // Check different possible token field names
    const token = data.access_token || data.token || data.accessToken;
    
    if (!token) {
        throw new Error('No valid token found in response');
    }
    
    // Save auth token
    authToken = token;
    currentUser = username;
    
    // Save to localStorage for persistence
    localStorage.setItem('authToken', authToken);
    localStorage.setItem('username', username);
    
    // Show chat interface
    showChatInterface();
    
    // Create a new chat session
    createNewSession();
}

// Logout function
function logout() {
    // Clear authentication
    authToken = null;
    currentUser = null;
    
    // Remove from localStorage
    localStorage.removeItem('authToken');
    localStorage.removeItem('username');
    
    // Reset UI
    chatMessages.innerHTML = '';
    messageInput.value = '';
    
    // Close any active EventSource
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
    
    // Show login form
    showLoginInterface();
}

// Show login interface
function showLoginInterface() {
    loginContainer.style.display = 'block';
    chatContainer.style.display = 'none';
    loginError.textContent = '';
    usernameInput.value = '';
    passwordInput.value = '';
}

// Show chat interface
function showChatInterface() {
    loginContainer.style.display = 'none';
    chatContainer.style.display = 'flex';
    userDisplay.textContent = `User: ${currentUser}`;
}

// Create a new chat session
async function createNewSession() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/chat/sessions`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': authToken.startsWith('Bearer ') ? authToken : `Bearer ${authToken}`
            },
            body: JSON.stringify({
                title: 'New Chat',
                model: modelSelect.value,
                user_id: currentUser
            })
        });

        if (!response.ok) {
            if (response.status === 401) {
                // Handle token expiration
                logout();
                loginError.textContent = 'Session expired. Please login again.';
                return;
            }
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
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': authToken.startsWith('Bearer ') ? authToken : `Bearer ${authToken}`
            },
            body: JSON.stringify({ message })
        });

        if (!response.ok) {
            if (response.status === 401) {
                // Handle token expiration
                logout();
                loginError.textContent = 'Session expired. Please login again.';
                return;
            }
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

    // Create a new EventSource with auth token
    const url = `${API_BASE_URL}/api/chat/sessions/${currentSessionId}/messages/stream`;
    
    // Instead of using EventSource directly, use fetch to post the message first
    fetch(url, {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            'Authorization': authToken.startsWith('Bearer ') ? authToken : `Bearer ${authToken}`
        },
        body: JSON.stringify({ message })
    })
    .then(response => {
        if (!response.ok) {
            if (response.status === 401) {
                // Handle token expiration
                logout();
                loginError.textContent = 'Session expired. Please login again.';
                return;
            }
            throw new Error(`Chat API error: ${response.statusText}`);
        }
        
        // Check if the response contains the message directly (non-streaming server)
        return response.json().then(data => {
            // If server doesn't support streaming, handle as regular response
            loadingElement.remove();
            addMessage(data.message, 'assistant', new Date(data.timestamp));
        }).catch(() => {
            // If we can't parse the response as JSON, assume streaming is supported
            setupEventSource();
        });
    })
    .catch(error => {
        console.error('Error initiating streaming message:', error);
        loadingElement.remove();
        addMessage('Failed to start streaming. Please try again.', 'assistant');
    });
    
    // Setup the EventSource for streaming
    function setupEventSource() {
        try {
            // Add auth token as a header by building a custom URL
            const token = encodeURIComponent(authToken);
            const streamUrl = `${API_BASE_URL}/api/chat/sessions/${currentSessionId}/messages/stream?token=${token}`;
            
            eventSource = new EventSource(streamUrl);
            
            eventSource.onmessage = (event) => {
                try {
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
                } catch (err) {
                    // Handle plain text chunks if server doesn't return JSON
                    if (assistantMessage === '') {
                        loadingElement.remove();
                    }
                    
                    assistantMessage += event.data;
                    
                    const existingMessage = document.querySelector('.assistant-message:last-child');
                    if (existingMessage) {
                        existingMessage.textContent = assistantMessage;
                    } else {
                        addMessage(assistantMessage, 'assistant');
                    }
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
        } catch (error) {
            console.error('Error setting up EventSource:', error);
            loadingElement.remove();
            addMessage('Failed to set up streaming. Please try again.', 'assistant');
        }
    }
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