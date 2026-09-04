/**
 * TradeAID Ultra-Slow Digital Matrix Rain Effect
 * - Large glowing numerals (0-9)
 * - Super slow, hypnotic, cinematic ambient speed
 * - Red & stark white cybernetic brand aesthetic
 */

(function () {
    function initMatrix() {
        const canvas = document.getElementById("matrix-canvas");
        if (!canvas) return;

        const ctx = canvas.getContext("2d");
        let width = (canvas.width = window.innerWidth);
        let height = (canvas.height = window.innerHeight);

        // Digits for matrix stream (numbers as requested)
        const chars = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"];
        // Larger font size (24px for clear readability and high-impact visual presence)
        const fontSize = 24;
        let columns = Math.floor(width / (fontSize * 1.35));
        let drops = [];

        function resetDrops() {
            width = canvas.width = window.innerWidth;
            height = canvas.height = window.innerHeight;
            columns = Math.floor(width / (fontSize * 1.35));
            drops = [];
            const rows = Math.ceil(height / fontSize);
            for (let i = 0; i < columns; i++) {
                drops[i] = {
                    y: Math.random() * rows,
                    // Ultra-slow speed: advances 0.08 to 0.22 rows per tick (~2 to 6 pixels per sec)
                    speed: 0.08 + Math.random() * 0.14,
                    // Random switch timer to morph the character
                    charChangeTimer: Math.floor(Math.random() * 15),
                    currentChar: chars[Math.floor(Math.random() * chars.length)],
                };
            }
        }
        resetDrops();

        let lastTime = 0;
        // 24 fps ticker, but with fractional micro-increments for super smooth, slow motion
        const interval = 1000 / 24;

        function draw() {
            // Very soft trailing black fade to create long, silky luminous trails
            ctx.fillStyle = "rgba(3, 4, 7, 0.09)";
            ctx.fillRect(0, 0, width, height);

            ctx.font = "bold " + fontSize + "px 'JetBrains Mono', 'Courier New', monospace";

            const rows = Math.ceil(height / fontSize);

            for (let i = 0; i < drops.length; i++) {
                const drop = drops[i];
                drop.charChangeTimer++;
                if (drop.charChangeTimer > 20) {
                    drop.currentChar = chars[Math.floor(Math.random() * chars.length)];
                    drop.charChangeTimer = 0;
                }

                const x = i * (fontSize * 1.35) + 6;
                const y = Math.floor(drop.y) * fontSize;

                // Glowing leading digit with distinct cyber aesthetic
                if (Math.random() > 0.94) {
                    ctx.fillStyle = "#ffffff";
                    ctx.shadowColor = "#ffffff";
                    ctx.shadowBlur = 12;
                } else if (Math.random() > 0.75) {
                    ctx.fillStyle = "#ff4d63";
                    ctx.shadowColor = "#ff1e38";
                    ctx.shadowBlur = 6;
                } else {
                    ctx.fillStyle = "rgba(255, 30, 56, 0.75)";
                    ctx.shadowColor = "#ff1e38";
                    ctx.shadowBlur = 2;
                }

                ctx.fillText(drop.currentChar, x, y);
                ctx.shadowBlur = 0;

                // Ultra slow downward advance
                drop.y += drop.speed;

                // Reset to top when passing bottom of viewport
                if (drop.y > rows && Math.random() > 0.975) {
                    drop.y = -2;
                    drop.speed = 0.08 + Math.random() * 0.14;
                }
            }
        }

        let animationFrame;
        function loop(timestamp) {
            if (!lastTime) lastTime = timestamp;
            const delta = timestamp - lastTime;

            if (delta > interval) {
                lastTime = timestamp - (delta % interval);
                draw();
            }

            animationFrame = requestAnimationFrame(loop);
        }
        animationFrame = requestAnimationFrame(loop);

        window.addEventListener("resize", () => {
            resetDrops();
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initMatrix);
    } else {
        initMatrix();
    }
})();

