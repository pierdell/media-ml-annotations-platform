// ═══════════════════════════════════════════════════════════
// Enhanced Demo Data Generators
// High-resolution heatmaps, 100s of detections, dense masks
// ═══════════════════════════════════════════════════════════

const DETECTION_LABELS = [
  { label: 'person',  color: '#FF6B6B' },
  { label: 'car',     color: '#4ECDC4' },
  { label: 'dog',     color: '#45B7D1' },
  { label: 'bicycle', color: '#F7DC6F' },
  { label: 'chair',   color: '#BB8FCE' },
  { label: 'laptop',  color: '#E74C3C' },
  { label: 'bottle',  color: '#2ECC71' },
  { label: 'phone',   color: '#E67E22' },
  { label: 'cup',     color: '#1ABC9C' },
  { label: 'book',    color: '#9B59B6' },
  { label: 'bag',     color: '#E91E63' },
  { label: 'sign',    color: '#FF9800' },
];

const SEGMENT_COLORS = [
  'rgba(255, 107, 107, 0.35)',
  'rgba(78, 205, 196, 0.35)',
  'rgba(69, 183, 209, 0.35)',
  'rgba(247, 220, 111, 0.35)',
  'rgba(187, 143, 206, 0.35)',
  'rgba(231, 76, 60, 0.35)',
  'rgba(46, 204, 113, 0.35)',
  'rgba(52, 152, 219, 0.35)',
];

const TRACK_COLORS = [
  'rgb(255, 107, 107)', 'rgb(78, 205, 196)', 'rgb(69, 183, 209)',
  'rgb(247, 220, 111)', 'rgb(187, 143, 206)', 'rgb(52, 152, 219)',
  'rgb(231, 76, 60)',   'rgb(46, 204, 113)', 'rgb(241, 196, 15)',
  'rgb(155, 89, 182)',
];

// ── High-Resolution Heatmap (256x grid) ──────────────────
export function generateHighResHeatmap(w, h) {
  const gridW = 256;
  const gridH = Math.round(gridW * (h / w));
  const values = new Float32Array(gridW * gridH);

  const numSpots = 5 + Math.floor(Math.random() * 5);
  const spots = [];
  for (let i = 0; i < numSpots; i++) {
    spots.push({
      cx: Math.random() * gridW,
      cy: Math.random() * gridH,
      sigma: 5 + Math.random() * 20,
      intensity: 0.4 + Math.random() * 0.6,
    });
  }

  for (let y = 0; y < gridH; y++) {
    for (let x = 0; x < gridW; x++) {
      let val = 0;
      for (const spot of spots) {
        const dx = x - spot.cx;
        const dy = y - spot.cy;
        val += spot.intensity * Math.exp(-(dx * dx + dy * dy) / (2 * spot.sigma * spot.sigma));
      }
      values[y * gridW + x] = Math.min(1, val);
    }
  }

  return { width: gridW, height: gridH, values };
}

// ── Mass Detections (100s of small objects) ──────────────
export function generateMassDetections(w, h, count = 200) {
  const detections = [];

  for (let i = 0; i < count; i++) {
    const det = DETECTION_LABELS[Math.floor(Math.random() * DETECTION_LABELS.length)];
    const bw = 20 + Math.random() * 60;
    const bh = 20 + Math.random() * 60;
    const bx = Math.random() * (w - bw);
    const by = Math.random() * (h - bh);

    detections.push({
      x: bx, y: by, w: bw, h: bh,
      label: det.label,
      color: det.color,
      confidence: 0.3 + Math.random() * 0.7,
    });
  }

  detections.sort((a, b) => b.confidence - a.confidence);
  return detections;
}

// ── High-Resolution Masks (many vertices) ────────────────
export function generateHighResMasks(w, h) {
  const numSegments = 8 + Math.floor(Math.random() * 5);
  const segments = [];

  for (let i = 0; i < numSegments; i++) {
    const cx = w * 0.1 + Math.random() * w * 0.8;
    const cy = h * 0.1 + Math.random() * h * 0.8;
    const numPoints = 30 + Math.floor(Math.random() * 20);
    const baseRadius = 30 + Math.random() * Math.min(w, h) * 0.15;
    const points = [];

    for (let j = 0; j < numPoints; j++) {
      const angle = (j / numPoints) * Math.PI * 2;
      const r = baseRadius * (0.6 + Math.random() * 0.8);
      points.push([
        cx + Math.cos(angle) * r,
        cy + Math.sin(angle) * r,
      ]);
    }

    const colorIdx = i % SEGMENT_COLORS.length;
    const det = DETECTION_LABELS[i % DETECTION_LABELS.length];
    segments.push({
      points,
      color: SEGMENT_COLORS[colorIdx],
      borderColor: det.color,
      label: det.label,
    });
  }

  return segments;
}

// ── Dense Tracking (20+ tracks) ──────────────────────────
export function generateDenseTracking(w, h) {
  const numTracks = 20 + Math.floor(Math.random() * 10);
  const tracks = [];

  for (let i = 0; i < numTracks; i++) {
    const numPoints = 50 + Math.floor(Math.random() * 50);
    let cx = Math.random() * w;
    let cy = Math.random() * h;
    const points = [];

    for (let j = 0; j < numPoints; j++) {
      cx += (Math.random() - 0.5) * 30;
      cy += (Math.random() - 0.5) * 20;
      cx = Math.max(10, Math.min(w - 10, cx));
      cy = Math.max(10, Math.min(h - 10, cy));
      points.push([cx, cy]);
    }

    tracks.push({
      points,
      color: TRACK_COLORS[i % TRACK_COLORS.length],
      label: `Track ${i + 1}`,
    });
  }

  return tracks;
}

// ── Generate all demo data ───────────────────────────────
export function generateAllDemoData(w, h) {
  return {
    heatmap:   generateHighResHeatmap(w, h),
    detection: generateMassDetections(w, h, 200),
    mask:      generateHighResMasks(w, h),
    tracking:  generateDenseTracking(w, h),
  };
}
