// Configuration
// No API base URL needed for simulated chat
let currentSessionId = null;

// DOM Elements
const chatMessages = document.getElementById('chat-messages');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const suggestionBtns = document.querySelectorAll('.suggestion-btn');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Event Listeners
    sendBtn.addEventListener('click', handleSendMessage);
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    });
    
    // Add event listeners to suggestion buttons
    suggestionBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const prompt = btn.dataset.prompt;
            handleSuggestionClick(prompt);
        });
    });
});

// Handle sending a message
function handleSendMessage() {
    const message = messageInput.value.trim();
    if (!message) return;
    
    // Add user message to chat
    addUserMessage(message);
    messageInput.value = '';
    
    // Show loading indicator
    const loadingElement = addLoadingIndicator();
    
    // Process the message and get response
    processUserMessage(message, loadingElement);
}

// Handle suggestion click
function handleSuggestionClick(prompt) {
    // Add user message to chat
    addUserMessage(prompt);
    
    // Show loading indicator
    const loadingElement = addLoadingIndicator();
    
    // Process the message and get response
    processUserMessage(prompt, loadingElement);
}

// Add user message to chat
function addUserMessage(message) {
    const messageElement = document.createElement('div');
    messageElement.className = 'message user-message';
    messageElement.innerHTML = `<p>${message}</p>`;
    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    // Remove suggestion buttons if present
    const suggestionContainer = chatMessages.querySelector('.suggestion-buttons');
    if (suggestionContainer) {
        suggestionContainer.remove();
    }
    
    // Remove industry buttons if present
    const industryContainer = chatMessages.querySelector('.industry-buttons');
    if (industryContainer) {
        industryContainer.remove();
    }
}

// Add assistant message to chat
function addAssistantMessage(message) {
    const messageElement = document.createElement('div');
    messageElement.className = 'message assistant-message';
    messageElement.innerHTML = `<p>${message}</p>`;
    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Add loading indicator
function addLoadingIndicator() {
    const loadingElement = document.createElement('div');
    loadingElement.className = 'message assistant-message';
    loadingElement.innerHTML = `
        <div class="loading-dots">
            <span></span>
            <span></span>
            <span></span>
        </div>
    `;
    chatMessages.appendChild(loadingElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return loadingElement;
}

// Process user message and generate response
function processUserMessage(message, loadingElement) {
    // Simulate network delay
    setTimeout(() => {
        // Remove loading indicator
        loadingElement.remove();
        
        // Process the message
        if (message === "How is AI affecting my business?" || message.toLowerCase().includes("affecting") && message.toLowerCase().includes("business")) {
            // First response asking for industry
            addAssistantMessage("I understand you're interested in how AI is affecting businesses. To give you the best tool recommendations, could you tell me what industry or business type you're in?");
            
            // Add industry selection buttons
            addIndustryButtons();
        } 
        else if (message === "e-commerce" || message.toLowerCase().includes("e-commerce") || message.toLowerCase().includes("ecommerce")) {
            // Response for e-commerce selection
            addAssistantMessage("Great! For e-commerce businesses, AI can bring significant advantages. Here are the top AI tools I'd recommend for your industry:");
            
            // Add tool recommendations for e-commerce
            // This could be expanded with actual tool listings
            
            // Add suggestion buttons for follow-up
            addFollowUpSuggestions();
        }
        else if (message === "Want only tools with a free plan?" || message.toLowerCase().includes("free")) {
            addAssistantMessage("I understand you're looking for AI tools with free plans. Here are some great options across different categories:");
            
            // Add suggestion buttons for follow-up
            addFollowUpSuggestions();
        }
        else if (message === "Looking for video-focused tools?" || message.toLowerCase().includes("video")) {
            addAssistantMessage("Here are the top AI video tools that can help with creation, editing, and optimization:");
            
            // Add suggestion buttons for follow-up
            addFollowUpSuggestions();
        }
        else {
            // Generic response for other queries
            addAssistantMessage("Thanks for your question. I'm here to help you find the right AI tools for your needs. Could you tell me more about what specific tasks or industry you're interested in?");
            
            // Add suggestion buttons
            addFollowUpSuggestions();
        }
    }, 1500);
}

// Add industry selection buttons
function addIndustryButtons() {
    const industries = [
        'e-commerce', 'finance', 'healthcare', 'education', 
        'marketing', 'software', 'media', 'legal', 'manufacturing'
    ];
    
    const buttonContainer = document.createElement('div');
    buttonContainer.className = 'industry-buttons';
    
    industries.forEach(industry => {
        const button = document.createElement('button');
        button.className = 'industry-btn';
        button.textContent = industry;
        button.addEventListener('click', () => {
            // Highlight selected button
            document.querySelectorAll('.industry-btn').forEach(btn => {
                btn.classList.remove('selected');
            });
            button.classList.add('selected');
            
            // Handle industry selection
            handleSuggestionClick(industry);
        });
        buttonContainer.appendChild(button);
    });
    
    chatMessages.appendChild(buttonContainer);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Add follow-up suggestion buttons
function addFollowUpSuggestions() {
    const suggestions = [
        'Show me AI tools for content creation',
        'What are the best AI chatbots?',
        'Compare pricing plans'
    ];
    
    const buttonContainer = document.createElement('div');
    buttonContainer.className = 'suggestion-buttons';
    
    suggestions.forEach(suggestion => {
        const button = document.createElement('button');
        button.className = 'suggestion-btn';
        button.textContent = suggestion;
        button.dataset.prompt = suggestion;
        button.addEventListener('click', () => {
            handleSuggestionClick(suggestion);
        });
        buttonContainer.appendChild(button);
    });
    
    chatMessages.appendChild(buttonContainer);
    chatMessages.scrollTop = chatMessages.scrollHeight;
} 