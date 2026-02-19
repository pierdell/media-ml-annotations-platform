// ═══════════════════════════════════════════════════════════
// Reactive State Management
// ═══════════════════════════════════════════════════════════

const listeners = new Map();

export const state = {
  // Current view mode
  viewMode: 'annotate', // 'annotate' | 'visualize' | 'compare'

  // Media
  mediaList: [],        // Array of { id, name, type, file, url, width, height, duration? }
  activeMediaId: null,
  mediaType: null,      // 'image' | 'video'

  // Viewport
  zoom: 1,
  panX: 0,
  panY: 0,
  viewportWidth: 0,
  viewportHeight: 0,
  mediaWidth: 0,
  mediaHeight: 0,

  // Tools
  activeTool: 'select',
  activeLabel: 'person',
  brushSize: 20,

  // Annotations
  annotations: [],       // Array of annotation objects
  selectedAnnotationId: null,
  nextAnnotationId: 1,

  // ML Layers
  mlLayers: {
    heatmap:   { visible: false, opacity: 0.6, data: null },
    detection: { visible: false, opacity: 0.8, data: null },
    mask:      { visible: false, opacity: 0.5, data: null },
    tracking:  { visible: false, opacity: 0.9, data: null },
  },

  // Video
  isPlaying: false,
  currentTime: 0,
  duration: 0,
  fps: 30,
  playbackSpeed: 1,

  // Compare
  comparePosition: 0.5,

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

export function subscribe(key, callback) {
  if (!listeners.has(key)) listeners.set(key, new Set());
  listeners.get(key).add(callback);
  return () => listeners.get(key).delete(callback);
}

export function emit(key, value) {
  if (listeners.has(key)) {
    for (const cb of listeners.get(key)) {
      try { cb(value); } catch (e) { console.error(`State listener error [${key}]:`, e); }
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
