'use strict';
const menu = document.getElementById('menu');
const sidebar = document.getElementById('sidebar');
menu.addEventListener('click', () => {
  const open = sidebar.classList.toggle('open');
  menu.setAttribute('aria-expanded', String(open));
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') {
    sidebar.classList.remove('open');
    menu.setAttribute('aria-expanded', 'false');
  }
});
const search = document.getElementById('search');
if (search) {
  const rows = [...document.querySelectorAll('#equipment-table tbody tr')];
  search.addEventListener('input', () => {
    const term = search.value.trim().toLowerCase();
    let matches = 0;
    rows.forEach(row => {
      row.hidden = !row.textContent.toLowerCase().includes(term);
      if (!row.hidden) matches++;
    });
    document.getElementById('no-match').hidden = matches !== 0;
  });
}
const equipment = document.getElementById('equipment');
if (equipment) {
  const form = document.getElementById('reservation-form');
  const quantity = document.getElementById('quantity');
  const note = document.getElementById('stock-note');
  const start = document.getElementById('start-time');
  const end = document.getElementById('end-time');
  const day = form.elements.reservation_date;
  const student = form.elements.student_id;
  let sequence = 0;
  const dialog = document.getElementById('booking-conflict');
  const title = document.getElementById('conflict-title');
  const message = document.getElementById('conflict-message');
  const slotNote = document.getElementById('conflict-slot');
  const useAvailable = document.getElementById('use-available');
  let lastNotice = '';
  let conflict = null;
  function showConflict(info, force = false) {
    if (!info) return;
    const signature = [equipment.value, day.value, start.value, end.value, quantity.value, info.kind, info.available].join('|');
    if (!force && lastNotice === signature) return;
    lastNotice = signature;
    title.textContent = info.kind === 'duplicate' ? 'Overlapping reservation' : info.available === 0 ? 'Equipment already reserved' : 'Requested quantity unavailable';
    message.textContent = info.kind === 'duplicate'
      ? 'An overlapping reservation already exists for this Student ID. Please select a different time.'
      : info.available === 0
        ? 'All units of this equipment are already reserved for the selected time slot. Please choose another time or equipment.'
        : Number.isInteger(info.available)
          ? 'Only ' + info.available + ' unit(s) are available. The requested quantity exceeds the remaining stock because of existing reservations or stock limits.'
          : 'The requested quantity is no longer available. Please select another time, equipment or quantity.';
    slotNote.textContent = equipment.selectedOptions[0]?.textContent.trim() + ' • ' + day.value + ' • ' + start.value + ' – ' + end.value;
    useAvailable.hidden = !(info.kind === 'stock' && Number.isInteger(info.available) && info.available > 0);
    if (useAvailable.hidden) useAvailable.style.display = 'none';
    else useAvailable.style.display = '';
    if (!dialog.open) { if (typeof dialog.showModal === 'function') dialog.showModal(); else alert(title.textContent + '\n' + message.textContent); }
  }
  document.getElementById('change-slot').addEventListener('click', () => { dialog.close(); start.focus(); });
  useAvailable.addEventListener('click', () => {
    if (conflict && Number.isInteger(conflict.available) && conflict.available > 0) {
      quantity.value = String(conflict.available);
      dialog.close();
      refresh();
      quantity.focus();
    }
  });
  form.addEventListener('invalid', event => {
    if (conflict && (event.target === quantity || event.target === student)) {
      event.preventDefault();
      showConflict(conflict, true);
    }
  }, true);
  if (form.dataset.conflict) {
    const initial = {kind: form.dataset.conflict.startsWith('An overlapping') ? 'duplicate' : 'stock'};
    showConflict(initial);
  }
  async function refresh() {
    const version = ++sequence;
    const stock = equipment.selectedOptions[0]?.dataset.stock;
    conflict = null;
    quantity.setCustomValidity('');
    student.setCustomValidity('');
    end.setCustomValidity(start.value && end.value && end.value <= start.value ? 'End time must be later than start time.' : '');
    if (stock === undefined) quantity.removeAttribute('max');
    else quantity.max = stock;
    note.textContent = stock === undefined ? 'Select equipment to see stock.' : stock + ' total units. Select a valid date and time to check availability.';
    if (!equipment.value || !day.value || !day.validity.valid || !start.value || !end.value || end.value <= start.value) return;
    const params = new URLSearchParams({equipment_id: equipment.value, reservation_date: day.value, start_time: start.value, end_time: end.value, student_id: form.dataset.guest === 'true' ? '' : student.value});
    try {
      const response = await fetch('/api/availability?' + params, {cache: 'no-store'});
      if (!response.ok) throw new Error('Availability unavailable');
      const result = await response.json();
      if (version !== sequence) return;
      quantity.max = result.available;
      note.textContent = result.available + ' of ' + result.stock + ' units available for this slot.';
      if (result.overlap) {
        conflict = {kind: 'duplicate'};
        student.setCustomValidity('An overlapping reservation already exists.');
      } else if (Number(quantity.value) > result.available) {
        conflict = {kind: 'stock', available: result.available};
        quantity.setCustomValidity('Requested quantity exceeds available equipment.');
      }
      if (conflict) showConflict(conflict);
      else { lastNotice = ''; if (dialog.open) dialog.close(); }
    } catch (error) {
      if (version === sequence) note.textContent = 'Live availability unavailable. The server will validate your request.';
    }
  }
  for (const field of [equipment, day, start, end, student, quantity]) field.addEventListener('input', refresh);
  refresh();
}
