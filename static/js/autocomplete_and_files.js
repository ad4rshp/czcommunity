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
                const response = await fetch(uploadUrl, {
                    method: 'POST',
                    body: formData
                });
                if (response.ok) {
                    msgInput.value = '';
                } else {
                    const data = await response.json();
                    alert(data.error || "Upload failed");
                }
            } catch (err) {
                alert("Upload error");
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
