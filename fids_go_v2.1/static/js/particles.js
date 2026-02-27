class AntigravityWave {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d', { alpha: false }); // Оптимизация контекста

        this.width = window.innerWidth;
        this.height = window.innerHeight;
        this.canvas.width = this.width;
        this.canvas.height = this.height;

        this.particles = [];
        this.rows = 25; // Чуть меньше рядов для плавности
        this.cols = 40;
        this.time = 0;
        this.animationId = null;

        this.primaryColor = '#ff0000';
        this.rgbColor = { r: 255, g: 0, b: 0 };

        this.init();

        window.addEventListener('resize', () => {
            this.width = window.innerWidth;
            this.height = window.innerHeight;
            this.canvas.width = this.width;
            this.canvas.height = this.height;
            this.init();
        });
    }

    init() {
        this.particles = [];
        const spacingX = this.width / this.cols;
        const spacingY = this.height / this.rows;

        for (let r = 0; r < this.rows; r++) {
            const relativeY = r / this.rows;
            if (relativeY > 0.55) continue;

            for (let c = 0; c < this.cols; c++) {
                const x = c * spacingX + spacingX / 2;
                const y = r * spacingY + spacingY / 2;

                const edgeGap = Math.abs(relativeY - 0.5);
                if (edgeGap < 0.1 && Math.random() > 0.4) continue;

                this.particles.push(new RectParticle(x, y, relativeY));
            }
        }
    }

    animate() {
        // Очистка кадра
        this.ctx.fillStyle = '#050505';
        this.ctx.fillRect(0, 0, this.width, this.height);

        this.time += 0.03; // Чуть уменьшил шаг для более плавного движения

        // Используем один проход цикла
        for (let i = 0; i < this.particles.length; i++) {
            this.particles[i].update(this.time);
            this.particles[i].draw(this.ctx, this.primaryColor, this.rgbColor);
        }

        this.animationId = requestAnimationFrame(() => this.animate());
    }

    start(color) {
        if (this.animationId) cancelAnimationFrame(this.animationId);
        if (color) {
            this.primaryColor = color;
            this.rgbColor = this.hexToRgb(color);
        }
        this.animate();
    }

    stop() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
        // Clear canvas or leave it dark? Usually clear or fill with background.
        // Given st.js resets body background, we might want to transparentize or fill black.
        // st.js sets body bg to default when stopping.
        // Let's clear the canvas to be safe.
        this.ctx.clearRect(0, 0, this.width, this.height);
    }

    hexToRgb(hex) {
        // Expand shorthand form (e.g. "03F") to full form (e.g. "0033FF")
        var shorthandRegex = /^#?([a-f\d])([a-f\d])([a-f\d])$/i;
        hex = hex.replace(shorthandRegex, function (m, r, g, b) {
            return r + r + g + g + b + b;
        });

        var result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return result ? {
            r: parseInt(result[1], 16),
            g: parseInt(result[2], 16),
            b: parseInt(result[3], 16)
        } : { r: 255, g: 0, b: 0 };
    }
}

class RectParticle {
    constructor(x, y, relativeY) {
        this.baseX = x;
        this.baseY = y;
        this.x = x;
        this.y = y;
        this.relativeY = relativeY;
        this.w = 16;
        this.h = 7;
        this.radius = 3;
    }

    update(time) {
        // Плавная математика без резких скачков
        const wave = Math.sin(time + (this.baseX * 0.005) + (this.baseY * 0.007));
        this.y = this.baseY + wave * 20;

        this.scale = 0.6 + (wave + 1) * 0.7;
        const fadeOut = Math.max(0, 1 - (this.relativeY * 1.8));
        this.opacity = (0.3 + (wave + 1) * 0.5) * fadeOut;
    }

    draw(ctx, color, rgb) {
        if (this.opacity < 0.1) return;

        ctx.save();
        ctx.translate(this.x, this.y);
        ctx.scale(this.scale, this.scale);
        ctx.globalAlpha = this.opacity;

        // Вместо shadowBlur используем градиентное свечение (работает в 10 раз быстрее)
        const glowSize = this.w * 2;
        const grad = ctx.createRadialGradient(0, 0, 0, 0, 0, glowSize);
        // Use passed RGB values for gradient
        grad.addColorStop(0, `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.8)`);
        grad.addColorStop(0.5, `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.2)`);
        grad.addColorStop(1, `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0)`);

        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(0, 0, glowSize, 0, Math.PI * 2);
        ctx.fill();

        // Основное "тело" искры
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.roundRect(-this.w / 2, -this.h / 2, this.w, this.h, this.radius);
        ctx.fill();

        ctx.restore();
    }
}