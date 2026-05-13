        // ===================================================================
        // Application State
        // ===================================================================
        const state = {
            chatHistory: [],
            isLoading: false,
            requestController: null
        };

        // ===================================================================
        // DOM Elements
        // ===================================================================
        const elements = {
            chatForm: document.getElementById('chatForm'),
            chatInput: document.getElementById('chatInput'),
            chatOutput: document.getElementById('chatOutput'),
            modelSelect: document.getElementById('modelSelect'),
            resetBtn: document.getElementById('resetBtn'),
            stopBtn: document.getElementById('stopBtn')
        };

        // ===================================================================
        // Utility Functions
        // ===================================================================
        // Keep client history capped to avoid growing the request payload
        const MAX_CLIENT_HISTORY = 20;

        const utils = {
            scrollToBottom() {
                requestAnimationFrame(() => {
                    window.scrollTo({
                        top: document.body.scrollHeight,
                        behavior: 'smooth'
                    });
                });
            },

            formatMessage(role, content) {
                const isUser = role === 'user';
                const label = isUser ? 'You' : 'TickerTalk';
                const messageClass = isUser ? 'user' : 'agent';
                const avatarClass = isUser ? 'user-avatar' : 'agent-avatar';
                const avatarText = isUser ? 'Y' : 'T';

                let processed = (content || '').replace(/\r\n/g, '\n');

                // Always convert inline markdown to HTML (works alongside any existing HTML tags)
                processed = processed
                    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
                    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                    .replace(/\*(?!\s)([^*\n]+?)\*/g, '<em>$1</em>'); // exclude bullet * (always followed by space)

                // If the content now contains block-level HTML elements, render as-is
                // (the LLM already structured it). Only do our own block parsing for plain text.
                const hasBlockHtml = /<(br|p|ul|ol|li|div|h[1-6]|blockquote)[\s>]/i.test(processed);

                if (!hasBlockHtml) {
                    // Convert unordered list markers (- or *) at line starts into <ul>
                    const lines = processed.split('\n');
                    let i = 0;
                    const out = [];
                    while (i < lines.length) {
                        const line = lines[i].trim();
                        // Ordered list (e.g., "1. item")
                        if (/^\d+\.\s+/.test(line)) {
                            out.push('<ol>');
                            while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
                                const itemText = lines[i].replace(/^\s*\d+\.\s+/, '').trim();
                                out.push(`<li>${itemText}</li>`);
                                i++;
                            }
                            out.push('</ol>');
                            continue;
                        }

                        // Unordered list
                        if (/^[\-*+]\s+/.test(line)) {
                            out.push('<ul>');
                            while (i < lines.length && /^[\s\-*+]+\s+/.test(lines[i])) {
                                const itemText = lines[i].replace(/^[\s\-*+]+\s+/, '').trim();
                                out.push(`<li>${itemText}</li>`);
                                i++;
                            }
                            out.push('</ul>');
                            continue;
                        }

                        // Normal paragraph line: convert single newlines to <br>
                        if (line === '') {
                            out.push('<br>');
                        } else {
                            out.push(line);
                        }

                        i++;
                    }

                    // Join with spaces but preserve explicit <br> and list markup
                    processed = out.join('\n');
                    // Preserve double-newlines as paragraph breaks, then convert singles
                    processed = processed.replace(/\n{2,}/g, '<br><br>');
                    processed = processed.replace(/\n/g, '<br>');
                    // Collapse 3+ consecutive <br> to two (paragraph gap)
                    processed = processed.replace(/(<br\s*\/?>\s*){3,}/gi, '<br><br>');
                } else {
                    // Has block HTML — preserve double breaks, collapse excess
                    processed = processed.replace(/\n{2,}/g, '<br><br>');
                    processed = processed.replace(/(<br\s*\/?>\s*){3,}/gi, '<br><br>');
                } // end !hasBlockHtml

                return `
                    <div class="message ${isUser ? 'user' : ''}">
                        <div class="avatar ${avatarClass}">${avatarText}</div>
                        <div class="message-body">
                            <div class="message-label">${label}</div>
                            <div class="message-content ${messageClass}">${processed}</div>
                        </div>
                    </div>
                `;
            },

            showLoading() {
                const loadingHtml = `
                    <div class="message" id="loadingMsg">
                        <div class="avatar agent-avatar">T</div>
                        <div class="message-body">
                            <div class="message-label">TickerTalk</div>
                            <div class="message-content agent">
                                <div class="thinking-dots"><span></span><span></span><span></span></div>
                            </div>
                        </div>
                    </div>
                `;
                elements.chatOutput.insertAdjacentHTML('beforeend', loadingHtml);
                this.scrollToBottom();
            },

            removeLoading() {
                const loadingMsg = document.getElementById('loadingMsg');
                if (loadingMsg) loadingMsg.remove();
            },

            clearEmptyState() {
                const emptyState = elements.chatOutput.querySelector('.empty-state');
                if (emptyState) {
                    emptyState.remove();
                }
            },

            renderAnalysisReply(reply) {
                const parsed = this.parseAnalysisJson(reply);
                if (!parsed) return null;

                const recs = parsed.recommendations || {};
                const labelClassMap = {
                    'STRONG BUY': 'badge-strong-buy',
                    'BUY': 'badge-buy',
                    'HOLD': 'badge-hold',
                    'SELL': 'badge-sell'
                };
                const iconMap = {
                    'STRONG BUY': '▲▲',
                    'BUY': '▲',
                    'HOLD': '◆',
                    'SELL': '▼'
                };

                const badge = (label) => {
                    const normalized = (label || 'N/A').toUpperCase();
                    const cls = labelClassMap[normalized] || 'badge-na';
                    const icon = iconMap[normalized] || '—';
                    return `<span class="badge ${cls}">${icon} ${normalized}</span>`;
                };

                const row = (title, data) => {
                    const label = data?.label || 'N/A';
                    const summary = data?.summary || '';
                    return `
                        <div class="rec-row">
                            <div>
                                <div class="rec-label">${title}</div>
                                <div class="stock-price-line">${summary}</div>
                            </div>
                            ${badge(label)}
                        </div>
                    `;
                };

                const quotePrice = parsed.price == null ? 'N/A' : `$${Number(parsed.price).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                const ticker = parsed.ticker || 'N/A';
                const companyName = parsed.company_name || ticker;

                return {
                    ticker,
                    html: `
                        <div class="stock-card">
                            <div class="stock-card-header">
                                <div>
                                    <div class="stock-name">${companyName}<span class="stock-ticker-badge">${ticker}</span></div>
                                    <div class="stock-price-line">${quotePrice} ${parsed.currency || ''}</div>
                                </div>
                            </div>
                            <div class="rec-section">
                                <div class="rec-section-title">Time Horizon Recommendations</div>
                                ${row('Short-term (1 week)', recs.short_term)}
                                ${row('Medium-term (3 months)', recs.medium_term)}
                                ${row('Long-term (6-12 months)', recs.long_term)}
                            </div>
                            <div class="rec-section">
                                <div class="rec-section-title">Component Summary</div>
                                ${row('Fundamental', recs.fundamental)}
                                ${row('Technical', recs.technical)}
                                ${row('Sentiment', recs.sentiment)}
                            </div>
                        </div>
                    `
                };
            },

            parseAnalysisJson(reply) {
                if (typeof reply !== 'string') return null;
                const trimmed = reply.trim();
                if (!trimmed.startsWith('{') || !trimmed.endsWith('}')) return null;
                try {
                    const parsed = JSON.parse(trimmed);
                    if (parsed && typeof parsed === 'object' && parsed.ticker && parsed.recommendations) {
                        return parsed;
                    }
                } catch (e) {
                    return null;
                }
                return null;
            }
        };

        // ===================================================================
        // Chat Functions
        // ===================================================================
        const chat = {
            async sendMessage(userMessage) {
                // Add user message to history and UI
                state.chatHistory.push({ role: 'user', content: userMessage });
                utils.clearEmptyState();
                elements.chatOutput.insertAdjacentHTML('beforeend', utils.formatMessage('user', userMessage));
                
                // Show loading state
                state.isLoading = true;
                state.requestController = new AbortController();
                utils.showLoading();
                elements.chatInput.disabled = true;
                elements.stopBtn.disabled = false;
                
                try {
                    // Call API
                    const response = await fetch('/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        signal: state.requestController.signal,
                        body: JSON.stringify({
                            history: state.chatHistory.slice(-MAX_CLIENT_HISTORY),
                            model: elements.modelSelect.value
                        })
                    });

                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }

                    const data = await response.json();
                    
                    // Remove loading
                    utils.removeLoading();

                    const analysisFromReply = data.analysis_html ? null : utils.renderAnalysisReply(data.reply);

                    // Render tool-usage chips (displayed only, not stored in history)
                    if (data.tool_updates && data.tool_updates.length > 0) {
                        const chipsHtml = data.tool_updates.map(t =>
                            `<div class="tool-chip">${t}</div>`
                        ).join('');
                        elements.chatOutput.insertAdjacentHTML(
                            'beforeend',
                            `<div class="tool-chips-row">${chipsHtml}</div>`
                        );
                    }

                    // If a full analysis block was returned, render it as the main card
                    if (data.analysis_html || analysisFromReply) {
                        const analysisHtml = data.analysis_html || analysisFromReply.html;
                        elements.chatOutput.insertAdjacentHTML('beforeend',
                            `<div class="message">
                                <div class="avatar agent-avatar">T</div>
                                <div class="message-body">
                                    <div class="message-label">TickerTalk</div>
                                    <div class="message-content agent">${analysisHtml}</div>
                                </div>
                            </div>`
                        );
                    }

                    // Render the conversational reply — skip if the analysis card already is the response
                    if (data.reply && !data.analysis_html && !analysisFromReply) {
                        state.chatHistory.push({ role: 'assistant', content: data.reply });
                        elements.chatOutput.insertAdjacentHTML('beforeend', utils.formatMessage('assistant', data.reply));
                    } else if (data.reply) {
                        // Show companion reply when it includes source links; otherwise avoid duplicate bubbles.
                        const hasLinkContent = /<a\s+href=|<b>Sources:<\/b>/i.test(data.reply);
                        if (!analysisFromReply && data.analysis_html && hasLinkContent) {
                            state.chatHistory.push({ role: 'assistant', content: data.reply });
                            elements.chatOutput.insertAdjacentHTML('beforeend', utils.formatMessage('assistant', data.reply));
                        } else {
                            state.chatHistory.push({ role: 'assistant', content: analysisFromReply ? `I ran a full analysis for ${analysisFromReply.ticker}.` : data.reply });
                        }
                    } else if (!data.analysis_html && !analysisFromReply) {
                        throw new Error('No reply received');
                    }
                } catch (error) {
                    if (error.name === 'AbortError') {
                        utils.removeLoading();
                        elements.chatOutput.insertAdjacentHTML('beforeend', utils.formatMessage('assistant', '<span style="color: var(--text-2);">Processing stopped.</span>'));
                    } else {
                        console.error('Error:', error);
                        utils.removeLoading();
                        elements.chatOutput.insertAdjacentHTML(
                            'beforeend',
                            utils.formatMessage('assistant', `<span style="color: #e74c3c;">Sorry, something went wrong. Please try again.</span>`)
                        );
                    }
                } finally {
                    state.isLoading = false;
                    state.requestController = null;
                    elements.chatInput.disabled = false;
                    elements.stopBtn.disabled = true;
                    elements.chatInput.focus();
                    utils.scrollToBottom();
                }
            },

            stopProcessing() {
                if (state.requestController) {
                    state.requestController.abort();
                }
            },

            reset() {
                state.chatHistory = [];
                elements.chatOutput.innerHTML = `
                    <div class="empty-state">
                        <div class="hero-icon">
                            <svg width="72" height="72" viewBox="0 0 72 72" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <rect width="72" height="72" rx="18" fill="rgba(20,184,166,0.1)"/>
                                <polyline points="14,52 26,34 36,42 48,24 58,30" stroke="#14b8a6" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
                                <circle cx="58" cy="30" r="3.5" fill="#14b8a6"/>
                            </svg>
                        </div>
                        <h2>Welcome to TickerTalk</h2>
                        <p>Real-time stock analysis powered by AI. Ask about any company.</p>
                        <div class="example-chips">
                            <button class="example-chip" onclick="useExample(this)">Analyse Apple</button>
                            <button class="example-chip" onclick="useExample(this)">How is Tesla doing?</button>
                            <button class="example-chip" onclick="useExample(this)">Give me a NVIDIA report</button>
                        </div>
                    </div>
                `;
                elements.chatInput.value = '';
                elements.chatInput.focus();
            }
        };

        // ===================================================================
        // Event Listeners
        // ===================================================================
        // Parse index-like strings into symbol/friendly
        function parseIndexRaw(raw) {
            const r = (raw || '').trim();
            if (!r) return null;
            let symbol = r;
            let friendly = r;

            if (r.toLowerCase().startsWith('index:')) {
                const payload = r.slice(6).trim();
                return parseIndexRaw(payload);
            }

            if (r.includes('|')) {
                const parts = r.split('|').map(s => s.trim()).filter(Boolean);
                if (parts.length >= 2) {
                    if (parts[0].startsWith('^') || /^[A-Z0-9\.]{1,6}$/.test(parts[0])) {
                        symbol = parts[0]; friendly = parts[1];
                    } else {
                        symbol = parts[1]; friendly = parts[0];
                    }
                    return { symbol, friendly };
                }
            }

            // Friendly (SYMBOL)
            const m = r.match(/\(([^)]+)\)/);
            if (m) {
                const inner = m[1].trim();
                if (inner.startsWith('^') || /^[A-Z0-9\.]{1,6}$/.test(inner)) {
                    symbol = inner;
                    friendly = r.replace(/\s*\([^)]+\)/, '').trim();
                    return { symbol, friendly };
                }
            }

            const m2 = r.match(/(\^[A-Z0-9\.]+)/);
            if (m2) {
                symbol = m2[1];
                friendly = r.replace(m2[0], '').trim() || symbol;
                return { symbol, friendly };
            }

            if (/^\^[A-Z0-9\.]{1,6}$/.test(r)) {
                return { symbol: r, friendly: r };
            }

            // Fuzzy friendly-name matching against known suggestions (e.g. "S&P 500")
            try {
                if (typeof INDEX_SUGGESTIONS !== 'undefined' && Array.isArray(INDEX_SUGGESTIONS)) {
                    const q = r.toLowerCase();
                    // prefer exact friendly match first
                    for (const it of INDEX_SUGGESTIONS) {
                        const parts = it.split('|');
                        const sym = (parts[0] || '').trim();
                        const friendlyName = (parts[1] || '').trim();
                        if (!friendlyName) continue;
                        if (friendlyName.toLowerCase() === q) {
                            return { symbol: sym, friendly: friendlyName };
                        }
                    }
                    // then substring match in friendly name
                    for (const it of INDEX_SUGGESTIONS) {
                        const parts = it.split('|');
                        const sym = (parts[0] || '').trim();
                        const friendlyName = (parts[1] || '').trim();
                        if (!friendlyName) continue;
                        if (friendlyName.toLowerCase().includes(q)) {
                            return { symbol: sym, friendly: friendlyName };
                        }
                    }
                    // fallback: symbol match
                    for (const it of INDEX_SUGGESTIONS) {
                        const parts = it.split('|');
                        const sym = (parts[0] || '').trim();
                        if (sym.toLowerCase() === q || sym.toLowerCase() === ('^' + q)) {
                            return { symbol: sym, friendly: sym };
                        }
                    }
                }
            } catch (e) {
                // ignore matching errors
            }

            return null;
        }

        async function validateAndSendIndex(symbol, friendly) {
            if (!symbol) return false;
            if (indexMsg) indexMsg.style.display = 'none';
            try {
                if (indexLoadBtn) indexLoadBtn.disabled = true;
                elements.chatInput.disabled = true;

                const resp = await fetch(`/api/price-history?ticker=${encodeURIComponent(symbol)}&period=1d`);
                if (!resp.ok) throw new Error('network');
                const data = await resp.json();
                const hasData = data && Array.isArray(data.dates) && data.dates.length > 0 && Array.isArray(data.prices) && data.prices.length > 0;
                if (!hasData) {
                    if (indexMsg) {
                        indexMsg.textContent = 'No intraday price data found for that symbol. Try the Yahoo-style index symbol (e.g. ^GSPC).';
                        indexMsg.style.display = 'block';
                    }
                    return false;
                }

                if (state.isLoading) return false;
                await chat.sendMessage(`index:${symbol}|${friendly}`);
                return true;
            } catch (err) {
                if (indexMsg) {
                    indexMsg.textContent = 'Could not validate symbol (network or invalid). Try ^GSPC or a known Yahoo symbol.';
                    indexMsg.style.display = 'block';
                }
                return false;
            } finally {
                if (indexLoadBtn) indexLoadBtn.disabled = false;
                elements.chatInput.disabled = false;
            }
        }

        elements.chatForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const rawMessage = elements.chatInput.value.trim();
            if (!rawMessage || state.isLoading) return;

            // If the user explicitly prefixes with 'index:' or includes '^', treat as index search
            const isIndexPrefix = rawMessage.toLowerCase().startsWith('index:');
            const hasCaret = rawMessage.indexOf('^') !== -1;

            // Clear input immediately
            elements.chatInput.value = '';

            if (isIndexPrefix || hasCaret) {
                const parsed = parseIndexRaw(rawMessage);
                if (parsed) {
                    const ok = await validateAndSendIndex(parsed.symbol, parsed.friendly);
                    if (ok) return; // handled
                }
                // If parsing/validation failed, fall through and show original as a normal chat message
            }

            // Send regular company/chat message
            await chat.sendMessage(rawMessage);
        });

        elements.resetBtn.addEventListener('click', () => {
            if (state.isLoading) return;
            chat.reset();
        });

        // Index input (select-or-type) handling and validation
        const indexInput = document.getElementById('indexInput');
        const indexLoadBtn = document.getElementById('indexLoadBtn');
        const indexMsg = document.getElementById('indexMsg');

        const sendIndexFromInput = async () => {
            if (!indexInput) return;
            const raw = indexInput.value.trim();
            if (!raw) return;

            // Check if there's an existing session
            if (state.chatHistory.length > 0) {
                const confirmSwitch = confirm(
                    '⚠️ Starting a new session will clear your current conversation.\n\n' +
                    'Do you want to continue?'
                );
                if (!confirmSwitch) {
                    indexInput.value = '';
                    return;
                }
            }

            // parse formats: 'SYMBOL|Friendly' or 'Friendly (SYMBOL)' or just SYMBOL
            let symbol = raw;
            let friendly = raw;

            if (raw.includes('|')) {
                const parts = raw.split('|').map(s => s.trim()).filter(Boolean);
                if (parts.length >= 2) {
                    if (parts[0].startsWith('^') || /^[A-Z0-9\.]{1,6}$/.test(parts[0])) {
                        symbol = parts[0]; friendly = parts[1];
                    } else {
                        symbol = parts[1]; friendly = parts[0];
                    }
                }
            } else {
                // Friendly (SYMBOL)
                const m = raw.match(/\(([^)]+)\)/);
                if (m) {
                    const inner = m[1].trim();
                    if (inner.startsWith('^') || /^[A-Z0-9\.]{1,6}$/.test(inner)) {
                        symbol = inner;
                        friendly = raw.replace(/\s*\([^)]+\)/, '').trim();
                    }
                } else {
                    const m2 = raw.match(/(\^[A-Z0-9\.]+)/);
                    if (m2) {
                        symbol = m2[1];
                        friendly = raw.replace(m2[0], '').trim() || symbol;
                    } else if (/^[A-Z0-9\.]{1,6}$/.test(raw)) {
                        symbol = raw; friendly = raw;
                    }
                }
            }

            if (indexMsg) { indexMsg.style.display = 'none'; }

                try {
                if (indexLoadBtn) indexLoadBtn.disabled = true;
                indexInput.disabled = true;

                const resp = await fetch(`/api/price-history?ticker=${encodeURIComponent(symbol)}&period=1d`);
                if (!resp.ok) throw new Error('network');
                const data = await resp.json();
                const hasData = data && Array.isArray(data.dates) && data.dates.length > 0 && Array.isArray(data.prices) && data.prices.length > 0;
                if (!hasData) {
                    if (indexMsg) {
                        indexMsg.textContent = 'No intraday price data found for that symbol. Try the Yahoo-style index symbol (e.g. ^GSPC).';
                        indexMsg.style.display = 'block';
                    }
                    return;
                }

                // Clear the session and chat history before starting new index query
                state.chatHistory = [];
                const messagesEl = document.getElementById('messages');
                if (messagesEl) messagesEl.innerHTML = '';
                
                indexInput.value = '';
                if (state.isLoading) return;
                await chat.sendMessage(`index:${symbol}|${friendly}`);
            } catch (err) {
                if (indexMsg) {
                    indexMsg.textContent = 'Could not validate symbol (network or invalid). Try ^GSPC or a known Yahoo symbol.';
                    indexMsg.style.display = 'block';
                }
            } finally {
                if (indexLoadBtn) indexLoadBtn.disabled = false;
                indexInput.disabled = false;
            }
        };

        if (indexLoadBtn) indexLoadBtn.addEventListener('click', async () => { await sendIndexFromInput(); });

        // ------------------
        // Index suggestions
        // ------------------
        const idxSuggestionsEl = document.getElementById('indexSuggestions');
        const INDEX_SUGGESTIONS = [
            '^GSPC|S&P 500',
            '^IXIC|Nasdaq Composite',
            '^DJI|Dow Jones',
            '^RUT|Russell 2000',
            '^FTSE|FTSE 100',
            '^N225|Nikkei 225',
            '^HSI|Hang Seng',
            '^KS11|KOSPI',
            '^SSEC|Shanghai Composite',
            '^BVSP|Bovespa',
            '^AORD|ASX 200',
            '^GSPTSE|TSX'
        ];

        let _filtered = [];
        let _selected = -1;

        function renderIndexSuggestions(items) {
            idxSuggestionsEl.innerHTML = '';
            if (!items || items.length === 0) {
                idxSuggestionsEl.style.display = 'none';
                idxSuggestionsEl.setAttribute('aria-hidden', 'true');
                return;
            }
            items.forEach((val, idx) => {
                const row = document.createElement('div');
                row.className = 'item';
                row.setAttribute('data-value', val);
                const parts = val.split('|');
                const symbol = parts[0] || val;
                const friendly = parts[1] || '';
                row.innerHTML = `<strong style="margin-right:8px;color:var(--primary-blue);">${symbol}</strong><span style="color:var(--text-secondary);">${friendly}</span>`;
                row.addEventListener('click', () => {
                    indexInput.value = val;
                    hideIndexSuggestions();
                    sendIndexFromInput();
                });
                idxSuggestionsEl.appendChild(row);
            });
            _selected = -1;
            // show and size
            idxSuggestionsEl.style.display = 'block';
            idxSuggestionsEl.setAttribute('aria-hidden', 'false');

            // compute desired height: prefer content height but cap to 220px
            const firstChild = idxSuggestionsEl.querySelector('.item');
            const itemH = firstChild ? Math.max(32, firstChild.offsetHeight) : 36;
            const desired = Math.min(220, items.length * itemH + 4);
            idxSuggestionsEl.style.maxHeight = desired + 'px';

            // If the input is near the bottom of the viewport, open above instead
            try {
                const rect = indexInput.getBoundingClientRect();
                const spaceBelow = window.innerHeight - rect.bottom;
                const spaceAbove = rect.top;
                if (spaceBelow < desired && spaceAbove > spaceBelow) {
                    idxSuggestionsEl.classList.add('above');
                } else {
                    idxSuggestionsEl.classList.remove('above');
                }
            } catch (e) {
                // ignore
                idxSuggestionsEl.classList.remove('above');
            }
        }

        function hideIndexSuggestions() {
            idxSuggestionsEl.style.display = 'none';
            idxSuggestionsEl.setAttribute('aria-hidden', 'true');
            _selected = -1;
        }

        function filterIndexSuggestions(q) {
            if (!q) return INDEX_SUGGESTIONS.slice();
            const lower = q.toLowerCase();
            return INDEX_SUGGESTIONS.filter(it => it.toLowerCase().includes(lower) || it.toLowerCase().startsWith(lower));
        }

        if (indexInput) {
            indexInput.addEventListener('input', (e) => {
                _filtered = filterIndexSuggestions(e.target.value.trim());
                renderIndexSuggestions(_filtered);
            });

            indexInput.addEventListener('keydown', (e) => {
                const items = idxSuggestionsEl.querySelectorAll('.item');
                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    if (items.length === 0) return;
                    _selected = Math.min(_selected + 1, items.length - 1);
                    items.forEach((it, i) => it.style.background = i === _selected ? '#eef2ff' : '');
                    if (items[_selected]) items[_selected].scrollIntoView({block: 'nearest'});
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    if (items.length === 0) return;
                    _selected = Math.max(_selected - 1, 0);
                    items.forEach((it, i) => it.style.background = i === _selected ? '#eef2ff' : '');
                    if (items[_selected]) items[_selected].scrollIntoView({block: 'nearest'});
                } else if (e.key === 'Enter') {
                    e.preventDefault();
                    if (_selected >= 0 && items[_selected]) {
                        indexInput.value = items[_selected].getAttribute('data-value');
                        hideIndexSuggestions();
                        sendIndexFromInput();
                    } else {
                        hideIndexSuggestions();
                        sendIndexFromInput();
                    }
                } else if (e.key === 'Escape') {
                    hideIndexSuggestions();
                }
            });

            indexInput.addEventListener('focus', () => {
                _filtered = filterIndexSuggestions(indexInput.value.trim());
                renderIndexSuggestions(_filtered);
            });

            document.addEventListener('click', (ev) => {
                if (!ev.target.closest || !ev.target.closest('.index-control')) {
                    hideIndexSuggestions();
                }
            });
        }

        // Focus input on page load
        window.addEventListener('load', () => {
            elements.chatInput.focus();
            // Apply dark mode by default
            document.documentElement.setAttribute('data-theme', 'dark');
        });

        // ===================================================================
        // Theme Toggle
        // ===================================================================
        const themeToggle = document.getElementById('themeToggle');
        themeToggle.addEventListener('click', () => {
            const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            document.documentElement.setAttribute('data-theme', isDark ? 'light' : 'dark');
            themeToggle.textContent = isDark ? '🌙' : '☀️';
            // Re-render existing chart instances with updated colors
            chartInstances.forEach((chart) => {
                const newIsDark = !isDark;
                const gridColor = newIsDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';
                const tickColor = newIsDark ? '#64748b' : '#94a3b8';
                if (chart.options.scales) {
                    ['x', 'y'].forEach(axis => {
                        if (chart.options.scales[axis]) {
                            chart.options.scales[axis].grid = { color: gridColor };
                            chart.options.scales[axis].ticks = { ...chart.options.scales[axis].ticks, color: tickColor };
                        }
                    });
                }
                chart.update();
            });
        });

        // ===================================================================
        // Scroll Indicator
        // ===================================================================
        const scrollIndicator = document.getElementById('scrollIndicator');
        let _scrollTicking = false;
        window.addEventListener('scroll', () => {
            if (_scrollTicking) return;
            _scrollTicking = true;
            requestAnimationFrame(() => {
                const distFromBottom = document.body.scrollHeight - window.scrollY - window.innerHeight;
                scrollIndicator.classList.toggle('visible', distFromBottom > 200);
                _scrollTicking = false;
            });
        }, { passive: true });

        elements.stopBtn.addEventListener('click', () => {
            if (state.isLoading) {
                chat.stopProcessing();
            }
        });
        scrollIndicator.addEventListener('click', () => utils.scrollToBottom());

        // ===================================================================
        // Example Chips
        // ===================================================================
        async function useExample(btn) {
            if (state.isLoading) return;
            const text = btn.textContent.trim();
            utils.clearEmptyState();
            await chat.sendMessage(text);
        }

        

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Escape to reset (if not loading)
            if (e.key === 'Escape' && !state.isLoading) {
                chat.reset();
            }
        });

        // ===================================================================
        // Chart handling (delegated)
        // ===================================================================
        const chartInstances = new Map();

        document.addEventListener('click', async (e) => {
            const toggleBtn = e.target.closest && e.target.closest('.toggle-chart-btn');
            if (toggleBtn) {
                const chartId = toggleBtn.getAttribute('data-chart-id');
                const ticker = toggleBtn.getAttribute('data-ticker');
                const chartDiv = document.getElementById(chartId);
                const btnText = document.getElementById('btn_' + chartId);

                if (!chartDiv) return;

                const isHidden = chartDiv.style.display === 'none' || chartDiv.style.display === '';
                if (isHidden) {
                    chartDiv.style.display = 'block';
                    if (btnText) btnText.textContent = 'Hide Chart ▲';
                    // Load default period if not loaded
                    if (!chartInstances.has(chartId)) {
                        // find the default active period button
                        const defaultBtn = chartDiv.querySelector('.period-btn.active') || chartDiv.querySelector('.period-btn[data-period="1mo"]');
                        const period = defaultBtn ? defaultBtn.getAttribute('data-period') : '1mo';
                        await loadChartData(chartId, ticker, period, defaultBtn);
                    }
                } else {
                    chartDiv.style.display = 'none';
                    if (btnText) btnText.textContent = 'Saw Chart';
                }

                return;
            }

            const periodBtn = e.target.closest && e.target.closest('.period-btn');
            if (periodBtn) {
                const period = periodBtn.getAttribute('data-period');
                const ticker = periodBtn.getAttribute('data-ticker');
                const chartId = periodBtn.getAttribute('data-chart-id');
                await loadChartData(chartId, ticker, period, periodBtn);
                return;
            }
        });

        async function loadChartData(chartId, ticker, period, triggeringBtn = null) {
            try {
                const loading = document.getElementById('loading_' + chartId);
                const canvas = document.getElementById('canvas_' + chartId);
                if (loading) loading.style.display = 'block';
                if (canvas) canvas.style.display = 'none';

                const resp = await fetch(`/api/price-history?ticker=${encodeURIComponent(ticker)}&period=${encodeURIComponent(period)}`);
                const data = await resp.json();

                if (data && data.dates && data.prices) {
                    renderChart(chartId, data.dates, data.prices, period);

                    // update active button styles
                    const parent = document.getElementById(chartId);
                    if (parent) {
                        parent.querySelectorAll('.period-btn').forEach(btn => {
                            btn.classList.remove('active');
                        });
                        if (triggeringBtn) {
                            triggeringBtn.classList.add('active');
                        }
                    }
                }
            } catch (err) {
                console.error('Error loading chart data:', err);
            } finally {
                const loading = document.getElementById('loading_' + chartId);
                const canvas = document.getElementById('canvas_' + chartId);
                if (loading) loading.style.display = 'none';
                if (canvas) canvas.style.display = 'block';
            }
        }

        function renderChart(chartId, dates, prices, period) {
            try {
                const canvasEl = document.getElementById('canvas_' + chartId);
                if (!canvasEl) return;

                const ctx = canvasEl.getContext('2d');

                if (chartInstances.has(chartId)) {
                    const inst = chartInstances.get(chartId);
                    try { inst.destroy(); } catch (e) { /* ignore */ }
                    chartInstances.delete(chartId);
                }

                // Enforce fixed pixel height on the canvas and its container to avoid
                // Chart.js responsive growth when re-rendering repeatedly.
                const container = document.getElementById(chartId);
                if (container) {
                    container.style.height = '270px'; // includes some padding for controls
                }

                // Ensure the canvas has a fixed drawing height
                canvasEl.style.height = '250px';
                canvasEl.style.maxHeight = '250px';
                canvasEl.height = 250;

                const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
                const gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';
                const tickColor = isDark ? '#64748b' : '#94a3b8';

                const color = prices[prices.length - 1] >= prices[0] ? '#10b981' : '#ef4444';

                const newChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: dates,
                        datasets: [{
                            label: '',
                            data: prices,
                            borderColor: color,
                            backgroundColor: color + '18',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.4,
                            pointRadius: period === '1d' ? 2 : 0,
                            pointHoverRadius: 5
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                mode: 'index',
                                intersect: false,
                                backgroundColor: isDark ? 'rgba(26,29,39,0.95)' : 'rgba(255,255,255,0.98)',
                                titleColor: isDark ? '#f1f5f9' : '#0f172a',
                                bodyColor: isDark ? '#94a3b8' : '#475569',
                                borderColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)',
                                borderWidth: 1,
                                callbacks: {
                                    label: (context) => '$' + context.parsed.y.toFixed(2)
                                }
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: false,
                                grid: { color: gridColor },
                                ticks: {
                                    color: tickColor,
                                    callback: (value) => '$' + value.toFixed(2)
                                }
                            },
                            x: {
                                grid: { color: gridColor },
                                ticks: {
                                    color: tickColor,
                                    maxRotation: 45,
                                    minRotation: 45,
                                    maxTicksLimit: period === '1d' ? 10 : (period === '5d' ? 5 : 8),
                                    // Strip time portion from x-axis labels (show date only)
                                    callback: function(value) {
                                        // value is the tick value (string label)
                                        if (typeof value === 'string' && value.indexOf(' ') !== -1) {
                                            return value.split(' ')[0];
                                        }
                                        return value;
                                    }
                                }
                            }
                        },
                        interaction: {
                            mode: 'nearest',
                            axis: 'x',
                            intersect: false
                        }
                    }
                });

                chartInstances.set(chartId, newChart);
            } catch (err) {
                console.error('Error rendering chart:', err);
            }
        }

        // ===================================================================
        // Market Overview
        // ===================================================================
        let marketOverviewData = null;
        let marketRefreshInterval = null;

        // Initialize market overview on page load
        async function initializeMarketOverview() {
            try {
                await loadMarketOverview();
                // Auto-refresh every 5 minutes
                marketRefreshInterval = setInterval(() => {
                    loadMarketOverview();
                }, 5 * 60 * 1000);
            } catch (err) {
                console.error('Failed to initialize market overview:', err);
            }
        }

        async function loadMarketOverview() {
            const overview = document.getElementById('marketOverview');
            if (!overview) return;

            try {
                overview.classList.add('loading');
                const response = await fetch('/api/market-overview');
                if (!response.ok) throw new Error('Network response was not ok');
                
                const data = await response.json();
                marketOverviewData = data;
                
                renderMarketSections(data);
            } catch (err) {
                console.error('Error loading market overview:', err);
                // Show error state
                showMarketError();
            } finally {
                overview.classList.remove('loading');
            }
        }

        function renderMarketSections(data) {
            if (data.most_active && data.most_active.length > 0) {
                renderMarketSection('activeSection', 'activeCarousel', data.most_active);
            }
            if (data.gainers && data.gainers.length > 0) {
                renderMarketSection('gainersSection', 'gainersCarousel', data.gainers);
            }
            if (data.movers && data.movers.length > 0) {
                renderMarketSection('moversSection', 'moversCarousel', data.movers);
            }
            if (data.losers && data.losers.length > 0) {
                renderMarketSection('losersSection', 'losersCarousel', data.losers);
            }
            renderMarketSummary(data);
        }

        function renderMarketSection(sectionId, carouselId, items) {
            const section = document.getElementById(sectionId);
            const carousel = document.getElementById(carouselId);
            
            if (!section || !carousel) return;

            section.style.display = section.tagName.toLowerCase() === 'details' ? 'inline-flex' : 'block';
            carousel.innerHTML = '';

            const isActiveSection = sectionId === 'activeSection';
            items.forEach(item => {
                const card = createMarketCard(item, isActiveSection);
                carousel.appendChild(card);
            });
        }

        function createMarketCard(item, showVolume = false) {
            const card = document.createElement('div');
            card.className = 'market-card';
            card.dataset.symbol = item.symbol;
            card.onclick = () => openModal(item);

            const isPositive = item.change_percent >= 0;
            const changeIcon = isPositive ? '▲' : '▼';
            const changeClass = isPositive ? 'positive' : 'negative';

            const volumeDisplay = item.volume ? formatVolume(item.volume) : 'N/A';

            const logoHTML = item.logo_url
                ? `<img src="${item.logo_url}" alt="${item.symbol}" class="market-card-logo" onerror="this.style.display='none'"/>`
                : '';

            let metricsHTML = `
                    <div class="market-card-price">$${item.price.toFixed(2)}</div>
                    <div class="market-card-change ${changeClass}" title="Volume: ${volumeDisplay}">
                        <span>${changeIcon}</span>
                        <span class="market-card-change-value">${isPositive ? '+' : ''}${item.change_percent.toFixed(2)}%</span>
                    </div>
            `;

            if (showVolume) {
                metricsHTML += `<div class="market-card-volume">Vol: ${volumeDisplay}</div>`;
            }

            card.innerHTML = `
                <div class="market-card-header">
                    <div class="market-card-main">
                        <div class="market-card-symbol">${item.symbol}</div>
                        <div class="market-card-name">${item.name}</div>
                    </div>
                    ${logoHTML}
                </div>
                <div class="market-card-metrics">
                    ${metricsHTML}
                </div>
            `;

            return card;
        }

        function renderMarketSummary(data) {
            const summary = document.getElementById('marketSummary');
            const summaryKicker = document.getElementById('marketSummaryKicker');
            const summaryTitle = document.getElementById('marketSummaryTitle');
            const summaryText = document.getElementById('marketSummaryText');
            const summaryActions = document.getElementById('marketSummaryActions');
            const summaryMeta = document.getElementById('marketSummaryMeta');
            const summaryBadge = document.getElementById('marketSummaryBadge');

            if (!summary || !summaryKicker || !summaryTitle || !summaryText || !summaryActions || !summaryMeta || !summaryBadge) {
                return;
            }

            const indices = Array.isArray(data.indices) ? data.indices.filter(Boolean) : [];
            const movers = Array.isArray(data.movers) ? data.movers.filter(Boolean) : [];
            const losers = Array.isArray(data.losers) ? data.losers.filter(Boolean) : [];

            if (!indices.length && !movers.length && !losers.length) {
                summary.style.display = 'none';
                return;
            }

            const marketOpen = isMarketOpenNow();
            const trendScore = indices.length ? averageChange(indices) : averageChange(movers.concat(losers));
            const trendPositive = trendScore >= 0;
            const trendLabel = indices.length
                ? (trendPositive ? 'higher' : 'lower')
                : (trendPositive ? 'higher' : 'lower');
            const leadingMover = movers.slice().sort((a, b) => Math.abs(b.change_percent || 0) - Math.abs(a.change_percent || 0))[0];
            const leadingLoser = losers[0];

            summary.style.display = 'block';
            summaryKicker.textContent = marketOpen ? 'Live session summary' : 'Today on the market';
            summaryBadge.textContent = marketOpen ? 'Market Open' : 'Market Closed';
            summary.classList.toggle('positive', trendPositive);
            summary.classList.toggle('negative', !trendPositive);

            summaryTitle.textContent = marketOpen
                ? `The market is trading ${trendLabel} right now.`
                : `The market finished the day ${trendLabel}.`;

            const indexLine = indices.length
                ? indices.map(item => `${prettyIndexName(item.symbol)} ${formatSignedPercent(item.change_percent)}`).join(' · ')
                : 'Index data is not available right now.';

            const moverLine = leadingMover
                ? `Top move: ${leadingMover.symbol} ${formatSignedPercent(leadingMover.change_percent)}.`
                : '';
            const loserLine = leadingLoser
                ? `Weakest name: ${leadingLoser.symbol} ${formatSignedPercent(leadingLoser.change_percent)}.`
                : '';

            summaryText.textContent = marketOpen
                ? `During the session, ${indexLine} ${moverLine} ${loserLine}`.trim()
                : `For the day, ${indexLine} ${moverLine} ${loserLine}`.trim();

            summaryActions.innerHTML = '';
            indices.forEach((item) => {
                summaryActions.appendChild(createSummaryButton({
                    label: `${prettyIndexName(item.symbol)} ${formatSignedPercent(item.change_percent)}`,
                    item,
                    tone: Number(item.change_percent) >= 0,
                }));
            });

            if (leadingMover) {
                summaryActions.appendChild(createSummaryButton({
                    label: `Top mover: ${leadingMover.symbol} ${formatSignedPercent(leadingMover.change_percent)}`,
                    item: leadingMover,
                    tone: Number(leadingMover.change_percent) >= 0,
                }));
            }

            if (leadingLoser) {
                summaryActions.appendChild(createSummaryButton({
                    label: `Top loser: ${leadingLoser.symbol} ${formatSignedPercent(leadingLoser.change_percent)}`,
                    item: leadingLoser,
                    tone: Number(leadingLoser.change_percent) >= 0,
                }));
            }

            const metaItems = [];
            const updatedAt = formatBrowserLocalTimestamp(data.timestamp);
            if (updatedAt) {
                metaItems.push(`Updated ${updatedAt}`);
            }

            summaryMeta.innerHTML = metaItems.map(item => `<span class="market-summary-pill">${item}</span>`).join('');
        }

        function createSummaryButton({ label, item, symbol, sectionId, tone }) {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = `market-summary-btn ${tone ? 'positive' : 'negative'}`;
            button.textContent = label;
            button.addEventListener('click', () => {
                if (item) {
                    openModal(item);
                    return;
                }
                focusMarketItem(symbol, sectionId);
            });
            return button;
        }

        function focusMarketItem(symbol, sectionId) {
            if (!sectionId) {
                openSummaryMarketItem(symbol);
                return;
            }

            const section = document.getElementById(sectionId);
            if (!section) return;

            if (section.tagName.toLowerCase() === 'details') {
                section.open = true;
            }

            section.scrollIntoView({ behavior: 'smooth', block: 'start' });

            if (!symbol) return;

            window.setTimeout(() => {
                const scope = document.getElementById(sectionId) || document;
                const escapedSymbol = String(symbol).replace(/"/g, '\\"');
                const card = scope.querySelector?.(`.market-card[data-symbol="${escapedSymbol}"]`);
                if (card) {
                    card.click();
                }
            }, 150);
        }

        function openSummaryMarketItem(symbol) {
            if (!symbol || !marketOverviewData) return;

            const pools = [marketOverviewData.indices, marketOverviewData.movers, marketOverviewData.gainers, marketOverviewData.losers, marketOverviewData.most_active];
            for (const pool of pools) {
                if (!Array.isArray(pool)) continue;
                const item = pool.find(entry => (entry?.symbol || '').toUpperCase() === String(symbol).toUpperCase());
                if (item) {
                    openModal(item);
                    return;
                }
            }
        }

        function formatBrowserLocalTimestamp(timestamp) {
            if (!timestamp) return '';

            const date = new Date(timestamp);
            if (Number.isNaN(date.getTime())) return '';

            const browserTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || undefined;
            return new Intl.DateTimeFormat(undefined, {
                month: 'short',
                day: 'numeric',
                hour: 'numeric',
                minute: '2-digit',
                timeZone: browserTimeZone,
            }).format(date);
        }

        function averageChange(items) {
            if (!items.length) return 0;
            const total = items.reduce((sum, item) => sum + (Number(item.change_percent) || 0), 0);
            return total / items.length;
        }

        function isMarketOpenNow() {
            const now = new Date();
            const parts = new Intl.DateTimeFormat('en-US', {
                timeZone: 'America/New_York',
                weekday: 'short',
                hour: 'numeric',
                minute: '2-digit',
                hour12: false,
            }).formatToParts(now).reduce((acc, part) => {
                if (part.type !== 'literal') acc[part.type] = part.value;
                return acc;
            }, {});

            const weekday = (parts.weekday || '').toLowerCase();
            if (weekday === 'sat' || weekday === 'sun') return false;

            const hour = parseInt(parts.hour || '0', 10);
            const minute = parseInt(parts.minute || '0', 10);
            const minutesSinceMidnight = (hour * 60) + minute;
            return minutesSinceMidnight >= (9 * 60 + 30) && minutesSinceMidnight < (16 * 60);
        }

        function prettyIndexName(symbol) {
            const mapping = {
                '^GSPC': 'S&P 500',
                '^IXIC': 'Nasdaq',
                '^DJI': 'Dow',
                '^RUT': 'Russell 2000',
            };
            return mapping[symbol] || symbol;
        }

        function formatSignedPercent(value) {
            const num = Number(value) || 0;
            return `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`;
        }

        function formatVolume(volume) {
            if (volume >= 1e9) return (volume / 1e9).toFixed(2) + 'B';
            if (volume >= 1e6) return (volume / 1e6).toFixed(2) + 'M';
            if (volume >= 1e3) return (volume / 1e3).toFixed(2) + 'K';
            return volume.toString();
        }

        function formatMarketCap(marketCap) {
            if (!marketCap) return 'N/A';
            if (marketCap >= 1e12) return '$' + (marketCap / 1e12).toFixed(2) + 'T';
            if (marketCap >= 1e9) return '$' + (marketCap / 1e9).toFixed(2) + 'B';
            if (marketCap >= 1e6) return '$' + (marketCap / 1e6).toFixed(2) + 'M';
            return '$' + marketCap.toFixed(2);
        }

        function openModal(item) {
            const modal = document.getElementById('previewModal');
            if (!modal) return;

            // Store the current symbol for the analyze button
            modal.dataset.symbol = item.symbol;

            // Update modal content
            document.getElementById('modalSymbol').textContent = item.symbol;
            document.getElementById('modalName').textContent = item.name;
            document.getElementById('modalPrice').textContent = '$' + item.price.toFixed(2);

            const modalLogo = document.getElementById('modalLogo');
            if (modalLogo && item.logo_url) {
                modalLogo.src = item.logo_url;
                modalLogo.alt = item.symbol;
                modalLogo.style.display = 'block';
            } else if (modalLogo) {
                modalLogo.style.display = 'none';
            }

            const isPositive = item.change_percent >= 0;
            const changeElement = document.getElementById('modalChange');
            const changeIcon = document.getElementById('modalChangeIcon');
            const changeValue = document.getElementById('modalChangeValue');

            changeElement.className = 'modal-change ' + (isPositive ? 'positive' : 'negative');
            changeIcon.textContent = isPositive ? '▲' : '▼';
            changeValue.textContent = (isPositive ? '+' : '') + item.change_percent.toFixed(2) + '%';

            // Set optional fields or show N/A
            document.getElementById('modalHigh').textContent = item.week_52_high ? '$' + item.week_52_high.toFixed(2) : 'N/A';
            document.getElementById('modalLow').textContent = item.week_52_low ? '$' + item.week_52_low.toFixed(2) : 'N/A';
            document.getElementById('modalMarketCap').textContent = formatMarketCap(item.market_cap);
            document.getElementById('modalVolume').textContent = item.volume ? formatVolume(item.volume) : 'N/A';

            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
        }

        function closeModal() {
            const modal = document.getElementById('previewModal');
            if (modal) {
                modal.classList.remove('active');
                document.body.style.overflow = 'auto';
            }
        }

        async function analyzeFromModal() {
            const modal = document.getElementById('previewModal');
            const symbol = modal.dataset.symbol;
            if (!symbol) return;

            closeModal();
            utils.clearEmptyState();
            await chat.sendMessage(`Analyze ${symbol}`);
        }

        function showMarketError() {
            const overview = document.getElementById('marketOverview');
            if (!overview) return;
            overview.innerHTML = '<p style="text-align: center; color: var(--text-3); padding: 2rem;">Unable to load market data. Please refresh the page.</p>';
        }

        // Close modal when clicking outside
        document.addEventListener('click', (e) => {
            const modal = document.getElementById('previewModal');
            if (modal && modal.classList.contains('active')) {
                if (e.target === modal) {
                    closeModal();
                }
            }
        });

        // Initialize market overview when page loads
        document.addEventListener('DOMContentLoaded', () => {
            initializeMarketOverview();
        });

        // Clean up interval on page unload
        window.addEventListener('beforeunload', () => {
            if (marketRefreshInterval) {
                clearInterval(marketRefreshInterval);
            }
        });
