// ═══════════════════════════════════════════════════════════
// Viewport-Agnostic Annotation Controller
// Works with both PixiRenderer and HybridRenderer
// ═══════════════════════════════════════════════════════════

import { state, setState, emit, getLabelColor, generateId } from './compare-state.js';

export class AnnotationController {
  /**
   * @param {HTMLElement} containerEl - viewport DOM element for event binding
   * @param {object} renderer - must implement: screenToCanvas(x,y), renderAnnotations(anns, selectedId)
   * @param {object} otherRenderer - the other viewport's renderer (to sync annotations)
   */
  constructor(containerEl, renderer, otherRenderer = null) {
    this.container = containerEl;
    this.renderer = renderer;
    this.otherRenderer = otherRenderer;

    this._isDrawing = false;
    this._drawStart = null;
    this._currentPoints = [];
    this._currentBrushStrokes = [];
    this._currentBrushStroke = [];
    this._tempAnnotation = null;

    this._onMouseDown = this._onMouseDown.bind(this);
    this._onMouseMove = this._onMouseMove.bind(this);
    this._onMouseUp = this._onMouseUp.bind(this);
    this._onDblClick = this._onDblClick.bind(this);
    this._onContextMenu = this._onContextMenu.bind(this);

    containerEl.addEventListener('mousedown', this._onMouseDown);
    window.addEventListener('mousemove', this._onMouseMove);
    window.addEventListener('mouseup', this._onMouseUp);
    containerEl.addEventListener('dblclick', this._onDblClick);
    containerEl.addEventListener('contextmenu', this._onContextMenu);
  }

  _isAnnotationTool() {
    return ['bbox', 'polygon', 'point', 'brush', 'freehand', 'polyline'].includes(state.activeTool);
  }

  _renderAll() {
    this.renderer.renderAnnotations(state.annotations, state.selectedAnnotationId);
    if (this.otherRenderer) {
      this.otherRenderer.renderAnnotations(state.annotations, state.selectedAnnotationId);
    }
  }

  _renderWithTemp() {
    if (this._tempAnnotation) {
      const withTemp = [...state.annotations, this._tempAnnotation];
      this.renderer.renderAnnotations(withTemp, state.selectedAnnotationId);
    } else {
      this._renderAll();
    }
    // Other renderer just shows committed annotations
    if (this.otherRenderer) {
      this.otherRenderer.renderAnnotations(state.annotations, state.selectedAnnotationId);
    }
  }

  _onMouseDown(e) {
    if (e.button !== 0) return;
    if (state.activeTool === 'pan') return;
    if (!state.mediaWidth) return;

    const pos = this.renderer.screenToCanvas(e.clientX, e.clientY);
    if (pos.x < 0 || pos.y < 0 || pos.x > state.mediaWidth || pos.y > state.mediaHeight) return;

    if (state.activeTool === 'select') {
      this._handleSelect(pos);
      return;
    }

    if (!this._isAnnotationTool()) return;

    switch (state.activeTool) {
      case 'bbox':
        this._isDrawing = true;
        this._drawStart = pos;
        this._tempAnnotation = {
          id: '_temp', type: 'bbox',
          x: pos.x, y: pos.y, w: 0, h: 0,
          label: state.activeLabel, color: getLabelColor(state.activeLabel),
        };
        break;

      case 'polygon':
        if (!this._isDrawing) {
          this._isDrawing = true;
          this._currentPoints = [[pos.x, pos.y]];
        } else {
          this._currentPoints.push([pos.x, pos.y]);
        }
        this._tempAnnotation = {
          id: '_temp', type: 'polygon',
          points: [...this._currentPoints], closed: true,
          label: state.activeLabel, color: getLabelColor(state.activeLabel),
        };
        this._renderWithTemp();
        e.stopPropagation();
        break;

      case 'polyline':
        if (!this._isDrawing) {
          this._isDrawing = true;
          this._currentPoints = [[pos.x, pos.y]];
        } else {
          this._currentPoints.push([pos.x, pos.y]);
        }
        this._tempAnnotation = {
          id: '_temp', type: 'polyline',
          points: [...this._currentPoints],
          label: state.activeLabel, color: getLabelColor(state.activeLabel),
        };
        this._renderWithTemp();
        e.stopPropagation();
        break;

      case 'point':
        this._addAnnotation({
          type: 'point', x: pos.x, y: pos.y,
          label: state.activeLabel, color: getLabelColor(state.activeLabel),
        });
        break;

      case 'freehand':
        this._isDrawing = true;
        this._currentPoints = [[pos.x, pos.y]];
        this._tempAnnotation = {
          id: '_temp', type: 'freehand',
          points: this._currentPoints,
          label: state.activeLabel, color: getLabelColor(state.activeLabel),
        };
        break;

      case 'brush':
        this._isDrawing = true;
        this._currentBrushStroke = [[pos.x, pos.y]];
        if (!this._tempAnnotation) {
          this._tempAnnotation = {
            id: '_temp', type: 'brush',
            strokes: [this._currentBrushStroke],
            brushSize: state.brushSize,
            label: state.activeLabel, color: getLabelColor(state.activeLabel),
          };
          this._currentBrushStrokes = [this._currentBrushStroke];
        } else {
          this._currentBrushStrokes.push(this._currentBrushStroke);
          this._tempAnnotation.strokes = this._currentBrushStrokes;
        }
        break;
    }

    e.stopPropagation();
  }

  _onMouseMove(e) {
    if (!this._isDrawing || !state.mediaWidth) return;
    const pos = this.renderer.screenToCanvas(e.clientX, e.clientY);

    switch (state.activeTool) {
      case 'bbox':
        if (this._tempAnnotation && this._drawStart) {
          this._tempAnnotation.x = Math.min(this._drawStart.x, pos.x);
          this._tempAnnotation.y = Math.min(this._drawStart.y, pos.y);
          this._tempAnnotation.w = Math.abs(pos.x - this._drawStart.x);
          this._tempAnnotation.h = Math.abs(pos.y - this._drawStart.y);
          this._renderWithTemp();
        }
        break;

      case 'freehand':
        if (this._tempAnnotation) {
          this._currentPoints.push([pos.x, pos.y]);
          this._tempAnnotation.points = this._currentPoints;
          this._renderWithTemp();
        }
        break;

      case 'brush':
        if (this._tempAnnotation) {
          this._currentBrushStroke.push([pos.x, pos.y]);
          this._renderWithTemp();
        }
        break;
    }
  }

  _onMouseUp() {
    if (!this._isDrawing) return;

    switch (state.activeTool) {
      case 'bbox':
        if (this._tempAnnotation && this._tempAnnotation.w > 5 && this._tempAnnotation.h > 5) {
          const { id, ...data } = this._tempAnnotation;
          this._addAnnotation(data);
        }
        this._tempAnnotation = null;
        this._isDrawing = false;
        this._drawStart = null;
        this._renderAll();
        break;

      case 'freehand':
        if (this._tempAnnotation && this._currentPoints.length > 3) {
          const { id, ...data } = this._tempAnnotation;
          this._addAnnotation(data);
        }
        this._tempAnnotation = null;
        this._isDrawing = false;
        this._currentPoints = [];
        this._renderAll();
        break;

      case 'brush':
        this._isDrawing = false;
        break;
    }
  }

  _onDblClick(e) {
    if (state.activeTool === 'polygon' && this._isDrawing && this._currentPoints.length >= 3) {
      this._addAnnotation({
        type: 'polygon', points: [...this._currentPoints], closed: true,
        label: state.activeLabel, color: getLabelColor(state.activeLabel),
      });
      this._isDrawing = false;
      this._currentPoints = [];
      this._tempAnnotation = null;
      this._renderAll();
      e.preventDefault();
      e.stopPropagation();
      return;
    }

    if (state.activeTool === 'polyline' && this._isDrawing && this._currentPoints.length >= 2) {
      this._addAnnotation({
        type: 'polyline', points: [...this._currentPoints],
        label: state.activeLabel, color: getLabelColor(state.activeLabel),
      });
      this._isDrawing = false;
      this._currentPoints = [];
      this._tempAnnotation = null;
      this._renderAll();
      e.preventDefault();
      e.stopPropagation();
      return;
    }

    if (state.activeTool === 'brush' && this._tempAnnotation) {
      if (this._currentBrushStrokes.length > 0) {
        const { id, ...data } = this._tempAnnotation;
        this._addAnnotation(data);
      }
      this._tempAnnotation = null;
      this._currentBrushStrokes = [];
      this._currentBrushStroke = [];
      this._renderAll();
      e.preventDefault();
      return;
    }
  }

  _onContextMenu(e) {
    if (state.activeTool === 'polygon' && this._isDrawing && this._currentPoints.length >= 3) {
      e.preventDefault();
      this._addAnnotation({
        type: 'polygon', points: [...this._currentPoints], closed: true,
        label: state.activeLabel, color: getLabelColor(state.activeLabel),
      });
      this._isDrawing = false;
      this._currentPoints = [];
      this._tempAnnotation = null;
      this._renderAll();
    }
    if (state.activeTool === 'polyline' && this._isDrawing && this._currentPoints.length >= 2) {
      e.preventDefault();
      this._addAnnotation({
        type: 'polyline', points: [...this._currentPoints],
        label: state.activeLabel, color: getLabelColor(state.activeLabel),
      });
      this._isDrawing = false;
      this._currentPoints = [];
      this._tempAnnotation = null;
      this._renderAll();
    }
  }

  // ── Selection ──────────────────────────────────────────

  _handleSelect(pos) {
    for (let i = state.annotations.length - 1; i >= 0; i--) {
      const ann = state.annotations[i];
      if (hitTest(ann, pos.x, pos.y)) {
        state.selectedAnnotationId = ann.id;
        this._renderAll();
        return;
      }
    }
    state.selectedAnnotationId = null;
    this._renderAll();
  }

  // ── CRUD ───────────────────────────────────────────────

  _addAnnotation(data) {
    const ann = { id: generateId(), ...data, createdAt: Date.now() };
    state.undoStack.push({ type: 'add', annotation: ann });
    state.redoStack = [];
    state.annotations.push(ann);
    state.selectedAnnotationId = ann.id;
    this._renderAll();
    return ann;
  }

  cancelDrawing() {
    this._isDrawing = false;
    this._drawStart = null;
    this._currentPoints = [];
    this._currentBrushStrokes = [];
    this._currentBrushStroke = [];
    this._tempAnnotation = null;
    this._renderAll();
  }

  destroy() {
    this.container.removeEventListener('mousedown', this._onMouseDown);
    window.removeEventListener('mousemove', this._onMouseMove);
    window.removeEventListener('mouseup', this._onMouseUp);
    this.container.removeEventListener('dblclick', this._onDblClick);
    this.container.removeEventListener('contextmenu', this._onContextMenu);
  }
}

// ── Hit Testing ──────────────────────────────────────────

function hitTest(ann, px, py) {
  switch (ann.type) {
    case 'bbox':
      return px >= ann.x && px <= ann.x + ann.w && py >= ann.y && py <= ann.y + ann.h;
    case 'polygon':
      return pointInPolygon(px, py, ann.points);
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

function pointInPolygon(px, py, points) {
  if (!points) return false;
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
    const dx = x2 - x1, dy = y2 - y1;
    const lenSq = dx * dx + dy * dy;
    let t = lenSq === 0 ? 0 : Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / lenSq));
    const projX = x1 + t * dx, projY = y1 + t * dy;
    if (Math.sqrt((px - projX) ** 2 + (py - projY) ** 2) < threshold) return true;
  }
  return false;
}
