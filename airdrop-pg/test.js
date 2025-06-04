document.addEventListener('DOMContentLoaded', () => {
    const connectBtn = document.getElementById('connectWalletBtn');
    const walletAddress = document.getElementById('walletAddress');
    const miniGameBtn = document.getElementById('miniGameBtn');

    let currentWallet = null;
    let socialStatus = { twitter: false, instagram: false };
    let claimStatus = { twitter: false, instagram: false };

    // Elementos do dropdown
    const dropdownHeader = document.querySelector('.dropdown-header');
    const questsList = document.querySelector('.quests-list');
    const chevron = dropdownHeader?.querySelector('.fa-chevron-down');

    // Dropdown toggle
    if (dropdownHeader && questsList && chevron) {
        dropdownHeader.addEventListener('click', () => {
            questsList.classList.toggle('open');
            chevron.classList.toggle('rotate');
        });
    }

    // Gerenciamento de estado local
    function loadState() {
        if (!currentWallet?.address) return;
        
        try {
            const savedSocialStatus = localStorage.getItem(`socialStatus_${currentWallet.address}`);
            const savedClaimStatus = localStorage.getItem(`claimStatus_${currentWallet.address}`);
            
            socialStatus = JSON.parse(savedSocialStatus) || { twitter: false, instagram: false };
            claimStatus = JSON.parse(savedClaimStatus) || { twitter: false, instagram: false };
        } catch (error) {
            console.error('Error loading state:', error);
        }
    }

    function saveState() {
        if (!currentWallet?.address) return;
        try {
            localStorage.setItem(`socialStatus_${currentWallet.address}`, JSON.stringify(socialStatus));
            localStorage.setItem(`claimStatus_${currentWallet.address}`, JSON.stringify(claimStatus));
        } catch (error) {
            console.error('Error saving state:', error);
        }
    }

    // Conexão da Wallet
    function setupWalletConnection() {
        if (connectBtn) {
            connectBtn.addEventListener('click', () => {
                window.postMessage({ 
                    type: 'OPEN_WALLET_CONNECT',
                    origin: window.location.origin 
                }, '*');
            });
        }

        window.addEventListener('message', (event) => {
            if (event.data.type === 'WALLET_CONNECTED') {
                handleWalletConnect(event.data.data);
            }
        });
    }

    // Handler de conexão da wallet
    function handleWalletConnect(data) {
        if (!data?.address) return;
        
        currentWallet = data;
        loadState();
        
        // Atualiza UI
        const shortAddress = `${data.address.slice(0, 6)}...${data.address.slice(-4)}`;
        walletAddress.textContent = shortAddress;
        walletAddress.style.display = 'block';
        connectBtn.innerHTML = `<i class="fas fa-check"></i> Connected`;
        connectBtn.disabled = true;

        // Atualiza estados
        updateClaimButtons();
        updateCooldownUI();
        setInterval(updateCooldownUI, 60000); // Atualiza a cada minuto
    }

    // Sistema de Cooldown
    async function checkGameCooldown() {
        try {
            const response = await fetch(`http://localhost:5000/quest/claim_status/mini_game/${currentWallet.address}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Validação adicional
            if (typeof data.last_played !== 'number' || typeof data.cooldown !== 'number') {
                throw new Error('Resposta inválida do servidor');
            }
            
            const lastPlayed = data.last_played * 1000; // Converter para milissegundos
            const cooldown = data.cooldown * 1000;
            const remaining = cooldown - (Date.now() - lastPlayed);
            
            return remaining > 0;
            
        } catch (error) {
            console.error('Erro na verificação de cooldown:', error);
            alert('Erro ao verificar disponibilidade do jogo');
            return true; // Bloquear jogo em caso de erro
        }
    }

    function updateCooldownUI() {
        if (!currentWallet) return;

        fetch(`http://localhost:5000/quest/claim_status/mini_game/${currentWallet.address}`)
            .then(response => {
                if (!response.ok) throw new Error('Network response was not ok');
                return response.json();
            })
            .then(data => {
                const lastPlayed = data.last_played * 1000;
                const cooldown = data.cooldown * 1000;
                const remaining = cooldown - (Date.now() - lastPlayed);

                if (remaining > 0) {
                    miniGameBtn.disabled = true;
                    const hours = Math.floor(remaining / (1000 * 60 * 60));
                    const minutes = Math.floor((remaining % (1000 * 60 * 60)) / (1000 * 60));
                    
                    miniGameBtn.innerHTML = `
                        <div class="cooldown-timer">⏳ ${hours}h ${minutes}m</div>
                        <i class="fas fa-gamepad"></i>
                        Mini Game
                        <span class="cooldown-tooltip">Próximo jogo em ${hours}h ${minutes}m</span>
                    `;
                } else {
                    miniGameBtn.disabled = false;
                    miniGameBtn.innerHTML = `
                        <i class="fas fa-gamepad"></i>
                        Mini Game
                    `;
                }
            })
            .catch(error => {
                console.error('Error updating cooldown UI:', error);
                miniGameBtn.disabled = true;
                miniGameBtn.innerHTML = `<i class="fas fa-exclamation-triangle"></i> Error`;
            });
    }

    // Sistema de Claims
    async function sendGameClaimTransaction(score) {
        try {
            const response = await fetch('http://localhost:5000/node/report_energy', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    wallet_address: currentWallet.address,
                    public_key: currentWallet.public_key || "",
                    energy: score,
                    quest: 'mini_game'
                }),
            });
            
            if (!response.ok) throw new Error('Network response was not ok');
            
            const result = await response.json();
            if (result.status === 'success') {
                updateCooldownUI();
                return true;
            }
            return false;
            
        } catch (err) {
            console.error('Game claim error:', err);
            alert('Error: ' + err.message);
            return false;
        }
    }

    async function sendClaimTransaction(platform) {
        try {
            const response = await fetch('http://localhost:5000/node/report_energy', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    wallet_address: currentWallet.address,
                    public_key: currentWallet.public_key || "",
                    energy: 50,
                    quest: platform
                }),
            });

            if (!response.ok) throw new Error('Network response was not ok');
            
            const result = await response.json();
            return result.status === 'success';
            
        } catch (err) {
            console.error('Claim error:', err);
            alert('Error: ' + err.message);
            return false;
        }
    }

    // Atualização dos botões de claim
    function updateClaimButtons() {
        if (!currentWallet) return;

        document.querySelectorAll('.quest-item').forEach(item => {
            const platform = item.querySelector('.social-link')?.dataset.platform;
            const btn = item.querySelector('.claim-btn');
            if (!platform || !btn) return;

            const canClaim = socialStatus[platform] && !claimStatus[platform];
            
            btn.classList.toggle('active', canClaim);
            btn.disabled = !canClaim;

            btn.innerHTML = canClaim 
                ? '<span>Claim 50 $SUN</span>'
                : claimStatus[platform] 
                    ? '<i class="fas fa-check"></i> Claimed!'
                    : '<span>Claim</span><i class="fas fa-lock"></i>';

            btn.style.cssText = claimStatus[platform] 
                ? 'background-color: #e0e0e0; color: #4CAF50; cursor: not-allowed;'
                : socialStatus[platform] 
                    ? 'cursor: pointer; background-color: #4CAF50; color: white;'
                    : 'cursor: default; background-color: #f0f0f0;';
        });
    }

    // Event Handlers
    function setupEventListeners() {
        // Mini-Game
        if (miniGameBtn) {
            miniGameBtn.addEventListener('click', async () => {
                if (!currentWallet) {
                    alert("Conecte sua wallet primeiro!");
                    return;
                }
                
                try {
                    const inCooldown = await checkGameCooldown();
                    if (inCooldown) {
                        alert("Você só pode jogar uma vez a cada 12 horas!");
                        return;
                    }
                    openGameModal();
                } catch (error) {
                    console.error('Error starting game:', error);
                    alert("Erro ao verificar cooldown!");
                }
            });
        }

        // Social Links
        document.querySelectorAll('.social-link').forEach(link => {
            link.addEventListener('click', function(e) {
                if (e.target.tagName === 'A' && currentWallet) {
                    const platform = this.dataset.platform;
                    platform && setTimeout(() => {
                        socialStatus[platform] = true;
                        saveState();
                        updateClaimButtons();
                    }, 1000);
                }
            });
        });

        // Claim Buttons
        document.addEventListener('click', async (e) => {
            const btn = e.target.closest('.claim-btn.active');
            if (!btn || !currentWallet) return;

            const platform = btn.closest('.quest-item')?.querySelector('.social-link')?.dataset.platform;
            if (!platform) return;

            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';

            try {
                const success = await sendClaimTransaction(platform);
                if (success) {
                    claimStatus[platform] = true;
                    saveState();
                }
            } catch (error) {
                console.error('Claim error:', error);
            } finally {
                updateClaimButtons();
            }
        });
    }

    // Inicialização
    setupWalletConnection();
    setupEventListeners();
    updateClaimButtons();
});

// Content Script da Extensão
if (typeof browser !== 'undefined') {
    window.addEventListener('message', (event) => {
        if (event.data.type === 'OPEN_WALLET_CONNECT') {
            browser.runtime.sendMessage({
                action: "openConnectWindow",
                origin: event.data.origin
            });
        }
    });

    browser.runtime.onMessage.addListener((msg) => {
        if (msg.action === "walletDataUpdate") {
            window.postMessage({
                type: 'WALLET_CONNECTED',
                data: msg.data
            }, '*');
        }
    });
}