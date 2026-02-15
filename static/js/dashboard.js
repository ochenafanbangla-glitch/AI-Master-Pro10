document.getElementById('get-signal-btn').addEventListener('click', async () => {
    const btn = document.getElementById('get-signal-btn');
    const predDisplay = document.getElementById('prediction-display');
    const cidAlertBox = document.getElementById('cid-alert-box');
    const dragonAlertBox = document.getElementById('dragon-alert-box');
    const patternBadge = document.getElementById('current-pattern-badge');
    
    btn.disabled = true;
    btn.innerText = 'ANALYZING...';
    predDisplay.classList.add('analyzing');
    cidAlertBox.style.display = 'none';
    dragonAlertBox.style.display = 'none';

    try {
        const response = await fetch('/api/get-signal');
        const data = await response.json();

        if (data.status === 'success') {
            predDisplay.innerText = data.prediction;
            predDisplay.style.color = data.prediction === 'BIG' ? '#00C853' : '#FF3D00';

            const confBar = document.getElementById('confidence-bar');
            const confText = document.getElementById('confidence-text');
            confBar.style.width = data.confidence + '%';
            confText.innerText = data.confidence + '%';

            document.getElementById('source-text').innerText = data.source;
            
            // Update Pattern Badge
            if (data.detected_pattern) {
                patternBadge.innerText = 'Pattern: ' + data.detected_pattern;
            }

            // Update CID Scanner Alert
            if (data.risk_alert) {
                const alertMsg = document.getElementById('cid-alert-msg');
                alertMsg.innerText = data.risk_alert;
                cidAlertBox.style.display = 'block';
            }

            // Update Dragon Alert
            if (data.dragon_alert) {
                const dragonMsg = document.getElementById('dragon-alert-msg');
                dragonMsg.innerText = data.dragon_alert;
                dragonAlertBox.style.display = 'block';
            }

            // Update Manager Status
            const riskStatus = document.getElementById('risk-status');
            const recoveryStatus = document.getElementById('recovery-status');
            
            if (data.risk_alert || data.dragon_alert) {
                riskStatus.innerText = 'INTERVENING';
                riskStatus.style.color = data.dragon_alert ? 'var(--accent-purple)' : '#FF3D00';
                recoveryStatus.innerText = 'ACTIVE';
                recoveryStatus.classList.remove('status-idle');
                recoveryStatus.classList.add('status-active');
            } else {
                riskStatus.innerText = 'Active';
                riskStatus.style.color = '';
                recoveryStatus.innerText = 'Idle';
                recoveryStatus.classList.remove('status-active');
                recoveryStatus.classList.add('status-idle');
            }
            
            // Enable result buttons
            document.querySelectorAll('.btn-result').forEach(b => b.disabled = false);
        } else if (data.status === 'waiting') {
            alert(data.message);
            predDisplay.innerText = 'WAIT';
            predDisplay.style.color = '#FFC107';
            document.getElementById('source-text').innerText = 'Data Collection Phase';
        } else {
            alert('Error: ' + data.message);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Connection error. Try again.');
    } finally {
        btn.disabled = false;
        btn.innerText = 'GET SIGNAL';
        predDisplay.classList.remove('analyzing');
    }
});

async function submitResult(actualResult) {
    const predDisplay = document.getElementById('prediction-display');
    const userChoice = predDisplay.innerText;
    
    // Disable buttons to prevent double submission
    const buttons = document.querySelectorAll('.btn-result');
    buttons.forEach(b => b.disabled = true);
    
    try {
        const response = await fetch('/api/submit-result', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                result: actualResult,
                user_choice: userChoice,
                bet_amount: 10
            })
        });
        const data = await response.json();
        if (data.status === 'success') {
            // Instead of location.reload(), we update the UI components
            updateDashboardUI();
        } else {
            alert(data.message);
            buttons.forEach(b => b.disabled = false);
        }
    } catch (error) {
        console.error('Error:', error);
        buttons.forEach(b => b.disabled = false);
    }
}

async function updateDashboardUI() {
    try {
        const response = await fetch('/api/dashboard-data');
        const data = await response.json();
        
        if (data.status === 'success') {
            // Update Accuracy
            document.getElementById('live-accuracy').innerText = data.accuracy + '%';
            
            // Update Learning Progress
            document.querySelector('.learning-stats').innerText = data.total_collected + ' Patterns Tracked';
            document.querySelector('.progress-bar-fill').style.width = data.learning_percent + '%';
            document.querySelectorAll('.progress-text')[1].innerText = data.learning_percent + '% Optimization';
            
            // Update History List
            const historyList = document.getElementById('history-list');
            if (data.trades.length === 0) {
                historyList.innerHTML = '<p style="text-align: center; color: var(--text-secondary); font-size: 0.9rem; padding: 20px;">No trades yet. Get a signal to start!</p>';
            } else {
                let html = '';
                data.trades.forEach(trade => {
                    const time = trade.timestamp.includes(' ') ? trade.timestamp.split(' ')[1] : trade.timestamp;
                    const statusClass = trade.actual_result === trade.ai_prediction ? 'status-win' : 'status-loss';
                    const statusText = trade.actual_result === trade.ai_prediction ? 'WIN' : 'LOSS';
                    
                    html += `
                    <div class="history-item">
                        <div class="item-info">
                            <span class="item-main">${trade.ai_prediction} → ${trade.actual_result || '???'}</span>
                            <span class="item-sub">${time} | Conf: ${trade.ai_confidence}%</span>
                        </div>
                        <div style="display: flex; align-items: center;">
                            ${trade.ai_prediction !== 'INITIAL' ? 
                                `<span class="item-status ${statusClass}">${statusText}</span>` : 
                                `<span class="item-status" style="background: #555;">DATA</span>`}
                            <button onclick="undoTrade('${trade.trade_id}')" class="undo-btn">Undo</button>
                        </div>
                    </div>`;
                });
                historyList.innerHTML = html;
            }
            
            // Reset Prediction Display
            const predDisplay = document.getElementById('prediction-display');
            if (data.total_collected < data.target_trades) {
                predDisplay.innerText = 'WAIT';
                predDisplay.style.color = '#FFC107';
                document.getElementById('source-text').innerText = 'Data Collection Phase';
                document.querySelectorAll('.btn-result').forEach(b => b.disabled = false);
            } else {
                predDisplay.innerText = '---';
                predDisplay.style.color = '';
                document.getElementById('source-text').innerText = 'Waiting...';
                document.querySelectorAll('.btn-result').forEach(b => b.disabled = true);
            }
            
            // Reset alerts
            document.getElementById('cid-alert-box').style.display = 'none';
            document.getElementById('dragon-alert-box').style.display = 'none';
            document.getElementById('current-pattern-badge').innerText = 'Pattern: ---';
            
        }
    } catch (error) {
        console.error('Error updating UI:', error);
    }
}

async function undoTrade(tradeId) {
    if (!confirm('Delete this entry and correct AI memory?')) return;

    try {
        const response = await fetch('/api/undo-trade', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ trade_id: tradeId })
        });
        const data = await response.json();
        if (data.status === 'success') {
            updateDashboardUI();
        } else {
            alert(data.message);
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

async function downloadCVC() {
    try {
        window.location.href = '/api/download-cvc';
    } catch (error) {
        console.error('Error downloading CVC:', error);
        alert('Failed to download CVC data.');
    }
}

async function startNewSession() {
    if (!confirm('Start a New Session? This will archive current data and reset the AI short-term memory (PEM) for better market adaptation.')) return;

    try {
        const response = await fetch('/api/new-session', {
            method: 'POST'
        });
        const data = await response.json();
        if (data.status === 'success') {
            alert(data.message);
            updateDashboardUI();
        } else {
            alert(data.message);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Connection error. Try again.');
    }
}

// Enable result buttons if we are in data collection phase (initial state)
window.onload = () => {
    const totalCollectedText = document.querySelector('.learning-stats').innerText;
    const count = parseInt(totalCollectedText);
    if (count < 20) {
        document.querySelectorAll('.btn-result').forEach(b => b.disabled = false);
    }
    
    // System Pause check removed
};
