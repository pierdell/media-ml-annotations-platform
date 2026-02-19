// ═══════════════════════════════════════════════════════════
// Media Loading & Management
// ═══════════════════════════════════════════════════════════

import { state, setState, emit } from './state.js';
import { toast, generateId, fileSize } from './utils.js';

const IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/bmp'];
const VIDEO_TYPES = ['video/mp4', 'video/webm', 'video/quicktime', 'video/x-msvideo'];

export function isImageFile(file) {
  return IMAGE_TYPES.includes(file.type) || /\.(jpe?g|png|webp|gif|bmp)$/i.test(file.name);
}

export function isVideoFile(file) {
  return VIDEO_TYPES.includes(file.type) || /\.(mp4|webm|mov|avi)$/i.test(file.name);
}

export async function loadMediaFiles(files) {
  const validFiles = Array.from(files).filter(f => isImageFile(f) || isVideoFile(f));
  if (validFiles.length === 0) {
    toast('No supported media files found', 'error');
    return;
  }

  for (const file of validFiles) {
    const mediaItem = {
      id: generateId(),
      name: file.name,
      type: isImageFile(file) ? 'image' : 'video',
      file: file,
      url: URL.createObjectURL(file),
      size: file.size,
      width: 0,
      height: 0,
      duration: 0,
    };

    if (mediaItem.type === 'image') {
      await loadImageDimensions(mediaItem);
    } else {
      await loadVideoDimensions(mediaItem);
    }

    state.mediaList.push(mediaItem);
  }

  emit('mediaList', state.mediaList);
  toast(`Loaded ${validFiles.length} file(s)`, 'success');

  // Auto-select first item if nothing selected
  if (!state.activeMediaId && state.mediaList.length > 0) {
    selectMedia(state.mediaList[0].id);
  }
}

function loadImageDimensions(item) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      item.width = img.naturalWidth;
      item.height = img.naturalHeight;
      resolve();
    };
    img.onerror = () => resolve();
    img.src = item.url;
  });
}

function loadVideoDimensions(item) {
  return new Promise((resolve) => {
    const video = document.createElement('video');
    video.preload = 'metadata';
    video.onloadedmetadata = () => {
      item.width = video.videoWidth;
      item.height = video.videoHeight;
      item.duration = video.duration;
      resolve();
    };
    video.onerror = () => resolve();
    video.src = item.url;
  });
}

export function selectMedia(mediaId) {
  const item = state.mediaList.find(m => m.id === mediaId);
  if (!item) return;

  setState('activeMediaId', mediaId);
  setState('mediaType', item.type);
  setState('mediaWidth', item.width);
  setState('mediaHeight', item.height);
  if (item.type === 'video') {
    setState('duration', item.duration);
    setState('currentTime', 0);
    setState('isPlaying', false);
  }

  // Reset annotations for new media
  setState('annotations', []);
  setState('selectedAnnotationId', null);

  emit('mediaChanged', item);
}

export function getActiveMedia() {
  return state.mediaList.find(m => m.id === state.activeMediaId) || null;
}

export function removeMedia(mediaId) {
  const idx = state.mediaList.findIndex(m => m.id === mediaId);
  if (idx === -1) return;

  const item = state.mediaList[idx];
  URL.revokeObjectURL(item.url);
  state.mediaList.splice(idx, 1);

  if (state.activeMediaId === mediaId) {
    if (state.mediaList.length > 0) {
      selectMedia(state.mediaList[Math.min(idx, state.mediaList.length - 1)].id);
    } else {
      setState('activeMediaId', null);
      setState('mediaType', null);
      emit('mediaChanged', null);
    }
  }

  emit('mediaList', state.mediaList);
}
