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

    // 2. GIF integration is handled in chat.js

    // 3. Autocomplete for @mentions and #channels
    const messageInput = document.getElementById('messageInput');
    const mentionSuggestions = document.getElementById('mentionSuggestions');
    
    if (messageInput && mentionSuggestions) {
        let isMentioning = false;
        let mentionType = null; // '@' or '#'
        let mentionStartIndex = -1;
        
        // Parse community data (available from chat.html)
        const communityData = JSON.parse(document.getElementById('community-data').textContent);
        const users = communityData.users || [];
        const channels = communityData.channels || [];
        
        messageInput.addEventListener('input', (e) => {
            const val = messageInput.value;
            const cursorPos = messageInput.selectionStart;
            const textBeforeCursor = val.slice(0, cursorPos);
            
            const lastAt = textBeforeCursor.lastIndexOf('@');
            const lastHash = textBeforeCursor.lastIndexOf('#');
            
            const lastTrigger = Math.max(lastAt, lastHash);
            
            if (lastTrigger !== -1 && !textBeforeCursor.slice(lastTrigger).includes(' ')) {
                isMentioning = true;
                mentionType = textBeforeCursor[lastTrigger];
                mentionStartIndex = lastTrigger;
                
                const query = textBeforeCursor.slice(lastTrigger + 1).toLowerCase();
                renderMentionSuggestions(mentionType, query);
            } else {
                isMentioning = false;
                mentionSuggestions.classList.add('hidden');
            }
        });
        
        function renderMentionSuggestions(type, query) {
            mentionSuggestions.innerHTML = '';
            let matches = [];
            
            if (type === '@') {
                matches = users.filter(u => u.username.toLowerCase().includes(query)).slice(0, 5);
                matches.forEach(m => {
                    const div = document.createElement('div');
                    div.className = 'suggestion-item';
                    div.innerHTML = `<i class="ph ph-user" style="color: ${m.color}"></i> ${m.username}`;
                    div.onclick = () => insertMention(`@${m.username}`);
                    mentionSuggestions.appendChild(div);
                });
            } else if (type === '#') {
                matches = channels.filter(c => c.name.toLowerCase().includes(query)).slice(0, 5);
                matches.forEach(c => {
                    const div = document.createElement('div');
                    div.className = 'suggestion-item';
                    div.innerHTML = `<i class="ph ph-hash"></i> ${c.name}`;
                    div.onclick = () => insertMention(`#${c.name}`);
                    mentionSuggestions.appendChild(div);
                });
            }
            
            if (matches.length > 0) {
                mentionSuggestions.classList.remove('hidden');
                // Position it above the cursor if possible, simplified here:
                mentionSuggestions.style.bottom = "60px";
                mentionSuggestions.style.left = "20px";
            } else {
                mentionSuggestions.classList.add('hidden');
            }
        }
        
        function insertMention(text) {
            const val = messageInput.value;
            const before = val.slice(0, mentionStartIndex);
            const after = val.slice(messageInput.selectionStart);
            messageInput.value = before + text + ' ' + after;
            mentionSuggestions.classList.add('hidden');
            messageInput.focus();
        }
    }
});
