// JARVIS Holographic Core Animation
// Renders a cinematic holographic core with concentric rings, orbital elements, and state visualization

export class HologramCore {
    constructor(canvas, options = {}) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');

        // Configuration
        this.config = {
            centerX: 0,
            centerY: 0,
            baseRadius: 0,
            maxRadius: 0,
            ringCount: 6,
            orbitalCount: 8,
            particleCount: 40,
            ...options
        };

        // Animation state
        this.time = 0;
        this.state = 'idle'; // idle, listening, thinking, speaking, error
        this.greetingVisible = false;
        this.greetingText = '';
        this.micLevel = 0;

        // Colors per state
        this.stateColors = {
            idle: { primary: '#00d4aa', secondary: '#008877', glow: 'rgba(0, 212, 170, 0.4)' },
            listening: { primary: '#00aaff', secondary: '#0077aa', glow: 'rgba(0, 170, 255, 0.5)' },
            thinking: { primary: '#ffaa00', secondary: '#cc8800', glow: 'rgba(255, 170, 0, 0.5)' },
            speaking: { primary: '#aa00ff', secondary: '#8800cc', glow: 'rgba(170, 0, 255, 0.5)' },
            error: { primary: '#ff0040', secondary: '#aa0020', glow: 'rgba(255, 0, 64, 0.6)' }
        };

        // Ring definitions
        this.rings = [];
        this.orbitals = [];
        this.particles = [];

        // Animation
        this.animationId = null;
        this.lastFrame = 0;
        this.running = false;

        // Initialize
        this.resize();
        this.initRings();
        this.initOrbitals();
        this.initParticles();

        // Handle resize
        window.addEventListener('resize', () => this.resize());
    }

    resize() {
        const rect = this.canvas.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;

        this.canvas.width = rect.width * dpr;
        this.canvas.height = rect.height * dpr;
        this.canvas.style.width = rect.width + 'px';
        this.canvas.style.height = rect.height + 'px';

        this.ctx.scale(dpr, dpr);

        this.config.centerX = rect.width / 2;
        this.config.centerY = rect.height / 2;
        this.config.baseRadius = Math.min(rect.width, rect.height) * 0.18;
        this.config.maxRadius = Math.min(rect.width, rect.height) * 0.42;

        this.reinitRings();
        this.reinitOrbitals();
    }

    initRings() {
        const { baseRadius, maxRadius, ringCount } = this.config;
        for (let i = 0; i < ringCount; i++) {
            const progress = i / (ringCount - 1);
            const radius = baseRadius + (maxRadius - baseRadius) * progress;
            this.rings.push({
                radius,
                baseRadius: radius,
                rotation: Math.random() * Math.PI * 2,
                speed: (0.02 + Math.random() * 0.03) * (Math.random() > 0.5 ? 1 : -1),
                thickness: 1 + Math.random() * 2,
                segments: 12 + i * 4,
                phaseOffset: Math.random() * Math.PI * 2,
                pulsePhase: Math.random() * Math.PI * 2,
                dashPattern: [8, 4, 4, 4][i % 4],
                opacity: 0.3 + Math.random() * 0.4
            });
        }
    }

    reinitRings() {
        const { baseRadius, maxRadius } = this.config;
        this.rings.forEach((ring, i) => {
            const progress = i / (this.config.ringCount - 1);
            ring.baseRadius = baseRadius + (maxRadius - baseRadius) * progress;
            ring.radius = ring.baseRadius;
        });
    }

    initOrbitals() {
        const { orbitalCount } = this.config;
        for (let i = 0; i < orbitalCount; i++) {
            this.orbitals.push({
                angle: (i / orbitalCount) * Math.PI * 2,
                radius: this.config.baseRadius * 0.6 + Math.random() * (this.config.maxRadius - this.config.baseRadius * 0.6),
                speed: 0.005 + Math.random() * 0.015,
                size: 3 + Math.random() * 5,
                trail: [],
                trailLength: 10 + Math.random() * 20,
                pulsePhase: Math.random() * Math.PI * 2
            });
        }
    }

    reinitOrbitals() {
        this.orbitals.forEach(orbital => {
            orbital.radius = Math.max(orbital.radius, this.config.baseRadius * 0.6);
        });
    }

    initParticles() {
        const { particleCount } = this.config;
        for (let i = 0; i < particleCount; i++) {
            this.particles.push({
                angle: Math.random() * Math.PI * 2,
                radius: this.config.baseRadius * 0.3 + Math.random() * (this.config.maxRadius - this.config.baseRadius * 0.3),
                speed: 0.002 + Math.random() * 0.008,
                size: 1 + Math.random() * 2,
                opacity: 0.1 + Math.random() * 0.4,
                phase: Math.random() * Math.PI * 2
            });
        }
    }

    setState(state) {
        this.state = state;
    }

    setGreeting(visible, text = '') {
        this.greetingVisible = visible;
        this.greetingText = text;
    }

    setMicLevel(level) {
        this.micLevel = Math.max(0, Math.min(1, level));
    }

    start() {
        if (this.running) return;
        this.running = true;
        this.lastFrame = performance.now();
        this.animate();
    }

    stop() {
        this.running = false;
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
    }

    animate(timestamp = 0) {
        if (!this.running) return;

        const dt = timestamp - this.lastFrame;
        this.lastFrame = timestamp;
        this.time += dt * 0.001;

        this.update(dt * 0.001);
        this.render();

        this.animationId = requestAnimationFrame((ts) => this.animate(ts));
    }

    update(dt) {
        const colors = this.stateColors[this.state] || this.stateColors.idle;

        // Update rings
        this.rings.forEach((ring, i) => {
            ring.rotation += ring.speed * dt * 60;
            ring.pulsePhase += dt * 2;

            // Pulse effect based on state
            const pulseIntensity = this.getPulseIntensity();
            ring.radius = ring.baseRadius * (1 + Math.sin(ring.pulsePhase) * 0.02 * pulseIntensity);

            // Listening state expands rings with mic level
            if (this.state === 'listening') {
                ring.radius += this.micLevel * 8 * (1 - i / this.rings.length);
            }
        });

        // Update orbitals
        this.orbitals.forEach(orbital => {
            orbital.angle += orbital.speed * dt * 60;
            orbital.trail.push({ x: orbital.angle, y: orbital.radius, time: this.time });
            if (orbital.trail.length > orbital.trailLength) orbital.trail.shift();
            orbital.pulsePhase += dt * 3;
        });

        // Update particles
        this.particles.forEach(particle => {
            particle.angle += particle.speed * dt * 60;
            particle.phase += dt * 2;
            particle.opacity = 0.1 + 0.4 * Math.sin(particle.phase);
        });
    }

    getPulseIntensity() {
        switch (this.state) {
            case 'listening': return 1.5;
            case 'thinking': return 1.2;
            case 'speaking': return 1.0;
            case 'error': return 2.0;
            default: return 1.0;
        }
    }

    render() {
        const ctx = this.ctx;
        const { centerX, centerY } = this.config;
        const colors = this.stateColors[this.state] || this.stateColors.idle;

        // Clear canvas
        ctx.clearRect(0, 0, this.canvas.width / (window.devicePixelRatio || 1), this.canvas.height / (window.devicePixelRatio || 1));

        // Save context
        ctx.save();
        ctx.translate(centerX, centerY);

        // Draw outer glow
        this.drawOuterGlow(colors);

        // Draw rings
        this.drawRings(colors);

        // Draw central core
        this.drawCore(colors);

        // Draw orbitals
        this.drawOrbitals(colors);

        // Draw particles
        this.drawParticles(colors);

        // Draw technical markings
        this.drawTechnicalMarkings(colors);

        // Draw state indicator
        this.drawStateIndicator(colors);

        // Draw greeting
        if (this.greetingVisible && this.greetingText) {
            this.drawGreeting(colors);
        }

        ctx.restore();
    }

    drawOuterGlow(colors) {
        const ctx = this.ctx;
        const maxRadius = this.config.maxRadius;

        const gradient = ctx.createRadialGradient(0, 0, maxRadius * 0.5, 0, 0, maxRadius * 1.5);
        gradient.addColorStop(0, colors.glow);
        gradient.addColorStop(0.5, colors.glow.replace('0.4', '0.1').replace('0.5', '0.15').replace('0.6', '0.2'));
        gradient.addColorStop(1, 'transparent');

        ctx.beginPath();
        ctx.arc(0, 0, maxRadius * 1.5, 0, Math.PI * 2);
        ctx.fillStyle = gradient;
        ctx.fill();
    }

    drawRings(colors) {
        const ctx = this.ctx;

        this.rings.forEach((ring, i) => {
            ctx.beginPath();
            ctx.arc(0, 0, ring.radius, 0, Math.PI * 2);

            ctx.strokeStyle = colors.primary;
            ctx.lineWidth = ring.thickness;
            ctx.globalAlpha = ring.opacity * (0.5 + 0.5 * Math.sin(this.time * 2 + ring.phaseOffset));

            // Set dash pattern
            ctx.setLineDash([ring.dashPattern, ring.dashPattern * 1.5]);
            ctx.lineDashOffset = -ring.rotation * 20;

            ctx.stroke();
            ctx.setLineDash([]);
            ctx.globalAlpha = 1;

            // Inner accent ring
            if (i % 2 === 0) {
                ctx.beginPath();
                ctx.arc(0, 0, ring.radius * 0.95, 0, Math.PI * 2);
                ctx.strokeStyle = colors.secondary;
                ctx.lineWidth = 0.5;
                ctx.globalAlpha = 0.3;
                ctx.stroke();
                ctx.globalAlpha = 1;
            }
        });
    }

    drawCore(colors) {
        const ctx = this.ctx;
        const baseRadius = this.config.baseRadius * 0.35;

        // Core glow layers
        for (let i = 3; i >= 0; i--) {
            const r = baseRadius * (1 + i * 0.3);
            const gradient = ctx.createRadialGradient(0, 0, 0, 0, 0, r);
            gradient.addColorStop(0, colors.primary);
            gradient.addColorStop(0.5, colors.secondary);
            gradient.addColorStop(1, 'transparent');

            ctx.beginPath();
            ctx.arc(0, 0, r, 0, Math.PI * 2);
            ctx.fillStyle = gradient;
            ctx.globalAlpha = 0.15 / (i + 1);
            ctx.fill();
        }

        // Central core
        const coreGradient = ctx.createRadialGradient(0, 0, 0, 0, 0, baseRadius);
        coreGradient.addColorStop(0, '#ffffff');
        coreGradient.addColorStop(0.3, colors.primary);
        coreGradient.addColorStop(0.7, colors.secondary);
        coreGradient.addColorStop(1, '#000000');

        ctx.beginPath();
        ctx.arc(0, 0, baseRadius, 0, Math.PI * 2);
        ctx.fillStyle = coreGradient;
        ctx.fill();

        // Core border
        ctx.beginPath();
        ctx.arc(0, 0, baseRadius, 0, Math.PI * 2);
        ctx.strokeStyle = colors.primary;
        ctx.lineWidth = 2;
        ctx.globalAlpha = 0.8;
        ctx.stroke();
        ctx.globalAlpha = 1;

        // Central identifier
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 11px JetBrains Mono, monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('JARVIS', 0, 1);

        // Core pulse
        const pulseScale = 1 + Math.sin(this.time * 3) * 0.05;
        ctx.beginPath();
        ctx.arc(0, 0, baseRadius * pulseScale, 0, Math.PI * 2);
        ctx.strokeStyle = colors.primary;
        ctx.lineWidth = 1;
        ctx.globalAlpha = 0.5 + 0.3 * Math.sin(this.time * 4);
        ctx.stroke();
        ctx.globalAlpha = 1;
    }

    drawOrbitals(colors) {
        const ctx = this.ctx;

        this.orbitals.forEach(orbital => {
            const x = Math.cos(orbital.angle) * orbital.radius;
            const y = Math.sin(orbital.angle) * orbital.radius;

            // Draw trail
            if (orbital.trail.length > 1) {
                ctx.beginPath();
                orbital.trail.forEach((point, i) => {
                    const px = Math.cos(point.x) * point.y;
                    const py = Math.sin(point.x) * point.y;
                    if (i === 0) ctx.moveTo(px, py);
                    else ctx.lineTo(px, py);
                });

                const trailGradient = ctx.createLinearGradient(
                    Math.cos(orbital.trail[0].x) * orbital.trail[0].y,
                    Math.sin(orbital.trail[0].x) * orbital.trail[0].y,
                    x, y
                );
                trailGradient.addColorStop(0, 'transparent');
                trailGradient.addColorStop(1, colors.primary);

                ctx.strokeStyle = trailGradient;
                ctx.lineWidth = 1.5;
                ctx.globalAlpha = 0.4;
                ctx.stroke();
            }

            // Orbital body
            const pulse = 1 + Math.sin(orbital.pulsePhase) * 0.3;
            const size = orbital.size * pulse;

            ctx.beginPath();
            ctx.arc(x, y, size, 0, Math.PI * 2);

            const orbitalGradient = ctx.createRadialGradient(x, y, 0, x, y, size);
            orbitalGradient.addColorStop(0, '#ffffff');
            orbitalGradient.addColorStop(0.5, colors.primary);
            orbitalGradient.addColorStop(1, colors.secondary);

            ctx.fillStyle = orbitalGradient;
            ctx.fill();

            // Orbital ring
            ctx.beginPath();
            ctx.arc(x, y, size * 1.5, 0, Math.PI * 2);
            ctx.strokeStyle = colors.primary;
            ctx.lineWidth = 1;
            ctx.globalAlpha = 0.4;
            ctx.stroke();
            ctx.globalAlpha = 1;
        });
    }

    drawParticles(colors) {
        const ctx = this.ctx;

        this.particles.forEach(particle => {
            const x = Math.cos(particle.angle) * particle.radius;
            const y = Math.sin(particle.angle) * particle.radius;

            ctx.beginPath();
            ctx.arc(x, y, particle.size, 0, Math.PI * 2);
            ctx.fillStyle = colors.primary;
            ctx.globalAlpha = particle.opacity;
            ctx.fill();
        });
        ctx.globalAlpha = 1;
    }

    drawTechnicalMarkings(colors) {
        const ctx = this.ctx;
        const maxRadius = this.config.maxRadius;

        ctx.strokeStyle = colors.primary;
        ctx.lineWidth = 0.5;
        ctx.globalAlpha = 0.15;

        // Cardinal direction lines
        for (let i = 0; i < 4; i++) {
            const angle = (i * Math.PI / 2) + this.time * 0.02;
            const x1 = Math.cos(angle) * this.config.baseRadius * 0.4;
            const y1 = Math.sin(angle) * this.config.baseRadius * 0.4;
            const x2 = Math.cos(angle) * maxRadius * 1.1;
            const y2 = Math.sin(angle) * maxRadius * 1.1;

            ctx.beginPath();
            ctx.moveTo(x1, y1);
            ctx.lineTo(x2, y2);
            ctx.stroke();
        }

        // Distance markers
        ctx.font = '8px JetBrains Mono, monospace';
        ctx.fillStyle = colors.primary;
        ctx.globalAlpha = 0.3;
        ctx.textAlign = 'center';

        for (let i = 1; i <= 4; i++) {
            const r = this.config.baseRadius + (maxRadius - this.config.baseRadius) * (i / 4);
            const label = `${Math.round(r / maxRadius * 100)}%`;
            ctx.fillText(label, 0, -r - 8);
        }

        ctx.globalAlpha = 1;
    }

    drawStateIndicator(colors) {
        const ctx = this.ctx;
        const maxRadius = this.config.maxRadius;

        // State ring at max radius
        ctx.beginPath();
        ctx.arc(0, 0, maxRadius * 1.05, 0, Math.PI * 2);
        ctx.strokeStyle = colors.primary;
        ctx.lineWidth = 2;
        ctx.setLineDash([10, 10]);
        ctx.lineDashOffset = -this.time * 20;
        ctx.globalAlpha = 0.6;
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.globalAlpha = 1;

        // State label
        const stateLabels = {
            idle: 'STANDBY',
            listening: 'LISTENING',
            thinking: 'PROCESSING',
            speaking: 'SPEAKING',
            error: 'ERROR'
        };

        ctx.fillStyle = colors.primary;
        ctx.font = 'bold 10px Orbitron, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(stateLabels[this.state] || 'IDLE', 0, maxRadius * 1.35);

        // Status dots
        const dotCount = 8;
        for (let i = 0; i < dotCount; i++) {
            const angle = (i / dotCount) * Math.PI * 2 + this.time * 0.5;
            const r = maxRadius * 1.05;
            const x = Math.cos(angle) * r;
            const y = Math.sin(angle) * r;

            ctx.beginPath();
            ctx.arc(x, y, 3, 0, Math.PI * 2);
            ctx.fillStyle = colors.primary;
            ctx.globalAlpha = 0.5 + 0.5 * Math.sin(this.time * 4 + i);
            ctx.fill();
        }
        ctx.globalAlpha = 1;
    }

    drawGreeting(colors) {
        const ctx = this.ctx;
        const maxRadius = this.config.maxRadius;

        ctx.fillStyle = colors.primary;
        ctx.font = '300 14px Space Grotesk, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.globalAlpha = 0.8 + 0.2 * Math.sin(this.time * 2);

        // Split greeting into lines if too long
        const maxWidth = maxRadius * 2.5;
        const words = this.greetingText.split(' ');
        let lines = [];
        let currentLine = '';

        words.forEach(word => {
            const testLine = currentLine + (currentLine ? ' ' : '') + word;
            const metrics = ctx.measureText(testLine);
            if (metrics.width > maxWidth && currentLine) {
                lines.push(currentLine);
                currentLine = word;
            } else {
                currentLine = testLine;
            }
        });
        if (currentLine) lines.push(currentLine);

        const lineHeight = 22;
        const startY = maxRadius * 1.6 - (lines.length - 1) * lineHeight / 2;

        lines.forEach((line, i) => {
            ctx.fillText(line, 0, startY + i * lineHeight);
        });

        ctx.globalAlpha = 1;
    }

    // Public method to get current state for UI sync
    getStateInfo() {
        return {
            state: this.state,
            colors: this.stateColors[this.state] || this.stateColors.idle
        };
    }
}

// Utility function to create and initialize hologram
export function createHologram(canvas, options = {}) {
    const hologram = new HologramCore(canvas, options);
    hologram.start();
    return hologram;
}
