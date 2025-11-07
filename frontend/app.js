// DiaryML Frontend - Vanilla JavaScript

const API_BASE = 'http://192.168.0.123:8000/api';

// State
const state = {
    unlocked: false,
    currentView: 'write',
    selectedImage: null,
    currentChatSession: null,
    chatSessions: []
};

// DOM Elements
const elements = {
    unlockScreen: document.getElementById('unlock-screen'),
    diaryScreen: document.getElementById('diary-screen'),
    unlockForm: document.getElementById('unlock-form'),
    passwordInput: document.getElementById('password-input'),
    unlockError: document.getElementById('unlock-error'),
    greetingText: document.getElementById('greeting-text'),
    suggestionsContainer: document.getElementById('suggestions-container'),
    entryForm: document.getElementById('entry-form'),
    entryContent: document.getElementById('entry-content'),
    imageInput: document.getElementById('image-input'),
    imagePreview: document.getElementById('image-preview'),
    entryFeedback: document.getElementById('entry-feedback'),
    moodDisplay: document.getElementById('mood-display'),
    chatForm: document.getElementById('chat-form'),
    chatInput: document.getElementById('chat-input'),
    chatMessages: document.getElementById('chat-messages'),
    entriesList: document.getElementById('entries-list'),
    moodTimeline: document.getElementById('mood-timeline'),
    lockBtn: document.getElementById('lock-btn')
};

// === Initialization ===

document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

function initializeApp() {
    // Setup event listeners
    setupEventListeners();

    // Check if already unlocked
    checkStatus();
}

function setupEventListeners() {
    // Unlock form
    elements.unlockForm.addEventListener('submit', handleUnlock);

    // Entry form
    elements.entryForm.addEventListener('submit', handleCreateEntry);
    elements.imageInput.addEventListener('change', handleImageSelect);

    // Chat form
    elements.chatForm.addEventListener('submit', handleChat);

    // Lock button
    elements.lockBtn.addEventListener('click', lockDiary);

    // Search button
    document.getElementById('search-btn').addEventListener('click', openSearchModal);

    // Settings button
    document.getElementById('settings-btn').addEventListener('click', openSettingsModal);

    // Chat session select
    document.getElementById('chat-session-select').addEventListener('change', handleChatSessionChange);

    // Tab switching
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', handleKeyboardShortcuts);

    // Word count on textarea
    elements.entryContent.addEventListener('input', updateWordCount);
}

// === Authentication ===

async function handleUnlock(e) {
    e.preventDefault();

    const password = elements.passwordInput.value;

    if (!password) {
        showError('Please enter a password');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/unlock`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password })
        });

        const data = await response.json();

        if (response.ok) {
            state.unlocked = true;
            showDiaryScreen();
            loadDailyGreeting();
            loadEntries();
        } else {
            showError(data.detail || 'Incorrect password');
        }
    } catch (error) {
        showError('Failed to connect to server. Make sure the backend is running.');
        console.error(error);
    }
}

async function checkStatus() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        const data = await response.json();

        if (data.unlocked) {
            state.unlocked = true;
            showDiaryScreen();
            loadDailyGreeting();
            loadEntries();
        }
    } catch (error) {
        console.log('Server not ready yet');
    }
}

function lockDiary() {
    state.unlocked = false;
    elements.unlockScreen.classList.add('active');
    elements.diaryScreen.classList.remove('active');
    elements.passwordInput.value = '';
}

function showError(message) {
    elements.unlockError.textContent = message;
    setTimeout(() => {
        elements.unlockError.textContent = '';
    }, 5000);
}

function showDiaryScreen() {
    elements.unlockScreen.classList.remove('active');
    elements.diaryScreen.classList.add('active');
    loadChatSessions();
}

// === Daily Greeting ===

async function loadDailyGreeting() {
    try {
        const response = await fetch(`${API_BASE}/daily-greeting`);
        const data = await response.json();

        // Display greeting
        elements.greetingText.textContent = data.greeting;

        // Display suggestions
        displaySuggestions(data.suggestions);

    } catch (error) {
        console.error('Failed to load greeting:', error);
        elements.greetingText.textContent = 'Good morning! Ready to capture today\'s thoughts?';
    }
}

function displaySuggestions(suggestions) {
    elements.suggestionsContainer.innerHTML = '';

    const allSuggestions = [
        ...(suggestions.projects || []),
        ...(suggestions.creative || []),
        ...(suggestions.media || []).slice(0, 2),
        ...(suggestions.wellness || [])
    ].slice(0, 6); // Limit to 6 suggestions

    allSuggestions.forEach(suggestion => {
        const chip = document.createElement('div');
        chip.className = 'suggestion-chip';
        chip.textContent = suggestion;
        chip.addEventListener('click', () => {
            elements.entryContent.value += `\n${suggestion}`;
            elements.entryContent.focus();
        });
        elements.suggestionsContainer.appendChild(chip);
    });
}

// === Entry Creation ===

function handleImageSelect(e) {
    const file = e.target.files[0];

    if (file) {
        state.selectedImage = file;

        // Preview image
        const reader = new FileReader();
        reader.onload = (e) => {
            elements.imagePreview.innerHTML = `<img src="${e.target.result}" alt="Preview" />`;
        };
        reader.readAsDataURL(file);
    }
}

async function handleCreateEntry(e) {
    e.preventDefault();

    const content = elements.entryContent.value.trim();

    if (!content) {
        showFeedback('Please write something first', 'error');
        return;
    }

    // Prepare form data
    const formData = new FormData();
    formData.append('content', content);
    formData.append('timestamp', new Date().toISOString());

    if (state.selectedImage) {
        formData.append('image', state.selectedImage);
    }

    try {
        elements.entryForm.classList.add('loading');

        const response = await fetch(`${API_BASE}/entries`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            showFeedback('Entry saved successfully!', 'success');

            // Display detected emotions
            displayMoods(data.emotions);

            // Clear form
            elements.entryContent.value = '';
            elements.imagePreview.innerHTML = '';
            state.selectedImage = null;
            elements.imageInput.value = '';

            // Reload entries
            loadEntries();

        } else {
            showFeedback(data.detail || 'Failed to save entry', 'error');
        }
    } catch (error) {
        showFeedback('Failed to save entry', 'error');
        console.error(error);
    } finally {
        elements.entryForm.classList.remove('loading');
    }
}

function showFeedback(message, type) {
    elements.entryFeedback.textContent = message;
    elements.entryFeedback.className = `feedback ${type}`;

    setTimeout(() => {
        elements.entryFeedback.className = 'feedback';
    }, 5000);
}

function displayMoods(emotions) {
    if (!emotions || Object.keys(emotions).length === 0) {
        elements.moodDisplay.classList.remove('visible');
        return;
    }

    const emotionColors = {
        joy: '#ffd93d',
        sadness: '#6bb6ff',
        anger: '#ff6b6b',
        fear: '#9d84b7',
        love: '#ff8fa3',
        surprise: '#95e1d3'
    };

    // Sort by score
    const sorted = Object.entries(emotions)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 4);

    let html = '<h4 style="margin-bottom: 0.75rem; font-size: 0.95rem;">Detected Mood:</h4>';

    sorted.forEach(([emotion, score]) => {
        const percentage = Math.round(score * 100);
        const color = emotionColors[emotion] || '#888';

        html += `
            <div class="mood-bar">
                <div class="mood-label">${emotion}</div>
                <div class="mood-progress">
                    <div class="mood-fill" style="width: ${percentage}%; background: ${color};"></div>
                </div>
                <div class="mood-value">${percentage}%</div>
            </div>
        `;
    });

    elements.moodDisplay.innerHTML = html;
    elements.moodDisplay.classList.add('visible');
}

// === Chat ===

async function handleChat(e) {
    e.preventDefault();

    const message = elements.chatInput.value.trim();

    if (!message) return;

    // Add user message to chat
    addChatMessage(message, 'user');

    // Clear input
    elements.chatInput.value = '';

    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message,
                session_id: state.currentChatSession
            })
        });

        const data = await response.json();

        if (response.ok) {
            addChatMessage(data.response, 'assistant');

            // Update current session ID if it was created
            if (data.session_id && !state.currentChatSession) {
                state.currentChatSession = data.session_id;
                loadChatSessions(); // Reload to show new session
            }
        } else {
            addChatMessage('Sorry, I encountered an error. Please try again.', 'assistant');
        }
    } catch (error) {
        addChatMessage('Failed to connect to AI. Make sure the model is loaded.', 'assistant');
        console.error(error);
    }
}

function addChatMessage(text, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${sender}`;
    messageDiv.textContent = text;

    // Add speaker button for assistant messages
    if (sender === 'assistant' && 'speechSynthesis' in window) {
        const speakBtn = document.createElement('button');
        speakBtn.className = 'speak-btn';
        speakBtn.textContent = '🔊';
        speakBtn.title = 'Read aloud';
        speakBtn.onclick = () => speakText(text);
        messageDiv.appendChild(speakBtn);
    }

    elements.chatMessages.appendChild(messageDiv);

    // Scroll to bottom
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

function speakText(text) {
    if ('speechSynthesis' in window) {
        // Cancel any ongoing speech
        window.speechSynthesis.cancel();

        // Create utterance
        const utterance = new SpeechSynthesisUtterance(text);

        // Use default voice (fast on Windows)
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;

        // Speak
        window.speechSynthesis.speak(utterance);
    }
}

// === Entries ===

async function loadEntries() {
    try {
        const response = await fetch(`${API_BASE}/entries?limit=20`);
        const data = await response.json();

        displayEntries(data.entries);
    } catch (error) {
        console.error('Failed to load entries:', error);
    }
}

function displayEntries(entries) {
    if (!entries || entries.length === 0) {
        elements.entriesList.innerHTML = '<p style="color: var(--text-secondary); text-align: center;">No entries yet. Start writing!</p>';
        return;
    }

    elements.entriesList.innerHTML = '';

    entries.forEach(entry => {
        const entryDiv = document.createElement('div');
        entryDiv.className = 'entry-item';

        const date = new Date(entry.timestamp).toLocaleDateString('en-US', {
            weekday: 'short',
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });

        let moodsHtml = '';
        if (entry.moods && Object.keys(entry.moods).length > 0) {
            const topMoods = Object.entries(entry.moods)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 3);

            moodsHtml = '<div class="entry-moods">';
            topMoods.forEach(([emotion, score]) => {
                const emotionColors = {
                    joy: '#ffd93d',
                    sadness: '#6bb6ff',
                    anger: '#ff6b6b',
                    fear: '#9d84b7',
                    love: '#ff8fa3',
                    surprise: '#95e1d3'
                };

                const color = emotionColors[emotion] || '#888';
                moodsHtml += `<span class="mood-tag" style="border-color: ${color}; color: ${color};">${emotion}</span>`;
            });
            moodsHtml += '</div>';
        }

        entryDiv.innerHTML = `
            <div class="entry-header">
                <div class="entry-date">${date}</div>
                <div class="entry-actions">
                    <button class="edit-btn" onclick="editEntry(${entry.id})" title="Edit entry">✏️</button>
                    <button class="delete-btn" onclick="deleteEntry(${entry.id})" title="Delete entry">×</button>
                </div>
            </div>
            <div class="entry-preview" id="entry-preview-${entry.id}">${entry.content}</div>
            <div class="entry-edit" id="entry-edit-${entry.id}" style="display: none;">
                <textarea class="entry-edit-textarea" id="entry-textarea-${entry.id}">${entry.content}</textarea>
                <div class="entry-edit-actions">
                    <button class="edit-save-btn" onclick="saveEditedEntry(${entry.id})">Save</button>
                    <button class="edit-cancel-btn" onclick="cancelEditEntry(${entry.id})">Cancel</button>
                </div>
            </div>
            ${moodsHtml}
        `;

        elements.entriesList.appendChild(entryDiv);
    });
}

async function deleteEntry(entryId) {
    if (!confirm('Are you sure you want to delete this entry? This cannot be undone.')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/entries/${entryId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            // Reload entries
            loadEntries();
        } else {
            alert('Failed to delete entry');
        }
    } catch (error) {
        console.error('Error deleting entry:', error);
        alert('Failed to delete entry');
    }
}

// === Mood Timeline ===

async function loadMoodTimeline() {
    try {
        const response = await fetch(`${API_BASE}/analytics/mood-timeline?days=14`);
        const data = await response.json();

        displayMoodTimeline(data.timeline);
    } catch (error) {
        console.error('Failed to load mood timeline:', error);
    }
}

function displayMoodTimeline(timeline) {
    if (!timeline || timeline.length === 0) {
        elements.moodTimeline.innerHTML = '<p style="color: var(--text-secondary); text-align: center;">Not enough data yet. Keep journaling!</p>';
        return;
    }

    // Group by date
    const byDate = {};
    timeline.forEach(entry => {
        if (!byDate[entry.date]) {
            byDate[entry.date] = {};
        }
        byDate[entry.date][entry.emotion] = entry.avg_score;
    });

    elements.moodTimeline.innerHTML = '';

    Object.entries(byDate).reverse().slice(0, 10).forEach(([date, emotions]) => {
        const timelineEntry = document.createElement('div');
        timelineEntry.className = 'timeline-entry';

        const dateFormatted = new Date(date).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric'
        });

        let emotionsHtml = '';
        const emotionColors = {
            joy: '#ffd93d',
            sadness: '#6bb6ff',
            anger: '#ff6b6b',
            fear: '#9d84b7',
            love: '#ff8fa3',
            surprise: '#95e1d3'
        };

        Object.entries(emotions).forEach(([emotion, score]) => {
            const width = Math.round(score * 100);
            const color = emotionColors[emotion] || '#888';

            emotionsHtml += `
                <div class="emotion-bar" style="width: ${width}px; background: ${color};" title="${emotion}: ${width}%">
                    ${width > 30 ? emotion : ''}
                </div>
            `;
        });

        timelineEntry.innerHTML = `
            <div class="timeline-date">${dateFormatted}</div>
            <div class="timeline-emotions">${emotionsHtml}</div>
        `;

        elements.moodTimeline.appendChild(timelineEntry);
    });
}

// === Tab Switching ===

function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabName);
    });

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });

    const contentMap = {
        'chat': 'chat-tab',
        'entries': 'entries-tab',
        'mood': 'mood-tab',
        'insights': 'insights-tab'
    };

    const contentId = contentMap[tabName];
    if (contentId) {
        document.getElementById(contentId).classList.add('active');

        // Load data if needed
        if (tabName === 'mood') {
            loadMoodTimeline();
        } else if (tabName === 'insights') {
            initializeInsightsTab();
        }
    }
}

// === Entry Editing ===

function editEntry(entryId) {
    // Hide preview, show edit textarea
    const preview = document.getElementById(`entry-preview-${entryId}`);
    const edit = document.getElementById(`entry-edit-${entryId}`);

    if (preview && edit) {
        preview.style.display = 'none';
        edit.style.display = 'block';

        // Focus the textarea
        const textarea = document.getElementById(`entry-textarea-${entryId}`);
        if (textarea) {
            textarea.focus();
            // Move cursor to end
            textarea.setSelectionRange(textarea.value.length, textarea.value.length);
        }
    }
}

function cancelEditEntry(entryId) {
    // Show preview, hide edit textarea
    const preview = document.getElementById(`entry-preview-${entryId}`);
    const edit = document.getElementById(`entry-edit-${entryId}`);

    if (preview && edit) {
        preview.style.display = 'block';
        edit.style.display = 'none';
    }
}

async function saveEditedEntry(entryId) {
    const textarea = document.getElementById(`entry-textarea-${entryId}`);

    if (!textarea) {
        return;
    }

    const newContent = textarea.value.trim();

    if (!newContent) {
        alert('Entry cannot be empty');
        return;
    }

    try {
        const formData = new FormData();
        formData.append('content', newContent);

        const response = await fetch(`${API_BASE}/entries/${entryId}`, {
            method: 'PUT',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            // Update was successful
            // Reload entries to show the updated content
            loadEntries();

            // Show success message briefly
            const preview = document.getElementById(`entry-preview-${entryId}`);
            if (preview) {
                preview.style.background = 'rgba(76, 175, 80, 0.1)';
                setTimeout(() => {
                    preview.style.background = '';
                }, 1000);
            }
        } else {
            alert(data.detail || 'Failed to update entry');
        }
    } catch (error) {
        console.error('Error updating entry:', error);
        alert('Failed to update entry');
    }
}

// === Search ===

function openSearchModal() {
    const modal = document.getElementById('search-modal');
    if (modal) {
        modal.style.display = 'flex';
        // Focus search input
        document.getElementById('search-query').focus();
    }
}

function closeSearchModal() {
    const modal = document.getElementById('search-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

async function performSearch() {
    const query = document.getElementById('search-query').value.trim();
    const startDate = document.getElementById('search-start-date').value;
    const endDate = document.getElementById('search-end-date').value;

    const moodCheckboxes = document.querySelectorAll('input[name="mood"]:checked');
    const selectedMoods = Array.from(moodCheckboxes).map(cb => cb.value);

    // Build query params
    const params = new URLSearchParams();
    if (query) params.append('q', query);
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (selectedMoods.length > 0) params.append('emotions', selectedMoods.join(','));

    try {
        const response = await fetch(`${API_BASE}/search?${params.toString()}`);
        const data = await response.json();

        displaySearchResults(data.results, query);
    } catch (error) {
        console.error('Search error:', error);
        document.getElementById('search-results').innerHTML =
            '<p style="color: var(--error); text-align: center;">Search failed. Please try again.</p>';
    }
}

function displaySearchResults(results, query) {
    const resultsDiv = document.getElementById('search-results');

    if (!results || results.length === 0) {
        resultsDiv.innerHTML = '<p style="text-align: center; color: var(--text-secondary);">No entries found matching your criteria.</p>';
        return;
    }

    resultsDiv.innerHTML = '';

    results.forEach(entry => {
        const date = new Date(entry.timestamp).toLocaleDateString('en-US', {
            weekday: 'short',
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });

        // Highlight search term if present
        let content = entry.content;
        if (query) {
            const regex = new RegExp(`(${query})`, 'gi');
            content = content.replace(regex, '<span class="search-highlight">$1</span>');
        }

        // Truncate content
        const preview = content.length > 300 ? content.substring(0, 300) + '...' : content;

        const resultDiv = document.createElement('div');
        resultDiv.className = 'search-result-item';
        resultDiv.innerHTML = `
            <div class="search-result-date">${date}</div>
            <div class="search-result-content">${preview}</div>
        `;

        resultDiv.addEventListener('click', () => {
            closeSearchModal();
            // Switch to entries tab and scroll to entry
            switchTab('entries');
            loadEntries();
        });

        resultsDiv.appendChild(resultDiv);
    });
}

// === Keyboard Shortcuts ===

function handleKeyboardShortcuts(e) {
    // Ctrl/Cmd + F: Search
    if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        e.preventDefault();
        openSearchModal();
    }

    // Ctrl/Cmd + L: Lock
    if ((e.ctrlKey || e.metaKey) && e.key === 'l') {
        e.preventDefault();
        lockDiary();
    }

    // Ctrl/Cmd + S: Save entry (if in entry textarea)
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        if (document.activeElement === elements.entryContent) {
            e.preventDefault();
            elements.entryForm.dispatchEvent(new Event('submit'));
        }
    }

    // Escape: Close modals
    if (e.key === 'Escape') {
        closeSearchModal();
    }
}

// === Word Count ===

function updateWordCount() {
    const text = elements.entryContent.value;
    const words = text.trim().split(/\s+/).filter(w => w.length > 0);
    const wordCount = words.length;
    const charCount = text.length;

    // Create or update word count display
    let wordCountDiv = document.getElementById('word-count-display');
    if (!wordCountDiv) {
        wordCountDiv = document.createElement('div');
        wordCountDiv.id = 'word-count-display';
        wordCountDiv.style.cssText = 'color: var(--text-secondary); font-size: 0.85rem; margin-top: 0.5rem; text-align: right;';
        elements.entryForm.insertBefore(wordCountDiv, elements.moodDisplay);
    }

    wordCountDiv.textContent = `${wordCount} words · ${charCount} characters`;
}

// === Backup & Restore ===

async function createBackup() {
    if (!confirm('Create a backup of your diary? This will download a zip file.')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/backup`);

        if (response.ok) {
            // Download the zip file
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;

            // Get filename from response headers
            const contentDisposition = response.headers.get('Content-Disposition');
            const filename = contentDisposition
                ? contentDisposition.split('filename=')[1].replace(/['"]/g, '')
                : `DiaryML_Backup_${new Date().toISOString().split('T')[0]}.zip`;

            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);

            alert('Backup created successfully!');
        } else {
            alert('Failed to create backup');
        }
    } catch (error) {
        console.error('Backup error:', error);
        alert('Failed to create backup');
    }
}

// Make backup function available globally
window.createBackup = createBackup;

// === Chat Session Management ===

async function loadChatSessions() {
    try {
        const response = await fetch(`${API_BASE}/chat/sessions`);
        const data = await response.json();

        state.chatSessions = data.sessions || [];

        // Update dropdown
        const select = document.getElementById('chat-session-select');
        select.innerHTML = '<option value="">New Chat</option>';

        state.chatSessions.forEach(session => {
            const option = document.createElement('option');
            option.value = session.id;
            const date = new Date(session.created_at).toLocaleDateString();
            const time = new Date(session.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            option.textContent = `${session.title || 'Chat'} (${date} ${time}) - ${session.message_count || 0} msgs`;
            select.appendChild(option);
        });

        // Set current session in dropdown
        if (state.currentChatSession) {
            select.value = state.currentChatSession;
        }
    } catch (error) {
        console.error('Failed to load chat sessions:', error);
    }
}

async function handleChatSessionChange(e) {
    const sessionId = e.target.value ? parseInt(e.target.value) : null;

    if (!sessionId) {
        // New chat
        state.currentChatSession = null;
        clearChatMessages();
        return;
    }

    // Load session messages
    state.currentChatSession = sessionId;
    await loadChatSessionMessages(sessionId);
}

async function loadChatSessionMessages(sessionId) {
    try {
        const response = await fetch(`${API_BASE}/chat/sessions/${sessionId}`);
        const data = await response.json();

        // Clear chat
        clearChatMessages();

        // Add messages
        data.messages.forEach(msg => {
            addChatMessage(msg.content, msg.role);
        });
    } catch (error) {
        console.error('Failed to load chat messages:', error);
    }
}

function clearChatMessages() {
    elements.chatMessages.innerHTML = '<div class="chat-message system">Ask me anything about your entries, or just talk about what\'s on your mind...</div>';
}

async function startNewChat() {
    state.currentChatSession = null;
    document.getElementById('chat-session-select').value = '';
    clearChatMessages();
}

async function clearCurrentChat() {
    if (!state.currentChatSession) {
        clearChatMessages();
        return;
    }

    if (!confirm('Clear all messages in this chat?')) {
        return;
    }

    try {
        await fetch(`${API_BASE}/chat/sessions/${state.currentChatSession}/clear`, {
            method: 'POST'
        });

        clearChatMessages();
        loadChatSessions();
    } catch (error) {
        console.error('Failed to clear chat:', error);
        alert('Failed to clear chat');
    }
}

async function deleteCurrentChat() {
    if (!state.currentChatSession) {
        alert('No chat session selected');
        return;
    }

    if (!confirm('Delete this chat permanently?')) {
        return;
    }

    try {
        await fetch(`${API_BASE}/chat/sessions/${state.currentChatSession}`, {
            method: 'DELETE'
        });

        state.currentChatSession = null;
        document.getElementById('chat-session-select').value = '';
        clearChatMessages();
        loadChatSessions();
    } catch (error) {
        console.error('Failed to delete chat:', error);
        alert('Failed to delete chat');
    }
}

// Make functions globally available
window.startNewChat = startNewChat;
window.clearCurrentChat = clearCurrentChat;
window.deleteCurrentChat = deleteCurrentChat;

// === Settings & Model Management ===

function openSettingsModal() {
    const modal = document.getElementById('settings-modal');
    if (modal) {
        modal.style.display = 'flex';
        loadModelInfo();
    }
}

function closeSettingsModal() {
    const modal = document.getElementById('settings-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

async function loadModelInfo() {
    try {
        const response = await fetch(`${API_BASE}/models/list`);
        const data = await response.json();

        // Display current model info
        const modelInfoDiv = document.getElementById('model-info');
        if (data.current_model) {
            const cm = data.current_model;
            modelInfoDiv.innerHTML = `
                <div style="font-weight: 600; margin-bottom: 0.5rem;">Currently Loaded Model</div>
                <div style="font-size: 0.95rem; margin-bottom: 0.5rem; color: var(--accent);">
                    📦 <strong>${cm.name || cm.filename}</strong>
                </div>
                <div style="font-size: 0.85rem;">
                    Size: <strong>${cm.size}</strong> |
                    Quantization: <strong>${cm.quantization}</strong>
                </div>
                <div style="font-size: 0.85rem; margin-top: 0.5rem; color: var(--text-secondary);">
                    ${cm.is_thinking ? '<span style="color: var(--accent);">🧠 Thinking Model</span>' : '📝 Standard Model'} |
                    ${cm.has_vision ? '<span style="color: var(--accent);">👁️ Vision Capable</span>' : '💬 Text-Only'}
                </div>
            `;
        } else {
            modelInfoDiv.innerHTML = '<div style="color: var(--error);">No model loaded</div>';
        }

        // Display available models
        const modelListDiv = document.getElementById('model-list');
        if (data.models && data.models.length > 0) {
            modelListDiv.innerHTML = '<h4 style="margin-bottom: 0.75rem;">Available Models</h4>';

            data.models.forEach(model => {
                const modelCard = document.createElement('div');
                modelCard.className = 'model-card';
                modelCard.innerHTML = `
                    <div class="model-card-info">
                        <div class="model-name">${model.filename}</div>
                        <div class="model-size">${model.size_mb} MB</div>
                    </div>
                    <button class="model-switch-btn" onclick="switchToModel('${model.filename}')">
                        Switch
                    </button>
                `;
                modelListDiv.appendChild(modelCard);
            });
        } else {
            modelListDiv.innerHTML = '<p style="color: var(--text-secondary);">No models found in models/ directory</p>';
        }
    } catch (error) {
        console.error('Failed to load model info:', error);
        document.getElementById('model-info').innerHTML = '<div style="color: var(--error);">Failed to load model info</div>';
    }
}

async function switchToModel(filename) {
    if (!confirm(`Switch to model: ${filename}?\n\nThis may take a moment to load.`)) {
        return;
    }

    try {
        const formData = new FormData();
        formData.append('model_filename', filename);

        const response = await fetch(`${API_BASE}/models/switch`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            const modelName = data.model_info.name || data.model_info.filename;
            const visionStatus = data.model_info.has_vision ? '👁️ Vision: Yes' : '💬 Vision: No (Text-Only)';
            const thinkingStatus = data.model_info.is_thinking ? '🧠 Thinking Model' : '📝 Standard Model';
            alert(`✓ Successfully switched to:\n📦 ${modelName}\n\nModel Info:\n- Size: ${data.model_info.size}\n- Quantization: ${data.model_info.quantization}\n- Context: ${data.model_info.context_window} tokens\n- ${visionStatus}\n- ${thinkingStatus}\n\n✓ This model will be remembered and reloaded on next startup!`);
            loadModelInfo(); // Reload to show new current model
        } else {
            alert(`Failed to switch model: ${data.detail}`);
        }
    } catch (error) {
        console.error('Failed to switch model:', error);
        alert('Failed to switch model. Check console for details.');
    }
}

// Make functions globally available
window.openSettingsModal = openSettingsModal;
window.closeSettingsModal = closeSettingsModal;
window.switchToModel = switchToModel;

// ========================================
// INSIGHTS TAB FUNCTIONALITY
// ========================================

let insightsCache = {
    moodCycles: null,
    projectMomentum: null,
    emotionalTriggers: null
};

function initializeInsightsTab() {
    // Setup insights navigation
    setupInsightsNavigation();

    // Load the first insight (mood cycles) by default
    loadInsight('mood-cycles');
}

function setupInsightsNavigation() {
    const insightNavBtns = document.querySelectorAll('.insights-nav-btn');

    insightNavBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Update button states
            insightNavBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Update content visibility
            document.querySelectorAll('.insight-content').forEach(content => {
                content.classList.remove('active');
            });

            const insightType = btn.dataset.insight;
            document.getElementById(`${insightType}-content`).classList.add('active');

            // Load data
            loadInsight(insightType);
        });
    });
}

async function loadInsight(insightType) {
    const cacheKey = insightType.replace(/-/g, '_');

    // Check cache first
    if (insightsCache[cacheKey]) {
        renderInsight(insightType, insightsCache[cacheKey]);
        return;
    }

    // Fetch data from API
    const endpointMap = {
        'mood-cycles': '/insights/mood-cycles',
        'project-momentum': '/insights/project-momentum',
        'emotional-triggers': '/insights/emotional-triggers'
    };

    const endpoint = endpointMap[insightType];
    if (!endpoint) return;

    try {
        const response = await fetch(`${API_BASE}${endpoint}?days=90`);
        const data = await response.json();

        // Cache the data
        insightsCache[cacheKey] = data;

        // Render the insight
        renderInsight(insightType, data);

    } catch (error) {
        console.error(`Error loading ${insightType}:`, error);
        showInsightError(insightType, 'Failed to load insights. Please try again.');
    }
}

function renderInsight(insightType, data) {
    const renderMap = {
        'mood-cycles': renderMoodCycles,
        'project-momentum': renderProjectMomentum,
        'emotional-triggers': renderEmotionalTriggers
    };

    const renderer = renderMap[insightType];
    if (renderer) {
        renderer(data);
    }
}

function renderMoodCycles(data) {
    const container = document.getElementById('mood-cycles-data');
    const loadingEl = document.querySelector('#mood-cycles-content .insight-loading');

    if (!data || !data.day_of_week || Object.keys(data.day_of_week).length === 0) {
        showInsightEmpty('mood-cycles', 'Not enough mood data yet. Keep journaling to discover your patterns!', '📊');
        return;
    }

    let html = '';

    // Summary
    if (data.summary) {
        html += `
            <div class="insight-summary">
                <p><strong>Key Insights:</strong></p>
                ${data.summary.map(s => `<p>• ${s}</p>`).join('')}
            </div>
        `;
    }

    // Day of Week Patterns
    if (data.day_of_week) {
        html += `
            <div class="insight-section">
                <h4><span class="insight-section-icon">📅</span> Day of Week Patterns</h4>
                <div class="day-of-week-grid">
        `;

        const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
        const bestDay = data.best_day?.day;
        const worstDay = data.worst_day?.day;

        days.forEach(day => {
            const dayData = data.day_of_week[day];
            if (!dayData) return;

            const topMood = Object.entries(dayData.moods)
                .sort((a, b) => b[1] - a[1])[0];

            const isBest = day === bestDay;
            const isWorst = day === worstDay;
            const cardClass = isBest ? 'best' : (isWorst ? 'worst' : '');

            html += `
                <div class="day-card ${cardClass}">
                    <div class="day-name">${day}</div>
                    <div class="day-mood">${topMood ? topMood[0] : 'N/A'}</div>
                    <div class="day-mood">${dayData.count} entries</div>
                </div>
            `;
        });

        html += `
                </div>
            </div>
        `;
    }

    // Time of Day Patterns
    if (data.time_of_day) {
        html += `
            <div class="insight-section">
                <h4><span class="insight-section-icon">⏰</span> Time of Day Patterns</h4>
                <div class="time-of-day-grid">
        `;

        const timeIcons = {
            'Morning': '🌅',
            'Afternoon': '☀️',
            'Evening': '🌆',
            'Night': '🌙'
        };

        ['Morning', 'Afternoon', 'Evening', 'Night'].forEach(time => {
            const timeData = data.time_of_day[time];
            if (!timeData || timeData.count === 0) return;

            const topMoods = Object.entries(timeData.moods)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 3);

            html += `
                <div class="time-card">
                    <div class="time-card-header">
                        <span class="time-icon">${timeIcons[time]}</span>
                        <span class="time-label">${time}</span>
                    </div>
                    <ul class="time-mood-list">
                        ${topMoods.map(([emotion, score]) =>
                            `<li>${emotion}: ${(score * 100).toFixed(0)}%</li>`
                        ).join('')}
                    </ul>
                    <div style="color: var(--text-secondary); font-size: 0.75rem; margin-top: 0.5rem;">
                        ${timeData.count} entries
                    </div>
                </div>
            `;
        });

        html += `
                </div>
            </div>
        `;
    }

    // Mood Streaks
    if (data.mood_streaks && data.mood_streaks.length > 0) {
        html += `
            <div class="insight-section">
                <h4><span class="insight-section-icon">🔥</span> Mood Streaks</h4>
                <ul class="streak-list">
        `;

        data.mood_streaks.forEach(streak => {
            html += `
                <li class="streak-item">
                    <div class="streak-dates">${streak.start_date} → ${streak.end_date} (${streak.length} days)</div>
                    <div class="streak-mood">Dominant mood: ${streak.mood}</div>
                </li>
            `;
        });

        html += `
                </ul>
            </div>
        `;
    }

    container.innerHTML = html;
    loadingEl.style.display = 'none';
    container.style.display = 'block';
}

function renderProjectMomentum(data) {
    const container = document.getElementById('project-momentum-data');
    const loadingEl = document.querySelector('#project-momentum-content .insight-loading');

    if (!data || !data.projects || data.projects.length === 0) {
        showInsightEmpty('project-momentum', 'No projects detected yet. Mention your projects in your entries!', '🚀');
        return;
    }

    let html = '';

    // Summary
    if (data.summary) {
        html += `
            <div class="insight-summary">
                <p><strong>Project Overview:</strong></p>
                ${data.summary.map(s => `<p>• ${s}</p>`).join('')}
            </div>
        `;
    }

    // Group projects by status
    const grouped = {
        stalled: data.projects.filter(p => p.classification === 'stalled'),
        accelerating: data.projects.filter(p => p.classification === 'accelerating'),
        consistent: data.projects.filter(p => p.classification === 'consistent')
    };

    const statusConfig = {
        stalled: { icon: '⚠️', title: 'Stalled Projects', color: '#f59e0b' },
        accelerating: { icon: '🚀', title: 'Accelerating Projects', color: '#10b981' },
        consistent: { icon: '📊', title: 'Consistent Projects', color: '#3b82f6' }
    };

    Object.entries(grouped).forEach(([status, projects]) => {
        if (projects.length === 0) return;

        const config = statusConfig[status];
        html += `
            <div class="insight-section">
                <h4><span class="insight-section-icon">${config.icon}</span> ${config.title}</h4>
                <div class="project-grid">
        `;

        projects.forEach(project => {
            html += `
                <div class="project-card ${status}">
                    <div class="project-card-header">
                        <div class="project-name">${project.name}</div>
                        <div class="project-status ${status}">${status}</div>
                    </div>
                    <div class="project-metrics">
                        <div class="project-metric">
                            <div class="project-metric-label">Total Mentions</div>
                            <div class="project-metric-value">${project.total_mentions}</div>
                        </div>
                        <div class="project-metric">
                            <div class="project-metric-label">Avg/Week</div>
                            <div class="project-metric-value">${project.avg_mentions_per_week.toFixed(1)}</div>
                        </div>
                        <div class="project-metric">
                            <div class="project-metric-label">Last Seen</div>
                            <div class="project-metric-value">${project.days_since_last_mention}d ago</div>
                        </div>
                    </div>
                </div>
            `;
        });

        html += `
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
    loadingEl.style.display = 'none';
    container.style.display = 'block';
}

function renderEmotionalTriggers(data) {
    const container = document.getElementById('emotional-triggers-data');
    const loadingEl = document.querySelector('#emotional-triggers-content .insight-loading');

    if (!data || (!data.positive_triggers?.length && !data.negative_triggers?.length)) {
        showInsightEmpty('emotional-triggers', 'Not enough data to identify emotional triggers yet.', '💭');
        return;
    }

    let html = '';

    // Summary
    if (data.summary) {
        html += `
            <div class="insight-summary">
                <p><strong>Emotional Patterns:</strong></p>
                ${data.summary.map(s => `<p>• ${s}</p>`).join('')}
            </div>
        `;
    }

    html += '<div class="trigger-grid">';

    // Positive Triggers
    if (data.positive_triggers && data.positive_triggers.length > 0) {
        html += `
            <div class="trigger-section positive">
                <h5>✨ Positive Triggers</h5>
                <ul class="trigger-list">
        `;

        data.positive_triggers.slice(0, 10).forEach(trigger => {
            html += `
                <li class="trigger-item">
                    <div>
                        <span class="trigger-keyword">${trigger.keyword}</span>
                        <span class="trigger-emotion"> → ${trigger.emotion}</span>
                    </div>
                    <span class="trigger-score">${(trigger.correlation * 100).toFixed(0)}%</span>
                </li>
            `;
        });

        html += `
                </ul>
            </div>
        `;
    }

    // Negative Triggers
    if (data.negative_triggers && data.negative_triggers.length > 0) {
        html += `
            <div class="trigger-section negative">
                <h5>⚡ Negative Triggers</h5>
                <ul class="trigger-list">
        `;

        data.negative_triggers.slice(0, 10).forEach(trigger => {
            html += `
                <li class="trigger-item">
                    <div>
                        <span class="trigger-keyword">${trigger.keyword}</span>
                        <span class="trigger-emotion"> → ${trigger.emotion}</span>
                    </div>
                    <span class="trigger-score">${(trigger.correlation * 100).toFixed(0)}%</span>
                </li>
            `;
        });

        html += `
                </ul>
            </div>
        `;
    }

    html += '</div>';

    container.innerHTML = html;
    loadingEl.style.display = 'none';
    container.style.display = 'block';
}

function showInsightEmpty(insightType, message, icon) {
    const container = document.getElementById(`${insightType}-data`);
    const loadingEl = document.querySelector(`#${insightType}-content .insight-loading`);

    container.innerHTML = `
        <div class="insight-empty">
            <div class="insight-empty-icon">${icon}</div>
            <p><strong>${message}</strong></p>
            <p>Your patterns will appear here as you continue journaling.</p>
        </div>
    `;

    loadingEl.style.display = 'none';
    container.style.display = 'block';
}

function showInsightError(insightType, message) {
    const container = document.getElementById(`${insightType}-data`);
    const loadingEl = document.querySelector(`#${insightType}-content .insight-loading`);

    container.innerHTML = `
        <div class="insight-empty">
            <div class="insight-empty-icon">⚠️</div>
            <p><strong>${message}</strong></p>
        </div>
    `;

    loadingEl.style.display = 'none';
    container.style.display = 'block';
}

// ========================================
// MOBILE RESPONSIVE MENU
// ========================================

// Initialize mobile menu
function initMobileMenu() {
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const mobileOverlay = document.getElementById('mobile-overlay');
    const sidebar = document.querySelector('.sidebar');

    if (!mobileMenuBtn || !mobileOverlay) {
        return; // Elements don't exist yet
    }

    // Show mobile menu button on small screens
    function updateMobileMenuVisibility() {
        if (window.innerWidth <= 1024) {
            mobileMenuBtn.style.display = 'flex';
        } else {
            mobileMenuBtn.style.display = 'none';
            // Close sidebar if open when resizing to desktop
            sidebar?.classList.remove('mobile-open');
            mobileOverlay.classList.remove('active');
        }
    }

    // Toggle mobile menu
    function toggleMobileMenu() {
        sidebar?.classList.toggle('mobile-open');
        mobileOverlay.classList.toggle('active');
        
        // Prevent body scrolling when menu is open
        if (sidebar?.classList.contains('mobile-open')) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = '';
        }
    }

    // Close mobile menu
    function closeMobileMenu() {
        sidebar?.classList.remove('mobile-open');
        mobileOverlay.classList.remove('active');
        document.body.style.overflow = '';
    }

    // Event listeners
    mobileMenuBtn.addEventListener('click', toggleMobileMenu);
    mobileOverlay.addEventListener('click', closeMobileMenu);

    // Close menu when clicking sidebar links
    if (sidebar) {
        sidebar.addEventListener('click', (e) => {
            if (e.target.tagName === 'BUTTON' || e.target.closest('button')) {
                closeMobileMenu();
            }
        });
    }

    // Handle window resize
    window.addEventListener('resize', updateMobileMenuVisibility);

    // Initial check
    updateMobileMenuVisibility();
}

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMobileMenu);
} else {
    initMobileMenu();
}

// Also initialize after diary unlock
const originalUnlockListener = document.getElementById('unlock-form')?.addEventListener;
if (originalUnlockListener) {
    const unlockForm = document.getElementById('unlock-form');
    unlockForm?.addEventListener('submit', (e) => {
        // Give the unlock process a moment, then initialize mobile menu
        setTimeout(initMobileMenu, 500);
    });
}

// Make mobile menu functions globally available
window.initMobileMenu = initMobileMenu;
