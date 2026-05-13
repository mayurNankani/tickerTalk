/**
 * Main Application Entry Point
 * Initializes Alpine.js and global stores
 */

document.addEventListener('alpine:init', () => {
    // Initialize global chart instances map
    window.chartInstances = new Map();
    
    // Note: analyze-stock event is handled in chatInterface component init()
    // No need to duplicate the listener here
});

// Focus input on page load
window.addEventListener('load', () => {
    const chatInput = document.querySelector('.chat-input');
    if (chatInput) {
        chatInput.focus();
    }
});
