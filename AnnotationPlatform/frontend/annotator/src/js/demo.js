// ═══════════════════════════════════════════════════════════
// Demo ML Data Generators
// Generates realistic-looking mock ML outputs for visualization
// ═══════════════════════════════════════════════════════════

import { state } from './state.js';

const DETECTION_LABELS = [
  { label: 'person',  color: '#FF6B6B' },
  { label: 'car',     color: '#4ECDC4' },
  { label: 'dog',     color: '#45B7D1' },
  { label: 'bicycle', color: '#F7DC6F' },
  { label: 'chair',   color: '#BB8FCE' },
  { label: 'laptop',  color: '#E74C3C' },
  { label: 'bottle',  color: '#2ECC71' },
  { label: 'phone',   color: '#E67E22' },
];

const SEGMENT_COLORS = [
  'rgba(255, 107, 107, 0.35)',
  'rgba(78, 205, 196, 0.35)',
  'rgba(69, 183, 209, 0.35)',
  'rgba(247, 220, 111, 0.35)',
  'rgba(187, 143, 206, 0.35)',
  'rgba(231, 76, 60, 0.35)',
  'rgba(46, 204, 113, 0.35)',
];

const TRACK_COLORS = [
  'rgb(255, 107, 107)',
  'rgb(78, 205, 196)',
  'rgb(69, 183, 209)',
  'rgb(247, 220, 111)',
  'rgb(187, 143, 206)',
  'rgb(52, 152, 219)',
  'rgb(231, 76, 60)',
  'rgb(46, 204, 113)',
];

// ── Heatmap ───────────────────────────────────────────────
export function generateHeatmapData() {
  const w = state.mediaWidth;
  const h = state.mediaHeight;
  const gridW = 32;
  const gridH = Math.round(gridW * (h / w));
  const values = new Float32Array(gridW * gridH);

  // Generate 3-5 gaussian hot spots
  const numSpots = 3 + Math.floor(Math.random() * 3);
  const spots = [];
  for (let i = 0; i < numSpots; i++) {
    spots.push({
      cx: Math.random() * gridW,
      cy: Math.random() * gridH,
      sigma: 2 + Math.random() * 4,
      intensity: 0.5 + Math.random() * 0.5,
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

// ── Object Detection ──────────────────────────────────────
export function generateDetectionData() {
  const w = state.mediaWidth;
  const h = state.mediaHeight;
  const numDetections = 4 + Math.floor(Math.random() * 6);
  const detections = [];

  for (let i = 0; i < numDetections; i++) {
    const det = DETECTION_LABELS[Math.floor(Math.random() * DETECTION_LABELS.length)];
    const bw = 60 + Math.random() * (w * 0.3);
    const bh = 60 + Math.random() * (h * 0.3);
    const bx = Math.random() * (w - bw);
    const by = Math.random() * (h - bh);

    detections.push({
      x: bx,
      y: by,
      w: bw,
      h: bh,
      label: det.label,
      color: det.color,
      confidence: 0.55 + Math.random() * 0.45,
    });
  }

  // Sort by confidence descending
  detections.sort((a, b) => b.confidence - a.confidence);
  return detections;
}

// ── Segmentation Masks ────────────────────────────────────
export function generateMaskData() {
  const w = state.mediaWidth;
  const h = state.mediaHeight;
  const numSegments = 3 + Math.floor(Math.random() * 4);
  const segments = [];

  for (let i = 0; i < numSegments; i++) {
    const cx = w * 0.15 + Math.random() * w * 0.7;
    const cy = h * 0.15 + Math.random() * h * 0.7;
    const numPoints = 8 + Math.floor(Math.random() * 12);
    const baseRadius = 40 + Math.random() * Math.min(w, h) * 0.2;
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

// ── Point Tracking ────────────────────────────────────────
export function generateTrackingData() {
  const w = state.mediaWidth;
  const h = state.mediaHeight;
  const numTracks = 5 + Math.floor(Math.random() * 8);
  const tracks = [];

  for (let i = 0; i < numTracks; i++) {
    const numPoints = 10 + Math.floor(Math.random() * 30);
    let cx = Math.random() * w;
    let cy = Math.random() * h;
    const points = [];

    for (let j = 0; j < numPoints; j++) {
      cx += (Math.random() - 0.5) * 40;
      cy += (Math.random() - 0.5) * 30;
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

// ── Video-specific: Animated tracking for video ───────────
export function generateVideoTrackingFrame(baseData, frameIndex, totalFrames) {
  if (!baseData) return null;

  return baseData.map(track => {
    const { points, color, label } = track;
    const progress = frameIndex / totalFrames;
    const endIdx = Math.floor(progress * points.length);
    return {
      points: points.slice(0, Math.max(1, endIdx)),
      color,
      label,
    };
  });
}

// ── Video-specific: Detection keyframes ───────────────────
export function generateVideoDetectionKeyframes(numFrames) {
  const keyframes = [];
  const interval = Math.max(1, Math.floor(numFrames / 10));

  for (let f = 0; f < numFrames; f += interval) {
    keyframes.push({
      frame: f,
      detections: generateDetectionData(),
    });
  }
  return keyframes;
}

// ── Generate all ML data at once ──────────────────────────
export function generateAllMlData() {
  return {
    heatmap: generateHeatmapData(),
    detection: generateDetectionData(),
    mask: generateMaskData(),
    tracking: generateTrackingData(),
  };
}
