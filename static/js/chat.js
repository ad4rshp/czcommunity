const channelSlugNode = document.getElementById('channel-slug');
const sessionIdNode = document.getElementById('session-id');
const currentUsername = JSON.parse(document.getElementById('current-username').textContent);

const wsProtocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
let wsUrl = '';
if (channelSlugNode) {
    const slug = JSON.parse(channelSlugNode.textContent);
    if (slug) {
        wsUrl = wsProtocol + window.location.host + '/ws/community/chat/' + slug + '/';
    }
} else if (sessionIdNode) {
    wsUrl = wsProtocol + window.location.host + '/ws/dm/' + JSON.parse(sessionIdNode.textContent) + '/';
}

let chatSocket = null;
if (wsUrl) {
    chatSocket = new WebSocket(wsUrl);
    
    // Disable input while connecting
    if (document.getElementById('messageInput')) {
        document.getElementById('messageInput').disabled = true;
        document.getElementById('messageInput').placeholder = "Connecting to chat...";
    }
}

const messageArea = document.getElementById('messageArea');
const chatForm = document.getElementById('chatForm');
const messageInput = document.getElementById('messageInput');
const typingIndicator = document.getElementById('typingIndicator');

let typingTimeout;
let editingMessageId = null;
const typingUsers = new Map();

function updateTypingIndicator() {
    if (!typingIndicator) return;
    
    // Check user preference
    const showTypingPref = localStorage.getItem('cz_pref_show_typing');
    if (showTypingPref !== null && JSON.parse(showTypingPref) === false) {
        typingIndicator.innerHTML = '';
        return;
    }
    
    // Auto purge typing entries older than 4.5 seconds
    const now = Date.now();
    for (const [user, ts] of typingUsers.entries()) {
        if (now - ts > 4500) {
            typingUsers.delete(user);
        }
    }
    
    const users = Array.from(typingUsers.keys());
    if (users.length === 0) {
        typingIndicator.innerHTML = '';
    } else if (users.length === 1) {
        typingIndicator.innerHTML = `<span class="typing-dots"></span> <strong>${escapeHtml(users[0])}</strong> is typing...`;
    } else if (users.length === 2) {
        typingIndicator.innerHTML = `<span class="typing-dots"></span> <strong>${escapeHtml(users[0])}</strong> and <strong>${escapeHtml(users[1])}</strong> are typing...`;
    } else {
        const othersCount = users.length - 2;
        const othersText = othersCount === 1 ? '1 other' : `${othersCount} others`;
        typingIndicator.innerHTML = `<span class="typing-dots"></span> <strong>${escapeHtml(users[0])}</strong>, <strong>${escapeHtml(users[1])}</strong>, and ${othersText} are typing...`;
    }
}

// Helper to escape HTML safely in typing strings
function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>"']/g, function(m) {
        return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[m];
    });
}

// Periodic cleanup for typing indicator
setInterval(() => {
    if (typingUsers.size > 0) {
        updateTypingIndicator();
    }
}, 1000);

// Basic Markdown Parser (bold, italic, inline code)
function parseMarkdown(text) {
    // text is already HTML escaped from the backend
    let parsed = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>'); // Bold
    parsed = parsed.replace(/\*(.*?)\*/g, '<em>$1</em>');               // Italic
    parsed = parsed.replace(/`(.*?)`/g, '<code>$1</code>');             // Code
    parsed = parsed.replace(/^> (.*$)/gm, '<blockquote>$1</blockquote>'); // Quotes
    parsed = parsed.replace(/\n/g, '<br>');                             // Line breaks
    return parsed;
}

if (chatSocket) {
    chatSocket.onmessage = function(e) {
        const data = JSON.parse(e.data);
        
        if (data.type === 'chat.error') {
            alert(data.message);
            return;
        }
        
        if (data.action === 'message.created') {
            const isOwn = data.author === currentUsername;
        
        let actionsHtml = `<button onclick="reactToMessage(${data.message_id})">React</button>
                           <button onclick="replyToMessage(${data.message_id}, '${data.author}')">Reply</button>`;
        if (isOwn) {
            actionsHtml += `
                <button onclick="startEdit(${data.message_id})">Edit</button>
                <button onclick="deleteMessage(${data.message_id})">Delete</button>
            `;
        } else {
            actionsHtml += `<button onclick="reportMessage(${data.message_id})">Report</button>`;
        }
        
        const avatarUrl = data.avatar_url || '/static/img/default_avatar.svg';
        const avatarContent = `<img src="${avatarUrl}" alt="${data.author}" style="width: 100%; height: 100%; border-radius: 50%; object-fit: cover;" onerror="this.src='/static/img/default_avatar.svg'">`;

        const isMentioned = data.content.includes('@' + currentUsername);
        const mentionClass = isMentioned ? 'mentioned' : '';

        const botBadge = data.is_bot ? '<span class="bot-badge" style="background: #5865F2; color: white; font-size: 0.65rem; padding: 2px 5px; border-radius: 4px; margin-left: 5px; vertical-align: middle;">APP</span>' : '';
        
        let mediaHtml = '';
        if (data.attachment_url) {
            if (data.attachment_url.match(/\.(jpeg|jpg|gif|png|webp)$/i)) {
                mediaHtml += `<div style="margin-top: 10px;"><img src="${data.attachment_url}" style="max-width: 100%; max-height: 300px; width: auto; object-fit: contain; border-radius: 8px;"></div>`;
            } else {
                mediaHtml += `<div style="margin-top: 10px;"><a href="${data.attachment_url}" target="_blank" style="color: var(--accent);"><i class="ph ph-file"></i> Download Attachment</a></div>`;
            }
        }
        
        if (data.embed_data && data.embed_data.type === 'gif') {
            mediaHtml += `<div style="margin-top: 10px;"><img src="${data.embed_data.url}" style="max-width: 100%; max-height: 250px; width: auto; object-fit: contain; border-radius: 8px;"></div>`;
        }

        const colorStyle = data.author_color ? `color: ${data.author_color};` : '';
        const messageHtml = `
            <div class="message-group ${mentionClass}" id="msg-${data.message_id}" data-raw-content="${data.content}">
                <div class="message-avatar" style="cursor: pointer;" onclick="openProfileModal('${data.author}', window.activeCommunitySlug)">${avatarContent}</div>
                <div class="message-content-wrapper">
                    <div class="message-meta">
                        <span class="author" style="cursor: pointer; ${colorStyle}" onclick="mentionUser('${data.author}')">${data.author}</span>
                        ${botBadge}
                        <span class="timestamp">${data.created_at}</span>
                    </div>
                    <div class="message-text">${parseMarkdown(data.content)}${mediaHtml}</div>
                </div>
                <div class="message-actions">
                    ${actionsHtml}
                </div>
            </div>
        `;
        // Clear typing indicator for author
        if (data.author && typingUsers.has(data.author)) {
            typingUsers.delete(data.author);
            updateTypingIndicator();
        }

        // Remove empty state if present
        const emptyState = document.querySelector('.empty-state');
        if (emptyState) emptyState.remove();

        messageArea.insertAdjacentHTML('beforeend', messageHtml);
        scrollToBottom();
    } 
    else if (data.action === 'message.updated') {
        const msgEl = document.getElementById(`msg-${data.message_id}`);
        if (msgEl) {
            msgEl.setAttribute('data-raw-content', data.content);
            const textEl = msgEl.querySelector('.message-text');
            textEl.innerHTML = parseMarkdown(data.content) + ' <span class="edited-tag">(edited)</span>';
        }
    }
    else if (data.action === 'message.deleted') {
        const msgEl = document.getElementById(`msg-${data.message_id}`);
        if (msgEl) {
            msgEl.remove();
        }
    }
    else if (data.action === 'message.reacted') {
        const msgEl = document.getElementById(`msg-${data.message_id}`);
        if (msgEl) {
            let reactionsEl = msgEl.querySelector('.reactions-container');
            if (!reactionsEl) {
                reactionsEl = document.createElement('div');
                reactionsEl.className = 'reactions-container';
                reactionsEl.style.marginTop = '8px';
                msgEl.querySelector('.message-content-wrapper').appendChild(reactionsEl);
            }
            
            // For MVP, just updating a single emoji count
            if (data.count > 0) {
                reactionsEl.innerHTML = `<span class="reaction-pill" onclick="reactToMessage(${data.message_id})" style="background: rgba(255,255,255,0.1); padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; cursor: pointer; display: inline-block;">${data.emoji} ${data.count}</span>`;
            } else {
                reactionsEl.innerHTML = '';
            }
        }
    }
    else if (data.action === 'typing.started') {
        if (data.author && data.author !== currentUsername) {
            typingUsers.set(data.author, Date.now());
            updateTypingIndicator();
        }
    } 
    else if (data.action === 'typing.stopped') {
        if (data.author) {
            typingUsers.delete(data.author);
            updateTypingIndicator();
        }
    }
};

    chatSocket.onopen = function(e) {
        const msgInput = document.getElementById('messageInput');
        if (msgInput) {
            msgInput.disabled = false;
            msgInput.placeholder = "Message...";
            msgInput.focus();
        }
    };

    chatSocket.onclose = function(e) {
        console.warn('Chat socket closed, attempting to reconnect in 2s...');
        const msgInput = document.getElementById('messageInput');
        if (msgInput) {
            msgInput.placeholder = "Reconnecting to chat...";
        }
        setTimeout(() => {
            if (wsUrl) {
                try {
                    window.location.reload();
                } catch(err) {}
            }
        }, 2500);
    };
}

chatForm.addEventListener('submit', function(e) {
    e.preventDefault();
    const content = messageInput.value.trim();
    if (!content) return;
    
    if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
        if (editingMessageId) {
            // Send edit action
            chatSocket.send(JSON.stringify({
                'action': 'message.update',
                'message_id': editingMessageId,
                'content': content
            }));
            cancelEdit();
        } else {
            // Handle slash commands here locally
            if (content === '/music') {
                if (typeof toggleRightPanel === 'function') {
                    toggleRightPanel('music');
                }
                messageInput.value = '';
                return;
            }
            
            // Send new message
            chatSocket.send(JSON.stringify({
                'action': 'message.create',
                'content': content
            }));
        }
        
        messageInput.value = '';
        chatSocket.send(JSON.stringify({
            'action': 'typing.stopped'
        }));
    }
});

// Edit & Delete Handlers
function startEdit(messageId) {
    const msgEl = document.getElementById(`msg-${messageId}`);
    if (msgEl) {
        editingMessageId = messageId;
        const rawContent = msgEl.getAttribute('data-raw-content');
        messageInput.value = rawContent;
        messageInput.focus();
        
        // Change UI to indicate editing mode
        document.querySelector('.send-btn').textContent = '💾';
    }
}

function cancelEdit() {
    editingMessageId = null;
    messageInput.value = '';
    document.querySelector('.send-btn').textContent = '➤';
}

function deleteMessage(messageId) {
    if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
        chatSocket.send(JSON.stringify({
            'action': 'message.delete',
            'message_id': messageId
        }));
    }
}

function reactToMessage(messageId) {
    chatSocket.send(JSON.stringify({
        'action': 'message.react',
        'message_id': messageId,
        'emoji': '❤️'
    }));
}

function reportMessage(messageId) {
    alert("This message has been reported to the moderators.");
}

function replyToMessage(messageId, authorName) {
    const input = document.getElementById('messageInput');
    const msgEl = document.getElementById(`msg-${messageId}`);
    if (msgEl) {
        let rawContent = msgEl.getAttribute('data-raw-content');
        rawContent = rawContent.replace(/^>.*$/gm, '').trim(); // Remove nested quotes
        const preview = rawContent.length > 50 ? rawContent.substring(0, 50) + '...' : rawContent;
        input.value = `> **${authorName}**: ${preview}\n` + input.value;
        input.focus();
    }
}

function mentionUser(username) {
    const input = document.getElementById('messageInput');
    if (input) {
        if (input.value.length === 0 || input.value.endsWith(' ') || input.value.endsWith('\n')) {
            input.value += `@${username} `;
        } else {
            input.value += ` @${username} `;
        }
        input.focus();
        input.selectionStart = input.selectionEnd = input.value.length;
    }
}



// Autocomplete Engine
const commandSuggestions = document.getElementById('commandSuggestions');
const communityDataNode = document.getElementById('community-data');
const communityData = communityDataNode ? JSON.parse(communityDataNode.textContent) : {users: [], channels: []};

const defaultCommands = [
    {name: "/profile", desc: "View profile"},
    {name: "/music", desc: "Open music player"}
];

function renderSuggestions(type, query, cursorIndex) {
    let html = '';
    let matches = [];
    
    if (type === '/') {
        matches = defaultCommands.filter(c => c.name.toLowerCase().startsWith(query.toLowerCase()));
        matches.forEach(m => {
            html += `<div class="suggestion-item" style="padding: 8px 12px; cursor: pointer; transition: background 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.05)'" onmouseout="this.style.background='transparent'" onclick="insertAutocomplete('${m.name}', ${cursorIndex})">
                        <strong>${m.name}</strong> - <span style="color: var(--text-muted); font-size: 0.9rem;">${m.desc}</span>
                     </div>`;
        });
    } else if (type === '@') {
        matches = communityData.users.filter(u => u.username.toLowerCase().includes(query.toLowerCase()));
        matches.forEach(m => {
            html += `<div class="suggestion-item" style="padding: 8px 12px; cursor: pointer; transition: background 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.05)'" onmouseout="this.style.background='transparent'" onclick="insertAutocomplete('@${m.username}', ${cursorIndex})">
                        <span style="color: ${m.color}; font-weight: bold; font-size: 1rem;">@${m.username}</span>
                     </div>`;
        });
    } else if (type === '#') {
        matches = communityData.channels.filter(c => c.name.toLowerCase().includes(query.toLowerCase()));
        matches.forEach(m => {
            html += `<div class="suggestion-item" style="padding: 8px 12px; cursor: pointer; transition: background 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.05)'" onmouseout="this.style.background='transparent'" onclick="insertAutocomplete('#${m.name}', ${cursorIndex})">
                        <strong style="color: var(--text-primary);">#${m.name}</strong>
                     </div>`;
        });
    }

    if (matches.length > 0) {
        if (commandSuggestions) {
            commandSuggestions.innerHTML = html;
            commandSuggestions.classList.remove('hidden');
        }
    } else {
        if (commandSuggestions) commandSuggestions.classList.add('hidden');
    }
}

window.insertAutocomplete = function(replacement, cursorIndex) {
    const text = messageInput.value;
    let triggerIdx = -1;
    for (let i = cursorIndex - 1; i >= 0; i--) {
        if (['@', '#', '/'].includes(text[i])) {
            triggerIdx = i;
            break;
        }
    }
    if (triggerIdx !== -1) {
        const newText = text.substring(0, triggerIdx) + replacement + ' ' + text.substring(cursorIndex);
        messageInput.value = newText;
        messageInput.focus();
    }
    if (commandSuggestions) commandSuggestions.classList.add('hidden');
};

messageInput.addEventListener('input', function() {
    const text = messageInput.value;
    const cursor = messageInput.selectionStart;
    
    let triggerType = null;
    let wordStartIdx = cursor;
    
    for (let i = cursor - 1; i >= 0; i--) {
        if (text[i] === ' ') break;
        if (['@', '#', '/'].includes(text[i])) {
            triggerType = text[i];
            wordStartIdx = i;
            break;
        }
    }
    
    if (triggerType) {
        const query = text.substring(wordStartIdx + (triggerType==='/'?0:1), cursor);
        renderSuggestions(triggerType, triggerType==='/'?'/'+query:query, cursor);
    } else {
        if (commandSuggestions) commandSuggestions.classList.add('hidden');
    }
    
    chatSocket.send(JSON.stringify({'action': 'typing.started'}));
    clearTimeout(typingTimeout);
    typingTimeout = setTimeout(() => {
        chatSocket.send(JSON.stringify({'action': 'typing.stopped'}));
    }, 2000);
});

messageInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (commandSuggestions) commandSuggestions.classList.add('hidden');
        if (typeof chatForm.requestSubmit === 'function') {
            chatForm.requestSubmit();
        } else {
            chatForm.dispatchEvent(new Event('submit', {cancelable: true, bubbles: true}));
        }
    }
    if (e.key === 'Escape') {
        if (editingMessageId) cancelEdit();
        if (commandSuggestions) commandSuggestions.classList.add('hidden');
    }
});

function scrollToBottom() {
    messageArea.scrollTop = messageArea.scrollHeight;
}
scrollToBottom();

// Desktop Sidebar Collapse & Mobile Drawer Logic
window.toggleSidebarCollapse = function() {
    const isCollapsed = document.documentElement.classList.toggle('cz-sidebar-collapsed');
    try {
        localStorage.setItem('cz_sidebar_collapsed', isCollapsed ? 'true' : 'false');
    } catch(e) {}
};

const openDrawerBtn = document.getElementById('openDrawerBtn');
const closeDrawerBtn = document.getElementById('closeDrawerBtn');
const channelDrawer = document.getElementById('channelDrawer');

// Create mobile drawer backdrop overlay if not present
let drawerBackdrop = document.querySelector('.channel-drawer-backdrop');
if (!drawerBackdrop && channelDrawer) {
    drawerBackdrop = document.createElement('div');
    drawerBackdrop.className = 'channel-drawer-backdrop';
    document.body.appendChild(drawerBackdrop);
    drawerBackdrop.addEventListener('click', () => {
        channelDrawer.classList.remove('open');
        drawerBackdrop.classList.remove('active');
    });
}

if (openDrawerBtn && channelDrawer) {
    openDrawerBtn.addEventListener('click', () => {
        channelDrawer.classList.add('open');
        if (drawerBackdrop) drawerBackdrop.classList.add('active');
    });
}
if (closeDrawerBtn && channelDrawer) {
    closeDrawerBtn.addEventListener('click', () => {
        channelDrawer.classList.remove('open');
        if (drawerBackdrop) drawerBackdrop.classList.remove('active');
    });
}

// Close drawer on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && channelDrawer && channelDrawer.classList.contains('open')) {
        channelDrawer.classList.remove('open');
        if (drawerBackdrop) drawerBackdrop.classList.remove('active');
    }
});

// Swipe to reply logic for mobile
let touchStartX = 0;
let touchStartY = 0;

document.getElementById('messageArea').addEventListener('touchstart', function(e) {
    const msgGroup = e.target.closest('.message-group');
    if (msgGroup) {
        touchStartX = e.changedTouches[0].screenX;
        touchStartY = e.changedTouches[0].screenY;
    }
}, {passive: true});

document.getElementById('messageArea').addEventListener('touchend', function(e) {
    const msgGroup = e.target.closest('.message-group');
    if (msgGroup) {
        let touchEndX = e.changedTouches[0].screenX;
        let touchEndY = e.changedTouches[0].screenY;
        
        let deltaX = touchEndX - touchStartX;
        let deltaY = Math.abs(touchEndY - touchStartY);
        
        // If swiped right by more than 60px horizontally
        if (deltaX > 60 && deltaY < 30) {
            const msgId = msgGroup.id.replace('msg-', '');
            const author = msgGroup.querySelector('.author').textContent;
            replyToMessage(msgId, author);
            
            // Visual feedback
            msgGroup.style.transform = 'translateX(10px)';
            setTimeout(() => {
                msgGroup.style.transform = 'translateX(0)';
            }, 200);
        }
    }
}, {passive: true});

// Parse markdown for existing messages on page load
document.querySelectorAll('.markdown-content').forEach(el => {
    // We only want to parse if it's not a deleted message
    if (!el.querySelector('em')) {
        let rawHtml = el.innerHTML;
        // Simple extraction to handle the edited tag separately if needed, 
        // but for now parseMarkdown handles it fine if we just run it.
        // To be safe, we just replace the text nodes or innerHTML without breaking the span
        let editedTag = el.querySelector('.edited-tag');
        let textToParse = el.textContent.replace('(edited)', '').trim();
        let newHtml = parseMarkdown(textToParse);
        if (editedTag) {
            newHtml += ' <span class="edited-tag">(edited)</span>';
        }
        el.innerHTML = newHtml;
    }
});

// Klipy GIF Integration
const KLIPY_API_KEY = "Yu490aqOSwi0XxwILqKIKpDpmZXCjOqRY2JB9jhcjvhf9TKinZXOuARjJVnWUFEU";
const gifBtn = document.getElementById('gifBtn');
const globalGifPicker = document.getElementById('globalGifPicker');
const gifSearchInput = document.getElementById('gifSearchInput');
const gifPickerResults = document.getElementById('gifPickerResults');

if (gifBtn && globalGifPicker) {
    gifBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        globalGifPicker.classList.toggle('hidden');
        if (!globalGifPicker.classList.contains('hidden')) {
            if (gifPickerResults.innerHTML.trim() === '') {
                loadGifCategories();
            }
            gifSearchInput.focus();
        }
    });

    document.addEventListener('click', (e) => {
        if (!globalGifPicker.contains(e.target) && e.target !== gifBtn && !gifBtn.contains(e.target)) {
            globalGifPicker.classList.add('hidden');
        }
    });

    let searchTimeout;
    gifSearchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        const query = e.target.value.trim();
        searchTimeout = setTimeout(() => {
            if (query.length > 0) {
                searchGifs(query);
            } else {
                loadGifCategories();
            }
        }, 500);
    });
}

function loadGifCategories() {
    // Klipy doesn't have a direct 'categories' equivalent, so we load trending by default
    fetch(`https://api.klipy.co/api/v1/${KLIPY_API_KEY}/gifs/trending?limit=20`)
        .then(res => res.json())
        .then(resData => {
            gifPickerResults.innerHTML = '';
            const results = resData.data.data || [];
            results.forEach(result => {
                const gifUrl = result.file.hd.gif.url;
                const item = document.createElement('div');
                item.className = 'gif-item';
                item.innerHTML = `<img src="${gifUrl}" alt="${result.title || 'Trending GIF'}">`;
                item.addEventListener('click', () => {
                    sendGif(gifUrl);
                    globalGifPicker.classList.add('hidden');
                });
                gifPickerResults.appendChild(item);
            });
        }).catch(err => console.error(err));
}

function searchGifs(query) {
    fetch(`https://api.klipy.co/api/v1/${KLIPY_API_KEY}/gifs/search?q=${encodeURIComponent(query)}&limit=20`)
        .then(res => res.json())
        .then(resData => {
            gifPickerResults.innerHTML = '';
            const results = resData.data.data || [];
            results.forEach(result => {
                const gifUrl = result.file.hd.gif.url;
                const item = document.createElement('div');
                item.className = 'gif-item';
                item.innerHTML = `<img src="${gifUrl}" alt="GIF">`;
                item.addEventListener('click', () => {
                    sendGif(gifUrl);
                    globalGifPicker.classList.add('hidden');
                    gifSearchInput.value = '';
                    loadGifCategories();
                });
                gifPickerResults.appendChild(item);
            });
        }).catch(err => console.error(err));
}

function sendGif(url) {
    if (chatSocket) {
        chatSocket.send(JSON.stringify({
            'action': 'message.create',
            'content': '',
            'embed_data': {
                'type': 'gif',
                'url': url
            }
        }));
    }
}

// --- Context Menu for Messages ---
const msgContextMenu = document.createElement('div');
msgContextMenu.className = 'message-context-menu';
msgContextMenu.style.position = 'absolute';
msgContextMenu.style.display = 'none';
msgContextMenu.style.zIndex = '1000';
msgContextMenu.style.background = 'var(--bg-surface)';
msgContextMenu.style.border = '1px solid var(--border)';
msgContextMenu.style.borderRadius = 'var(--radius-sm)';
msgContextMenu.style.padding = '5px 0';
msgContextMenu.style.boxShadow = '0 8px 16px rgba(0,0,0,0.5)';
msgContextMenu.style.minWidth = '150px';
document.body.appendChild(msgContextMenu);

function hideContextMenu() {
    msgContextMenu.style.display = 'none';
}

document.addEventListener('click', hideContextMenu);
document.addEventListener('scroll', hideContextMenu, true);

let longPressTimer;
let isLongPress = false;

document.addEventListener('contextmenu', function(e) {
    const msgEl = e.target.closest('.message-group');
    if (msgEl) {
        e.preventDefault();
        showContextMenu(e.pageX, e.pageY, msgEl);
    }
});

document.addEventListener('touchstart', function(e) {
    const msgEl = e.target.closest('.message-group');
    if (msgEl) {
        isLongPress = false;
        longPressTimer = setTimeout(() => {
            isLongPress = true;
            const touch = e.touches[0];
            showContextMenu(touch.pageX, touch.pageY, msgEl);
        }, 600); // 600ms for long press
    }
}, {passive: true});

document.addEventListener('touchend', function(e) {
    clearTimeout(longPressTimer);
});

document.addEventListener('touchmove', function(e) {
    clearTimeout(longPressTimer);
});

function showContextMenu(x, y, msgEl) {
    const msgId = msgEl.getAttribute('data-msg-id');
    const author = msgEl.getAttribute('data-author');
    if (!msgId) return;

    const isOwn = author === currentUsername;
    
    let menuHtml = '';
    
    menuHtml += `<div class="ctx-item" onclick="reactToMessage('${msgId}')"><i class="ph ph-heart"></i> React</div>`;
    menuHtml += `<div class="ctx-item" onclick="replyToMessage('${msgId}', '${author}')"><i class="ph ph-arrow-u-up-left"></i> Reply</div>`;
    
    if (isOwn) {
        menuHtml += `<div class="ctx-item" onclick="startEdit('${msgId}')"><i class="ph ph-pencil-simple"></i> Edit</div>`;
    }
    
    if (isOwn || window.canManageMessages) {
        menuHtml += `<div class="ctx-item text-danger" onclick="deleteMessage('${msgId}')"><i class="ph ph-trash"></i> Delete</div>`;
    }
    
    if (!isOwn) {
        menuHtml += `<div class="ctx-item text-danger" onclick="reportMessage('${msgId}')"><i class="ph ph-flag"></i> Report</div>`;
        if (window.canKickMembers) {
            menuHtml += `<div class="ctx-item text-danger" onclick="kickUser('${author}')"><i class="ph ph-user-minus"></i> Kick User</div>`;
        }
        if (window.canBanMembers) {
            menuHtml += `<div class="ctx-item text-danger" onclick="banUser('${author}')"><i class="ph ph-prohibit"></i> Ban User</div>`;
        }
    }

    msgContextMenu.innerHTML = menuHtml;
    msgContextMenu.style.display = 'block';
    
    // Boundary check
    const rect = msgContextMenu.getBoundingClientRect();
    if (x + rect.width > window.innerWidth) x -= rect.width;
    if (y + rect.height > window.innerHeight) y -= rect.height;
    
    msgContextMenu.style.left = x + 'px';
    msgContextMenu.style.top = y + 'px';
}

function kickUser(username) {
    if(confirm('Are you sure you want to kick ' + username + '?')) {
        // Mock kick action for MVP
        alert(username + ' was kicked from the server.');
    }
}
function banUser(username) {
    if(confirm('Are you sure you want to permanently ban ' + username + '?')) {
        // Mock ban action for MVP
        alert(username + ' was banned from the server.');
    }
}

