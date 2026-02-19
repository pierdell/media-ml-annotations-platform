// ═══════════════════════════════════════════════════════════
// ML Annotations Platform - Main Application Entry
// ═══════════════════════════════════════════════════════════

import { state, setState, emit, subscribe, getLabelColor } from './state.js';
import { toast, fileSize, generateId } from './utils.js';
import { loadMediaFiles, selectMedia, getActiveMedia, removeMedia } from './media.js';
import { initViewport, fitToView, renderAllOverlays, renderAnnotations } from './viewport.js';
import { initAnnotations, deleteAnnotation, undo, redo, cancelCurrentDrawing } from './annotations.js';
import { initTimeline, togglePlay } from './timeline.js';
import { generateHeatmapData, generateDetectionData, generateMaskData, generateTrackingData, generateAllMlData } from './demo.js';

// ═══════════════════════════════════════════════════════════
// Initialize
// ═══════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  initViewport();
  initAnnotations();
  initTimeline();

  setupFileImport();
  setupDragDrop();
  setupToolbar();
  setupViewTabs();
  setupRightPanel();
  setupLayerControls();
  setupZoomControls();
  setupKeyboardShortcuts();
  setupExport();

  // Subscribe to state changes
  subscribe('mediaList', updateMediaQueue);
  subscribe('mediaChanged', updateMediaInfo);
  subscribe('annotationsChanged', updateAnnotationsList);
  subscribe('annotationSelected', updatePropertiesPanel);
  subscribe('zoomChanged', updateZoomDisplay);

  toast('Welcome! Drop images or videos to get started.', 'info');
});

// ═══════════════════════════════════════════════════════════
// File Import
// ═══════════════════════════════════════════════════════════
function setupFileImport() {
  const fileInput = document.getElementById('fileInput');
  const btnImport = document.getElementById('btnImport');
  const btnDropZoneImport = document.getElementById('btnDropZoneImport');
  const btnAddMoreMedia = document.getElementById('btnAddMoreMedia');

  const triggerImport = () => fileInput.click();
  btnImport.addEventListener('click', triggerImport);
  btnDropZoneImport.addEventListener('click', triggerImport);
  btnAddMoreMedia?.addEventListener('click', triggerImport);

  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      loadMediaFiles(e.target.files);
      e.target.value = '';
    }
  });
}

// ═══════════════════════════════════════════════════════════
// Drag & Drop
// ═══════════════════════════════════════════════════════════
function setupDragDrop() {
  const dropZone = document.getElementById('dropZone');
  const viewport = document.getElementById('viewport');

  const preventDefaults = (e) => { e.preventDefault(); e.stopPropagation(); };

  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evt => {
    viewport.addEventListener(evt, preventDefaults);
    document.body.addEventListener(evt, preventDefaults);
  });

  viewport.addEventListener('dragenter', () => dropZone?.classList.add('drag-over'));
  viewport.addEventListener('dragover', () => dropZone?.classList.add('drag-over'));
  viewport.addEventListener('dragleave', (e) => {
    if (!viewport.contains(e.relatedTarget)) {
      dropZone?.classList.remove('drag-over');
    }
  });
  viewport.addEventListener('drop', (e) => {
    dropZone?.classList.remove('drag-over');
    if (e.dataTransfer?.files.length > 0) {
      loadMediaFiles(e.dataTransfer.files);
    }
  });

  // Also handle drops on the body if the drop zone is hidden
  document.body.addEventListener('drop', (e) => {
    if (e.dataTransfer?.files.length > 0) {
      loadMediaFiles(e.dataTransfer.files);
    }
  });
}

// ═══════════════════════════════════════════════════════════
// Toolbar
// ═══════════════════════════════════════════════════════════
function setupToolbar() {
  // Tool buttons
  document.querySelectorAll('.tool-btn[data-tool]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tool-btn[data-tool]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      setState('activeTool', btn.dataset.tool);
      cancelCurrentDrawing();

      // Update cursor
      const viewport = document.getElementById('viewport');
      if (btn.dataset.tool === 'pan') {
        viewport.style.cursor = 'grab';
      } else if (['bbox', 'polygon', 'point', 'freehand', 'polyline', 'brush'].includes(btn.dataset.tool)) {
        viewport.style.cursor = 'crosshair';
      } else {
        viewport.style.cursor = 'default';
      }
    });
  });

  // Label buttons
  document.querySelectorAll('.label-btn[data-label]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.label-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      setState('activeLabel', btn.dataset.label);
    });
  });

  // Add label button
  document.getElementById('btnAddLabel')?.addEventListener('click', showAddLabelModal);

  // Undo/Redo
  document.getElementById('btnUndo')?.addEventListener('click', undo);
  document.getElementById('btnRedo')?.addEventListener('click', redo);
}

// ═══════════════════════════════════════════════════════════
// View Tabs
// ═══════════════════════════════════════════════════════════
function setupViewTabs() {
  document.querySelectorAll('.tab-btn[data-view]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn[data-view]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      setState('viewMode', btn.dataset.view);

      // Handle compare slider visibility
      const slider = document.getElementById('compareSlider');
      if (btn.dataset.view === 'compare') {
        slider?.classList.remove('hidden');
        setupCompareSlider();
      } else {
        slider?.classList.add('hidden');
      }

      // Auto-enable ML layers in visualize mode
      if (btn.dataset.view === 'visualize' && state.activeMediaId) {
        enableAllMlLayers();
      }
    });
  });
}

function enableAllMlLayers() {
  const mlData = generateAllMlData();
  Object.keys(state.mlLayers).forEach(key => {
    state.mlLayers[key].visible = true;
    state.mlLayers[key].data = mlData[key];
  });
  updateLayerVisibilityUI();
  renderAllOverlays();
  toast('ML visualization layers enabled', 'success');
}

function setupCompareSlider() {
  const slider = document.getElementById('compareSlider');
  if (!slider) return;

  let isDragging = false;
  slider.addEventListener('mousedown', () => { isDragging = true; });
  window.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    const viewport = document.getElementById('viewport');
    const rect = viewport.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    state.comparePosition = Math.max(0.05, Math.min(0.95, pct));
    slider.style.left = (state.comparePosition * 100) + '%';

    // Apply clip to overlay canvases
    const clipRight = state.comparePosition * 100;
    document.querySelectorAll('.overlay-canvas').forEach(c => {
      c.style.clipPath = `inset(0 ${100 - clipRight}% 0 0)`;
    });
  });
  window.addEventListener('mouseup', () => { isDragging = false; });
}

// ═══════════════════════════════════════════════════════════
// Right Panel
// ═══════════════════════════════════════════════════════════
function setupRightPanel() {
  document.querySelectorAll('.panel-tab[data-panel]').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.panel-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.panel-content').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(tab.dataset.panel + 'Panel')?.classList.add('active');
    });
  });

  // Confidence slider display
  const conf = document.getElementById('propConfidence');
  const confVal = document.getElementById('propConfidenceVal');
  conf?.addEventListener('input', () => {
    confVal.textContent = conf.value + '%';
  });
}

// ═══════════════════════════════════════════════════════════
// Layer Controls
// ═══════════════════════════════════════════════════════════
function setupLayerControls() {
  // Toggle visibility
  document.querySelectorAll('.layer-visibility').forEach(btn => {
    btn.addEventListener('click', () => {
      const layerItem = btn.closest('.layer-item');
      const layerKey = layerItem.dataset.layer;
      const layer = state.mlLayers[layerKey];
      if (!layer) return;

      // Generate data if needed
      if (!layer.data) {
        switch (layerKey) {
          case 'heatmap': layer.data = generateHeatmapData(); break;
          case 'detection': layer.data = generateDetectionData(); break;
          case 'mask': layer.data = generateMaskData(); break;
          case 'tracking': layer.data = generateTrackingData(); break;
        }
      }

      layer.visible = !layer.visible;
      btn.dataset.visible = layer.visible.toString();
      renderAllOverlays();
    });
  });

  // Opacity sliders
  document.querySelectorAll('.layer-opacity').forEach(slider => {
    slider.addEventListener('input', () => {
      const layerItem = slider.closest('.layer-item');
      const layerKey = layerItem.dataset.layer;
      if (state.mlLayers[layerKey]) {
        state.mlLayers[layerKey].opacity = slider.value / 100;
        renderAllOverlays();
      }
    });
  });

  // Generate demo ML data button
  document.getElementById('btnAddMlLayer')?.addEventListener('click', () => {
    if (!state.activeMediaId) {
      toast('Load media first', 'error');
      return;
    }
    // Regenerate all ML data
    const mlData = generateAllMlData();
    Object.keys(state.mlLayers).forEach(key => {
      state.mlLayers[key].data = mlData[key];
      state.mlLayers[key].visible = true;
    });
    updateLayerVisibilityUI();
    renderAllOverlays();
    toast('Generated new ML demo data', 'success');
  });
}

function updateLayerVisibilityUI() {
  document.querySelectorAll('.layer-item').forEach(item => {
    const key = item.dataset.layer;
    const btn = item.querySelector('.layer-visibility');
    if (btn && state.mlLayers[key]) {
      btn.dataset.visible = state.mlLayers[key].visible.toString();
    }
  });
}

// ═══════════════════════════════════════════════════════════
// Zoom Controls
// ═══════════════════════════════════════════════════════════
function setupZoomControls() {
  document.getElementById('btnZoomIn')?.addEventListener('click', () => {
    setState('zoom', Math.min(state.zoom * 1.25, 20));
    emit('zoomChanged', state.zoom);
  });
  document.getElementById('btnZoomOut')?.addEventListener('click', () => {
    setState('zoom', Math.max(state.zoom / 1.25, 0.05));
    emit('zoomChanged', state.zoom);
  });
  document.getElementById('btnFitView')?.addEventListener('click', fitToView);
}

function updateZoomDisplay(zoom) {
  const label = document.getElementById('zoomLevel');
  if (label) label.textContent = Math.round(zoom * 100) + '%';
}

// ═══════════════════════════════════════════════════════════
// Keyboard Shortcuts
// ═══════════════════════════════════════════════════════════
function setupKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    // Don't trigger shortcuts when typing in inputs
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;

    const key = e.key.toLowerCase();

    // Tool shortcuts
    const toolMap = { v: 'select', h: 'pan', b: 'bbox', p: 'polygon', m: 'brush', f: 'freehand', l: 'polyline' };
    if (toolMap[key] && !e.ctrlKey && !e.metaKey) {
      const btn = document.querySelector(`.tool-btn[data-tool="${toolMap[key]}"]`);
      btn?.click();
      return;
    }

    // Period/comma for point tool
    if (key === '.' && !e.ctrlKey && !e.shiftKey) {
      if (state.mediaType === 'video') {
        // Next frame
        document.getElementById('btnNextFrame')?.click();
      } else {
        document.querySelector('.tool-btn[data-tool="point"]')?.click();
      }
      return;
    }
    if (key === ',' && state.mediaType === 'video') {
      document.getElementById('btnPrevFrame')?.click();
      return;
    }

    // Space = play/pause for video
    if (key === ' ' && state.mediaType === 'video') {
      e.preventDefault();
      togglePlay();
      return;
    }

    // Undo/Redo
    if ((e.ctrlKey || e.metaKey) && key === 'z' && !e.shiftKey) {
      e.preventDefault();
      undo();
      return;
    }
    if ((e.ctrlKey || e.metaKey) && key === 'z' && e.shiftKey) {
      e.preventDefault();
      redo();
      return;
    }

    // Delete selected annotation
    if ((key === 'delete' || key === 'backspace') && state.selectedAnnotationId) {
      e.preventDefault();
      deleteAnnotation(state.selectedAnnotationId);
      return;
    }

    // Escape = cancel current drawing or deselect
    if (key === 'escape') {
      cancelCurrentDrawing();
      setState('selectedAnnotationId', null);
      emit('annotationSelected', null);
      renderAnnotations();
      return;
    }

    // Zoom shortcuts
    if ((e.ctrlKey || e.metaKey) && key === '=') {
      e.preventDefault();
      document.getElementById('btnZoomIn')?.click();
    }
    if ((e.ctrlKey || e.metaKey) && key === '-') {
      e.preventDefault();
      document.getElementById('btnZoomOut')?.click();
    }
    if ((e.ctrlKey || e.metaKey) && key === '0') {
      e.preventDefault();
      fitToView();
    }

    // Number keys 1-5 for labels
    if (['1', '2', '3', '4', '5'].includes(key) && !e.ctrlKey && !e.metaKey) {
      const labels = document.querySelectorAll('.label-btn[data-label]');
      const idx = parseInt(key) - 1;
      if (labels[idx]) labels[idx].click();
    }
  });

  // Track space key for pan while held
  document.addEventListener('keydown', (e) => {
    if (e.key === ' ' && state.mediaType !== 'video') {
      e.preventDefault();
      document.getElementById('viewport').style.cursor = 'grab';
    }
  });
}

// ═══════════════════════════════════════════════════════════
// Media Queue UI
// ═══════════════════════════════════════════════════════════
function updateMediaQueue() {
  const container = document.getElementById('mediaQueue');
  if (!container) return;

  if (state.mediaList.length === 0) {
    container.innerHTML = '<div class="empty-state-small">No media loaded</div>';
    document.getElementById('projectName').textContent = 'No media loaded';
    return;
  }

  container.innerHTML = '';
  for (const media of state.mediaList) {
    const item = document.createElement('div');
    item.className = `media-queue-item ${media.id === state.activeMediaId ? 'active' : ''}`;
    item.innerHTML = `
      <div class="media-thumb" style="background: var(--bg-primary)"></div>
      <span class="media-queue-name">${media.name}</span>
      <span class="media-queue-type">${media.type}</span>
    `;
    item.addEventListener('click', () => selectMedia(media.id));

    // Generate thumbnail
    if (media.type === 'image') {
      const thumb = item.querySelector('.media-thumb');
      const img = new Image();
      img.onload = () => {
        thumb.style.background = `url(${media.url}) center/cover`;
      };
      img.src = media.url;
    }

    container.appendChild(item);
  }
}

function updateMediaInfo(media) {
  document.getElementById('infoType').textContent = media ? media.type.toUpperCase() : '-';
  document.getElementById('infoDimensions').textContent = media ? `${media.width} x ${media.height}` : '-';
  document.getElementById('infoSize').textContent = media ? fileSize(media.size) : '-';
  document.getElementById('infoDuration').textContent = media?.duration ? (media.duration.toFixed(2) + 's') : '-';
  document.getElementById('projectName').textContent = media ? media.name : 'No media loaded';
}

// ═══════════════════════════════════════════════════════════
// Annotations List UI
// ═══════════════════════════════════════════════════════════
function updateAnnotationsList() {
  const container = document.getElementById('annotationsList');
  const countEl = document.getElementById('annotationCount');
  if (!container) return;

  countEl.textContent = state.annotations.length;

  if (state.annotations.length === 0) {
    container.innerHTML = '<div class="empty-state-small">No annotations yet</div>';
    return;
  }

  container.innerHTML = '';
  for (const ann of state.annotations) {
    const item = document.createElement('div');
    item.className = `annotation-item ${ann.id === state.selectedAnnotationId ? 'selected' : ''}`;

    const typeIcons = {
      bbox: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="1"/></svg>',
      polygon: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12,2 22,8.5 18,20 6,20 2,8.5"/></svg>',
      point: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4" fill="currentColor"/></svg>',
      freehand: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 12c2-4 4-6 7-6s4 4 6 4 4-4 7-4"/></svg>',
      polyline: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3,17 9,8 15,14 21,5"/></svg>',
      brush: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="8"/></svg>',
    };

    item.innerHTML = `
      <span class="ann-type-icon" style="color: ${ann.color}">${typeIcons[ann.type] || ''}</span>
      <span class="ann-label"><span style="color: ${ann.color}">${ann.label || 'Unlabeled'}</span> <span style="color: var(--text-tertiary)">${ann.type}</span></span>
      <button class="ann-delete" title="Delete">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    `;

    item.addEventListener('click', (e) => {
      if (e.target.closest('.ann-delete')) {
        deleteAnnotation(ann.id);
        return;
      }
      setState('selectedAnnotationId', ann.id);
      emit('annotationSelected', ann);
      renderAnnotations();
      updateAnnotationsList();
    });

    container.appendChild(item);
  }
}

// ═══════════════════════════════════════════════════════════
// Properties Panel
// ═══════════════════════════════════════════════════════════
function updatePropertiesPanel(ann) {
  const selProps = document.getElementById('selectionProperties');
  const propLabel = document.getElementById('propLabel');
  const propConf = document.getElementById('propConfidence');
  const propConfVal = document.getElementById('propConfidenceVal');
  const propOccluded = document.getElementById('propOccluded');
  const propTruncated = document.getElementById('propTruncated');
  const propNotes = document.getElementById('propNotes');

  if (!ann) {
    selProps.innerHTML = '<div class="empty-state-small">Select an annotation to edit</div>';
    [propLabel, propConf, propOccluded, propTruncated, propNotes].forEach(el => {
      if (el) el.disabled = true;
    });
    return;
  }

  // Show selection info
  let info = `<div class="info-row"><span>Type</span><span>${ann.type}</span></div>`;
  if (ann.type === 'bbox') {
    info += `<div class="info-row"><span>Position</span><span>${Math.round(ann.x)}, ${Math.round(ann.y)}</span></div>`;
    info += `<div class="info-row"><span>Size</span><span>${Math.round(ann.w)} x ${Math.round(ann.h)}</span></div>`;
  } else if (ann.type === 'point') {
    info += `<div class="info-row"><span>Position</span><span>${Math.round(ann.x)}, ${Math.round(ann.y)}</span></div>`;
  } else if (ann.points) {
    info += `<div class="info-row"><span>Points</span><span>${ann.points.length}</span></div>`;
  }
  info += `<div class="info-row"><span>ID</span><span style="font-size:9px">${ann.id}</span></div>`;
  selProps.innerHTML = info;

  // Enable attribute fields
  [propLabel, propConf, propOccluded, propTruncated, propNotes].forEach(el => {
    if (el) el.disabled = false;
  });

  // Set values
  if (propLabel) propLabel.value = ann.label || 'Person';
  if (propNotes) propNotes.value = ann.notes || '';
}

// ═══════════════════════════════════════════════════════════
// Export
// ═══════════════════════════════════════════════════════════
function setupExport() {
  document.getElementById('btnExport')?.addEventListener('click', () => {
    if (state.annotations.length === 0) {
      toast('No annotations to export', 'error');
      return;
    }

    const exportData = {
      version: '1.0',
      media: getActiveMedia() ? {
        name: getActiveMedia().name,
        type: getActiveMedia().type,
        width: state.mediaWidth,
        height: state.mediaHeight,
      } : null,
      annotations: state.annotations.map(ann => {
        const clean = { ...ann };
        delete clean.id;
        delete clean.createdAt;
        return clean;
      }),
      labels: state.labels,
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `annotations_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast('Annotations exported!', 'success');
  });
}

// ═══════════════════════════════════════════════════════════
// Add Label Modal
// ═══════════════════════════════════════════════════════════
function showAddLabelModal() {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal">
      <h3>Add New Label</h3>
      <input class="modal-input" id="newLabelName" placeholder="Label name..." autofocus>
      <div style="display:flex; align-items:center; gap:8px; margin-bottom:16px;">
        <label style="font-size:12px; color: var(--text-secondary)">Color:</label>
        <input type="color" id="newLabelColor" value="#FF8C00" style="width:32px; height:24px; border:none; background:none; cursor:pointer;">
      </div>
      <div class="modal-actions">
        <button class="modal-btn" id="cancelLabel">Cancel</button>
        <button class="modal-btn primary" id="confirmLabel">Add</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);

  const nameInput = overlay.querySelector('#newLabelName');
  nameInput.focus();

  const close = () => overlay.remove();
  overlay.querySelector('#cancelLabel').addEventListener('click', close);
  overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });

  const confirm = () => {
    const name = nameInput.value.trim();
    if (!name) return;
    const color = overlay.querySelector('#newLabelColor').value;
    const id = name.toLowerCase().replace(/\s+/g, '_');

    state.labels.push({ id, name, color });

    // Add to palette
    const palette = document.getElementById('labelPalette');
    const btn = document.createElement('button');
    btn.className = 'label-btn';
    btn.dataset.label = id;
    btn.style.setProperty('--label-color', color);
    btn.title = name;
    btn.innerHTML = `<span class="label-dot"></span><span class="label-name">${name}</span>`;
    btn.addEventListener('click', () => {
      document.querySelectorAll('.label-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      setState('activeLabel', id);
    });
    palette.appendChild(btn);

    // Also add to properties dropdown
    const opt = document.createElement('option');
    opt.value = id;
    opt.textContent = name;
    document.getElementById('propLabel')?.appendChild(opt);

    toast(`Label "${name}" added`, 'success');
    close();
  };

  overlay.querySelector('#confirmLabel').addEventListener('click', confirm);
  nameInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') confirm(); });
}
