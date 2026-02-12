// ═══════════════════════════════════════════════════════════
// Viewport: Canvas Management, Pan, Zoom, Rendering
// ═══════════════════════════════════════════════════════════

import { state, setState, emit, subscribe } from './state.js';
import { clamp } from './utils.js';
import { getActiveMedia } from './media.js';

let viewportEl, canvasWorkspace, canvasContainer;
let mediaCanvas, mediaCtx;
let heatmapCanvas, heatmapCtx;
let detectionCanvas, detectionCtx;
let maskCanvas, maskCtx;
let trackingCanvas, trackingCtx;
let annotationCanvas, annotationCtx;
let minimapCanvas, minimapCtx, minimapViewport;
let cursorInfo, cursorCoords, cursorPixel;

let loadedImage = null;
let videoSource = null;
let animFrameId = null;

// Pan state
let isPanning = false;
let panStartX = 0, panStartY = 0;
let panStartPanX = 0, panStartPanY = 0;

export function initViewport() {
  viewportEl = document.getElementById('viewport');
  canvasWorkspace = document.getElementById('canvasWorkspace');
  canvasContainer = document.getElementById('canvasContainer');

  mediaCanvas = document.getElementById('mediaCanvas');
  mediaCtx = mediaCanvas.getContext('2d');
  heatmapCanvas = document.getElementById('heatmapCanvas');
  heatmapCtx = heatmapCanvas.getContext('2d');
  detectionCanvas = document.getElementById('detectionCanvas');
  detectionCtx = detectionCanvas.getContext('2d');
  maskCanvas = document.getElementById('maskCanvas');
  maskCtx = maskCanvas.getContext('2d');
  trackingCanvas = document.getElementById('trackingCanvas');
  trackingCtx = trackingCanvas.getContext('2d');
  annotationCanvas = document.getElementById('annotationCanvas');
  annotationCtx = annotationCanvas.getContext('2d');

  minimapCanvas = document.getElementById('minimapCanvas');
  minimapCtx = minimapCanvas.getContext('2d');
  minimapViewport = document.getElementById('minimapViewport');

  cursorInfo = document.getElementById('cursorInfo');
  cursorCoords = document.getElementById('cursorCoords');
  cursorPixel = document.getElementById('cursorPixel');

  videoSource = document.getElementById('videoSource');

  // Events
  viewportEl.addEventListener('wheel', onWheel, { passive: false });
  viewportEl.addEventListener('mousedown', onMouseDown);
  window.addEventListener('mousemove', onMouseMove);
  window.addEventListener('mouseup', onMouseUp);
  viewportEl.addEventListener('mousemove', onViewportMouseMove);
  viewportEl.addEventListener('mouseleave', () => cursorInfo?.classList.add('hidden'));

  // Subscriptions
  subscribe('mediaChanged', onMediaChanged);
  subscribe('zoom', updateTransform);

  // Observe viewport resize
  const ro = new ResizeObserver(() => {
    state.viewportWidth = viewportEl.clientWidth;
    state.viewportHeight = viewportEl.clientHeight;
    updateMinimap();
  });
  ro.observe(viewportEl);
}

function onMediaChanged(media) {
  const dropZone = document.getElementById('dropZone');
  if (!media) {
    dropZone.classList.remove('hidden');
    canvasWorkspace.classList.add('hidden');
    document.getElementById('timeline').classList.add('hidden');
    cancelAnimationFrame(animFrameId);
    return;
  }

  dropZone.classList.add('hidden');
  canvasWorkspace.classList.remove('hidden');

  // Size all canvases
  const w = media.width;
  const h = media.height;
  [mediaCanvas, heatmapCanvas, detectionCanvas, maskCanvas, trackingCanvas, annotationCanvas].forEach(c => {
    c.width = w;
    c.height = h;
    c.style.width = w + 'px';
    c.style.height = h + 'px';
  });

  canvasContainer.style.width = w + 'px';
  canvasContainer.style.height = h + 'px';

  if (media.type === 'image') {
    document.getElementById('timeline').classList.add('hidden');
    loadedImage = new Image();
    loadedImage.onload = () => {
      mediaCtx.drawImage(loadedImage, 0, 0);
      fitToView();
      renderAllOverlays();
      updateMinimap();
    };
    loadedImage.src = media.url;
  } else {
    document.getElementById('timeline').classList.remove('hidden');
    videoSource.src = media.url;
    videoSource.load();
    videoSource.onloadeddata = () => {
      fitToView();
      drawVideoFrame();
      renderAllOverlays();
      updateMinimap();
    };
  }
}

export function fitToView() {
  if (!state.mediaWidth || !state.mediaHeight) return;
  const vw = viewportEl.clientWidth;
  const vh = viewportEl.clientHeight;
  const scaleX = (vw - 40) / state.mediaWidth;
  const scaleY = (vh - 40) / state.mediaHeight;
  const scale = Math.min(scaleX, scaleY, 3);
  setState('zoom', scale);
  setState('panX', (vw - state.mediaWidth * scale) / 2);
  setState('panY', (vh - state.mediaHeight * scale) / 2);
  updateTransform();
  emit('zoomChanged', scale);
}

function updateTransform() {
  if (!canvasContainer) return;
  canvasContainer.style.transform = `translate(${state.panX}px, ${state.panY}px) scale(${state.zoom})`;
  updateMinimap();
}

// ── Zoom ──────────────────────────────────────────────────
function onWheel(e) {
  e.preventDefault();
  const delta = e.deltaY > 0 ? 0.9 : 1.1;
  const newZoom = clamp(state.zoom * delta, 0.05, 20);

  // Zoom toward cursor
  const rect = viewportEl.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;

  const wx = (mx - state.panX) / state.zoom;
  const wy = (my - state.panY) / state.zoom;

  state.zoom = newZoom;
  state.panX = mx - wx * newZoom;
  state.panY = my - wy * newZoom;

  updateTransform();
  emit('zoomChanged', newZoom);
}

// ── Pan ───────────────────────────────────────────────────
function onMouseDown(e) {
  if (e.button === 1 || (e.button === 0 && (state.activeTool === 'pan' || e.spaceKey))) {
    isPanning = true;
    panStartX = e.clientX;
    panStartY = e.clientY;
    panStartPanX = state.panX;
    panStartPanY = state.panY;
    viewportEl.style.cursor = 'grabbing';
    e.preventDefault();
  }
}

function onMouseMove(e) {
  if (isPanning) {
    state.panX = panStartPanX + (e.clientX - panStartX);
    state.panY = panStartPanY + (e.clientY - panStartY);
    updateTransform();
  }
}

function onMouseUp(e) {
  if (isPanning) {
    isPanning = false;
    viewportEl.style.cursor = '';
  }
}

function onViewportMouseMove(e) {
  if (!state.activeMediaId) return;
  const rect = viewportEl.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;
  const wx = Math.floor((mx - state.panX) / state.zoom);
  const wy = Math.floor((my - state.panY) / state.zoom);

  if (wx >= 0 && wy >= 0 && wx < state.mediaWidth && wy < state.mediaHeight) {
    cursorInfo.classList.remove('hidden');
    cursorCoords.textContent = `${wx}, ${wy}`;
    // Sample pixel color from media canvas
    try {
      const pixel = mediaCtx.getImageData(wx, wy, 1, 1).data;
      cursorPixel.style.background = `rgb(${pixel[0]}, ${pixel[1]}, ${pixel[2]})`;
    } catch (_) {}
  } else {
    cursorInfo.classList.add('hidden');
  }
}

// ── Video Frame Rendering ─────────────────────────────────
export function drawVideoFrame() {
  if (!videoSource || videoSource.readyState < 2) return;
  mediaCtx.drawImage(videoSource, 0, 0, state.mediaWidth, state.mediaHeight);
  renderAllOverlays();
  updateMinimap();
}

export function startVideoLoop() {
  function loop() {
    if (!state.isPlaying) return;
    drawVideoFrame();
    state.currentTime = videoSource.currentTime;
    emit('timeUpdate', state.currentTime);
    animFrameId = requestAnimationFrame(loop);
  }
  animFrameId = requestAnimationFrame(loop);
}

export function stopVideoLoop() {
  cancelAnimationFrame(animFrameId);
}

export function getVideoElement() {
  return videoSource;
}

// ── Overlay Rendering ─────────────────────────────────────
export function renderAllOverlays() {
  renderHeatmap();
  renderDetections();
  renderMasks();
  renderTracking();
  renderAnnotations();
}

function renderHeatmap() {
  heatmapCtx.clearRect(0, 0, state.mediaWidth, state.mediaHeight);
  const layer = state.mlLayers.heatmap;
  if (!layer.visible || !layer.data) {
    heatmapCanvas.style.opacity = 0;
    return;
  }
  heatmapCanvas.style.opacity = layer.opacity;

  const { width, height, values } = layer.data;
  const cellW = state.mediaWidth / width;
  const cellH = state.mediaHeight / height;

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const val = values[y * width + x];
      if (val < 0.05) continue;
      const hue = (1 - val) * 240; // blue(0) -> red(1)
      heatmapCtx.fillStyle = `hsla(${hue}, 100%, 50%, ${val * 0.8})`;
      heatmapCtx.fillRect(x * cellW, y * cellH, cellW + 1, cellH + 1);
    }
  }
}

function renderDetections() {
  detectionCtx.clearRect(0, 0, state.mediaWidth, state.mediaHeight);
  const layer = state.mlLayers.detection;
  if (!layer.visible || !layer.data) {
    detectionCanvas.style.opacity = 0;
    return;
  }
  detectionCanvas.style.opacity = layer.opacity;

  for (const det of layer.data) {
    const color = det.color || '#00FF88';
    detectionCtx.strokeStyle = color;
    detectionCtx.lineWidth = 3;
    detectionCtx.strokeRect(det.x, det.y, det.w, det.h);

    // Label background
    const labelText = `${det.label} ${(det.confidence * 100).toFixed(0)}%`;
    detectionCtx.font = 'bold 14px -apple-system, sans-serif';
    const tw = detectionCtx.measureText(labelText).width;
    detectionCtx.fillStyle = color;
    detectionCtx.fillRect(det.x, det.y - 22, tw + 12, 22);
    detectionCtx.fillStyle = '#000';
    detectionCtx.fillText(labelText, det.x + 6, det.y - 6);

    // Confidence bar
    detectionCtx.fillStyle = color;
    detectionCtx.globalAlpha = 0.3;
    detectionCtx.fillRect(det.x, det.y + det.h, det.w * det.confidence, 4);
    detectionCtx.globalAlpha = 1;
  }
}

function renderMasks() {
  maskCtx.clearRect(0, 0, state.mediaWidth, state.mediaHeight);
  const layer = state.mlLayers.mask;
  if (!layer.visible || !layer.data) {
    maskCanvas.style.opacity = 0;
    return;
  }
  maskCanvas.style.opacity = layer.opacity;

  for (const seg of layer.data) {
    maskCtx.fillStyle = seg.color;
    maskCtx.beginPath();
    if (seg.points.length > 0) {
      maskCtx.moveTo(seg.points[0][0], seg.points[0][1]);
      for (let i = 1; i < seg.points.length; i++) {
        maskCtx.lineTo(seg.points[i][0], seg.points[i][1]);
      }
      maskCtx.closePath();
      maskCtx.fill();
    }

    // Outline
    maskCtx.strokeStyle = seg.borderColor || seg.color;
    maskCtx.lineWidth = 2;
    maskCtx.stroke();

    // Label
    if (seg.label) {
      const cx = seg.points.reduce((s, p) => s + p[0], 0) / seg.points.length;
      const cy = seg.points.reduce((s, p) => s + p[1], 0) / seg.points.length;
      maskCtx.font = 'bold 12px -apple-system, sans-serif';
      maskCtx.fillStyle = '#fff';
      maskCtx.textAlign = 'center';
      maskCtx.fillText(seg.label, cx, cy);
      maskCtx.textAlign = 'start';
    }
  }
}

function renderTracking() {
  trackingCtx.clearRect(0, 0, state.mediaWidth, state.mediaHeight);
  const layer = state.mlLayers.tracking;
  if (!layer.visible || !layer.data) {
    trackingCanvas.style.opacity = 0;
    return;
  }
  trackingCanvas.style.opacity = layer.opacity;

  for (const track of layer.data) {
    const { points, color, label } = track;
    if (points.length === 0) continue;

    // Draw trail
    trackingCtx.strokeStyle = color;
    trackingCtx.lineWidth = 2;
    trackingCtx.setLineDash([]);
    trackingCtx.beginPath();
    trackingCtx.moveTo(points[0][0], points[0][1]);
    for (let i = 1; i < points.length; i++) {
      trackingCtx.lineTo(points[i][0], points[i][1]);
    }
    trackingCtx.stroke();

    // Draw points with decreasing size
    for (let i = 0; i < points.length; i++) {
      const radius = 2 + (i / points.length) * 5;
      const alpha = 0.3 + (i / points.length) * 0.7;
      trackingCtx.beginPath();
      trackingCtx.arc(points[i][0], points[i][1], radius, 0, Math.PI * 2);
      trackingCtx.fillStyle = color.replace(')', `, ${alpha})`).replace('rgb', 'rgba');
      trackingCtx.fill();
    }

    // Current point (last)
    const last = points[points.length - 1];
    trackingCtx.beginPath();
    trackingCtx.arc(last[0], last[1], 8, 0, Math.PI * 2);
    trackingCtx.fillStyle = color;
    trackingCtx.fill();
    trackingCtx.strokeStyle = '#fff';
    trackingCtx.lineWidth = 2;
    trackingCtx.stroke();

    // Label
    if (label) {
      trackingCtx.font = 'bold 11px -apple-system, sans-serif';
      trackingCtx.fillStyle = '#fff';
      trackingCtx.fillText(label, last[0] + 12, last[1] + 4);
    }
  }
}

export function renderAnnotations() {
  annotationCtx.clearRect(0, 0, state.mediaWidth, state.mediaHeight);

  for (const ann of state.annotations) {
    const isSelected = ann.id === state.selectedAnnotationId;
    const color = ann.color || '#FF6B6B';

    switch (ann.type) {
      case 'bbox':
        drawBBox(annotationCtx, ann, color, isSelected);
        break;
      case 'polygon':
        drawPolygon(annotationCtx, ann, color, isSelected);
        break;
      case 'point':
        drawPoint(annotationCtx, ann, color, isSelected);
        break;
      case 'freehand':
        drawFreehand(annotationCtx, ann, color, isSelected);
        break;
      case 'polyline':
        drawPolyline(annotationCtx, ann, color, isSelected);
        break;
      case 'brush':
        drawBrushStrokes(annotationCtx, ann, color, isSelected);
        break;
    }
  }
}

function drawBBox(ctx, ann, color, selected) {
  ctx.strokeStyle = color;
  ctx.lineWidth = selected ? 3 : 2;
  if (selected) ctx.setLineDash([]);
  else ctx.setLineDash([]);
  ctx.strokeRect(ann.x, ann.y, ann.w, ann.h);

  // Fill
  ctx.fillStyle = color.replace(')', ', 0.1)').replace('rgb', 'rgba');
  if (!color.startsWith('rgba')) ctx.fillStyle = hexToRgba(color, 0.1);
  ctx.fillRect(ann.x, ann.y, ann.w, ann.h);

  // Label
  const labelText = ann.label || 'Unlabeled';
  ctx.font = 'bold 12px -apple-system, sans-serif';
  const tw = ctx.measureText(labelText).width;
  ctx.fillStyle = color;
  ctx.fillRect(ann.x, ann.y - 20, tw + 10, 20);
  ctx.fillStyle = '#000';
  ctx.fillText(labelText, ann.x + 5, ann.y - 5);

  // Handles if selected
  if (selected) {
    const handles = [
      [ann.x, ann.y], [ann.x + ann.w, ann.y],
      [ann.x, ann.y + ann.h], [ann.x + ann.w, ann.y + ann.h],
      [ann.x + ann.w / 2, ann.y], [ann.x + ann.w / 2, ann.y + ann.h],
      [ann.x, ann.y + ann.h / 2], [ann.x + ann.w, ann.y + ann.h / 2],
    ];
    for (const [hx, hy] of handles) {
      ctx.fillStyle = '#fff';
      ctx.fillRect(hx - 4, hy - 4, 8, 8);
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.strokeRect(hx - 4, hy - 4, 8, 8);
    }
  }
  ctx.setLineDash([]);
}

function drawPolygon(ctx, ann, color, selected) {
  if (!ann.points || ann.points.length < 2) return;
  ctx.beginPath();
  ctx.moveTo(ann.points[0][0], ann.points[0][1]);
  for (let i = 1; i < ann.points.length; i++) {
    ctx.lineTo(ann.points[i][0], ann.points[i][1]);
  }
  if (ann.closed !== false) ctx.closePath();

  ctx.fillStyle = hexToRgba(color, 0.15);
  ctx.fill();
  ctx.strokeStyle = color;
  ctx.lineWidth = selected ? 3 : 2;
  ctx.stroke();

  // Vertices
  for (const [px, py] of ann.points) {
    ctx.beginPath();
    ctx.arc(px, py, selected ? 5 : 3, 0, Math.PI * 2);
    ctx.fillStyle = selected ? '#fff' : color;
    ctx.fill();
    if (selected) {
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.stroke();
    }
  }

  // Label at centroid
  if (ann.label && ann.points.length >= 3) {
    const cx = ann.points.reduce((s, p) => s + p[0], 0) / ann.points.length;
    const cy = ann.points.reduce((s, p) => s + p[1], 0) / ann.points.length;
    ctx.font = 'bold 12px -apple-system, sans-serif';
    ctx.fillStyle = color;
    ctx.textAlign = 'center';
    ctx.fillText(ann.label, cx, cy);
    ctx.textAlign = 'start';
  }
}

function drawPoint(ctx, ann, color, selected) {
  ctx.beginPath();
  ctx.arc(ann.x, ann.y, selected ? 8 : 6, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
  ctx.strokeStyle = '#fff';
  ctx.lineWidth = 2;
  ctx.stroke();

  if (selected) {
    ctx.beginPath();
    ctx.arc(ann.x, ann.y, 14, 0, Math.PI * 2);
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  if (ann.label) {
    ctx.font = 'bold 11px -apple-system, sans-serif';
    ctx.fillStyle = '#fff';
    ctx.fillText(ann.label, ann.x + 12, ann.y + 4);
  }
}

function drawFreehand(ctx, ann, color, selected) {
  if (!ann.points || ann.points.length < 2) return;
  ctx.beginPath();
  ctx.moveTo(ann.points[0][0], ann.points[0][1]);
  for (let i = 1; i < ann.points.length; i++) {
    ctx.lineTo(ann.points[i][0], ann.points[i][1]);
  }
  ctx.strokeStyle = color;
  ctx.lineWidth = selected ? 4 : 2.5;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.stroke();
}

function drawPolyline(ctx, ann, color, selected) {
  if (!ann.points || ann.points.length < 2) return;
  ctx.beginPath();
  ctx.moveTo(ann.points[0][0], ann.points[0][1]);
  for (let i = 1; i < ann.points.length; i++) {
    ctx.lineTo(ann.points[i][0], ann.points[i][1]);
  }
  ctx.strokeStyle = color;
  ctx.lineWidth = selected ? 3 : 2;
  ctx.stroke();

  for (const [px, py] of ann.points) {
    ctx.beginPath();
    ctx.arc(px, py, selected ? 5 : 3, 0, Math.PI * 2);
    ctx.fillStyle = selected ? '#fff' : color;
    ctx.fill();
  }
}

function drawBrushStrokes(ctx, ann, color, selected) {
  if (!ann.strokes || ann.strokes.length === 0) return;
  for (const stroke of ann.strokes) {
    if (stroke.length < 2) continue;
    ctx.beginPath();
    ctx.moveTo(stroke[0][0], stroke[0][1]);
    for (let i = 1; i < stroke.length; i++) {
      ctx.lineTo(stroke[i][0], stroke[i][1]);
    }
    ctx.strokeStyle = hexToRgba(color, 0.6);
    ctx.lineWidth = ann.brushSize || 20;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.stroke();
  }
}

function hexToRgba(hex, alpha) {
  if (!hex || hex.startsWith('rgba')) return hex;
  if (!hex.startsWith('#')) return hex;
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

// ── Minimap ───────────────────────────────────────────────
function updateMinimap() {
  if (!state.mediaWidth || !state.mediaHeight) return;

  const mw = minimapCanvas.width;
  const mh = minimapCanvas.height;
  const scale = Math.min(mw / state.mediaWidth, mh / state.mediaHeight);

  minimapCtx.clearRect(0, 0, mw, mh);
  minimapCtx.fillStyle = '#0a0a0f';
  minimapCtx.fillRect(0, 0, mw, mh);

  // Draw media thumbnail
  minimapCtx.save();
  const drawW = state.mediaWidth * scale;
  const drawH = state.mediaHeight * scale;
  const drawX = (mw - drawW) / 2;
  const drawY = (mh - drawH) / 2;

  if (loadedImage && state.mediaType === 'image') {
    minimapCtx.drawImage(loadedImage, drawX, drawY, drawW, drawH);
  } else if (videoSource && state.mediaType === 'video' && videoSource.readyState >= 2) {
    minimapCtx.drawImage(videoSource, drawX, drawY, drawW, drawH);
  } else {
    minimapCtx.fillStyle = '#1a1a2e';
    minimapCtx.fillRect(drawX, drawY, drawW, drawH);
  }
  minimapCtx.restore();

  // Draw viewport rect
  const vw = viewportEl.clientWidth;
  const vh = viewportEl.clientHeight;
  const vpX = drawX + (-state.panX / state.zoom) * scale;
  const vpY = drawY + (-state.panY / state.zoom) * scale;
  const vpW = (vw / state.zoom) * scale;
  const vpH = (vh / state.zoom) * scale;

  minimapViewport.style.left = vpX + 'px';
  minimapViewport.style.top = vpY + 'px';
  minimapViewport.style.width = vpW + 'px';
  minimapViewport.style.height = vpH + 'px';
}

// ── Export for external use ───────────────────────────────
export function getCanvasContexts() {
  return {
    mediaCtx, heatmapCtx, detectionCtx, maskCtx, trackingCtx, annotationCtx,
  };
}

export function screenToCanvas(clientX, clientY) {
  const rect = viewportEl.getBoundingClientRect();
  const mx = clientX - rect.left;
  const my = clientY - rect.top;
  return {
    x: (mx - state.panX) / state.zoom,
    y: (my - state.panY) / state.zoom,
  };
}
