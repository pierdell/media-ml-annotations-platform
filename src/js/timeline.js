// ═══════════════════════════════════════════════════════════
// Video Timeline Controls
// ═══════════════════════════════════════════════════════════

import { state, setState, emit, subscribe } from './state.js';
import { formatTime, clamp } from './utils.js';
import { getVideoElement, drawVideoFrame, startVideoLoop, stopVideoLoop, renderAllOverlays } from './viewport.js';
import { generateVideoTrackingFrame } from './demo.js';

let videoEl;
let videoTrackBar, videoProgress, videoPlayhead;
let tlCurrentTime, tlDuration, tlFrameInfo;
let timelineRuler;
let isSeeking = false;
let baseTrackingData = null;

export function initTimeline() {
  videoEl = getVideoElement();

  videoTrackBar = document.getElementById('videoTrackBar');
  videoProgress = document.getElementById('videoProgress');
  videoPlayhead = document.getElementById('videoPlayhead');
  tlCurrentTime = document.getElementById('tlCurrentTime');
  tlDuration = document.getElementById('tlDuration');
  tlFrameInfo = document.getElementById('tlFrameInfo');
  timelineRuler = document.getElementById('timelineRuler');

  // Play/Pause
  document.getElementById('btnPlayPause').addEventListener('click', togglePlay);

  // Frame stepping
  document.getElementById('btnPrevFrame').addEventListener('click', () => stepFrame(-1));
  document.getElementById('btnNextFrame').addEventListener('click', () => stepFrame(1));

  // Speed control
  document.getElementById('playbackSpeed').addEventListener('change', (e) => {
    state.playbackSpeed = parseFloat(e.target.value);
    if (videoEl) videoEl.playbackRate = state.playbackSpeed;
  });

  // Track bar seeking
  videoTrackBar?.addEventListener('mousedown', startSeek);
  window.addEventListener('mousemove', onSeekMove);
  window.addEventListener('mouseup', stopSeek);

  // Subscribe to events
  subscribe('timeUpdate', updateTimeDisplay);
  subscribe('mediaChanged', onMediaChanged);
}

function onMediaChanged(media) {
  if (!media || media.type !== 'video') return;

  videoEl = getVideoElement();
  baseTrackingData = null;

  videoEl.onloadedmetadata = () => {
    setState('duration', videoEl.duration);
    setState('currentTime', 0);
    tlDuration.textContent = formatTime(videoEl.duration);
    tlCurrentTime.textContent = formatTime(0);

    const totalFrames = Math.floor(videoEl.duration * state.fps);
    tlFrameInfo.textContent = `Frame 0 / ${totalFrames}`;

    buildRuler(videoEl.duration);
    buildDemoTracks(totalFrames);
  };

  videoEl.ontimeupdate = () => {
    if (isSeeking) return;
    state.currentTime = videoEl.currentTime;
    emit('timeUpdate', videoEl.currentTime);
    updateVideoOverlays();
  };

  videoEl.onended = () => {
    setState('isPlaying', false);
    updatePlayPauseIcon();
    stopVideoLoop();
  };
}

export function togglePlay() {
  if (!videoEl || !state.activeMediaId || state.mediaType !== 'video') return;

  if (state.isPlaying) {
    videoEl.pause();
    setState('isPlaying', false);
    stopVideoLoop();
  } else {
    videoEl.playbackRate = state.playbackSpeed;
    videoEl.play();
    setState('isPlaying', true);
    startVideoLoop();
  }
  updatePlayPauseIcon();
}

function updatePlayPauseIcon() {
  const playIcon = document.querySelector('#btnPlayPause .icon-play');
  const pauseIcon = document.querySelector('#btnPlayPause .icon-pause');
  if (state.isPlaying) {
    playIcon.classList.add('hidden');
    pauseIcon.classList.remove('hidden');
  } else {
    playIcon.classList.remove('hidden');
    pauseIcon.classList.add('hidden');
  }
}

function stepFrame(direction) {
  if (!videoEl || state.mediaType !== 'video') return;
  const wasPlaying = state.isPlaying;
  if (wasPlaying) {
    videoEl.pause();
    setState('isPlaying', false);
    stopVideoLoop();
    updatePlayPauseIcon();
  }

  const frameDuration = 1 / state.fps;
  videoEl.currentTime = clamp(
    videoEl.currentTime + direction * frameDuration,
    0,
    videoEl.duration
  );

  setTimeout(() => {
    drawVideoFrame();
    state.currentTime = videoEl.currentTime;
    emit('timeUpdate', videoEl.currentTime);
    updateVideoOverlays();
  }, 50);
}

function updateTimeDisplay(time) {
  if (!tlCurrentTime) return;
  tlCurrentTime.textContent = formatTime(time);
  const totalFrames = Math.floor(state.duration * state.fps);
  const currentFrame = Math.floor(time * state.fps);
  tlFrameInfo.textContent = `Frame ${currentFrame} / ${totalFrames}`;

  // Update playhead position
  if (videoTrackBar && state.duration > 0) {
    const pct = (time / state.duration) * 100;
    videoPlayhead.style.left = pct + '%';
    videoProgress.style.width = pct + '%';
  }
}

function updateVideoOverlays() {
  // If tracking is visible, animate tracking points based on current time
  if (state.mlLayers.tracking.visible && state.mlLayers.tracking.data) {
    if (!baseTrackingData) {
      baseTrackingData = state.mlLayers.tracking.data;
    }
    const totalFrames = Math.floor(state.duration * state.fps);
    const currentFrame = Math.floor(state.currentTime * state.fps);
    const animatedData = generateVideoTrackingFrame(baseTrackingData, currentFrame, totalFrames);
    if (animatedData) {
      state.mlLayers.tracking.data = animatedData;
    }
  }
  renderAllOverlays();
}

// ── Seeking ───────────────────────────────────────────────
function startSeek(e) {
  isSeeking = true;
  seekToPosition(e);
}

function onSeekMove(e) {
  if (!isSeeking) return;
  seekToPosition(e);
}

function stopSeek() {
  if (!isSeeking) return;
  isSeeking = false;
}

function seekToPosition(e) {
  if (!videoTrackBar || !videoEl) return;
  const rect = videoTrackBar.getBoundingClientRect();
  const pct = clamp((e.clientX - rect.left) / rect.width, 0, 1);
  videoEl.currentTime = pct * state.duration;
  state.currentTime = videoEl.currentTime;
  emit('timeUpdate', state.currentTime);

  setTimeout(() => {
    drawVideoFrame();
    updateVideoOverlays();
  }, 30);
}

// ── Ruler & Demo Tracks ───────────────────────────────────
function buildRuler(duration) {
  if (!timelineRuler) return;
  timelineRuler.innerHTML = '';
  const interval = duration > 60 ? 10 : duration > 10 ? 2 : 0.5;
  const trackWidth = timelineRuler.offsetWidth || 800;

  for (let t = 0; t <= duration; t += interval) {
    const pct = (t / duration) * 100;
    const tick = document.createElement('div');
    tick.className = 'ruler-tick major';
    tick.style.left = pct + '%';

    const label = document.createElement('span');
    label.className = 'ruler-tick-label';
    label.style.left = pct + '%';
    label.textContent = formatTime(t).split('.')[0];

    timelineRuler.appendChild(tick);
    timelineRuler.appendChild(label);

    // Minor ticks
    const minorInterval = interval / 4;
    for (let mt = minorInterval; mt < interval && t + mt <= duration; mt += minorInterval) {
      const mPct = ((t + mt) / duration) * 100;
      const mTick = document.createElement('div');
      mTick.className = 'ruler-tick minor';
      mTick.style.left = mPct + '%';
      timelineRuler.appendChild(mTick);
    }
  }
}

function buildDemoTracks(totalFrames) {
  // Add demo keyframes to the keyframe track
  const keyframeTrack = document.getElementById('keyframeTrackBar');
  if (keyframeTrack) {
    keyframeTrack.innerHTML = '';
    const numKeyframes = 8 + Math.floor(Math.random() * 12);
    for (let i = 0; i < numKeyframes; i++) {
      const frame = Math.floor(Math.random() * totalFrames);
      const pct = (frame / totalFrames) * 100;
      const kf = document.createElement('div');
      kf.className = 'track-keyframe';
      kf.style.left = pct + '%';
      kf.title = `Keyframe at frame ${frame}`;
      keyframeTrack.appendChild(kf);
    }
  }

  // Add demo detection segments
  const detTrack = document.getElementById('detectionTrackBar');
  if (detTrack) {
    detTrack.innerHTML = '';
    const colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#F7DC6F'];
    let pos = 0;
    while (pos < 100) {
      const width = 5 + Math.random() * 15;
      const gap = 2 + Math.random() * 8;
      const seg = document.createElement('div');
      seg.className = 'track-segment';
      seg.style.left = pos + '%';
      seg.style.width = Math.min(width, 100 - pos) + '%';
      seg.style.background = colors[Math.floor(Math.random() * colors.length)];
      detTrack.appendChild(seg);
      pos += width + gap;
    }
  }
}
