const canvas = document.getElementById("game-canvas");
const ctx = canvas.getContext("2d");
canvas.width = window.innerWidth * 0.8; // 80% of screen width
canvas.height = window.innerHeight * 0.8; // 80% of screen height

const scoreElement = document.getElementById("score-center");
const levelElement = document.getElementById("level-center");
const timerElement = document.getElementById("timer-center");
const highScoreElement = document.getElementById("high-score-center");
const pauseButton = document.getElementById("pause-button");

let snake = [{ x: 200, y: 200 }];
let food = { x: 300, y: 300, score: 1 };
let direction = { x: 10, y: 0 };
let score = 0;
let level = 1;
let gameSpeed = 200; // Default speed
let highScore = localStorage.getItem("highScore") || 0;
let snakeColor = "limegreen"; // Default color
let isPaused = false;
let startTime = Date.now(); // Record the start time
let updateTimer;

// Sounds
const foodSound = new Audio("food-sound.mp3");
const gameOverSound = new Audio("game-over-sound.mp3");
const moveSound = new Audio("move-sound.mp3");
const musicSound = new Audio("music.mp3");

musicSound.loop = true;
musicSound.volume = 0.5;
musicSound.play().catch(err => console.error("Music failed to play:", err));

// Difficulty selection
const levelSpeeds = {
    easy: 360,
    medium: 290,
    hard: 180,
};
document.querySelectorAll(".difficulty-button").forEach(button => {
    button.addEventListener("click", () => {
        const difficulty = button.dataset.difficulty;
        gameSpeed = levelSpeeds[difficulty];
        console.log(`Difficulty set to ${difficulty}. Speed: ${gameSpeed}ms`); // Debugging log
        resetGame();
    });
});

// Generate random food
function randomFoodPosition() {
    let position;
    let isOnSnake;
    do {
        const x = Math.floor(Math.random() * (canvas.width / 10)) * 10;
        const y = Math.floor(Math.random() * (canvas.height / 10)) * 10;
        const type = Math.random() < 0.2 ? "special" : "normal"; // 20% chance special
        position = { x, y, score: type === "special" ? 5 : 1, type };
        isOnSnake = snake.some(segment => segment.x === position.x && segment.y === position.y);
    } while (isOnSnake);
    return position;
}

// Food eaten check
function isFoodEaten(head, food) {
    return Math.abs(head.x - food.x) < 10 && Math.abs(head.y - food.y) < 10;
}

// Draw snake
function drawSnake() {
    snake.forEach((segment, index) => {
        if (index === 0) {
            ctx.beginPath();
            ctx.rect(segment.x, segment.y, 10, 10);
            ctx.fillStyle = "gold";
            ctx.fill();
            ctx.beginPath();
            ctx.arc(segment.x + 3, segment.y + 3, 1.5, 0, 2 * Math.PI);
            ctx.fillStyle = "black";
            ctx.fill();
            ctx.beginPath();
            ctx.arc(segment.x + 7, segment.y + 3, 1.5, 0, 2 * Math.PI);
            ctx.fill();
        } else {
            ctx.beginPath();
            ctx.ellipse(segment.x + 5, segment.y + 5, 6, 4, 0, 0, 2 * Math.PI);
            ctx.fillStyle = snakeColor;
            ctx.fill();
        }
    });
}

// Draw food
function drawFood() {
    ctx.beginPath();
    ctx.arc(food.x + 5, food.y + 5, 5, 0, 2 * Math.PI);
    ctx.fillStyle = food.type === "special" ? "purple" : "red";
    ctx.fill();
    ctx.fillStyle = "white";
    ctx.font = "10px Arial";
    ctx.fillText(food.score, food.x, food.y - 5);
}

// Move snake
function moveSnake() {
    const head = { x: snake[0].x + direction.x, y: snake[0].y + direction.y };
    if (head.x < 0) head.x = canvas.width - 10;
    if (head.x >= canvas.width) head.x = 0;
    if (head.y < 0) head.y = canvas.height - 10;
    if (head.y >= canvas.height) head.y = 0;

    snake.unshift(head);

    if (isFoodEaten(head, food)) {
        score += food.score;
        foodSound.play().catch(err => console.error("Food sound failed:", err));
        food = randomFoodPosition();
        if (score % 10 === 0) {
            level++;
            gameSpeed = Math.max(50, gameSpeed - 20); // Speed increases as levels increase
            console.log(`Level up! New Speed: ${gameSpeed}ms`); // Debugging log
            clearTimeout(updateTimer);
            update();
        }
    } else {
        snake.pop();
    }
}

// Collision check
function checkSelfCollision() {
    const head = snake[0];
    return snake.slice(1).some(segment => segment.x === head.x && segment.y === head.y);
}

// Draw background
function drawBackground() {
    const gradient = ctx.createRadialGradient(
        canvas.width / 2,
        canvas.height / 2,
        0,
        canvas.width / 2,
        canvas.height / 2,
        canvas.width
    );
    gradient.addColorStop(0, "#001f3f");
    gradient.addColorStop(1, "#0074D9");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
}

// Timer update
function updateTimerDisplay() {
    const currentTime = Date.now();
    const elapsedTime = Math.floor((currentTime - startTime) / 1000); // Time in seconds
    timerElement.textContent = `Time: ${elapsedTime}s`;
}

// Update game
function update() {
    if (checkSelfCollision()) {
        musicSound.pause();
        gameOverSound.play();
        alert(`Game Over! Your Score: ${score}. Retry Level ${level}`);
        resetGame();
        return;
    }

    if (!isPaused) {
        moveSnake();
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        drawBackground();
        drawSnake();
        drawFood();
        updateTimerDisplay();

        scoreElement.textContent = `Score: ${score}`;
        levelElement.textContent = `Level: ${level}`;
        highScoreElement.textContent = `High Score: ${highScore}`;

        if (score > highScore) {
            highScore = score;
            localStorage.setItem("highScore", highScore);
        }

        updateTimer = setTimeout(update, gameSpeed);
    }
}

// Reset game
function resetGame() {
    musicSound.pause();
    musicSound.currentTime = 0;
    snake = [{ x: 200, y: 200 }];
    food = randomFoodPosition();
    direction = { x: 10, y: 0 };
    score = 0;
    level = 1;
    startTime = Date.now(); // Reset timer
    musicSound.play().catch(err => console.error("Music failed to play:", err));
    update();
}

// Keyboard input for desktop controls
document.addEventListener("keydown", event => {
    if (event.key === "ArrowUp" && direction.y === 0) direction = { x: 0, y: -10 };
    if (event.key === "ArrowDown" && direction.y === 0) direction = { x: 0, y: 10 };
    if (event.key === "ArrowLeft" && direction.x === 0) direction = { x: -10, y: 0 };
    if (event.key === "ArrowRight" && direction.x === 0) direction = { x: 10, y: 0 };

    moveSound.play().catch(err => console.error("Move sound failed:", err));
});

// Touch input for mobile controls
canvas.addEventListener("touchstart", handleTouchStart, false);

function handleTouchStart(event) {
    const touch = event.touches[0];
    const touchX = touch.clientX;
    const touchY = touch.clientY;

    // Move the snake based on the touch position
    if (touchY < canvas.height / 2 && direction.y === 0) {
        direction = { x: 0, y: -10 }; // Up
    } else if (touchY >= canvas.height / 2 && direction.y === 0) {
        direction = { x: 0, y: 10 }; // Down
    } else if (touchX < canvas.width / 2 && direction.x === 0) {
        direction = { x: -10, y: 0 }; // Left
    } else if (touchX >= canvas.width / 2 && direction.x === 0) {
        direction = { x: 10, y: 0 }; // Right
    }
}

// Pause button
pauseButton.addEventListener("click", () => {
    isPaused = !isPaused;
    pauseButton.textContent = isPaused ? "Resume" : "Pause";
    if (!isPaused) update(); // Resume game
});

// Start the game
update();
