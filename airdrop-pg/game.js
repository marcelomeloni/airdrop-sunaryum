// Adicione estas variáveis no topo
const GAME_DURATION = 30;
let gameActive = false;
let countdownInterval;
let flareInterval;
let comboCheckInterval;

// Função para abrir o modal corrigida
function openGameModal() {
    document.getElementById('gameOverlay').style.display = 'block';
    document.getElementById('gameModal').style.display = 'block';
    startGame();
}

// Função de início do jogo corrigida
function startGame() {
    if (gameActive) return;
    gameActive = true;
    
    timer = GAME_DURATION;
    score = 0;
    combo = 1;
    flaresActive = 0;
    updateUI();

    // Limpa qualquer intervalo anterior
    clearInterval(countdownInterval);
    clearInterval(flareInterval);
    clearInterval(comboCheckInterval);

    countdownInterval = setInterval(() => {
        timer--;
        document.getElementById('timer').textContent = timer;
        
        if(timer <= 5) {
            document.getElementById('timer').classList.add('timer-critical');
        }
        
        if(timer <= 0) {
            endGame();
            clearInterval(countdownInterval);
        }
    }, 1000);

    // Sistema de criação de flares
    flareInterval = setInterval(() => {
        if(timer <= 0 || !gameActive) {
            clearInterval(flareInterval);
            return;
        }
        
        if(flaresActive < 5) createFlare();
    }, 800);

    // Sistema de combo
    comboCheckInterval = setInterval(() => {
        if(timer <= 0 || !gameActive) {
            clearInterval(comboCheckInterval);
            return;
        }
        
        combo = Math.max(1, combo - 0.2);
        document.getElementById('combo').textContent = `x${combo.toFixed(1)}`;
    }, 2000);
}
async function handleGameEnd(finalScore) {
    const gameControls = document.querySelector('.game-controls');
    gameControls.innerHTML = `
        <div class="game-result">
            <i class="fas fa-spinner fa-spin"></i>
            Enviando ${finalScore} energia...
        </div>
    `;

    try {
        const success = await sendGameClaimTransaction(finalScore);
        if (success) {
            updateCooldownUI(); // Atualiza o estado do cooldown
        }
        gameControls.innerHTML = `
            <div class="game-result">
                ${success ? 
                    `<i class="fas fa-check success"></i>
                     ${finalScore} energia enviada com sucesso!` :
                    `<i class="fas fa-times error"></i>
                     Falha no envio, tente novamente!`}
            </div>
            <button class="game-btn" id="closeGame">Fechar</button>
        `;
        
    } catch (error) {
        console.error('Game end error:', error);
        gameControls.innerHTML = `
            <div class="game-result error">
                <i class="fas fa-times"></i>
                Erro na conexão!
            </div>
            <button class="game-btn" id="closeGame">Fechar</button>
        `;
    }
}
// Função de término do jogo corrigida
function endGame() {
    gameActive = false;
    clearInterval(countdownInterval);
    clearInterval(flareInterval);
    clearInterval(comboCheckInterval);

    // Enviar pontuação e atualizar UI
    handleGameEnd(score);
}

function showGameResults(finalScore) {
    const resultsElement = document.getElementById('gameResults');
    const energyEarned = Math.floor(finalScore / 10);
    
    document.getElementById('finalScore').textContent = finalScore;
    document.getElementById('energyEarned').textContent = energyEarned;
    
    resultsElement.classList.add('show');
    
    // Atualizar a UI de energia ganha
    if(typeof updateEnergyDisplay === 'function') {
        updateEnergyDisplay(energyEarned);
    }
}

document.getElementById('confirmResults').addEventListener('click', () => {
    document.getElementById('gameResults').classList.remove('show');
});


function createFlare() {
    const sunCore = document.querySelector('.sun-core');
    const flare = document.createElement('div');
    flare.className = 'flare';
    
    // Configuração inicial
    let removeTimeout;
    let canClick = true;

    // Cálculo do ângulo e posição
    const angle = Math.random() * Math.PI * 2;
    const distance = 120 + (Math.random() * 60);
    const centerX = sunCore.offsetWidth / 2;
    const centerY = sunCore.offsetHeight / 2;
    const x = centerX + Math.cos(angle) * distance - 15;
    const y = centerY + Math.sin(angle) * distance - 15;

    // Aplicar estilos
    flare.style.left = `${x}px`;
    flare.style.top = `${y}px`;
    flare.style.transform = `rotate(${angle}rad)`;

    // Animação de entrada
    flare.style.opacity = '0';
    flare.animate(
        [{ opacity: 0 }, { opacity: 1 }],
        { duration: 300, easing: 'ease-out' }
    ).onfinish = () => flare.style.opacity = '1';

    // Remoção automática após 1.5s
    removeTimeout = setTimeout(() => {
        flare.animate(
            [{ opacity: 1 }, { opacity: 0 }],
            { duration: 300, easing: 'ease-in' }
        ).onfinish = () => {
            flare.remove();
            flaresActive--;
            resetCombo();
        };
    }, 1500);

    // Handler de clique corrigido
    flare.addEventListener('click', (e) => {
        if (!canClick) return;
        canClick = false;

        // Cancelar remoção automática
        clearTimeout(removeTimeout);

        // Atualizar pontuação
        score += Math.floor(10 * combo);
        combo += 0.5;
        flaresActive--;

        // Efeito visual
        createComboEffect(e);
        animateFlareClick(flare);

        // Atualizar UI
        updateUI();
    });

    sunCore.appendChild(flare);
    flaresActive++;
}

function resetCombo() {
    combo = 1;
    document.getElementById('combo').textContent = `x${combo.toFixed(1)}`;
}

function animateFlareClick(flare) {
    flare.animate(
        [
            { transform: 'scale(1)', opacity: 1 },
            { transform: 'scale(1.5)', opacity: 0 }
        ],
        { duration: 300, easing: 'ease-out' }
    ).onfinish = () => flare.remove();
}
function createComboEffect(e) {
    const comboText = document.createElement('div');
    comboText.className = 'combo-effect';
    comboText.textContent = `+${Math.floor(10 * combo)}! COMBO x${combo.toFixed(1)}`;
    
    // Posicionar efeito junto ao clique
    const rect = e.target.getBoundingClientRect();
    comboText.style.left = `${rect.left + rect.width/2}px`;
    comboText.style.top = `${rect.top + rect.height/2}px`;
    
    document.body.appendChild(comboText);
    setTimeout(() => comboText.remove(), 500);
}
function updateUI() {
    document.getElementById('score').textContent = score;
    document.getElementById('combo').textContent = `x${combo.toFixed(1)}`;
}

function closeGameModal() {
    document.querySelectorAll('.flare').forEach(f => f.remove());
    document.getElementById('gameOverlay').style.display = 'none';
    document.getElementById('gameModal').style.display = 'none';
    document.getElementById('timer').textContent = GAME_DURATION;
    document.getElementById('timer').classList.remove('timer-critical');
}

// Atualizar os event listeners
document.getElementById('closeGame').addEventListener('click', closeGameModal);
document.getElementById('closeGameModal').addEventListener('click', closeGameModal);
document.getElementById('gameOverlay').addEventListener('click', closeGameModal);