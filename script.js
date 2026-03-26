document.addEventListener("DOMContentLoaded", () => {
    initIntro();
    initScrollAnimations();
    initVisualizer();
});

/*
 * ----------------------------------------------------
 * LAUNCH INTRO OVERLAY
 * ----------------------------------------------------
 */
function initIntro() {
    const introNode = document.querySelector('.launch-intro');
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const introHold = reduceMotion ? 700 : 2100;
    const introExit = reduceMotion ? 0 : 900;

    if (!introNode) {
        document.body.classList.remove('intro-active');
        return;
    }

    window.requestAnimationFrame(() => {
        document.body.classList.add('intro-mounted');
    });

    window.setTimeout(() => {
        document.body.classList.add('intro-complete');
        document.body.classList.remove('intro-active');
    }, introHold);

    window.setTimeout(() => {
        introNode.remove();
    }, introHold + introExit);
}



/* 
 * ----------------------------------------------------
 * JUMPY, ENERGETIC SCROLL OBSERVER
 * ----------------------------------------------------
 */
function initScrollAnimations() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                // Unobserver once it's visible so it doesn't jump constantly,
                // or leave it to jump every time you scroll up/down (which we will do for energy)
                // observer.unobserve(entry.target); 
            } else {
                // If you want it to jump again when scrolled back into view
                entry.target.classList.remove('is-visible');
            }
        });
    }, {
        threshold: 0.1, // Trigger when 10% visible
        rootMargin: "0px 0px -50px 0px" // Trigger slightly before it hits the true bottom
    });

    const jumpElements = document.querySelectorAll('.reveal-jump');
    jumpElements.forEach(el => observer.observe(el));
}


/* 
 * ----------------------------------------------------
 * SCROLLING RIGHT-TO-LEFT SINE VISUALIZER
 * WITH OCCASIONAL HIGH-ENERGY BURSTS
 * ----------------------------------------------------
 */
const visContainer = document.getElementById('audio-vis');
const signalReactor = document.getElementById('signal-reactor');
const NUM_BARS = 32;
let bars = [];
let phase = 0;

// Autonomous burst tracking
let burstEnergy = 0;
let lastBurstTime = 0;
let nextBurstDelay = 4000; // Time until first burst

function initVisualizer() {
    if (!visContainer) return;

    for (let i = 0; i < NUM_BARS; i++) {
        let bar = document.createElement('div');
        bar.className = 'vis-bar';
        visContainer.appendChild(bar);
        bars.push(bar);
    }

    // Start the 60fps render loop
    requestAnimationFrame(renderVisualizer);
}

function renderVisualizer(timestamp) {
    if (!visContainer) return;

    // Trigger an occasional jump/burst randomly every 4-8 seconds
    if (timestamp - lastBurstTime > nextBurstDelay) {
        lastBurstTime = timestamp;
        nextBurstDelay = 4000 + (Math.random() * 4000); // randomize next delay
        burstEnergy = 4.0; // Trigger a huge jump
    }

    // "reverting to normal" - Decay the burst energy slowly back to zero
    burstEnergy *= 0.94; 

    // "faster scrolling" - Base horizontal phase speed is 0.05, but burst makes it flow much faster
    const phaseSpeed = 0.05 + (burstEnergy * 0.04);
    phase += phaseSpeed;

    bars.forEach((bar, index) => {
        // Base sine waves flowing left to right
        const waveSpread = 0.2;
        
        let wave1 = Math.sin(phase - (index * waveSpread)) * 30;
        let wave2 = Math.cos(phase * 0.7 - (index * 0.15)) * 15;
        
        // Base amplitude
        let targetHeight = 35 + wave1 + wave2;

        // "huger height of the sine" - Organic, natural energy bursts
        if (burstEnergy > 0.05) {
            // A natural audio transient pushes a smooth cluster of frequencies up together
            // We mix two moving sine waves based on absolute timestamp so the spikes drift organically
            let energyWave1 = Math.sin((index * 0.3) + (timestamp * 0.003)) * 0.5 + 0.5; 
            let energyWave2 = Math.cos((index * 0.8) - (timestamp * 0.007)) * 0.5 + 0.5; 
            
            // Combine for a complex but smooth peak cluster that naturally shifts over time
            let organicModifier = (energyWave1 * 0.7) + (energyWave2 * 0.3);
            
            // Taper the burst envelope heavily at the edges so the center gets the most chaotic energy
            let burstEnvelope = Math.sin((index / NUM_BARS) * Math.PI);
            
            // Scale by burstEnergy (adds up to 90% vertical jump smoothly)
            targetHeight += (organicModifier * burstEnergy * 20.0) * burstEnvelope;
        }
        
        // Ensure bounds 5% to 100% height limit
        targetHeight = Math.max(5, Math.min(100, targetHeight));
        
        bar.style.height = `${targetHeight}%`;
    });

    // Subtly and smoothly sway the entire card if energy is high
    if (signalReactor) {
        let driftX = Math.sin(timestamp * 0.005) * burstEnergy * 1.5;
        let driftY = Math.cos(timestamp * 0.003) * burstEnergy * 2.0;
        let rotateZ = Math.sin(timestamp * 0.002) * burstEnergy * 0.2;
        
        signalReactor.style.transform = `translate3d(${driftX.toFixed(2)}px, ${driftY.toFixed(2)}px, 0) rotateZ(${rotateZ.toFixed(2)}deg)`;
    }

    requestAnimationFrame(renderVisualizer);
}
