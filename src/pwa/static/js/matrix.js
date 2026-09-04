/**
 * TradeAID Red Matrix Rain Background (010101010101)
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

        for (let i = 0; i < columns; i++) {
            drops[i] = Math.floor(Math.random() * -50);
        }

        function draw() {
            // Translucent black overlay creates the trailing fade effect
            ctx.fillStyle = "rgba(4, 5, 8, 0.08)";
            ctx.fillRect(0, 0, width, height);

            ctx.font = fontSize + "px 'JetBrains Mono', monospace";

            for (let i = 0; i < drops.length; i++) {
                const text = chars[Math.floor(Math.random() * chars.length)];
                const x = i * fontSize;
                const y = drops[i] * fontSize;

                // Glowing red binary stream with occasional stark white spark
                if (Math.random() > 0.96) {
                    ctx.fillStyle = "#ffffff"; // Stark white highlight spark
                    ctx.shadowColor = "#ff1e38";
                    ctx.shadowBlur = 8;
                } else {
                    ctx.fillStyle = "#ff1e38"; // Neon brand red
                    ctx.shadowColor = "#ff0033";
                    ctx.shadowBlur = 4;
                }

                ctx.fillText(text, x, y);
                ctx.shadowBlur = 0;

                if (y > height && Math.random() > 0.975) {
                    drops[i] = 0;
                }
                drops[i]++;
            }
        }

        let animationFrame;
        function loop() {
            draw();
            animationFrame = requestAnimationFrame(loop);
        }
        loop();

        window.addEventListener("resize", () => {
            width = canvas.width = window.innerWidth;
            height = canvas.height = window.innerHeight;
            columns = Math.floor(width / fontSize);
            drops = [];
            for (let i = 0; i < columns; i++) {
                drops[i] = Math.floor(Math.random() * -50);
            }
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initMatrix);
    } else {
        initMatrix();
    }
})();
