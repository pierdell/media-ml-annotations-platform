// ═══════════════════════════════════════════════════════════
// Shared State for Comparison Page
// Shared annotations/ML data + per-viewport zoom/pan
// ═══════════════════════════════════════════════════════════

const listeners = new Map();

export const state = {
  // Media
  mediaUrl: null,
  mediaWidth: 0,
  mediaHeight: 0,

  // Tools
  activeTool: 'select',
  activeLabel: 'person',
  brushSize: 20,

  // Annotations (shared across both viewports)
  annotations: [],
  selectedAnnotationId: null,

  // ML Layers (shared data, per-viewport visibility managed by renderers)
  mlLayers: {
    heatmap:   { visible: false, opacity: 0.6, data: null },
    detection: { visible: false, opacity: 0.8, data: null },
    mask:      { visible: false, opacity: 0.5, data: null },
    tracking:  { visible: false, opacity: 0.9, data: null },
  },

  // Undo/Redo
  undoStack: [],
  redoStack: [],

  // Labels
  labels: [
    { id: 'person',  name: 'Person',  color: '#FF6B6B' },
    { id: 'vehicle', name: 'Vehicle', color: '#4ECDC4' },
    { id: 'animal',  name: 'Animal',  color: '#45B7D1' },
    { id: 'object',  name: 'Object',  color: '#F7DC6F' },
    { id: 'text',    name: 'Text',    color: '#BB8FCE' },
  ],
};

// Per-viewport state
const viewportStates = {
  left:  { zoom: 1, panX: 0, panY: 0 },
  right: { zoom: 1, panX: 0, panY: 0 },
};

export function getViewportState(id) {
  return viewportStates[id];
}

export function subscribe(key, callback) {
  if (!listeners.has(key)) listeners.set(key, new Set());
  listeners.get(key).add(callback);
  return () => listeners.get(key).delete(callback);
}

export function emit(key, value) {
  if (listeners.has(key)) {
    for (const cb of listeners.get(key)) {
      try { cb(value); } catch (e) { console.error(`State error [${key}]:`, e); }
    }
  }
}

export function setState(key, value) {
  state[key] = value;
  emit(key, value);
}

export function getLabelColor(labelId) {
  const label = state.labels.find(l => l.id === labelId);
  return label ? label.color : '#888888';
}

// ── Utility functions ──────────────────────────────────────

export function clamp(val, min, max) {
  return Math.max(min, Math.min(max, val));
}

export function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
}

export function hexToRgba(hex, alpha = 1) {
  if (!hex || !hex.startsWith('#')) return hex;
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
