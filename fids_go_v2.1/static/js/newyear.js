/**
 * New Year's Surprise Logic
 * Triggers fireworks and greeting if the date is New Year's Eve/Day
 * or if ?test_newyear=true is present in the URL.
 */

(function () {
    // Configuration
    const CONFIG = {
        checkInterval: 1000, // Check every second
        targetMonth: 0, // January (0-indexed)
        targetDate: 1,
        targetHour: 0,
        targetMinute: 0,
        triggerWindowMinutes: 5, // Keep active for 5 minutes after midnight
        testParam: 'test_newyear',
        audioPath: '/go/static/audio/test.mp3',
        // audioPath: '/go/static/audio/test.mp3', // Absolute path test audio
    };

    let isActive = false;
    let canvas, ctx;
    let fireworks = [];
    let particles = [];
    let audio = null;

    function init() {
        // Check if we should trigger immediately (URL param)
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get(CONFIG.testParam) === 'true') {
            startCelebration();
            return;
        }

        // Start time checking loop
        setInterval(checkTime, CONFIG.checkInterval);
        checkTime(); // Initial check
    }

    function checkTime() {
        const now = new Date();

        // Logic: 
        // 1. Dec 31st 23:59:00 - 23:59:59 (Countdown or Pre-trigger - we'll just trigger at 23:59:50 for now or strictly midnight)
        // 2. Jan 1st 00:00:00 - 00:20:00 (Celebration)

        const isDec31 = now.getMonth() === 11 && now.getDate() === 31;
        const isJan1 = now.getMonth() === 0 && now.getDate() === 1;

        let shouldTrigger = false;

        if (isDec31) {
            // Trigger a bit before midnight? or strictly at 23:59:59?
            // Let's trigger from 23:59:55
            if (now.getHours() === 23 && now.getMinutes() === 59 && now.getSeconds() >= 50) {
                shouldTrigger = true;
            }
        } else if (isJan1) {
            // Active for first X minutes of Jan 1
            if (now.getHours() === 0 && now.getMinutes() < CONFIG.triggerWindowMinutes) {
                shouldTrigger = true;
            }
        }

        if (shouldTrigger && !isActive) {
            startCelebration();
        } else if (!shouldTrigger && isActive) {
            stopCelebration();
        }
    }

    function startCelebration() {
        isActive = true;
        console.log("Happy New Year! Starting celebration...");

        createOverlay();
        startFireworks();
        playAudio();
    }

    function stopCelebration() {
        isActive = false;
        if (audio) {
            audio.pause();
            audio.currentTime = 0;
        }
        const overlay = document.getElementById('ny-overlay');
        if (overlay) {
            overlay.remove();
        }
    }

    function createOverlay() {
        if (document.getElementById('ny-overlay')) return;

        const overlay = document.createElement('div');
        overlay.id = 'ny-overlay';
        overlay.innerHTML = `
            <canvas id="ny-canvas"></canvas>
            <div class="ny-message-container">
                <h1 class="ny-title">Аэропорт Ош поздравляет</h1>
                <h2 class="ny-title">С Новым Годом!</h2>
                <div class="ny-subtitle">2026</div>
            </div>
        `;
        document.body.appendChild(overlay);

        canvas = document.getElementById('ny-canvas');
        ctx = canvas.getContext('2d');
        resizeCanvas();

        window.addEventListener('resize', resizeCanvas);

        // Start animation loop
        requestAnimationFrame(loop);
    }

    function resizeCanvas() {
        if (!canvas) return;
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }

    function playAudio() {
        // Construct absolute path based on current origin
        // e.g., http://localhost:8080/go/static/audio/newyear.mp3
        const audioUrl = window.location.origin + '/go/static/audio/test.mp3';
        // const audioUrl = window.location.origin + '/go/static/audio/test.mp3';
        console.log('Attempting to play audio from:', audioUrl);

        audio = new Audio(audioUrl);
        audio.loop = false;
        audio.volume = 0.5;

        // Unlock audio on user interaction if autoplay is blocked
        const playPromise = audio.play();

        if (playPromise !== undefined) {
            playPromise.then(_ => {
                console.log('Audio playback started');
            })
                .catch(error => {
                    console.log('Audio autoplay blocked. Waiting for interaction.', error);

                    // Add one-time click listener to body to start audio
                    const unlockAudio = () => {
                        audio.play();
                        document.body.removeEventListener('click', unlockAudio);
                        document.body.removeEventListener('touchstart', unlockAudio);
                    };

                    document.body.addEventListener('click', unlockAudio);
                    document.body.addEventListener('touchstart', unlockAudio);
                });
        }
    }

    // --- Fireworks Logic ---
    function random(min, max) { return Math.random() * (max - min) + min; }

    class Firework {
        constructor(sx, sy, tx, ty) {
            this.x = sx;
            this.y = sy;
            this.sx = sx;
            this.sy = sy;
            this.tx = tx;
            this.ty = ty;
            this.distanceToTarget = Math.sqrt(Math.pow(tx - sx, 2) + Math.pow(ty - sy, 2));
            this.distanceTraveled = 0;
            this.coordinates = [];
            this.coordinateCount = 3;
            while (this.coordinateCount--) {
                this.coordinates.push([this.x, this.y]);
            }
            this.angle = Math.atan2(ty - sy, tx - sx);
            this.speed = 2;
            this.acceleration = 1.05;
            this.brightness = random(50, 70);
            this.targetRadius = 1;
        }

        update(index) {
            this.coordinates.pop();
            this.coordinates.unshift([this.x, this.y]);

            if (this.targetRadius < 8) this.targetRadius += 0.3;
            else this.targetRadius = 1;

            this.speed *= this.acceleration;
            const vx = Math.cos(this.angle) * this.speed;
            const vy = Math.sin(this.angle) * this.speed;
            this.distanceTraveled = Math.sqrt(Math.pow(this.sx - this.x - vx, 2) + Math.pow(this.sy - this.y - vy, 2));

            if (this.distanceTraveled >= this.distanceToTarget) {
                createParticles(this.tx, this.ty);
                fireworks.splice(index, 1);
            } else {
                this.x += vx;
                this.y += vy;
            }
        }

        draw() {
            ctx.beginPath();
            ctx.moveTo(this.coordinates[this.coordinates.length - 1][0], this.coordinates[this.coordinates.length - 1][1]);
            ctx.lineTo(this.x, this.y);
            ctx.strokeStyle = `hsl(${random(0, 360)}, 100%, ${this.brightness}%)`;
            ctx.stroke();
        }
    }

    class Particle {
        constructor(x, y) {
            this.x = x;
            this.y = y;
            this.coordinates = [];
            this.coordinateCount = 5;
            while (this.coordinateCount--) {
                this.coordinates.push([this.x, this.y]);
            }
            this.angle = random(0, Math.PI * 2);
            this.speed = random(1, 10);
            this.friction = 0.95;
            this.gravity = 1;
            this.hue = random(0, 360);
            this.brightness = random(50, 80);
            this.alpha = 1;
            this.decay = random(0.015, 0.03);
        }

        update(index) {
            this.coordinates.pop();
            this.coordinates.unshift([this.x, this.y]);
            this.speed *= this.friction;
            this.x += Math.cos(this.angle) * this.speed;
            this.y += Math.sin(this.angle) * this.speed + this.gravity;
            this.alpha -= this.decay;

            if (this.alpha <= this.decay) {
                particles.splice(index, 1);
            }
        }

        draw() {
            ctx.beginPath();
            ctx.moveTo(this.coordinates[this.coordinates.length - 1][0], this.coordinates[this.coordinates.length - 1][1]);
            ctx.lineTo(this.x, this.y);
            ctx.strokeStyle = `hsla(${this.hue}, 100%, ${this.brightness}%, ${this.alpha})`;
            ctx.stroke();
        }
    }

    function createParticles(x, y) {
        let particleCount = 30;
        while (particleCount--) {
            particles.push(new Particle(x, y));
        }
    }

    function startFireworks() {
        // Initialization if needed
    }

    function loop() {
        if (!isActive) return;
        requestAnimationFrame(loop);

        // Slow fade effect for trails
        ctx.globalCompositeOperation = 'destination-out';
        ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.globalCompositeOperation = 'lighter';

        // Create new fireworks randomly
        if (Math.random() < 0.05) { // Chance per frame
            fireworks.push(new Firework(
                canvas.width / 2,
                canvas.height,
                random(0, canvas.width),
                random(0, canvas.height / 2)
            ));
        }

        let i = fireworks.length;
        while (i--) {
            fireworks[i].draw();
            fireworks[i].update(i);
        }

        let j = particles.length;
        while (j--) {
            particles[j].draw();
            particles[j].update(j);
        }
    }

    // Run initialization
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
