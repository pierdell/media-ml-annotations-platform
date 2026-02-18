// ═══════════════════════════════════════════════════════════
// Full PixiJS Renderer (Option 2)
// Everything rendered via WebGL through PixiJS
// ═══════════════════════════════════════════════════════════

import { clamp, hexToRgba } from './compare-state.js';

export class PixiRenderer {
  constructor(containerEl, vpState) {
    this.container = containerEl;
    this.vpState = vpState;
    this.app = null;
    this.worldContainer = null;
    this.mediaSprite = null;
    this.heatmapSprite = null;
    this.detectionContainer = null;
    this.maskGraphics = null;
    this.trackingGraphics = null;
    this.annotationContainer = null;
    this.mediaWidth = 0;
    this.mediaHeight = 0;
    this._textPool = [];
    this._isPanning = false;
    this._panStart = { x: 0, y: 0, panX: 0, panY: 0 };
    this._layerVisibility = {
      heatmap: { visible: false, opacity: 0.6 },
      detection: { visible: false, opacity: 0.8 },
      mask: { visible: false, opacity: 0.5 },
      tracking: { visible: false, opacity: 0.9 },
    };
  }

  async init() {
    this.app = new PIXI.Application();
    await this.app.init({
      background: '#0a0a0f',
      resizeTo: this.container,
      antialias: true,
      resolution: window.devicePixelRatio || 1,
      autoDensity: true,
    });
    this.container.appendChild(this.app.canvas);
    this.app.canvas.style.display = 'block';

    this.worldContainer = new PIXI.Container();
    this.app.stage.addChild(this.worldContainer);

    // Layer order: media → heatmap → masks → detections → tracking → annotations
    this.mediaSprite = new PIXI.Sprite();
    this.worldContainer.addChild(this.mediaSprite);

    this.heatmapSprite = new PIXI.Sprite();
    this.heatmapSprite.visible = false;
    this.worldContainer.addChild(this.heatmapSprite);

    this.maskGraphics = new PIXI.Graphics();
    this.maskGraphics.visible = false;
    this.worldContainer.addChild(this.maskGraphics);

    this.detectionContainer = new PIXI.Container();
    this.detectionContainer.visible = false;
    this.worldContainer.addChild(this.detectionContainer);

    this.trackingGraphics = new PIXI.Graphics();
    this.trackingGraphics.visible = false;
    this.worldContainer.addChild(this.trackingGraphics);

    this.annotationContainer = new PIXI.Container();
    this.worldContainer.addChild(this.annotationContainer);

    // Events
    this.container.addEventListener('wheel', (e) => this._onWheel(e), { passive: false });
    this.container.addEventListener('mousedown', (e) => this._onMouseDown(e));
    this._onMouseMoveBound = (e) => this._onMouseMove(e);
    this._onMouseUpBound = (e) => this._onMouseUp(e);
    window.addEventListener('mousemove', this._onMouseMoveBound);
    window.addEventListener('mouseup', this._onMouseUpBound);
  }

  async setMedia(imageUrl, w, h) {
    this.mediaWidth = w;
    this.mediaHeight = h;
    const texture = await PIXI.Assets.load(imageUrl);
    this.mediaSprite.texture = texture;
    this.mediaSprite.width = w;
    this.mediaSprite.height = h;
    this.fitToView();
  }

  fitToView() {
    const vw = this.container.clientWidth;
    const vh = this.container.clientHeight;
    const scaleX = (vw - 40) / this.mediaWidth;
    const scaleY = (vh - 40) / this.mediaHeight;
    const scale = Math.min(scaleX, scaleY, 3);
    this.vpState.zoom = scale;
    this.vpState.panX = (vw - this.mediaWidth * scale) / 2;
    this.vpState.panY = (vh - this.mediaHeight * scale) / 2;
    this._applyTransform();
  }

  _applyTransform() {
    this.worldContainer.scale.set(this.vpState.zoom);
    this.worldContainer.position.set(this.vpState.panX, this.vpState.panY);
  }

  // ── Zoom / Pan ─────────────────────────────────────────

  _onWheel(e) {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    const newZoom = clamp(this.vpState.zoom * delta, 0.05, 20);

    const rect = this.container.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    const wx = (mx - this.vpState.panX) / this.vpState.zoom;
    const wy = (my - this.vpState.panY) / this.vpState.zoom;

    this.vpState.zoom = newZoom;
    this.vpState.panX = mx - wx * newZoom;
    this.vpState.panY = my - wy * newZoom;
    this._applyTransform();
  }

  _onMouseDown(e) {
    if (e.button === 1) {
      this._isPanning = true;
      this._panStart = { x: e.clientX, y: e.clientY, panX: this.vpState.panX, panY: this.vpState.panY };
      e.preventDefault();
    }
  }

  _onMouseMove(e) {
    if (this._isPanning) {
      this.vpState.panX = this._panStart.panX + (e.clientX - this._panStart.x);
      this.vpState.panY = this._panStart.panY + (e.clientY - this._panStart.y);
      this._applyTransform();
    }
  }

  _onMouseUp() {
    this._isPanning = false;
  }

  // ── Coordinate Transform ───────────────────────────────

  screenToCanvas(clientX, clientY) {
    const rect = this.container.getBoundingClientRect();
    const mx = clientX - rect.left;
    const my = clientY - rect.top;
    return {
      x: (mx - this.vpState.panX) / this.vpState.zoom,
      y: (my - this.vpState.panY) / this.vpState.zoom,
    };
  }

  getContainerRect() {
    return this.container.getBoundingClientRect();
  }

  // ── Heatmap ────────────────────────────────────────────

  setHeatmapData(data) {
    if (!data) { this.heatmapSprite.visible = false; return; }

    const { width, height, values } = data;
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    const imgData = ctx.createImageData(width, height);

    for (let i = 0; i < values.length; i++) {
      const val = values[i];
      if (val < 0.05) { imgData.data[i * 4 + 3] = 0; continue; }
      const hue = (1 - val) * 240;
      const [r, g, b] = hslToRgb(hue / 360, 1, 0.5);
      imgData.data[i * 4]     = r;
      imgData.data[i * 4 + 1] = g;
      imgData.data[i * 4 + 2] = b;
      imgData.data[i * 4 + 3] = Math.floor(val * 204); // 0.8 * 255
    }
    ctx.putImageData(imgData, 0, 0);

    if (this.heatmapSprite.texture && this.heatmapSprite.texture !== PIXI.Texture.EMPTY) {
      this.heatmapSprite.texture.destroy(true);
    }
    this.heatmapSprite.texture = PIXI.Texture.from(canvas);
    this.heatmapSprite.width = this.mediaWidth;
    this.heatmapSprite.height = this.mediaHeight;
  }

  // ── Detections ─────────────────────────────────────────

  setDetectionData(detections) {
    this.detectionContainer.removeChildren();
    this._textPool = [];
    if (!detections) return;

    const g = new PIXI.Graphics();
    this.detectionContainer.addChild(g);

    for (const det of detections) {
      const color = det.color || '#00FF88';
      const colorNum = colorToNumber(color);

      // Box stroke
      g.rect(det.x, det.y, det.w, det.h);
      g.stroke({ width: 3, color: colorNum });

      // Label background
      const labelText = `${det.label} ${(det.confidence * 100).toFixed(0)}%`;
      const tw = labelText.length * 8;
      g.rect(det.x, det.y - 20, tw + 12, 20);
      g.fill(colorNum);

      // Confidence bar
      g.rect(det.x, det.y + det.h, det.w * det.confidence, 4);
      g.fill({ color: colorNum, alpha: 0.3 });

      // Label text
      const text = new PIXI.Text({
        text: labelText,
        style: { fontFamily: '-apple-system, sans-serif', fontSize: 12, fontWeight: 'bold', fill: '#000000' },
      });
      text.position.set(det.x + 6, det.y - 19);
      this.detectionContainer.addChild(text);
    }
  }

  // ── Masks ──────────────────────────────────────────────

  setMaskData(masks) {
    this.maskGraphics.clear();
    if (!masks) return;

    for (const seg of masks) {
      if (!seg.points || seg.points.length < 3) continue;
      const flat = seg.points.flat();
      const fillColor = parseRgbaColor(seg.color);
      const borderColor = colorToNumber(seg.borderColor || '#ffffff');

      this.maskGraphics.poly(flat);
      this.maskGraphics.fill({ color: fillColor.color, alpha: fillColor.alpha });
      this.maskGraphics.stroke({ width: 2, color: borderColor });
    }
  }

  // ── Tracking ───────────────────────────────────────────

  setTrackingData(tracks) {
    this.trackingGraphics.clear();
    if (!tracks) return;

    for (const track of tracks) {
      const { points, color } = track;
      if (!points || points.length === 0) continue;
      const colorNum = parseRgbColor(color);

      // Trail line
      this.trackingGraphics.moveTo(points[0][0], points[0][1]);
      for (let i = 1; i < points.length; i++) {
        this.trackingGraphics.lineTo(points[i][0], points[i][1]);
      }
      this.trackingGraphics.stroke({ width: 2, color: colorNum });

      // Points with increasing size
      for (let i = 0; i < points.length; i++) {
        const radius = 2 + (i / points.length) * 5;
        const alpha = 0.3 + (i / points.length) * 0.7;
        this.trackingGraphics.circle(points[i][0], points[i][1], radius);
        this.trackingGraphics.fill({ color: colorNum, alpha });
      }

      // Current point (last)
      const last = points[points.length - 1];
      this.trackingGraphics.circle(last[0], last[1], 8);
      this.trackingGraphics.fill(colorNum);
      this.trackingGraphics.circle(last[0], last[1], 8);
      this.trackingGraphics.stroke({ width: 2, color: 0xffffff });
    }
  }

  // ── Annotations ────────────────────────────────────────

  renderAnnotations(annotations, selectedId) {
    this.annotationContainer.removeChildren();
    if (!annotations) return;

    const g = new PIXI.Graphics();
    this.annotationContainer.addChild(g);

    for (const ann of annotations) {
      const isSelected = ann.id === selectedId;
      const color = ann.color || '#FF6B6B';
      const colorNum = colorToNumber(color);

      switch (ann.type) {
        case 'bbox': this._drawBBox(g, ann, colorNum, color, isSelected); break;
        case 'polygon': this._drawPolygon(g, ann, colorNum, color, isSelected); break;
        case 'point': this._drawPoint(g, ann, colorNum, isSelected); break;
        case 'freehand': this._drawFreehand(g, ann, colorNum, isSelected); break;
        case 'polyline': this._drawPolyline(g, ann, colorNum, isSelected); break;
        case 'brush': this._drawBrush(g, ann, colorNum, isSelected); break;
      }
    }
  }

  _drawBBox(g, ann, colorNum, colorHex, selected) {
    g.rect(ann.x, ann.y, ann.w, ann.h);
    g.fill({ color: colorNum, alpha: 0.1 });
    g.stroke({ width: selected ? 3 : 2, color: colorNum });

    // Label
    const labelText = ann.label || 'Unlabeled';
    const tw = labelText.length * 7;
    g.rect(ann.x, ann.y - 20, tw + 10, 20);
    g.fill(colorNum);

    const text = new PIXI.Text({
      text: labelText,
      style: { fontFamily: '-apple-system, sans-serif', fontSize: 12, fontWeight: 'bold', fill: '#000000' },
    });
    text.position.set(ann.x + 5, ann.y - 19);
    this.annotationContainer.addChild(text);

    if (selected) {
      const handles = [
        [ann.x, ann.y], [ann.x + ann.w, ann.y],
        [ann.x, ann.y + ann.h], [ann.x + ann.w, ann.y + ann.h],
        [ann.x + ann.w / 2, ann.y], [ann.x + ann.w / 2, ann.y + ann.h],
        [ann.x, ann.y + ann.h / 2], [ann.x + ann.w, ann.y + ann.h / 2],
      ];
      for (const [hx, hy] of handles) {
        g.rect(hx - 4, hy - 4, 8, 8);
        g.fill(0xffffff);
        g.stroke({ width: 1.5, color: colorNum });
      }
    }
  }

  _drawPolygon(g, ann, colorNum, colorHex, selected) {
    if (!ann.points || ann.points.length < 2) return;
    const flat = ann.points.flat();
    g.poly(flat);
    g.fill({ color: colorNum, alpha: 0.15 });
    g.stroke({ width: selected ? 3 : 2, color: colorNum });

    for (const [px, py] of ann.points) {
      g.circle(px, py, selected ? 5 : 3);
      g.fill(selected ? 0xffffff : colorNum);
      if (selected) g.stroke({ width: 2, color: colorNum });
    }
  }

  _drawPoint(g, ann, colorNum, selected) {
    g.circle(ann.x, ann.y, selected ? 8 : 6);
    g.fill(colorNum);
    g.stroke({ width: 2, color: 0xffffff });

    if (selected) {
      g.circle(ann.x, ann.y, 14);
      g.stroke({ width: 1.5, color: colorNum });
    }
  }

  _drawFreehand(g, ann, colorNum, selected) {
    if (!ann.points || ann.points.length < 2) return;
    g.moveTo(ann.points[0][0], ann.points[0][1]);
    for (let i = 1; i < ann.points.length; i++) {
      g.lineTo(ann.points[i][0], ann.points[i][1]);
    }
    g.stroke({ width: selected ? 4 : 2.5, color: colorNum, cap: 'round', join: 'round' });
  }

  _drawPolyline(g, ann, colorNum, selected) {
    if (!ann.points || ann.points.length < 2) return;
    g.moveTo(ann.points[0][0], ann.points[0][1]);
    for (let i = 1; i < ann.points.length; i++) {
      g.lineTo(ann.points[i][0], ann.points[i][1]);
    }
    g.stroke({ width: selected ? 3 : 2, color: colorNum });

    for (const [px, py] of ann.points) {
      g.circle(px, py, selected ? 5 : 3);
      g.fill(selected ? 0xffffff : colorNum);
    }
  }

  _drawBrush(g, ann, colorNum, selected) {
    if (!ann.strokes || ann.strokes.length === 0) return;
    for (const stroke of ann.strokes) {
      if (stroke.length < 2) continue;
      g.moveTo(stroke[0][0], stroke[0][1]);
      for (let i = 1; i < stroke.length; i++) {
        g.lineTo(stroke[i][0], stroke[i][1]);
      }
      g.stroke({ width: ann.brushSize || 20, color: colorNum, alpha: 0.6, cap: 'round', join: 'round' });
    }
  }

  // ── Layer Visibility ───────────────────────────────────

  setLayerVisibility(layer, visible, opacity) {
    this._layerVisibility[layer] = { visible, opacity };
    switch (layer) {
      case 'heatmap':
        this.heatmapSprite.visible = visible;
        this.heatmapSprite.alpha = opacity;
        break;
      case 'detection':
        this.detectionContainer.visible = visible;
        this.detectionContainer.alpha = opacity;
        break;
      case 'mask':
        this.maskGraphics.visible = visible;
        this.maskGraphics.alpha = opacity;
        break;
      case 'tracking':
        this.trackingGraphics.visible = visible;
        this.trackingGraphics.alpha = opacity;
        break;
    }
  }

  destroy() {
    window.removeEventListener('mousemove', this._onMouseMoveBound);
    window.removeEventListener('mouseup', this._onMouseUpBound);
    this.app?.destroy(true);
  }
}

// ── Color Helpers ────────────────────────────────────────

function colorToNumber(hex) {
  if (!hex || !hex.startsWith('#')) return 0xffffff;
  return parseInt(hex.slice(1), 16);
}

function parseRgbaColor(rgba) {
  const m = rgba.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+))?\)/);
  if (!m) return { color: 0xffffff, alpha: 1 };
  const color = (parseInt(m[1]) << 16) | (parseInt(m[2]) << 8) | parseInt(m[3]);
  return { color, alpha: m[4] !== undefined ? parseFloat(m[4]) : 1 };
}

function parseRgbColor(rgb) {
  const m = rgb.match(/rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)/);
  if (!m) return 0xffffff;
  return (parseInt(m[1]) << 16) | (parseInt(m[2]) << 8) | parseInt(m[3]);
}

function hslToRgb(h, s, l) {
  let r, g, b;
  if (s === 0) { r = g = b = l; }
  else {
    const hue2rgb = (p, q, t) => {
      if (t < 0) t += 1; if (t > 1) t -= 1;
      if (t < 1/6) return p + (q - p) * 6 * t;
      if (t < 1/2) return q;
      if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
      return p;
    };
    const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
    const p = 2 * l - q;
    r = hue2rgb(p, q, h + 1/3);
    g = hue2rgb(p, q, h);
    b = hue2rgb(p, q, h - 1/3);
  }
  return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)];
}
