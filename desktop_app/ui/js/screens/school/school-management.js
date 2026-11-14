import { apiPost } from '../../core/api.js';
import { getBootstrap } from '../../core/state.js';
import { esc, toast, openModal, closeModal } from '../../core/dom.js';

function options(items, label = item => item.name) {
  return items.map(item => `<option value="${esc(item.id)}">${esc(label(item))}</option>`).join('');
}

function refreshSchoolScreen() {
  document.getElementById('btn-refresh')?.click();
}

export function openNewTeacherModal() {
  const data = getBootstrap()?.school || {};
  const schools = data.schools || [];
  openModal('Add Teacher', `
    <div class="form-group">
      <label class="form-label required" for="teacher-name">Full Name</label>
      <input class="form-control" id="teacher-name" required autofocus placeholder="e.g. Muhammad Ali" />
    </div>
    <div class="form-group">
      <label class="form-label" for="teacher-department">Department</label>
      <input class="form-control" id="teacher-department" value="Academic" />
    </div>
    <div class="form-group">
      <label class="form-label" for="teacher-email">Work Email</label>
      <input class="form-control" id="teacher-email" type="email" placeholder="teacher@school.com" />
    </div>
    <div class="form-group">
      <label class="form-label" for="teacher-phone">Phone</label>
      <input class="form-control" id="teacher-phone" placeholder="0300-1234567" />
    </div>
    <input type="hidden" id="teacher-school" value="${esc(schools[0]?.id || '')}" />
  `, async () => {
    const name = document.getElementById('teacher-name')?.value.trim();
    if (!name) throw new Error('Teacher name is required.');
    await apiPost('/api/teachers', {
      name,
      department: document.getElementById('teacher-department')?.value.trim() || 'Academic',
      work_email: document.getElementById('teacher-email')?.value.trim() || '',
      phone_numbers: document.getElementById('teacher-phone')?.value.trim() || '',
      school_id: Number(document.getElementById('teacher-school')?.value || 0) || null,
    });
    closeModal();
    toast('Teacher added successfully.', 'success');
    refreshSchoolScreen();
  }, { submitLabel: 'Add Teacher' });
}

export function openNewClassModal() {
  const data = getBootstrap()?.school || {};
  const schools = data.schools || [];
  const standards = data.base_standards || [];
  const divisions = data.divisions || [];
  const mediums = data.mediums || [];
  const rooms = data.classrooms || [];
  const teachers = data.teachers || [];

  if (!schools.length || !standards.length || !divisions.length || !mediums.length) {
    toast('Set up a school, standard, division, and medium before adding a class.', 'error');
    return;
  }

  openModal('Add Class', `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
      <div class="form-group">
        <label class="form-label required" for="class-school">School</label>
        <select class="form-control" id="class-school">${options(schools)}</select>
      </div>
      <div class="form-group">
        <label class="form-label required" for="class-standard">Grade / Standard</label>
        <select class="form-control" id="class-standard">${options(standards)}</select>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
      <div class="form-group">
        <label class="form-label required" for="class-division">Division</label>
        <select class="form-control" id="class-division">${options(divisions)}</select>
      </div>
      <div class="form-group">
        <label class="form-label required" for="class-medium">Medium</label>
        <select class="form-control" id="class-medium">${options(mediums)}</select>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
      <div class="form-group">
        <label class="form-label required" for="class-capacity">Seat Capacity</label>
        <input class="form-control" id="class-capacity" type="number" min="1" value="40" required />
      </div>
      <div class="form-group">
        <label class="form-label" for="class-teacher">Class Teacher</label>
        <select class="form-control" id="class-teacher">
          <option value="">— Unassigned —</option>${options(teachers)}
        </select>
      </div>
    </div>
    <div class="form-group">
      <label class="form-label" for="class-room">Classroom</label>
      <select class="form-control" id="class-room">
        <option value="">— Unassigned —</option>${options(rooms, item => item.name || item.number)}
      </select>
    </div>
  `, async () => {
    const capacity = Number(document.getElementById('class-capacity')?.value);
    if (!capacity || capacity < 1) throw new Error('Seat capacity must be at least 1.');
    await apiPost('/api/school/classes', {
      school_id: Number(document.getElementById('class-school')?.value),
      standard_id: Number(document.getElementById('class-standard')?.value),
      division_id: Number(document.getElementById('class-division')?.value),
      medium_id: Number(document.getElementById('class-medium')?.value),
      capacity,
      teacher_id: Number(document.getElementById('class-teacher')?.value) || null,
      class_room_id: Number(document.getElementById('class-room')?.value) || null,
    });
    closeModal();
    toast('Class added successfully.', 'success');
    refreshSchoolScreen();
  }, { submitLabel: 'Add Class', wide: true });
}
