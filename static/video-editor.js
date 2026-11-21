const recording = document.querySelector('#recording');
const form = document.querySelector('#trim-form');
const startInput = form.elements.namedItem('start');
const endInput = form.elements.namedItem('end');
const feedback = document.querySelector('#trim-feedback');
let clipEnd = null;

recording.addEventListener('loadedmetadata', () => {
  const duration = (Math.floor(recording.duration * 1000) / 1000).toFixed(3);
  startInput.max = endInput.max = duration;
  if (!endInput.value) endInput.value = duration;
});
recording.addEventListener('error', () => {
  const message = document.querySelector('#player-feedback');
  message.textContent = 'This recording could not be played. Try downloading the original.';
  message.hidden = false;
});
for (const button of form.querySelectorAll('[data-mark]')) {
  button.addEventListener('click', () => {
    form.elements.namedItem(button.dataset.mark).value = (Math.floor(recording.currentTime * 1000) / 1000).toFixed(3);
  });
}
function preview(start, end) {
  feedback.textContent = '';
  if (!Number.isFinite(recording.duration) || !Number.isFinite(start) || !Number.isFinite(end)
      || start < 0 || end <= start || end > recording.duration) {
    feedback.textContent = 'Choose start and end times within the recording.';
    return;
  }
  clipEnd = end;
  recording.currentTime = start;
  recording.scrollIntoView({block:'nearest'});
  recording.play().catch(() => { feedback.textContent = 'Playback could not start.'; });
}
recording.addEventListener('timeupdate', () => {
  if (clipEnd !== null && recording.currentTime >= clipEnd) {
    recording.pause();
    clipEnd = null;
  }
});
document.querySelector('#preview-trim').addEventListener('click', () => preview(startInput.valueAsNumber, endInput.valueAsNumber));
for (const button of document.querySelectorAll('[data-start]')) {
  button.addEventListener('click', () => preview(Number(button.dataset.start), Number(button.dataset.end)));
}

for (const button of document.querySelectorAll('[data-seek]')) {
  button.addEventListener('click', () => {
    const target = Number(button.dataset.seek);
    if (!Number.isFinite(target) || target < 0) return;
    clipEnd = null;
    const seek = () => {
      recording.currentTime = Math.min(target, recording.duration || target);
      recording.scrollIntoView({behavior:'smooth', block:'center'});
      recording.focus({preventScroll:true});
    };
    if (recording.readyState < 1) recording.addEventListener('loadedmetadata', seek, {once:true});
    else seek();
  });
}
