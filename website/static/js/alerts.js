function showToast(message, type = 'success') {
   const notification = document.getElementById('notification-container');
   if (!notification) return;
   
   const toast = document.createElement('div');
   toast.classList.add('toast', type);
   toast.setAttribute('role', 'alert');
   toast.setAttribute('aria-live', 'assertive');
   toast.setAttribute('aria-atomic', 'true');
   
   toast.innerHTML = `
       <span class="toast-icon">
           <i class="fas ${type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-exclamation-circle' : type === 'warning' ? 'fa-exclamation-triangle' : 'fa-info-circle'}"></i>
       </span>
       <span>${message}</span>
       <button class="close-btn" aria-label="Close" onclick="this.parentElement.remove();">
           <i class="fas fa-times"></i>
       </button>
   `;
   
   notification.appendChild(toast);
   
   // Auto-remove toast after 3 seconds
   setTimeout(() => {
       toast.style.animation = "hide 0.5s forwards";
       toast.addEventListener('animationend', () => {
           toast.remove();
       }, { once: true });
   }, 3000);
}

