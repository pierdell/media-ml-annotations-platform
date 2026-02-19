// ═══════════════════════════════════════════════════════════
// Compare App - Entry Point
// Wires up two renderers side-by-side for comparison
// ═══════════════════════════════════════════════════════════

import { state, setState, getViewportState } from './compare-state.js';
import { PixiRenderer } from './pixi-renderer.js';
import { HybridRenderer } from './hybrid-renderer.js';
import { AnnotationController } from './annotation-interaction.js';
import { generateAllDemoData } from './compare-demo.js';

let leftRenderer, rightRenderer;
let leftController, rightController;
let mediaLoaded = false;

// ── Toast ────────────────────────────────────────────────
function toast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => { el.classList.add('fade-out'); setTimeout(() => el.remove(), 300); }, 2500);
}

// ── Init ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  const leftEl = document.getElementById('viewport-left');
  const rightEl = document.getElementById('viewport-right');

  // Create renderers
  leftRenderer = new PixiRenderer(leftEl, getViewportState('left'));
  rightRenderer = new HybridRenderer(rightEl, getViewportState('right'));

  await Promise.all([leftRenderer.init(), rightRenderer.init()]);

  // Create annotation controllers (each draws on its own viewport, syncs to the other)
  leftController = new AnnotationController(leftEl, leftRenderer, rightRenderer);
  rightController = new AnnotationController(rightEl, rightRenderer, leftRenderer);

  setupToolbar();
  setupLabelButtons();
  setupLayerToggles();
  setupImport();
  setupDragDrop();
  setupKeyboardShortcuts();
  startFpsCounter();

  toast('Drop an image or click Import to start', 'info');
});

// ── Media Loading ────────────────────────────────────────
async function loadImage(file) {
  const url = URL.createObjectURL(file);
  const img = new Image();

  await new Promise((resolve, reject) => {
    img.onload = resolve;
    img.onerror = reject;
    img.src = url;
  });

  const w = img.naturalWidth;
  const h = img.naturalHeight;
  setState('mediaWidth', w);
  setState('mediaHeight', h);
  setState('mediaUrl', url);
  state.annotations = [];
  state.selectedAnnotationId = null;

  await Promise.all([
    leftRenderer.setMedia(url, w, h),
    rightRenderer.setMedia(url, w, h),
  ]);

  mediaLoaded = true;
  document.getElementById('drop-left').classList.add('hidden');
  document.getElementById('drop-right').classList.add('hidden');

  toast(`Loaded ${file.name} (${w}x${h})`, 'success');
}

// ── Import / Drag-Drop ──────────────────────────────────
function setupImport() {
  const fileInput = document.getElementById('fileInput');
  document.getElementById('btnImport').addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) loadImage(e.target.files[0]);
  });
}

function setupDragDrop() {
  document.body.addEventListener('dragover', (e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; });
  document.body.addEventListener('drop', (e) => {
    e.preventDefault();
    const file = Array.from(e.dataTransfer.files).find(f => f.type.startsWith('image/'));
    if (file) loadImage(file);
  });
}

// ── Toolbar ──────────────────────────────────────────────
function setupToolbar() {
  document.querySelectorAll('.tool-btn[data-tool]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tool-btn[data-tool]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      setState('activeTool', btn.dataset.tool);
    });
  });
}

function setupLabelButtons() {
  document.querySelectorAll('.label-btn[data-label]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.label-btn[data-label]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      setState('activeLabel', btn.dataset.label);
    });
  });
}

// ── Layer Toggles ────────────────────────────────────────
function setupLayerToggles() {
  // Generate ML data
  document.getElementById('btnGenerateML').addEventListener('click', () => {
    if (!mediaLoaded) { toast('Load an image first', 'error'); return; }

    const t0 = performance.now();
    const data = generateAllDemoData(state.mediaWidth, state.mediaHeight);
    const genTime = (performance.now() - t0).toFixed(0);

    // Store in shared state
    state.mlLayers.heatmap.data = data.heatmap;
    state.mlLayers.detection.data = data.detection;
    state.mlLayers.mask.data = data.mask;
    state.mlLayers.tracking.data = data.tracking;

    // Push to both renderers
    leftRenderer.setHeatmapData(data.heatmap);
    rightRenderer.setHeatmapData(data.heatmap);
    leftRenderer.setDetectionData(data.detection);
    rightRenderer.setDetectionData(data.detection);
    leftRenderer.setMaskData(data.mask);
    rightRenderer.setMaskData(data.mask);
    leftRenderer.setTrackingData(data.tracking);
    rightRenderer.setTrackingData(data.tracking);

    // Enable all layers
    ['heatmap', 'detection', 'mask', 'tracking'].forEach(layer => {
      state.mlLayers[layer].visible = true;
      leftRenderer.setLayerVisibility(layer, true, state.mlLayers[layer].opacity);
      rightRenderer.setLayerVisibility(layer, true, state.mlLayers[layer].opacity);
    });

    // Update UI
    document.querySelectorAll('.layer-toggle').forEach(btn => btn.classList.add('active'));

    const detCount = data.detection.length;
    const maskCount = data.mask.length;
    toast(`Generated ${detCount} detections, ${maskCount} masks, 256x heatmap in ${genTime}ms`, 'success');
  });

  // Individual layer toggles
  document.querySelectorAll('.layer-toggle[data-layer]').forEach(btn => {
    btn.addEventListener('click', () => {
      const layer = btn.dataset.layer;
      const ml = state.mlLayers[layer];
      if (!ml.data) {
        toast('Generate ML data first', 'error');
        return;
      }

      ml.visible = !ml.visible;
      btn.classList.toggle('active', ml.visible);

      leftRenderer.setLayerVisibility(layer, ml.visible, ml.opacity);
      rightRenderer.setLayerVisibility(layer, ml.visible, ml.opacity);
    });
  });
}

// ── Keyboard Shortcuts ───────────────────────────────────
function setupKeyboardShortcuts() {
  const toolMap = { v: 'select', h: 'pan', b: 'bbox', p: 'polygon', f: 'freehand', l: 'polyline' };

  document.addEventListener('keydown', (e) => {
    const key = e.key.toLowerCase();

    if (toolMap[key] && !e.ctrlKey && !e.metaKey) {
      document.querySelectorAll('.tool-btn[data-tool]').forEach(b => b.classList.remove('active'));
      const btn = document.querySelector(`.tool-btn[data-tool="${toolMap[key]}"]`);
      if (btn) btn.classList.add('active');
      setState('activeTool', toolMap[key]);
      return;
    }

    if (key === 'escape') {
      leftController.cancelDrawing();
      rightController.cancelDrawing();
      state.selectedAnnotationId = null;
      leftRenderer.renderAnnotations(state.annotations, null);
      rightRenderer.renderAnnotations(state.annotations, null);
    }

    if ((e.ctrlKey || e.metaKey) && key === 'z' && !e.shiftKey) {
      e.preventDefault();
      undo();
    }
    if ((e.ctrlKey || e.metaKey) && key === 'z' && e.shiftKey) {
      e.preventDefault();
      redo();
    }

    if (key === 'delete' || key === 'backspace') {
      if (state.selectedAnnotationId) {
        const idx = state.annotations.findIndex(a => a.id === state.selectedAnnotationId);
        if (idx !== -1) {
          const removed = state.annotations.splice(idx, 1)[0];
          state.undoStack.push({ type: 'delete', annotation: removed, index: idx });
          state.redoStack = [];
          state.selectedAnnotationId = null;
          leftRenderer.renderAnnotations(state.annotations, null);
          rightRenderer.renderAnnotations(state.annotations, null);
        }
      }
    }
  });
}

function undo() {
  if (state.undoStack.length === 0) return;
  const action = state.undoStack.pop();
  state.redoStack.push(action);

  if (action.type === 'add') {
    const idx = state.annotations.findIndex(a => a.id === action.annotation.id);
    if (idx !== -1) state.annotations.splice(idx, 1);
  } else if (action.type === 'delete') {
    state.annotations.splice(action.index, 0, action.annotation);
  }

  leftRenderer.renderAnnotations(state.annotations, state.selectedAnnotationId);
  rightRenderer.renderAnnotations(state.annotations, state.selectedAnnotationId);
}

function redo() {
  if (state.redoStack.length === 0) return;
  const action = state.redoStack.pop();
  state.undoStack.push(action);

  if (action.type === 'add') {
    state.annotations.push(action.annotation);
  } else if (action.type === 'delete') {
    const idx = state.annotations.findIndex(a => a.id === action.annotation.id);
    if (idx !== -1) state.annotations.splice(idx, 1);
  }

  leftRenderer.renderAnnotations(state.annotations, state.selectedAnnotationId);
  rightRenderer.renderAnnotations(state.annotations, state.selectedAnnotationId);
}

// ── FPS Counter ──────────────────────────────────────────
function startFpsCounter() {
  const fpsLeft = document.getElementById('fps-left');
  const fpsRight = document.getElementById('fps-right');
  let frames = 0;
  let lastTime = performance.now();

  function tick() {
    frames++;
    const now = performance.now();
    if (now - lastTime >= 500) {
      const fps = Math.round(frames / ((now - lastTime) / 1000));
      fpsLeft.textContent = `${fps} FPS`;
      fpsRight.textContent = `${fps} FPS`;
      frames = 0;
      lastTime = now;
    }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}
