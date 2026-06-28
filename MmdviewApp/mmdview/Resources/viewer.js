// viewer.js — テスト可能な純粋ロジック

var ZOOM_MIN = 0.5;
var ZOOM_MAX = 2.0;
var ZOOM_STEP = 0.25;
var ZOOM_DEFAULT = 1;
var BASE_SCALE = 0.75;

function clampZoom(z) {
  return Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, z));
}

function stepZoom(current, delta) {
  return clampZoom(Math.round((current + delta) * 100) / 100);
}

function wheelZoom(current, deltaY) {
  return clampZoom(Math.round((current - deltaY * 0.01) * 1000) / 1000);
}

function zoomLabel(zoom) {
  return Math.round(zoom * 100) + '%';
}

function effectiveZoom(zoom) {
  return zoom * BASE_SCALE;
}

function parseStoredZoom(raw) {
  var z = parseFloat(raw);
  return isNaN(z) ? ZOOM_DEFAULT : z;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    ZOOM_MIN: ZOOM_MIN,
    ZOOM_MAX: ZOOM_MAX,
    ZOOM_STEP: ZOOM_STEP,
    ZOOM_DEFAULT: ZOOM_DEFAULT,
    BASE_SCALE: BASE_SCALE,
    clampZoom: clampZoom,
    stepZoom: stepZoom,
    wheelZoom: wheelZoom,
    zoomLabel: zoomLabel,
    effectiveZoom: effectiveZoom,
    parseStoredZoom: parseStoredZoom,
  };
}
