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
let reconnectTimer = null;

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
    return str.replace(/[&<>"']/g, function (m) {
        return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[m];
    });
}

// Periodic cleanup for typing indicator
setInterval(() => {
    if (typingUsers.size > 0) {
        updateTypingIndicator();
    }
}, 1000);

// Basic Markdown Parser (bold, italic, inline code, @mentions)
function parseMarkdown(text) {
    if (!text) return '';
    // text is already HTML escaped from the backend
    let parsed = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>'); // Bold
    parsed = parsed.replace(/\*(.*?)\*/g, '<em>$1</em>');               // Italic
    parsed = parsed.replace(/`(.*?)`/g, '<code>$1</code>');             // Code
    parsed = parsed.replace(/^> (.*$)/gm, '<blockquote>$1</blockquote>'); // Quotes
    
    // Parse @mentions into interactive styled badges
    parsed = parsed.replace(/@([a-zA-Z0-9_.-]+)/g, (match, username) => {
        const isMe = currentUsername && username.toLowerCase() === currentUsername.toLowerCase();
        const meClass = isMe ? ' mention-me' : '';
        return `<span class="mention-tag${meClass}" onclick="event.stopPropagation(); mentionUser('${username}')">@${username}</span>`;
    });

    parsed = parsed.replace(/\n/g, '<br>');                             // Line breaks
    return parsed;
}

function initChatSocket() {
    if (!wsUrl) return;

    if (chatSocket) {
        try {
            chatSocket.onopen = null;
            chatSocket.onclose = null;
            chatSocket.onerror = null;
            chatSocket.onmessage = null;
            chatSocket.close();
        } catch (e) { }
    }

    try {
        chatSocket = new WebSocket(wsUrl);
    } catch (err) {
        console.error('Failed to create WebSocket:', err);
        const input = document.getElementById('messageInput');
        if (input) input.disabled = false;
        return;
    }

    // Safety fallback: if socket takes > 2s to connect, make sure input is usable
    setTimeout(() => {
        const input = document.getElementById('messageInput');
        if (input && input.disabled && (!chatSocket || chatSocket.readyState !== WebSocket.OPEN)) {
            input.disabled = false;
            input.placeholder = "Message...";
        }
    }, 2000);

    chatSocket.onopen = function (e) {
        console.log('Chat WebSocket connected');
        const input = document.getElementById('messageInput');
        if (input) {
            input.disabled = false;
            input.placeholder = "Message...";
        }
    };

    chatSocket.onclose = function (e) {
        console.warn('Chat socket closed, attempting reconnect in 2s...');
        const input = document.getElementById('messageInput');
        if (input && !input.value) {
            input.placeholder = "Reconnecting to chat...";
        }
        if (reconnectTimer) clearTimeout(reconnectTimer);
        reconnectTimer = setTimeout(() => {
            initChatSocket();
        }, 2000);
    };

    chatSocket.onerror = function (err) {
        console.error('Chat WebSocket error:', err);
        const input = document.getElementById('messageInput');
        if (input) {
            input.disabled = false;
        }
    };

    chatSocket.onmessage = function (e) {
        const data = JSON.parse(e.data);

        if (data.type === 'chat.error') {
            alert(data.message);
            return;
        }

        if (data.action === 'message.created') {
            const isOwn = data.author === currentUsername;
            const canManage = window.canManageMessages === true;

            let actionsHtml = `
                <button type="button" class="msg-action-btn" onclick="reactToMessage(${data.message_id})" title="Add Reaction" aria-label="Reaction"><i class="ph-bold ph-heart"></i></button>
                <button type="button" class="msg-action-btn" onclick="replyToMessage(${data.message_id}, '${data.author}')" title="Reply to message" aria-label="Reply"><i class="ph-bold ph-arrow-bend-up-left"></i></button>
            `;
            if (isOwn) {
                actionsHtml += `<button type="button" class="msg-action-btn" onclick="startEdit(${data.message_id})" title="Edit message" aria-label="Edit"><i class="ph-bold ph-pencil-simple"></i></button>`;
            }
            if (isOwn || canManage) {
                actionsHtml += `<button type="button" class="msg-action-btn danger" onclick="deleteMessage(${data.message_id})" title="Delete message" aria-label="Delete"><i class="ph-bold ph-trash"></i></button>`;
            }
            if (!isOwn) {
                actionsHtml += `<button type="button" class="msg-action-btn" onclick="reportMessage(${data.message_id})" title="Report message" aria-label="Report"><i class="ph-bold ph-flag"></i></button>`;
            }

            const avatarUrl = data.avatar_url || '/static/img/default_avatar.svg';
            const avatarContent = `<img src="${avatarUrl}" alt="${data.author}" style="width: 100%; height: 100%; border-radius: 50%; object-fit: cover;" onerror="this.src='/static/img/default_avatar.svg'">`;

            const isMentioned = currentUsername && data.content && (
                data.content.toLowerCase().includes('@' + currentUsername.toLowerCase()) ||
                data.content.includes('@everyone') ||
                data.content.includes('@here')
            );
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
            let replyHtml = '';
            if (data.reply_to) {
                replyHtml = `
                    <div class="message-reply-preview" onclick="scrollToMessage(${data.reply_to.id})" title="Jump to message">
                        <div class="reply-spine-curve"></div>
                        <img src="${data.reply_to.avatar_url}" class="reply-avatar" alt="${data.reply_to.author}" onerror="this.src='/static/img/default_avatar.svg'">
                        <span class="reply-author">@${data.reply_to.author}</span>
                        <span class="reply-snippet">${data.reply_to.content}</span>
                    </div>
                `;
            }

            const messageHtml = `
                <div class="message-group ${mentionClass}" id="msg-${data.message_id}" data-msg-id="${data.message_id}" data-author="${data.author}" data-raw-content="${data.content}">
                    <div class="message-avatar" style="cursor: pointer;" onclick="openProfileModal('${data.author}', window.activeCommunitySlug)">${avatarContent}</div>
                    <div class="message-content-wrapper">
                        ${replyHtml}
                        <div class="message-meta">
                            <span class="author" style="cursor: pointer; ${colorStyle}" onclick="mentionUser('${data.author}')">${data.author}</span>
                            ${botBadge}
                            <span class="timestamp">${data.created_at}</span>
                        </div>
                        <div class="message-text">${parseMarkdown(data.content)}${mediaHtml}</div>
                        <div class="message-actions">
                            ${actionsHtml}
                        </div>
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
}

// Initialize chat WebSocket
initChatSocket();

// Rate limiting & Outgoing Queue (Handles spamming by queueing after 4-5 messages)
const SPAM_THRESHOLD = 4; // After 4 rapid messages, subsequent messages are queued
const SPAM_WINDOW_MS = 5000; // 5-second window
const QUEUE_DELAY_MS = 1200; // 1.2s delay between queued messages

let recentSentTimestamps = [];
let outgoingQueue = [];
let isProcessingQueue = false;

function sendMessageDirect(content) {
    if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
        recentSentTimestamps.push(Date.now());
        const payload = {
            'action': 'message.create',
            'content': content
        };
        if (window.activeReplyMessageId) {
            payload.reply_to_id = window.activeReplyMessageId;
            cancelReply();
        }
        chatSocket.send(JSON.stringify(payload));
        try {
            chatSocket.send(JSON.stringify({
                'action': 'typing.stopped'
            }));
        } catch (err) { }
    } else {
        console.warn('Chat socket not open. Initiating connection & queueing message...');
        initChatSocket();
        queuePendingMessage(content);
    }
}

function queuePendingMessage(content) {
    const tempId = 'pending-' + Date.now() + '-' + Math.random().toString(36).substr(2, 5);
    renderPendingMessage(tempId, content);
    outgoingQueue.push({ tempId, content });

    if (!isProcessingQueue) {
        processOutgoingQueue();
    }
}

function renderPendingMessage(tempId, content) {
    const avatarUrl = window.currentUserAvatar || '/static/img/default_avatar.svg';
    const nowTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const pendingHtml = `
        <div class="message-group pending" id="${tempId}" data-raw-content="${escapeHtml(content)}">
            <div class="message-avatar">
                <img src="${avatarUrl}" alt="${escapeHtml(currentUsername)}" style="width: 100%; height: 100%; border-radius: 50%; object-fit: cover;" onerror="this.src='/static/img/default_avatar.svg'">
            </div>
            <div class="message-content-wrapper">
                <div class="message-meta">
                    <span class="author">${escapeHtml(currentUsername)}</span>
                    <span class="timestamp">${nowTime}</span>
                </div>
                <div class="message-text">${parseMarkdown(escapeHtml(content))}</div>
            </div>
        </div>
    `;

    messageArea.insertAdjacentHTML('beforeend', pendingHtml);
    scrollToBottom();
}

function processOutgoingQueue() {
    if (outgoingQueue.length === 0) {
        isProcessingQueue = false;
        return;
    }

    isProcessingQueue = true;

    setTimeout(() => {
        if (outgoingQueue.length === 0) {
            isProcessingQueue = false;
            return;
        }

        const item = outgoingQueue.shift();

        // Send via socket
        if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
            recentSentTimestamps.push(Date.now());
            chatSocket.send(JSON.stringify({
                'action': 'message.create',
                'content': item.content
            }));
        }

        // Remove placeholder after brief delay (server message.created replaces it)
        setTimeout(() => {
            const pendingEl = document.getElementById(item.tempId);
            if (pendingEl) pendingEl.remove();
        }, 800);

        // Process next item in queue
        processOutgoingQueue();
    }, QUEUE_DELAY_MS);
}

if (chatForm) {
    chatForm.addEventListener('submit', function (e) {
        e.preventDefault();
        const content = messageInput.value.trim();
        if (!content) return;

        if (editingMessageId) {
            if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
                chatSocket.send(JSON.stringify({
                    'action': 'message.update',
                    'message_id': editingMessageId,
                    'content': content
                }));
                cancelEdit();
            }
            return;
        }

        // Slash command
        if (content === '/music') {
            if (typeof toggleRightPanel === 'function') {
                toggleRightPanel('music');
            }
            messageInput.value = '';
            messageInput.style.height = 'auto';
            return;
        }

        messageInput.value = '';
        messageInput.style.height = 'auto';

        const now = Date.now();
        // Filter timestamps within recent window
        recentSentTimestamps = recentSentTimestamps.filter(t => (now - t) < SPAM_WINDOW_MS);

        // If spam threshold reached or queue has items: queue message
        if (recentSentTimestamps.length >= SPAM_THRESHOLD || outgoingQueue.length > 0) {
            queuePendingMessage(content);
        } else {
            sendMessageDirect(content);
        }
    });

    // Clicking anywhere in composer padding or input wrap focuses the input
    chatForm.addEventListener('click', function (e) {
        if (!e.target.closest('button') && !e.target.closest('input[type="file"]') && !e.target.closest('#quickEmojiPalette')) {
            if (messageInput && document.activeElement !== messageInput) {
                messageInput.focus();
            }
        }
    });
}

// Edit & Delete Handlers
function startEdit(messageId) {
    const msgEl = document.getElementById(`msg-${messageId}`);
    if (msgEl) {
        editingMessageId = messageId;
        const rawContent = msgEl.getAttribute('data-raw-content');
        messageInput.value = rawContent;
        messageInput.focus();
        messageInput.style.height = 'auto';
        messageInput.style.height = Math.min(messageInput.scrollHeight, 140) + 'px';

        // Change UI to indicate editing mode
        const sendBtn = document.querySelector('.composer-send-btn, .send-btn');
        if (sendBtn) {
            sendBtn.innerHTML = '<i class="ph-fill ph-check"></i>';
            sendBtn.title = "Save Edit (Enter)";
        }
    }
}

function cancelEdit() {
    editingMessageId = null;
    messageInput.value = '';
    messageInput.style.height = 'auto';
    const sendBtn = document.querySelector('.composer-send-btn, .send-btn');
    if (sendBtn) {
        sendBtn.innerHTML = '<i class="ph-fill ph-paper-plane-tilt"></i>';
        sendBtn.title = "Send Message (Enter)";
    }
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
    if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
        chatSocket.send(JSON.stringify({
            'action': 'message.react',
            'message_id': messageId,
            'emoji': '❤️'
        }));
    }
}

function reportMessage(messageId) {
    if (typeof window.openReportModal === 'function') {
        window.openReportModal(messageId);
    } else {
        alert("Report dialog unavailable");
    }
}
window.reportMessage = reportMessage;

// Modern Discord-Style Reply State & Controls
window.activeReplyMessageId = null;
window.activeReplyAuthor = null;
window.activeReplyMention = true;

window.replyToMessage = function(messageId, authorName) {
    const msgEl = document.getElementById(`msg-${messageId}`);
    if (!msgEl) return;
    
    let rawContent = msgEl.getAttribute('data-raw-content') || '';
    rawContent = rawContent.replace(/^>.*$/gm, '').trim();
    const preview = rawContent.length > 55 ? rawContent.substring(0, 55) + '...' : rawContent;
    
    window.activeReplyMessageId = messageId;
    window.activeReplyAuthor = authorName;
    
    const replyBar = document.getElementById('replyBar');
    const authorEl = document.getElementById('replyAuthorName');
    const previewEl = document.getElementById('replyPreviewText');
    
    if (replyBar && authorEl && previewEl) {
        authorEl.textContent = '@' + authorName;
        previewEl.textContent = preview;
        replyBar.style.display = 'flex';
    }
    
    if (messageInput) {
        messageInput.focus();
    }
};

window.cancelReply = function() {
    window.activeReplyMessageId = null;
    window.activeReplyAuthor = null;
    const replyBar = document.getElementById('replyBar');
    if (replyBar) replyBar.style.display = 'none';
};

window.toggleReplyMention = function(checked) {
    window.activeReplyMention = checked;
    const badge = document.getElementById('replyMentionBadge');
    if (badge) {
        badge.innerHTML = `<i class="ph-bold ph-at"></i> ${checked ? 'ON' : 'OFF'}`;
        badge.style.opacity = checked ? '1' : '0.5';
    }
};

window.scrollToMessage = function(messageId) {
    const el = document.getElementById(`msg-${messageId}`);
    if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.classList.add('pulse-highlight');
        setTimeout(() => el.classList.remove('pulse-highlight'), 1800);
    }
};

// Auto scroll on direct jump link (?jump=<id>)
(function checkJumpOnLoad() {
    function runJump() {
        const urlParams = new URLSearchParams(window.location.search);
        const jumpId = urlParams.get('jump');
        if (jumpId) {
            setTimeout(() => {
                window.scrollToMessage(jumpId);
            }, 350);
        }
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', runJump);
    } else {
        runJump();
    }
})();

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
const communityData = communityDataNode ? JSON.parse(communityDataNode.textContent) : { users: [], channels: [] };

const defaultCommands = [
    { name: "/profile", desc: "View profile" },
    { name: "/music", desc: "Open music player" }
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
        matches = communityData.channels.filter(c => c.type !== 'voice' && c.name.toLowerCase().includes(query.toLowerCase()));
        matches.forEach(m => {
            html += `<div class="suggestion-item" style="padding: 8px 12px; cursor: pointer; transition: background 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.05)'" onmouseout="this.style.background='transparent'" onclick="insertAutocomplete('#${m.name}', ${cursorIndex})">
                        <strong style="color: var(--text-primary);"><i class="ph ph-hash"></i> ${m.name}</strong>
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

window.insertAutocomplete = function (replacement, cursorIndex) {
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

messageInput.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 140) + 'px';

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
        const query = text.substring(wordStartIdx + (triggerType === '/' ? 0 : 1), cursor);
        renderSuggestions(triggerType, triggerType === '/' ? '/' + query : query, cursor);
    } else {
        if (commandSuggestions) commandSuggestions.classList.add('hidden');
    }

    if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
        chatSocket.send(JSON.stringify({ 'action': 'typing.started' }));
    }
    clearTimeout(typingTimeout);
    typingTimeout = setTimeout(() => {
        if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
            chatSocket.send(JSON.stringify({ 'action': 'typing.stopped' }));
        }
    }, 2000);
});

messageInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (commandSuggestions) commandSuggestions.classList.add('hidden');
        if (typeof chatForm.requestSubmit === 'function') {
            chatForm.requestSubmit();
        } else {
            chatForm.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
        }
    }
    if (e.key === 'Escape') {
        if (window.activeReplyMessageId) cancelReply();
        if (editingMessageId) cancelEdit();
        if (commandSuggestions) commandSuggestions.classList.add('hidden');
    }
});

function scrollToBottom() {
    messageArea.scrollTop = messageArea.scrollHeight;
}
scrollToBottom();

// Desktop Sidebar Collapse & Mobile Drawer Logic
window.toggleSidebarCollapse = function () {
    const isCollapsed = document.documentElement.classList.toggle('cz-sidebar-collapsed');
    try {
        localStorage.setItem('cz_sidebar_collapsed', isCollapsed ? 'true' : 'false');
    } catch (e) { }
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

document.getElementById('messageArea').addEventListener('touchstart', function (e) {
    const msgGroup = e.target.closest('.message-group');
    if (msgGroup) {
        touchStartX = e.changedTouches[0].screenX;
        touchStartY = e.changedTouches[0].screenY;
    }
}, { passive: true });

document.getElementById('messageArea').addEventListener('touchend', function (e) {
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
}, { passive: true });

// Parse markdown and mentions for existing messages on page load
document.querySelectorAll('.message-group').forEach(msgEl => {
    const rawContent = msgEl.getAttribute('data-raw-content') || '';
    if (currentUsername && rawContent.toLowerCase().includes('@' + currentUsername.toLowerCase())) {
        msgEl.classList.add('mentioned');
    }
    const textEl = msgEl.querySelector('.markdown-content, .message-text');
    if (textEl && !textEl.dataset.parsed) {
        textEl.dataset.parsed = 'true';
        let editedTag = textEl.querySelector('.edited-tag');
        let textToParse = textEl.textContent.replace('(edited)', '').trim();
        let newHtml = parseMarkdown(textToParse);
        if (editedTag) {
            newHtml += ' <span class="edited-tag">(edited)</span>';
        }
        textEl.innerHTML = newHtml;
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

document.addEventListener('contextmenu', function (e) {
    const msgEl = e.target.closest('.message-group');
    if (msgEl) {
        e.preventDefault();
        showContextMenu(e.pageX, e.pageY, msgEl);
    }
});

document.addEventListener('touchstart', function (e) {
    const msgEl = e.target.closest('.message-group');
    if (msgEl) {
        isLongPress = false;
        longPressTimer = setTimeout(() => {
            isLongPress = true;
            const touch = e.touches[0];
            showContextMenu(touch.pageX, touch.pageY, msgEl);
        }, 600); // 600ms for long press
    }
}, { passive: true });

document.addEventListener('touchend', function (e) {
    clearTimeout(longPressTimer);
});

document.addEventListener('touchmove', function (e) {
    clearTimeout(longPressTimer);
});

function showContextMenu(x, y, msgEl) {
    const msgId = msgEl.getAttribute('data-msg-id');
    const author = msgEl.getAttribute('data-author');
    if (!msgId) return;

    const isOwn = !!(author && currentUsername && author.toLowerCase() === currentUsername.toLowerCase());
    const canManage = window.canManageMessages === true;
    const canKick = window.canKickMembers === true;
    const canBan = window.canBanMembers === true;
    const isTargetProtected = isOwn ||
        (window.communityOwner && author.toLowerCase() === window.communityOwner.toLowerCase()) ||
        author.toLowerCase() === 'admin';

    let menuHtml = '';

    menuHtml += `<div class="ctx-item" onclick="reactToMessage('${msgId}')"><i class="ph ph-heart"></i> React</div>`;
    menuHtml += `<div class="ctx-item" onclick="replyToMessage('${msgId}', '${author}')"><i class="ph ph-arrow-u-up-left"></i> Reply</div>`;

    if (isOwn) {
        menuHtml += `<div class="ctx-item" onclick="startEdit('${msgId}')"><i class="ph ph-pencil-simple"></i> Edit</div>`;
    }

    // Only author or members with MANAGE_MESSAGES permission can delete
    if (isOwn || canManage) {
        menuHtml += `<div class="ctx-item text-danger" onclick="deleteMessage('${msgId}')"><i class="ph ph-trash"></i> Delete</div>`;
    }

    if (!isOwn) {
        menuHtml += `<div class="ctx-item text-danger" onclick="reportMessage('${msgId}')"><i class="ph ph-flag"></i> Report Message</div>`;
        menuHtml += `<div class="ctx-item text-danger" onclick="toggleBlockUser('${author}')"><i class="ph ph-prohibit"></i> Block @${author}</div>`;
        // Only show Kick/Ban if user has permissions AND target is NOT an admin/owner
        if (canKick && !isTargetProtected) {
            menuHtml += `<div class="ctx-item text-danger" onclick="kickUser('${author}')"><i class="ph ph-user-minus"></i> Kick User</div>`;
        }
        if (canBan && !isTargetProtected) {
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
    if (confirm('Are you sure you want to kick ' + username + '?')) {
        // Mock kick action for MVP
        alert(username + ' was kicked from the server.');
    }
}
function banUser(username) {
    if (confirm('Are you sure you want to permanently ban ' + username + '?')) {
        // Mock ban action for MVP
        alert(username + ' was banned from the server.');
    }
}

// Quick Emoji Palette Handler
function toggleEmojiPalette(forceState) {
    const palette = document.getElementById('quickEmojiPalette');
    if (!palette) return;
    const shouldShow = typeof forceState === 'boolean' ? forceState : (palette.style.display === 'none' || !palette.style.display);
    palette.style.display = shouldShow ? 'block' : 'none';
}

function insertEmoji(emoji) {
    const input = document.getElementById('messageInput');
    if (!input) return;
    const start = input.selectionStart || input.value.length;
    const end = input.selectionEnd || input.value.length;
    const text = input.value;
    input.value = text.substring(0, start) + emoji + text.substring(end);
    input.focus();
    input.selectionStart = input.selectionEnd = start + emoji.length;
    toggleEmojiPalette(false);
}

// Close emoji palette on outside click
document.addEventListener('click', function (e) {
    const palette = document.getElementById('quickEmojiPalette');
    const trigger = document.getElementById('emojiPickerBtn');
    if (palette && palette.style.display !== 'none' && !palette.contains(e.target) && trigger && !trigger.contains(e.target)) {
        palette.style.display = 'none';
    }
});

// Auto-reconnect chat WebSocket when internet connectivity returns
window.addEventListener('online', function () {
    console.log('Network online detected, verifying chat connection...');
    if (!chatSocket || chatSocket.readyState !== WebSocket.OPEN) {
        initChatSocket();
    }
});


