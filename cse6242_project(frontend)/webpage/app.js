// Chat application logic
const chatContainer = document.getElementById('chatContainer');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');

// Store conversation history
let conversationHistory = [];

// Add event listeners
sendButton.addEventListener('click', sendMessage);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Send message function
async function sendMessage() {
    const message = messageInput.value.trim();

    if (!message) return;

    // Clear input
    messageInput.value = '';

    // Disable send button
    sendButton.disabled = true;

    // Remove welcome message if it exists
    const welcomeMsg = chatContainer.querySelector('.welcome-message');
    if (welcomeMsg) {
        welcomeMsg.remove();
    }

    // Add user message to chat
    addMessage(message, 'user');

    // Add to conversation history
    conversationHistory.push({ role: 'user', content: message });

    // Show typing indicator
    const typingIndicator = showTypingIndicator();

    try {
        // Send request to backend
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                history: conversationHistory
            })
        });

        if (!response.ok) {
            throw new Error('Failed to get response');
        }

        const data = await response.json();

        // Remove typing indicator
        typingIndicator.remove();

        if (data.success) {
            // Add assistant message
            addMessage(data.message, 'assistant');

            // Add to conversation history
            conversationHistory.push({ role: 'assistant', content: data.message });

            // Optional: Log tool calls for debugging
            if (data.tool_calls && data.tool_calls.length > 0) {
                console.log('Agent called tools:', data.tool_calls);
            }
        } else {
            addMessage('Sorry, I encountered an error. Please try again.', 'assistant');
        }

    } catch (error) {
        console.error('Error:', error);
        typingIndicator.remove();
        addMessage('Sorry, I encountered an error. Please try again.', 'assistant');
    } finally {
        // Re-enable send button
        sendButton.disabled = false;
        messageInput.focus();
    }
}

// Add message to chat container
function addMessage(text, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;

    const avatarDiv = document.createElement('div');
    avatarDiv.className = 'message-avatar';

    const avatarImg = document.createElement('img');
    avatarImg.src = sender === 'user' ? 'figure/web_logo/user-svgrepo-com.svg' : 'figure/web_logo/student-svgrepo-com.svg';
    avatarImg.alt = sender;

    avatarDiv.appendChild(avatarImg);

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = text;

    messageDiv.appendChild(avatarDiv);
    messageDiv.appendChild(contentDiv);

    chatContainer.appendChild(messageDiv);

    // Scroll to bottom
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// Show typing indicator
function showTypingIndicator() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';

    const avatarDiv = document.createElement('div');
    avatarDiv.className = 'message-avatar';

    const avatarImg = document.createElement('img');
    avatarImg.src = 'figure/web_logo/student-svgrepo-com.svg';
    avatarImg.alt = 'assistant';

    avatarDiv.appendChild(avatarImg);

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    const typingDiv = document.createElement('div');
    typingDiv.className = 'typing-indicator';
    typingDiv.innerHTML = '<span></span><span></span><span></span>';

    contentDiv.appendChild(typingDiv);

    messageDiv.appendChild(avatarDiv);
    messageDiv.appendChild(contentDiv);

    chatContainer.appendChild(messageDiv);

    // Scroll to bottom
    chatContainer.scrollTop = chatContainer.scrollHeight;

    return messageDiv;
}
