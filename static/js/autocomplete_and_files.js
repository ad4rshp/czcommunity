document.addEventListener('DOMContentLoaded', () => {
    // 1. File Upload Logic
    const fileInput = document.getElementById('fileInput');
    const chatForm = document.getElementById('chatForm');
    
    if(fileInput && chatForm) {
        fileInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            
            const formData = new FormData();
            formData.append('file', file);
            
            // Allow sending a message with the file
            const msgInput = document.getElementById('messageInput');
            if (msgInput.value.trim() !== "") {
                formData.append('content', msgInput.value.trim());
            }
            
            let currentChannelSlug = JSON.parse(document.getElementById('channel-slug').textContent);
            let uploadUrl = `/community/chat/channel/${currentChannelSlug}/upload/`;
            
            msgInput.disabled = true;
            msgInput.placeholder = "Uploading...";
            
            try {
                const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
                const csrfCookie = document.cookie.split(';').map(value => value.trim())
                    .find(value => value.startsWith('csrftoken='));
                const csrfToken = csrfInput?.value || (csrfCookie ? decodeURIComponent(csrfCookie.substring(10)) : '');
                const response = await fetch(uploadUrl, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrfToken },
                    body: formData
                });
                if (response.ok) {
                    msgInput.value = '';
                } else {
                    const data = await response.json();
                    if (window.showCzToast) {
                        showCzToast(data.error || "Upload failed", "error");
                    } else {
                        console.error(data.error || "Upload failed");
                    }
                }
            } catch (err) {
                if (window.showCzToast) {
                    showCzToast("Upload error", "error");
                } else {
                    console.error("Upload error", err);
                }
            } finally {
                msgInput.disabled = false;
                msgInput.placeholder = `Message #${currentChannelSlug}`;
                msgInput.focus();
                fileInput.value = ''; // Reset
            }
        });
    }

    // 2. GIF integration and Autocomplete (@, #, /) are cleanly managed by chat.js
});
