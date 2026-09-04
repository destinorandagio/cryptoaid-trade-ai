/**
 * TradeAID Upward Red Matrix Stream (010101010101)
 * Direction: Bottom to Top (Rising)
 * Speed: Slow, hypnotic, cyber-ambient
 * Brand Colors: White, Red & Black
 */

(function () {
    function initMatrix() {
        const canvas = document.getElementById("matrix-canvas");
        if (!canvas) return;

        const ctx = canvas.getContext("2d");
        let width = (canvas.width = window.innerWidth);
        let height = (canvas.height = window.innerHeight);

        const chars = ["0", "1"];
        const fontSize = 14;
        let columns = Math.floor(width / fontSize);
        let drops = [];

        function resetDrops() {
            columns = Math.floor(width / fontSize);
            drops = [];
            const rows = Math.ceil(height / fontSize);
            for (let i = 0; i < columns; i++) {
                // Initialize randomly below the screen or throughout the screen
                drops[i] = Math.floor(Math.random() * (rows + 40));
            }
        }
        resetDrops();

        let lastTime = 0;
        const fps = 22; // Controlled, slow & hypnotic update rate (approx 22 steps/sec)
        const interval = 1000 / fps;

        function draw() {
            // Translucent black trail creating upward vanishing tails
            ctx.fillStyle = "rgba(3, 4, 7, 0.14)";
            ctx.fillRect(0, 0, width, height);

            ctx.font = fontSize + "px 'JetBrains Mono', monospace";

            const rows = Math.ceil(height / fontSize);

            for (let i = 0; i < drops.length; i++) {
                const text = chars[Math.floor(Math.random() * chars.length)];
                const x = i * fontSize;
                const y = drops[i] * fontSize;

                // Rare stark white leading spark, otherwise deep neon red
                if (Math.random() > 0.96) {
                    ctx.fillStyle = "#ffffff";
                    ctx.shadowColor = "#ff1e38";
                    ctx.shadowBlur = 8;
                } else if (Math.random() > 0.85) {
                    ctx.fillStyle = "#ff4d63";
                    ctx.shadowColor = "#ff1e38";
                    ctx.shadowBlur = 4;
                } else {
                    ctx.fillStyle = "#ff1e38";
                    ctx.shadowColor = "#b91c1c";
                    ctx.shadowBlur = 2;
                }

                ctx.fillText(text, x, y);
                ctx.shadowBlur = 0;

                // When stream rises past top of screen (y < 0), reset to bottom
                if (drops[i] * fontSize < 0 && Math.random() > 0.965) {
                    drops[i] = rows + Math.floor(Math.random() * 15);
                }

                // Move UPWARDS (decreases y row)
                drops[i]--;
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
            width = canvas.width = window.innerWidth;
            height = canvas.height = window.innerHeight;
            resetDrops();
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initMatrix);
    } else {
        initMatrix();
    }
})();
