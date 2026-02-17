document.getElementById('get-signal-btn').addEventListener('click', async () => {
    const btn = document.getElementById('get-signal-btn');
    const predDisplay = document.getElementById('prediction-display');
    const cidAlertBox = document.getElementById('cid-alert-box');
    const dragonAlertBox = document.getElementById('dragon-alert-box');
    const patternBadge = document.getElementById('current-pattern-badge');
    
    btn.disabled = true;
    btn.innerText = 'বিশ্লেষণ করা হচ্ছে...';
    predDisplay.classList.add('analyzing');
    cidAlertBox.style.display = 'none';
    dragonAlertBox.style.display = 'none';

    try {
        const response = await fetch('/api/get-signal');
        const data = await response.json();

        if (data.status === 'success') {
            if (data.prediction === 'SKIP/RISKY') {
                predDisplay.innerText = 'SKIP/RISKY';
                predDisplay.style.fontSize = '2.5rem';
                predDisplay.style.color = '#FFA500';
            } else {
                predDisplay.innerText = data.prediction === 'BIG' ? 'BIG' : 'SMALL';
                predDisplay.style.fontSize = '3.5rem';
            }
            
            // Color Coding Logic (Silent Safety)
            if (data.warning_color === 'Orange') {
                predDisplay.style.color = '#FFA500'; // Orange for high risk
            } else {
                predDisplay.style.color = data.prediction === 'BIG' ? '#00C853' : '#FF3D00'; // Green/Red for low risk
            }

            const confBar = document.getElementById('confidence-bar');
            const confText = document.getElementById('confidence-text');
            confBar.style.width = data.confidence + '%';
            confText.innerText = data.confidence + '%';
            
            // Update Probability
            const probText = document.getElementById('probability-text');
            if (probText) probText.innerText = data.probability + '%';

            document.getElementById('source-text').innerText = data.source;
            
            // Update Pattern Badge
            if (data.detected_pattern) {
                patternBadge.innerText = 'প্যাটার্ন: ' + data.detected_pattern;
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

            // Update Volatility
            updateVolatilityUI(data.volatility_score, data.volatility_status);

            // Update Manager Status
            const riskStatus = document.getElementById('risk-status');
            if (data.risk_alert || data.dragon_alert) {
                riskStatus.innerText = 'হস্তক্ষেপ';
                riskStatus.style.color = data.dragon_alert ? 'var(--accent-purple)' : '#FF3D00';
                const probStatus = document.getElementById('probability-status');
                if (probStatus) {
                    probStatus.innerText = 'সতর্ক';
                    probStatus.style.color = '#FF3D00';
                }
            } else {
                riskStatus.innerText = 'সক্রিয়';
                riskStatus.style.color = '';
                const probStatus = document.getElementById('probability-status');
                if (probStatus) {
                    probStatus.innerText = 'সক্রিয়';
                    probStatus.style.color = '';
                }
            }
            
            // Enable result buttons
            document.querySelectorAll('.btn-result').forEach(b => b.disabled = false);
        } else {
            alert('ত্রুটি: ' + data.message);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('সংযোগ বিচ্ছিন্ন হয়েছে। আবার চেষ্টা করুন।');
    } finally {
        btn.disabled = false;
        btn.innerText = 'সিগন্যাল নিন';
        predDisplay.classList.remove('analyzing');
    }
});

async function submitResult(actualResult) {
    const predDisplay = document.getElementById('prediction-display');
    const userChoice = predDisplay.innerText;
    
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
            document.getElementById('live-accuracy').innerText = data.accuracy + '%';
            document.querySelector('.learning-stats').innerText = data.total_collected + ' প্যাটার্ন ট্র্যাক করা হয়েছে';
            document.querySelector('.progress-bar-fill').style.width = data.learning_percent + '%';
            document.querySelectorAll('.progress-text')[1].innerText = data.learning_percent + '% অপ্টিমাইজেশন';
            
            const historyList = document.getElementById('history-list');
            if (data.trades.length === 0) {
                historyList.innerHTML = '<p style="text-align: center; color: var(--text-secondary); font-size: 0.9rem; padding: 20px;">এখনো কোনো ট্রেড নেই। শুরু করতে সিগন্যাল নিন!</p>';
            } else {
                let html = '';
                data.trades.forEach(trade => {
                    const time = trade.timestamp.includes(' ') ? trade.timestamp.split(' ')[1] : trade.timestamp;
                    const statusClass = trade.actual_result === trade.ai_prediction ? 'status-win' : 'status-loss';
                    const statusText = trade.actual_result === trade.ai_prediction ? 'জয়' : 'হার';
                    const predText = trade.ai_prediction === 'BIG' ? 'BIG' : trade.ai_prediction === 'SMALL' ? 'SMALL' : trade.ai_prediction;
                    const actualText = trade.actual_result === 'BIG' ? 'BIG' : trade.actual_result === 'SMALL' ? 'SMALL' : '???';
                    
                    html += `
                    <div class="history-item">
                        <div class="item-info">
                            <span class="item-main">${predText} → ${actualText}</span>
                            <span class="item-sub">${time} | কনফিডেন্স: ${trade.ai_confidence}%</span>
                        </div>
                        <div style="display: flex; align-items: center;">
                            ${trade.ai_prediction !== 'INITIAL' ? 
                                `<span class="item-status ${statusClass}">${statusText}</span>` : 
                                `<span class="item-status" style="background: #555;">ডেটা</span>`}
                            <button onclick="undoTrade('${trade.trade_id}')" class="undo-btn">মুছুন</button>
                        </div>
                    </div>`;
                });
                historyList.innerHTML = html;
            }
            
            const predDisplay = document.getElementById('prediction-display');
            predDisplay.innerText = '---';
            predDisplay.style.color = '';
            document.getElementById('source-text').innerText = 'অপেক্ষা করুন...';
            document.querySelectorAll('.btn-result').forEach(b => b.disabled = true);
            
            document.getElementById('cid-alert-box').style.display = 'none';
            document.getElementById('dragon-alert-box').style.display = 'none';
            document.getElementById('current-pattern-badge').innerText = 'প্যাটার্ন: ---';

            // Update Volatility on dashboard refresh
            updateVolatilityUI(data.volatility_score, data.volatility_status);
        }
    } catch (error) {
        console.error('Error updating UI:', error);
    }
}

async function undoTrade(tradeId) {
    if (!confirm('এই এন্ট্রিটি মুছে ফেলতে এবং AI মেমরি সংশোধন করতে চান?')) return;
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

function updateVolatilityUI(score, status) {
    const volBar = document.getElementById('volatility-bar');
    const volStatus = document.getElementById('volatility-status');
    if (volBar && volStatus) {
        volBar.style.width = score + '%';
        volStatus.innerText = status;
        
        let color = 'var(--success-green)';
        if (status === 'EXTREME') color = 'var(--error-red)';
        else if (status === 'VOLATILE') color = '#FFA500';
        else if (status === 'NORMAL') color = 'var(--accent-blue)';
        
        volBar.style.background = color;
        volStatus.style.color = color;
    }
}

async function startNewSession() {
    if (!confirm('নতুন সেশন শুরু করতে চান? এটি বর্তমান ডেটা আর্কাইভ করবে এবং উন্নত মার্কেট অ্যাডাপ্টেশনের জন্য AI শর্ট-টার্ম মেমরি (PEM) রিসেট করবে।')) return;
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

window.onload = () => {
    document.querySelectorAll('.btn-result').forEach(b => b.disabled = false);
};

async function savePattern() {
    const inputs = document.querySelectorAll('.game-input');
    const pattern = [];
    let isValid = true;
    
    inputs.forEach(input => {
        const val = input.value.toUpperCase();
        if (val === 'B' || val === 'S') {
            pattern.push(val === 'B' ? 'BIG' : 'SMALL');
        } else if (val !== '') {
            isValid = false;
        }
    });

    if (!isValid) {
        alert('অনুগ্রহ করে শুধু B অথবা S ইনপুট দিন।');
        return;
    }

    if (pattern.length < 5) {
        alert('কমপক্ষে ৫টি গেমের রেজাল্ট দিন।');
        return;
    }

    try {
        const response = await fetch('/api/save-bulk-pattern', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pattern: pattern })
        });
        const data = await response.json();
        if (data.status === 'success') {
            alert('প্যাটার্ন সফলভাবে সেভ করা হয়েছে!');
            updateDashboardUI();
        } else {
            alert(data.message);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('প্যাটার্ন সেভ করতে সমস্যা হয়েছে।');
    }
}

async function uploadScreenshot(input) {
    if (!input.files || !input.files[0]) return;
    
    const file = input.files[0];
    const formData = new FormData();
    formData.append('file', file);

    const originalBtnText = document.querySelector('button[onclick*="screenshot-input"]').innerText;
    const ocrBtn = document.querySelector('button[onclick*="screenshot-input"]');
    
    ocrBtn.disabled = true;
    ocrBtn.innerText = 'প্রসেসিং...';

    try {
        const response = await fetch('/api/ocr-screenshot', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        
        if (data.status === 'success') {
            const results = data.results;
            // Clear all inputs first
            for (let i = 0; i < 15; i++) {
                document.getElementById(`game-${i}`).value = '';
            }
            // Fill inputs from newest to oldest (as returned by OCR)
            results.forEach((val, index) => {
                if (index < 15) {
                    document.getElementById(`game-${index}`).value = val;
                }
            });
            alert('স্ক্রিনশট থেকে ডেটা নেয়া হয়েছে!');
        } else {
            alert('ত্রুটি: ' + data.message);
        }
    } catch (error) {
        console.error('OCR Error:', error);
        alert('স্ক্রিনশট প্রসেস করতে সমস্যা হয়েছে।');
    } finally {
        ocrBtn.disabled = false;
        ocrBtn.innerText = originalBtnText;
        input.value = ''; // Reset file input
    }
}
