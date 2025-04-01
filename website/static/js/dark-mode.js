const themeIcon = document.querySelector('.theme-toggle i');

themeSwitch.addEventListener('change', function () {
    if (this.checked) {
        themeIcon.classList.remove('fa-sun');
        themeIcon.classList.add('fa-moon');
    } else {
        themeIcon.classList.remove('fa-moon');
        themeIcon.classList.add('fa-sun');
    }
});


document.addEventListener('DOMContentLoaded', function() {
    const chatBubble = document.getElementById('chatBubble');
    const chatBox = document.getElementById('chatBox');
    const closeChat = document.getElementById('closeChat');
    const messageInput = document.getElementById('messageInput');
    const sendMessage = document.getElementById('sendMessage');
    const chatMessages = document.getElementById('chatMessages');

    // Toggle chat box visibility
    chatBubble.addEventListener('click', function() {
      chatBox.style.display = chatBox.style.display === 'flex' ? 'none' : 'flex';
    });

    closeChat.addEventListener('click', function(e) {
      e.stopPropagation();
      chatBox.style.display = 'none';
    });

    // Send message functionality
    function sendMessageHandler() {
      const message = messageInput.value.trim();
      if (message) {
        // Add message to chat
        const messageElement = document.createElement('div');
        messageElement.textContent = message;
        messageElement.style.marginBottom = '10px';
        messageElement.style.padding = '8px 12px';
        messageElement.style.backgroundColor = '#f1f1f1';
        messageElement.style.borderRadius = '5px';
        messageElement.style.maxWidth = '80%';
        messageElement.style.alignSelf = 'flex-end';
        
        if (document.body.classList.contains('dark-mode')) {
          messageElement.style.backgroundColor = '#444';
          messageElement.style.color = 'white';
        }
        
        chatMessages.appendChild(messageElement);
        messageInput.value = '';
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        // Here you would typically send the message to your server
        // For now, we'll just simulate a response after 1 second
        setTimeout(() => {
          const responseElement = document.createElement('div');
          responseElement.textContent = "Thanks for your message!";
          responseElement.style.marginBottom = '10px';
          responseElement.style.padding = '8px 12px';
          responseElement.style.backgroundColor = '#e1f5fe';
          responseElement.style.borderRadius = '5px';
          responseElement.style.maxWidth = '80%';
          
          if (document.body.classList.contains('dark-mode')) {
            responseElement.style.backgroundColor = '#1a3e72';
            responseElement.style.color = 'white';
          }
          
          chatMessages.appendChild(responseElement);
          chatMessages.scrollTop = chatMessages.scrollHeight;
        }, 1000);
      }
    }

    sendMessage.addEventListener('click', sendMessageHandler);
    
    messageInput.addEventListener('keypress', function(e) {
      if (e.key === 'Enter') {
        sendMessageHandler();
      }
    });
  });