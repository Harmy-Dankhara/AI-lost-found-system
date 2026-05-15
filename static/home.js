if (window.AOS) AOS.init({ duration: 1000, once: true });

function syncNotifications() {
    const baseBadge = document.getElementById('nav-badge');
    const myBadge = document.getElementById('premium-nav-badge');
    
    if (baseBadge && myBadge) {
        myBadge.textContent = baseBadge.textContent;
        myBadge.style.display = baseBadge.style.display;
        
        const observer = new MutationObserver(() => {
            myBadge.textContent = baseBadge.textContent;
            myBadge.style.display = baseBadge.style.display;
        });
        observer.observe(baseBadge, { attributes: true, childList: true, subtree: true });
    }
}
document.addEventListener('DOMContentLoaded', syncNotifications);

window.togglePremiumNotif = function() {
    const baseDropdown = document.getElementById('notif-dropdown');
    const myDropdown = document.getElementById('premium-notif-dropdown');
    if (baseDropdown && myDropdown) {
        myDropdown.innerHTML = baseDropdown.innerHTML;
        myDropdown.classList.toggle('active');
    }
}

// Typewriter Effect
const twLine1 = document.getElementById('tw-line1');
const twLine2 = document.getElementById('tw-line2');
if (twLine1 && twLine2) {
    const text1 = "Welcome to ";
    const text2 = "AI Lost & Found";
    let i = 0, j = 0;
    function typeLine1() {
        if (i < text1.length) {
            twLine1.textContent += text1.charAt(i);
            i++; setTimeout(typeLine1, 60);
        } else {
            setTimeout(typeLine2, 200);
        }
    }
    function typeLine2() {
        if (j < text2.length) {
            twLine2.textContent += text2.charAt(j);
            j++; setTimeout(typeLine2, 60);
        }
    }
    setTimeout(typeLine1, 500);
}

// Background Canvas Particles (Stars)
const bgCanvas = document.getElementById('bg-canvas');
if (bgCanvas) {
    const bgCtx = bgCanvas.getContext('2d');
    let w, h, particlesArray = [];
    function initBg() {
        w = bgCanvas.width = window.innerWidth;
        h = bgCanvas.height = window.innerHeight;
        particlesArray = [];
        for(let i=0; i<150; i++){
            particlesArray.push({
                x: Math.random() * w, y: Math.random() * h,
                size: Math.random() * 1.5,
                alpha: Math.random() * 0.8
            });
        }
    }
    function animateBg() {
        requestAnimationFrame(animateBg);
        bgCtx.clearRect(0, 0, w, h);
        particlesArray.forEach(p => {
            p.alpha += (Math.random() - 0.5) * 0.05;
            if(p.alpha <= 0) p.alpha = 0.1;
            if(p.alpha >= 0.8) p.alpha = 0.8;
            
            bgCtx.fillStyle = `rgba(168, 85, 247, ${p.alpha})`;
            bgCtx.beginPath(); bgCtx.arc(p.x, p.y, p.size, 0, Math.PI * 2); bgCtx.fill();
            
            // Constellation lines
            particlesArray.forEach(p2 => {
                const dist = Math.hypot(p.x - p2.x, p.y - p2.y);
                if(dist < 80) {
                    bgCtx.strokeStyle = `rgba(124, 58, 237, ${0.1 - dist/800})`;
                    bgCtx.beginPath(); bgCtx.moveTo(p.x, p.y); bgCtx.lineTo(p2.x, p2.y); bgCtx.stroke();
                }
            });
        });
    }
    window.addEventListener('resize', initBg);
    initBg(); animateBg();
}

// Three.js Brain Particle System
const brainCanvas = document.getElementById('brainCanvas');
if (brainCanvas && window.THREE) {
    const renderer = new THREE.WebGLRenderer({ canvas: brainCanvas, alpha: true, antialias: true });
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 1000);
    camera.position.z = 9;
    
    function resizeBrain() {
        const parent = brainCanvas.parentElement;
        renderer.setSize(parent.clientWidth, parent.clientHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        camera.aspect = parent.clientWidth / parent.clientHeight;
        camera.updateProjectionMatrix();
    }
    window.addEventListener('resize', resizeBrain);
    
    const brainGroup = new THREE.Group();
    scene.add(brainGroup);
    
    // Keep the environment group (named brainGroup)
    // We removed the particle brain generation so the environment wraps around the CSS image    // Holographic Rings around brain
    const ring1Geo = new THREE.RingGeometry(3.6, 3.65, 64);
    const ring1Mat = new THREE.MeshBasicMaterial({ color: 0x00e5ff, transparent: true, opacity: 0.6, side: THREE.DoubleSide, blending: THREE.AdditiveBlending });
    const ring1 = new THREE.Mesh(ring1Geo, ring1Mat);
    ring1.rotation.x = Math.PI / 2;
    ring1.position.y = -3.5;
    brainGroup.add(ring1);

    const ring2Geo = new THREE.RingGeometry(4.2, 4.22, 64);
    const ring2Mat = new THREE.MeshBasicMaterial({ color: 0xa855f7, transparent: true, opacity: 0.4, side: THREE.DoubleSide, blending: THREE.AdditiveBlending });
    const ring2 = new THREE.Mesh(ring2Geo, ring2Mat);
    ring2.rotation.x = Math.PI / 2 + 0.2;
    ring2.rotation.y = 0.2;
    ring2.position.y = -3.5;
    brainGroup.add(ring2);

    // Transparent Holographic Light Beam (Projector effect)
    const coneGeo = new THREE.ConeGeometry(4.5, 12, 64, 1, true);
    const coneMat = new THREE.MeshBasicMaterial({ color: 0x00e5ff, transparent: true, opacity: 0.08, side: THREE.DoubleSide, blending: THREE.AdditiveBlending });
    const beam = new THREE.Mesh(coneGeo, coneMat);
    beam.position.y = -8;
    beam.rotation.x = Math.PI;
    brainGroup.add(beam);

    // Orbit-like curved neural connection lines (Jarvis rings)
    const orbitGroup = new THREE.Group();
    for (let i = 0; i < 4; i++) {
        const orbitGeo = new THREE.TorusGeometry(4.5 + i * 0.4, 0.015, 16, 100);
        const orbitMat = new THREE.MeshBasicMaterial({ color: i % 2 === 0 ? 0x00e5ff : 0xa855f7, transparent: true, opacity: 0.3, blending: THREE.AdditiveBlending });
        const orbit = new THREE.Mesh(orbitGeo, orbitMat);
        orbit.rotation.x = Math.random() * Math.PI;
        orbit.rotation.y = Math.random() * Math.PI;
        orbitGroup.add(orbit);
    }
    brainGroup.add(orbitGroup);

    // Light Pulses (Energy travelling)
    const pulseCount = 30;
    const pulseGeo = new THREE.BufferGeometry();
    const pulsePosArray = new Float32Array(pulseCount * 3);
    pulseGeo.setAttribute('position', new THREE.BufferAttribute(pulsePosArray, 3));
    const pulseMat = new THREE.PointsMaterial({ size: 0.4, color: 0xffffff, transparent: true, opacity: 1, blending: THREE.AdditiveBlending });
    const pulses = new THREE.Points(pulseGeo, pulseMat);
    brainGroup.add(pulses);

    const pulseAngles = Array(pulseCount).fill(0).map(()=>Math.random() * Math.PI * 2);
    const pulseRadii = Array(pulseCount).fill(0).map(()=> 1.5 + Math.random() * 1.8);
    const pulseSpeeds = Array(pulseCount).fill(0).map(()=> 0.02 + Math.random() * 0.03);
    const pulseYOffsets = Array(pulseCount).fill(0).map(()=> (Math.random() - 0.5) * 3);

    // Brain Position Adjustment
    brainGroup.position.y = 1;

    resizeBrain();
    
    let t = 0;
    function render() {
        requestAnimationFrame(render);
        t += 0.005;
        
        // Continuous smooth rotation
        brainGroup.rotation.y = t * 0.8;
        brainGroup.rotation.x = Math.sin(t) * 0.15;
        
        // Massive Breathing pulse effect
        const scale = 1.3 + Math.sin(t * 8) * 0.04;
        brainGroup.scale.set(scale, scale, scale);
        
        // Rotate rings in opposite directions
        ring1.rotation.z -= 0.01;
        ring2.rotation.z += 0.005;

        // Rotate Orbiting Jarvis rings
        orbitGroup.rotation.x -= 0.002;
        orbitGroup.rotation.y += 0.003;
        orbitGroup.rotation.z -= 0.001;
        
        // Animate light pulses travelling through network
        const pArr = pulses.geometry.attributes.position.array;
        for(let i=0; i<pulseCount; i++) {
            pulseAngles[i] += pulseSpeeds[i];
            const a = pulseAngles[i];
            const r = pulseRadii[i] * (1 + Math.sin(a*3)*0.1); // slight wobble
            pArr[i*3] = Math.cos(a) * r;
            pArr[i*3+1] = pulseYOffsets[i] + Math.sin(a * 4) * 0.5;
            pArr[i*3+2] = Math.sin(a) * r;
        }
        pulses.geometry.attributes.position.needsUpdate = true;

        renderer.render(scene, camera);
    }
    render();
}
