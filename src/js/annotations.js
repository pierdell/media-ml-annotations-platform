// ═══════════════════════════════════════════════════════════
// Annotation Tools & Drawing
// ═══════════════════════════════════════════════════════════

import { state, setState, emit, subscribe, getLabelColor } from './state.js';
import { generateId, toast } from './utils.js';
import { screenToCanvas, renderAnnotations } from './viewport.js';

let viewportEl;
let isDrawing = false;
let drawStart = null;
let currentPoints = [];
let currentBrushStrokes = [];
let currentBrushStroke = [];
let tempAnnotation = null;

export function initAnnotations() {
  viewportEl = document.getElementById('viewport');

  viewportEl.addEventListener('mousedown', onMouseDown);
  window.addEventListener('mousemove', onMouseMove);
  window.addEventListener('mouseup', onMouseUp);
  viewportEl.addEventListener('dblclick', onDoubleClick);
  viewportEl.addEventListener('contextmenu', onContextMenu);
}

function isAnnotationTool() {
  return ['bbox', 'polygon', 'point', 'brush', 'freehand', 'polyline'].includes(state.activeTool);
}

function onMouseDown(e) {
  if (e.button !== 0) return;
  if (state.activeTool === 'pan') return;
  if (!state.activeMediaId) return;

  const pos = screenToCanvas(e.clientX, e.clientY);
  if (pos.x < 0 || pos.y < 0 || pos.x > state.mediaWidth || pos.y > state.mediaHeight) return;

  if (state.activeTool === 'select') {
    handleSelect(pos);
    return;
  }

  if (!isAnnotationTool()) return;

  switch (state.activeTool) {
    case 'bbox':
      isDrawing = true;
      drawStart = pos;
      tempAnnotation = {
        id: '_temp',
        type: 'bbox',
        x: pos.x, y: pos.y, w: 0, h: 0,
        label: state.activeLabel,
        color: getLabelColor(state.activeLabel),
      };
      break;

    case 'polygon':
      if (!isDrawing) {
        isDrawing = true;
        currentPoints = [[pos.x, pos.y]];
      } else {
        currentPoints.push([pos.x, pos.y]);
      }
      updateTempPolygon();
      e.stopPropagation();
      break;

    case 'polyline':
      if (!isDrawing) {
        isDrawing = true;
        currentPoints = [[pos.x, pos.y]];
      } else {
        currentPoints.push([pos.x, pos.y]);
      }
      updateTempPolyline();
      e.stopPropagation();
      break;

    case 'point':
      addAnnotation({
        type: 'point',
        x: pos.x,
        y: pos.y,
        label: state.activeLabel,
        color: getLabelColor(state.activeLabel),
      });
      break;

    case 'freehand':
      isDrawing = true;
      currentPoints = [[pos.x, pos.y]];
      tempAnnotation = {
        id: '_temp',
        type: 'freehand',
        points: currentPoints,
        label: state.activeLabel,
        color: getLabelColor(state.activeLabel),
      };
      break;

    case 'brush':
      isDrawing = true;
      currentBrushStroke = [[pos.x, pos.y]];
      if (!tempAnnotation) {
        tempAnnotation = {
          id: '_temp',
          type: 'brush',
          strokes: [currentBrushStroke],
          brushSize: state.brushSize,
          label: state.activeLabel,
          color: getLabelColor(state.activeLabel),
        };
        currentBrushStrokes = [currentBrushStroke];
      } else {
        currentBrushStrokes.push(currentBrushStroke);
        tempAnnotation.strokes = currentBrushStrokes;
      }
      break;
  }

  e.stopPropagation();
}

function onMouseMove(e) {
  if (!isDrawing || !state.activeMediaId) return;

  const pos = screenToCanvas(e.clientX, e.clientY);

  switch (state.activeTool) {
    case 'bbox':
      if (tempAnnotation && drawStart) {
        tempAnnotation.x = Math.min(drawStart.x, pos.x);
        tempAnnotation.y = Math.min(drawStart.y, pos.y);
        tempAnnotation.w = Math.abs(pos.x - drawStart.x);
        tempAnnotation.h = Math.abs(pos.y - drawStart.y);
        renderWithTemp();
      }
      break;

    case 'freehand':
      if (tempAnnotation) {
        currentPoints.push([pos.x, pos.y]);
        tempAnnotation.points = currentPoints;
        renderWithTemp();
      }
      break;

    case 'brush':
      if (tempAnnotation) {
        currentBrushStroke.push([pos.x, pos.y]);
        renderWithTemp();
      }
      break;
  }
}

function onMouseUp(e) {
  if (!isDrawing) return;

  switch (state.activeTool) {
    case 'bbox':
      if (tempAnnotation && tempAnnotation.w > 5 && tempAnnotation.h > 5) {
        const { id, ...annData } = tempAnnotation;
        addAnnotation(annData);
      }
      tempAnnotation = null;
      isDrawing = false;
      drawStart = null;
      renderAnnotations();
      break;

    case 'freehand':
      if (tempAnnotation && currentPoints.length > 3) {
        const { id, ...annData } = tempAnnotation;
        addAnnotation(annData);
      }
      tempAnnotation = null;
      isDrawing = false;
      currentPoints = [];
      renderAnnotations();
      break;

    case 'brush':
      // Brush stays active - accumulates strokes until tool change or double-click
      isDrawing = false;
      break;

    // polygon and polyline continue on click, not mouseup
  }
}

function onDoubleClick(e) {
  const pos = screenToCanvas(e.clientX, e.clientY);

  if (state.activeTool === 'polygon' && isDrawing && currentPoints.length >= 3) {
    finishPolygon();
    e.preventDefault();
    e.stopPropagation();
    return;
  }

  if (state.activeTool === 'polyline' && isDrawing && currentPoints.length >= 2) {
    finishPolyline();
    e.preventDefault();
    e.stopPropagation();
    return;
  }

  if (state.activeTool === 'brush' && tempAnnotation) {
    finishBrush();
    e.preventDefault();
    return;
  }
}

function onContextMenu(e) {
  // Right-click finishes polygon/polyline
  if (state.activeTool === 'polygon' && isDrawing && currentPoints.length >= 3) {
    e.preventDefault();
    finishPolygon();
    return;
  }
  if (state.activeTool === 'polyline' && isDrawing && currentPoints.length >= 2) {
    e.preventDefault();
    finishPolyline();
    return;
  }
}

function updateTempPolygon() {
  tempAnnotation = {
    id: '_temp',
    type: 'polygon',
    points: [...currentPoints],
    closed: true,
    label: state.activeLabel,
    color: getLabelColor(state.activeLabel),
  };
  renderWithTemp();
}

function updateTempPolyline() {
  tempAnnotation = {
    id: '_temp',
    type: 'polyline',
    points: [...currentPoints],
    label: state.activeLabel,
    color: getLabelColor(state.activeLabel),
  };
  renderWithTemp();
}

function finishPolygon() {
  if (currentPoints.length >= 3) {
    addAnnotation({
      type: 'polygon',
      points: [...currentPoints],
      closed: true,
      label: state.activeLabel,
      color: getLabelColor(state.activeLabel),
    });
  }
  isDrawing = false;
  currentPoints = [];
  tempAnnotation = null;
  renderAnnotations();
}

function finishPolyline() {
  if (currentPoints.length >= 2) {
    addAnnotation({
      type: 'polyline',
      points: [...currentPoints],
      label: state.activeLabel,
      color: getLabelColor(state.activeLabel),
    });
  }
  isDrawing = false;
  currentPoints = [];
  tempAnnotation = null;
  renderAnnotations();
}

function finishBrush() {
  if (tempAnnotation && currentBrushStrokes.length > 0) {
    const { id, ...annData } = tempAnnotation;
    addAnnotation(annData);
  }
  tempAnnotation = null;
  currentBrushStrokes = [];
  currentBrushStroke = [];
  renderAnnotations();
}

function renderWithTemp() {
  renderAnnotations();
  if (tempAnnotation) {
    // Temporarily add to render
    const saved = state.annotations;
    state.annotations = [...saved, tempAnnotation];
    renderAnnotations();
    state.annotations = saved;
  }
}

function handleSelect(pos) {
  // Hit test annotations in reverse order (top first)
  for (let i = state.annotations.length - 1; i >= 0; i--) {
    const ann = state.annotations[i];
    if (hitTest(ann, pos.x, pos.y)) {
      setState('selectedAnnotationId', ann.id);
      emit('annotationSelected', ann);
      renderAnnotations();
      return;
    }
  }
  // Deselect
  setState('selectedAnnotationId', null);
  emit('annotationSelected', null);
  renderAnnotations();
}

function hitTest(ann, px, py) {
  switch (ann.type) {
    case 'bbox':
      return px >= ann.x && px <= ann.x + ann.w && py >= ann.y && py <= ann.y + ann.h;
    case 'polygon':
      return pointInPolygonTest(px, py, ann.points);
    case 'point':
      return (px - ann.x) ** 2 + (py - ann.y) ** 2 < 200;
    case 'freehand':
    case 'polyline':
      return nearPolyline(px, py, ann.points, 10);
    case 'brush':
      return ann.strokes?.some(s => nearPolyline(px, py, s, ann.brushSize / 2));
    default:
      return false;
  }
}

function pointInPolygonTest(px, py, points) {
  let inside = false;
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    const xi = points[i][0], yi = points[i][1];
    const xj = points[j][0], yj = points[j][1];
    if ((yi > py) !== (yj > py) && px < (xj - xi) * (py - yi) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

function nearPolyline(px, py, points, threshold) {
  if (!points) return false;
  for (let i = 0; i < points.length - 1; i++) {
    const [x1, y1] = points[i];
    const [x2, y2] = points[i + 1];
    const dist = distToSegment(px, py, x1, y1, x2, y2);
    if (dist < threshold) return true;
  }
  return false;
}

function distToSegment(px, py, x1, y1, x2, y2) {
  const dx = x2 - x1, dy = y2 - y1;
  const lenSq = dx * dx + dy * dy;
  if (lenSq === 0) return Math.sqrt((px - x1) ** 2 + (py - y1) ** 2);
  let t = ((px - x1) * dx + (py - y1) * dy) / lenSq;
  t = Math.max(0, Math.min(1, t));
  const projX = x1 + t * dx;
  const projY = y1 + t * dy;
  return Math.sqrt((px - projX) ** 2 + (py - projY) ** 2);
}

// ── CRUD ──────────────────────────────────────────────────
export function addAnnotation(annData) {
  const ann = {
    id: generateId(),
    ...annData,
    createdAt: Date.now(),
  };

  // Push undo
  state.undoStack.push({ type: 'add', annotation: ann });
  state.redoStack = [];

  state.annotations.push(ann);
  setState('selectedAnnotationId', ann.id);
  emit('annotationsChanged', state.annotations);
  emit('annotationSelected', ann);
  renderAnnotations();
  return ann;
}

export function deleteAnnotation(annId) {
  const idx = state.annotations.findIndex(a => a.id === annId);
  if (idx === -1) return;

  const removed = state.annotations.splice(idx, 1)[0];
  state.undoStack.push({ type: 'delete', annotation: removed, index: idx });
  state.redoStack = [];

  if (state.selectedAnnotationId === annId) {
    setState('selectedAnnotationId', null);
    emit('annotationSelected', null);
  }
  emit('annotationsChanged', state.annotations);
  renderAnnotations();
}

export function undo() {
  if (state.undoStack.length === 0) return;
  const action = state.undoStack.pop();
  state.redoStack.push(action);

  if (action.type === 'add') {
    const idx = state.annotations.findIndex(a => a.id === action.annotation.id);
    if (idx !== -1) state.annotations.splice(idx, 1);
  } else if (action.type === 'delete') {
    state.annotations.splice(action.index, 0, action.annotation);
  }

  emit('annotationsChanged', state.annotations);
  renderAnnotations();
}

export function redo() {
  if (state.redoStack.length === 0) return;
  const action = state.redoStack.pop();
  state.undoStack.push(action);

  if (action.type === 'add') {
    state.annotations.push(action.annotation);
  } else if (action.type === 'delete') {
    const idx = state.annotations.findIndex(a => a.id === action.annotation.id);
    if (idx !== -1) state.annotations.splice(idx, 1);
  }

  emit('annotationsChanged', state.annotations);
  renderAnnotations();
}

export function cancelCurrentDrawing() {
  isDrawing = false;
  drawStart = null;
  currentPoints = [];
  currentBrushStrokes = [];
  currentBrushStroke = [];
  tempAnnotation = null;
  renderAnnotations();
}
