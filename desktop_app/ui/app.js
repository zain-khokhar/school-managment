// Offline Desktop ERP Application Controller (All 10 School Management Modules)
(function () {
  "use strict";

  const state = {
    tab: "dashboard",
    filter: "",
    data: null,
    modalHandler: null,
  };

  const TAB_TITLES = {
    dashboard: "Overview Dashboard (All 10 Modules)",
    school: "1. Core School, Academic Years, Classes & Students",
    fees: "2. School Fees, Registers & Student Payslips",
    attendance: "3. Daily Attendance, Leave Requests & 31-Day Excel Sheets",
    assignment: "4. Teacher & Student Homework Assignments",
    timetable: "5. Regular & Examination Timetables",
    exam: "6. Examinations, Marksheets, Grades & Re-Evaluation",
    library: "7. Library Catalog, Cards, Book Issues & Fines",
    event: "8. School Events & Student Registrations",
    hostel: "9. School Hostels, Rooms & Resident Allocations",
    transport: "10. Fleet Vehicles, Routes, Registrations & Transfers",
  };

  function esc(val) {
    if (val === null || val === undefined) return "";
    return String(val)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function badge(status) {
    const s = String(status || "").toLowerCase();
    let cls = "badge-neutral";
    if (["paid", "approve", "pass"].includes(s)) {
      cls = "badge-success";
    } else if (["done", "fees_received", "confirm", "validate", "running", "available", "open", "active"].includes(s)) {
      cls = "badge-info";
    } else if (["pending", "toapprove", "issue", "re-evaluation", "reissue", "reservation", "expire"].includes(s)) {
      cls = "badge-warn";
    } else if (["cancel", "cancelled", "reject", "terminate", "fail", "fine", "lost"].includes(s)) {
      cls = "badge-danger";
    }
    return `<span class="badge ${cls}">${esc(status)}</span>`;
  }

  function toast(msg, type = "success") {
    const container = document.getElementById("toast-container");
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => el.remove(), 3800);
  }

  async function apiCall(url, method = "GET", body = null) {
    const headers = { "Content-Type": "application/json" };
    if (window.ERP_SESSION_TOKEN) {
      headers["X-Session-Token"] = window.ERP_SESSION_TOKEN;
    }
    const opts = { method, headers, credentials: "same-origin" };
    if (body !== null) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    const json = await res.json();
    if (!res.ok || !json.ok) {
      throw new Error(json.error || `Request failed (${res.status})`);
    }
    return json;
  }

  async function loadBootstrap() {
    try {
      const data = await apiCall("/api/bootstrap");
      state.data = data;
      if (typeof window.ERP_ON_LEGACY_BOOTSTRAP === "function") {
        window.ERP_ON_LEGACY_BOOTSTRAP(data);
        return;
      }
      updateSidebarPills();
      renderCurrentTab();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  function updateSidebarPills() {
    if (!state.data) return;
    const d = state.data;
    const setPill = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = String(val);
    };
    setPill("pill-school", d.school.students.length);
    setPill("pill-fees", d.fees.payslips.length);
    setPill("pill-attendance", d.attendance.daily.length);
    setPill("pill-assignment", d.assignment.student_assignments.length);
    setPill("pill-timetable", d.timetable.timetables.length);
    setPill("pill-exam", d.exam.results.length);
    setPill("pill-library", d.library.books.length);
    setPill("pill-event", d.event.registrations.length);
    setPill("pill-hostel", d.hostel.residents.length);
    setPill("pill-transport", d.transport.participants.length);
  }

  function matchesFilter(obj) {
    if (!state.filter) return true;
    const q = state.filter.toLowerCase();
    return JSON.stringify(obj).toLowerCase().includes(q);
  }

  function openModal(title, fieldsHtml, onSubmit) {
    if (typeof window.ERP_BRIDGE_OPEN_MODAL === "function") {
      window.ERP_BRIDGE_OPEN_MODAL(title, fieldsHtml, async () => {
        const formEl = document.getElementById("modal-form");
        const formData = new FormData(formEl);
        await onSubmit(formData);
        await loadBootstrap();
      });
      return;
    }
    document.getElementById("modal-title").textContent = title;
    document.getElementById("modal-body").innerHTML = fieldsHtml;
    state.modalHandler = onSubmit;
    document.getElementById("modal-backdrop").classList.add("open");
  }

  function closeModal() {
    document.getElementById("modal-backdrop").classList.remove("open");
    state.modalHandler = null;
  }

  function renderCurrentTab() {
    const container = document.getElementById("main-view");
    document.getElementById("page-title").textContent = TAB_TITLES[state.tab] || "School ERP";
    if (!state.data) {
      container.innerHTML = `<div class="panel"><div class="panel-header"><div class="panel-title">Loading SQLite WAL Engine...</div></div></div>`;
      return;
    }

    switch (state.tab) {
      case "dashboard":
        container.innerHTML = renderDashboard();
        break;
      case "school":
        container.innerHTML = renderSchool();
        break;
      case "fees":
        container.innerHTML = renderFees();
        break;
      case "attendance":
        container.innerHTML = renderAttendance();
        break;
      case "assignment":
        container.innerHTML = renderAssignment();
        break;
      case "timetable":
        container.innerHTML = renderTimetable();
        break;
      case "exam":
        container.innerHTML = renderExam();
        break;
      case "library":
        container.innerHTML = renderLibrary();
        break;
      case "event":
        container.innerHTML = renderEvent();
        break;
      case "hostel":
        container.innerHTML = renderHostel();
        break;
      case "transport":
        container.innerHTML = renderTransport();
        break;
    }
  }

  // ---------------------------------------------------------------------------
  // 0. Dashboard View
  // ---------------------------------------------------------------------------
  function renderDashboard() {
    const k = state.data.kpis;
    const students = state.data.school.students.filter(matchesFilter);
    return `
      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">Active Students</div>
          <div class="kpi-value">${k.active_students}</div>
          <div class="kpi-sub">${k.classes} Active Classes • ${k.teachers} Faculty</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Fees Collected</div>
          <div class="kpi-value">Rs. ${k.fees_collected.toLocaleString()}</div>
          <div class="kpi-sub">Pending Due: Rs. ${k.fees_due.toLocaleString()}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Library Stock Available</div>
          <div class="kpi-value">${k.available_books}</div>
          <div class="kpi-sub">${state.data.library.issues.length} Total Book Issues</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Hostel &amp; Transport</div>
          <div class="kpi-value">${k.hostel_residents} / ${k.transport_participants}</div>
          <div class="kpi-sub">Hostel Residents / Bus Riders</div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">Enrolled Students Directory (Quick Cross-Module Actions)</div>
          <div class="panel-toolbar">
            <button class="btn btn-primary" onclick="window.ERP.openNewStudentModal()">+ New Student Admission</button>
            <button class="btn" onclick="window.ERP.openAssignRollModal()">Assign Roll Nos</button>
            <button class="btn" onclick="window.ERP.openPromoteModal()">Promote Academic Year</button>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>PID</th>
                <th class="num">Roll</th>
                <th>Student Name</th>
                <th>Class</th>
                <th>Academic Year</th>
                <th class="num">Age</th>
                <th>State</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${students
                .map(
                  (s) => `
                <tr>
                  <td class="num"><strong>${esc(s.pid)}</strong></td>
                  <td class="num">${s.roll_no || "-"}</td>
                  <td>${esc(s.student_name)} ${esc(s.middle)} ${esc(s.last)}</td>
                  <td>${esc(s.class_name || "-")}</td>
                  <td>${esc(s.academic_year_name || "-")}</td>
                  <td class="num">${s.age} yrs</td>
                  <td>${badge(s.state)}</td>
                  <td>
                    ${
                      s.state === "draft"
                        ? `<button class="btn btn-xs btn-primary" onclick="window.ERP.studentAction(${s.id}, 'admission_done')">Admit</button>`
                        : ""
                    }
                    ${
                      s.state === "done"
                        ? `<button class="btn btn-xs" onclick="window.ERP.studentAction(${s.id}, 'set_alumni')">Set Alumni</button>
                           <button class="btn btn-xs btn-danger" onclick="window.ERP.studentAction(${s.id}, 'terminate')">Terminate</button>`
                        : ""
                    }
                  </td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  // ---------------------------------------------------------------------------
  // 1. School & Students View
  // ---------------------------------------------------------------------------
  function renderSchool() {
    const d = state.data.school;
    const standards = d.standards.filter(matchesFilter);
    const teachers = d.teachers.filter(matchesFilter);
    return `
      ${renderDashboard()}
      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">School Standards &amp; Seat Capacity</div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Class</th>
                <th>Medium</th>
                <th>Class Teacher</th>
                <th>Room</th>
                <th class="num">Total Capacity</th>
                <th class="num">Admitted Students</th>
                <th class="num">Remaining Seats</th>
              </tr>
            </thead>
            <tbody>
              ${standards
                .map(
                  (st) => `
                <tr>
                  <td><strong>${esc(st.display_name)}</strong></td>
                  <td>${esc(st.medium_name)}</td>
                  <td>${esc(st.teacher_name || "-")}</td>
                  <td>${esc(st.room_name || "-")}</td>
                  <td class="num">${st.capacity}</td>
                  <td class="num">${st.total_students}</td>
                  <td class="num"><strong>${st.remaining_seats}</strong></td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">Faculty &amp; Teachers</div>
          <div class="panel-toolbar">
            <button class="btn btn-primary" onclick="window.ERP.openNewTeacherModal()">+ Add Teacher</button>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Department</th>
                <th>Email</th>
                <th class="num">Phone</th>
              </tr>
            </thead>
            <tbody>
              ${teachers
                .map(
                  (t) => `
                <tr>
                  <td><strong>${esc(t.name)}</strong></td>
                  <td>${esc(t.department || "-")}</td>
                  <td>${esc(t.work_email || "-")}</td>
                  <td class="num">${esc(t.phone_numbers || "-")}</td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  // ---------------------------------------------------------------------------
  // 2. School Fees View
  // ---------------------------------------------------------------------------
  function renderFees() {
    const slips = state.data.fees.payslips.filter(matchesFilter);
    return `
      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">Student Fee Payslips &amp; Invoices</div>
          <div class="panel-toolbar">
            <button class="btn btn-primary" onclick="window.ERP.openNewPayslipModal()">+ Generate Fee Payslip</button>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Slip No</th>
                <th>Student</th>
                <th>Class</th>
                <th>Structure</th>
                <th class="num">Date</th>
                <th class="num">Total</th>
                <th class="num">Paid</th>
                <th class="num">Due</th>
                <th>State</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${slips
                .map(
                  (p) => `
                <tr>
                  <td class="num"><strong>${esc(p.number)}</strong></td>
                  <td>${esc(p.student_name)} (${esc(p.pid)})</td>
                  <td>${esc(p.class_name || "-")}</td>
                  <td>${esc(p.structure_name || "-")}</td>
                  <td class="num">${esc(p.date)}</td>
                  <td class="num">Rs. ${Number(p.total).toLocaleString()}</td>
                  <td class="num">Rs. ${Number(p.paid_amount).toLocaleString()}</td>
                  <td class="num"><strong>Rs. ${Number(p.due_amount).toLocaleString()}</strong></td>
                  <td>${badge(p.state)}</td>
                  <td>
                    ${
                      p.state === "draft"
                        ? `<button class="btn btn-xs btn-primary" onclick="window.ERP.payslipAction(${p.id}, 'confirm')">Confirm</button>`
                        : ""
                    }
                    ${
                      p.state === "confirm" || p.state === "pending"
                        ? `<button class="btn btn-xs btn-primary" onclick="window.ERP.payslipAction(${p.id}, 'pay')">Pay Full</button>`
                        : ""
                    }
                  </td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  // ---------------------------------------------------------------------------
  // 3. Attendance & XLSX Export View
  // ---------------------------------------------------------------------------
  function renderAttendance() {
    const daily = state.data.attendance.daily.filter(matchesFilter);
    const leaves = state.data.attendance.leaves.filter(matchesFilter);
    return `
      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">Daily Attendance Roll Call &amp; 31-Day Monthly Matrix</div>
          <div class="panel-toolbar">
            <button class="btn btn-primary" onclick="window.ERP.openNewAttendanceModal()">+ New Daily Attendance</button>
            <a class="btn btn-secondary" href="/api/attendance/export-xlsx" target="_blank">Export 31-Day Excel (.xlsx)</a>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th class="num">Date</th>
                <th>Class</th>
                <th>Teacher</th>
                <th class="num">Total</th>
                <th class="num">Present</th>
                <th class="num">Absent</th>
                <th>State</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${daily
                .map(
                  (a) => `
                <tr>
                  <td class="num"><strong>${esc(a.date)}</strong></td>
                  <td>${esc(a.class_name)}</td>
                  <td>${esc(a.teacher_name || "-")}</td>
                  <td class="num">${a.total_student}</td>
                  <td class="num">${a.total_presence}</td>
                  <td class="num">${a.total_absent}</td>
                  <td>${badge(a.state)}</td>
                  <td>
                    ${
                      a.state === "draft"
                        ? `<button class="btn btn-xs btn-primary" onclick="window.ERP.attendanceAction(${a.id}, 'validate')">Validate &amp; Sync Sheet</button>`
                        : `<button class="btn btn-xs" onclick="window.ERP.attendanceAction(${a.id}, 'draft')">Reset to Draft</button>`
                    }
                  </td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">Student Leave Requests (Auto-Syncs Absent on Roll Call)</div>
          <div class="panel-toolbar">
            <button class="btn btn-primary" onclick="window.ERP.openNewLeaveModal()">+ New Leave Request</button>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Reason / Title</th>
                <th>Student</th>
                <th>Class</th>
                <th class="num">Start Date</th>
                <th class="num">End Date</th>
                <th class="num">Days</th>
                <th>State</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${leaves
                .map(
                  (l) => `
                <tr>
                  <td><strong>${esc(l.name)}</strong></td>
                  <td>${esc(l.student_name)}</td>
                  <td>${esc(l.class_name || "-")}</td>
                  <td class="num">${esc(l.start_date)}</td>
                  <td class="num">${esc(l.end_date)}</td>
                  <td class="num">${l.days}</td>
                  <td>${badge(l.state)}</td>
                  <td>
                    ${
                      l.state === "draft" || l.state === "toapprove"
                        ? `<button class="btn btn-xs btn-primary" onclick="window.ERP.leaveAction(${l.id}, 'approve')">Approve</button>
                           <button class="btn btn-xs btn-danger" onclick="window.ERP.leaveAction(${l.id}, 'reject')">Reject</button>`
                        : ""
                    }
                  </td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  // ---------------------------------------------------------------------------
  // 4. Assignments View
  // ---------------------------------------------------------------------------
  function renderAssignment() {
    const stuAssigns = state.data.assignment.student_assignments.filter(matchesFilter);
    return `
      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">Homework &amp; Student Assignments</div>
          <div class="panel-toolbar">
            <button class="btn btn-primary" onclick="window.ERP.openNewAssignmentModal()">+ Assign Class Homework</button>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Assignment</th>
                <th>Subject</th>
                <th>Class</th>
                <th>Student</th>
                <th class="num">Assign Date</th>
                <th class="num">Due Date</th>
                <th>Type</th>
                <th>State</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${stuAssigns
                .map(
                  (a) => `
                <tr>
                  <td><strong>${esc(a.name)}</strong></td>
                  <td>${esc(a.subject_name)}</td>
                  <td>${esc(a.class_name)}</td>
                  <td>${esc(a.student_name)}</td>
                  <td class="num">${esc(a.assign_date)}</td>
                  <td class="num">${esc(a.due_date)}</td>
                  <td>${esc(a.submission_type)} (${esc(a.attachfile_format || "any")})</td>
                  <td>${badge(a.state)}</td>
                  <td>
                    ${
                      a.state !== "done"
                        ? `<button class="btn btn-xs btn-primary" onclick="window.ERP.assignmentAction(${a.id}, 'done')">Submit &amp; Done</button>
                           <button class="btn btn-xs btn-danger" onclick="window.ERP.assignmentAction(${a.id}, 'reject')">Reject</button>`
                        : ""
                    }
                  </td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  // ---------------------------------------------------------------------------
  // 5. Timetables View
  // ---------------------------------------------------------------------------
  function renderTimetable() {
    const timetables = state.data.timetable.timetables.filter(matchesFilter);
    return timetables
      .map(
        (tt) => `
      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">${esc(tt.name)} — ${esc(tt.class_name)} (${esc(tt.timetable_type.toUpperCase())})</div>
          <div class="panel-toolbar">
            <span class="badge badge-info">${esc(tt.year_name)}</span>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Day / Exam Date</th>
                <th class="num">Start Time</th>
                <th class="num">End Time</th>
                <th>Subject</th>
                <th>Teacher / Supervisor</th>
                <th>Classroom</th>
              </tr>
            </thead>
            <tbody>
              ${(tt.timetable_ids || [])
                .map(
                  (ln) => `
                <tr>
                  <td><strong>${esc(ln.exm_date || ln.week_day)}</strong></td>
                  <td class="num">${Number(ln.start_time).toFixed(2)}</td>
                  <td class="num">${Number(ln.end_time).toFixed(2)}</td>
                  <td>${esc(ln.subject_name)}</td>
                  <td>${esc(ln.teacher_name || "-")}</td>
                  <td>${esc(ln.room_name || "-")}</td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>`
      )
      .join("");
  }

  // ---------------------------------------------------------------------------
  // 6. Exams & Results View
  // ---------------------------------------------------------------------------
  function renderExam() {
    const results = state.data.exam.results.filter(matchesFilter);
    return `
      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">Student Exam Marksheets, Grades &amp; Re-Evaluation</div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Exam</th>
                <th>Student</th>
                <th>Class</th>
                <th>Subject Marks Breakdown</th>
                <th class="num">Total</th>
                <th class="num">Percentage</th>
                <th>Grade</th>
                <th>Result</th>
                <th>State</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${results
                .map(
                  (r) => `
                <tr>
                  <td><strong>${esc(r.exam_name)}</strong> (${esc(r.exam_code)})</td>
                  <td>${esc(r.student_name)}</td>
                  <td>${esc(r.standard_name || "-")}</td>
                  <td>
                    ${(r.subjects || [])
                      .map(
                        (sub) =>
                          `<span style="margin-right:8px;">${esc(sub.subject_name)}: <strong class="num">${
                            r.state.includes("re-evaluation") && sub.marks_reeval > 0
                              ? sub.marks_reeval
                              : sub.obtain_marks
                          }/${sub.maximum_marks}</strong></span>`
                      )
                      .join("")}
                  </td>
                  <td class="num"><strong>${r.total}</strong></td>
                  <td class="num">${Number(r.percentage).toFixed(2)}%</td>
                  <td><strong>${esc(r.grade || "-")}</strong></td>
                  <td>${badge(r.result)}</td>
                  <td>${badge(r.state)}</td>
                  <td>
                    ${
                      r.state === "confirm"
                        ? `<button class="btn btn-xs" onclick="window.ERP.examResultAction(${r.id}, 're_evaluate')">Re-Evaluate</button>
                           <button class="btn btn-xs btn-primary" onclick="window.ERP.examResultAction(${r.id}, 'done')">Mark Done</button>`
                        : ""
                    }
                    ${
                      r.state === "re-evaluation"
                        ? `<button class="btn btn-xs btn-primary" onclick="window.ERP.examResultAction(${r.id}, 're_eval_confirm')">Confirm Re-Eval</button>`
                        : ""
                    }
                  </td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  // ---------------------------------------------------------------------------
  // 7. Library View
  // ---------------------------------------------------------------------------
  function renderLibrary() {
    const books = state.data.library.books.filter(matchesFilter);
    const issues = state.data.library.issues.filter(matchesFilter);
    return `
      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">Library Books Catalog &amp; Live Stock Availability</div>
          <div class="panel-toolbar">
            <button class="btn btn-primary" onclick="window.ERP.openNewBookModal()">+ Add Book</button>
            <button class="btn" onclick="window.ERP.openNewIssueModal()">Issue Book to Card</button>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th class="num">ISBN</th>
                <th>Author</th>
                <th>Rack</th>
                <th class="num">Total Qty</th>
                <th class="num">Available</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              ${books
                .map(
                  (b) => `
                <tr>
                  <td><strong>${esc(b.name)}</strong></td>
                  <td class="num">${esc(b.isbn || "-")}</td>
                  <td>${esc(b.author_name || "-")}</td>
                  <td>${esc(b.rack_name || "-")}</td>
                  <td class="num">${b.qty_available}</td>
                  <td class="num"><strong>${b.books_available}</strong></td>
                  <td>${badge(b.availability)}</td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">Book Issues, Returns, Penalties &amp; Lost Books</div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Issue Code</th>
                <th>Book</th>
                <th>Card / Borrower</th>
                <th class="num">Issue Date</th>
                <th class="num">Due Return</th>
                <th class="num">Penalty</th>
                <th>State</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${issues
                .map(
                  (i) => `
                <tr>
                  <td class="num"><strong>${esc(i.issue_code)}</strong></td>
                  <td>${esc(i.book_name)}</td>
                  <td>${esc(i.card_name)} (${esc(i.card_code)})</td>
                  <td class="num">${esc(i.date_issue)}</td>
                  <td class="num">${esc(i.date_return || "-")}</td>
                  <td class="num">Rs. ${Number(i.penalty + i.lost_penalty).toLocaleString()}</td>
                  <td>${badge(i.state)}</td>
                  <td>
                    ${
                      i.state === "issue" || i.state === "reissue"
                        ? `<button class="btn btn-xs btn-primary" onclick="window.ERP.issueAction(${i.id}, 'return')">Return Book</button>
                           <button class="btn btn-xs" onclick="window.ERP.issueAction(${i.id}, 'reissue')">Reissue</button>
                           <button class="btn btn-xs btn-danger" onclick="window.ERP.issueAction(${i.id}, 'lost')">Lost</button>`
                        : ""
                    }
                    ${
                      i.state === "fine"
                        ? `<button class="btn btn-xs btn-primary" onclick="window.ERP.issueAction(${i.id}, 'pay_fine')">Pay Fine</button>`
                        : ""
                    }
                  </td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  // ---------------------------------------------------------------------------
  // 8. School Events View
  // ---------------------------------------------------------------------------
  function renderEvent() {
    const events = state.data.event.events.filter(matchesFilter);
    const regs = state.data.event.registrations.filter(matchesFilter);
    return `
      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">School Events &amp; Olympiads</div>
          <div class="panel-toolbar">
            <button class="btn btn-primary" onclick="window.ERP.openNewEventModal()">+ Create Event</button>
            <button class="btn" onclick="window.ERP.openNewEventRegModal()">+ Register Student</button>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Event Name</th>
                <th>Type</th>
                <th class="num">Start Date</th>
                <th class="num">End Date</th>
                <th>Contact Teacher</th>
                <th class="num">Registrations</th>
              </tr>
            </thead>
            <tbody>
              ${events
                .map(
                  (e) => `
                <tr>
                  <td><strong>${esc(e.name)}</strong></td>
                  <td>${badge(e.event_type)}</td>
                  <td class="num">${esc(e.start_date)}</td>
                  <td class="num">${esc(e.end_date)}</td>
                  <td>${esc(e.teacher_name || "-")}</td>
                  <td class="num">${e.registration_count}</td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">Event Participant Registrations</div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Event</th>
                <th>Student</th>
                <th>Class</th>
                <th>State</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${regs
                .map(
                  (r) => `
                <tr>
                  <td><strong>${esc(r.event_name)}</strong></td>
                  <td>${esc(r.student_name)} (${esc(r.pid)})</td>
                  <td>${esc(r.standard_name || "-")}</td>
                  <td>${badge(r.state)}</td>
                  <td>
                    ${
                      r.state === "draft"
                        ? `<button class="btn btn-xs btn-primary" onclick="window.ERP.eventRegAction(${r.id}, 'confirm')">Confirm</button>`
                        : `<button class="btn btn-xs btn-danger" onclick="window.ERP.eventRegAction(${r.id}, 'cancel')">Cancel</button>`
                    }
                  </td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  // ---------------------------------------------------------------------------
  // 9. School Hostel View
  // ---------------------------------------------------------------------------
  function renderHostel() {
    const rooms = state.data.hostel.rooms.filter(matchesFilter);
    const residents = state.data.hostel.residents.filter(matchesFilter);
    return `
      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">Hostel Rooms &amp; Bed Availability</div>
          <div class="panel-toolbar">
            <button class="btn btn-primary" onclick="window.ERP.openNewHostelResidentModal()">+ Allocate Hostel Bed</button>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Hostel</th>
                <th>Type</th>
                <th>Room No</th>
                <th class="num">Floor</th>
                <th class="num">Capacity</th>
                <th class="num">Available Beds</th>
                <th class="num">Monthly Rent</th>
              </tr>
            </thead>
            <tbody>
              ${rooms
                .map(
                  (rm) => `
                <tr>
                  <td><strong>${esc(rm.hostel_name)}</strong></td>
                  <td>${badge(rm.hostel_type)}</td>
                  <td class="num"><strong>${esc(rm.room_no)}</strong></td>
                  <td class="num">${rm.floor_no}</td>
                  <td class="num">${rm.student_per_room}</td>
                  <td class="num"><strong>${rm.availability}</strong></td>
                  <td class="num">Rs. ${Number(rm.rent_amount).toLocaleString()}</td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">Hostel Residents &amp; Fee Status</div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Reg Code</th>
                <th>Student</th>
                <th>Hostel &amp; Room</th>
                <th class="num">Admission</th>
                <th class="num">Discharge</th>
                <th class="num">Total Rent</th>
                <th class="num">Remaining</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${residents
                .map(
                  (hs) => `
                <tr>
                  <td class="num"><strong>${esc(hs.hostel_id)}</strong></td>
                  <td>${esc(hs.student_name)} (${esc(hs.pid)})</td>
                  <td>${esc(hs.hostel_name)} — ${esc(hs.room_no)}</td>
                  <td class="num">${esc(hs.admission_date)}</td>
                  <td class="num">${esc(hs.discharge_date)}</td>
                  <td class="num">Rs. ${Number(hs.room_rent).toLocaleString()}</td>
                  <td class="num">Rs. ${Number(hs.remaining_amount).toLocaleString()}</td>
                  <td>${badge(hs.status)}</td>
                  <td>
                    ${
                      hs.status === "reservation" || hs.status === "pending"
                        ? `<button class="btn btn-xs btn-primary" onclick="window.ERP.hostelAction(${hs.id}, 'pay')">Pay Rent</button>`
                        : ""
                    }
                    ${
                      hs.status !== "discharge" && hs.status !== "cancel"
                        ? `<button class="btn btn-xs btn-danger" onclick="window.ERP.hostelAction(${hs.id}, 'discharge')">Discharge</button>`
                        : ""
                    }
                  </td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  // ---------------------------------------------------------------------------
  // 10. School Transport View
  // ---------------------------------------------------------------------------
  function renderTransport() {
    const vehicles = state.data.transport.vehicles.filter(matchesFilter);
    const participants = state.data.transport.participants.filter(matchesFilter);
    return `
      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">Fleet Vehicles &amp; Seat Occupancy</div>
          <div class="panel-toolbar">
            <button class="btn btn-primary" onclick="window.ERP.openNewTransportRegModal()">+ Register Student on Route</button>
            <button class="btn" onclick="window.ERP.openTransferVehicleModal()">Transfer Vehicle Wizard</button>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>License Plate</th>
                <th>Vehicle Model</th>
                <th>Driver Name</th>
                <th class="num">Driver License</th>
                <th class="num">Total Seats</th>
                <th class="num">Occupied Seats</th>
              </tr>
            </thead>
            <tbody>
              ${vehicles
                .map(
                  (v) => `
                <tr>
                  <td class="num"><strong>${esc(v.license_plate)}</strong></td>
                  <td>${esc(v.model_name)}</td>
                  <td>${esc(v.driver_name || "-")}</td>
                  <td class="num">${esc(v.driver_licence_no || "-")}</td>
                  <td class="num">${v.seats}</td>
                  <td class="num"><strong>${v.participant_count}</strong></td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">Active Transport Participants</div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>PID</th>
                <th>Student</th>
                <th>Route</th>
                <th>Vehicle</th>
                <th class="num">Start Date</th>
                <th class="num">End Date</th>
                <th class="num">Fees</th>
                <th>State</th>
              </tr>
            </thead>
            <tbody>
              ${participants
                .map(
                  (tp) => `
                <tr>
                  <td class="num"><strong>${esc(tp.stu_pid_id)}</strong></td>
                  <td>${esc(tp.student_name)}</td>
                  <td>${esc(tp.route_name)}</td>
                  <td>${esc(tp.license_plate)} (${esc(tp.model_name)})</td>
                  <td class="num">${esc(tp.tr_reg_date)}</td>
                  <td class="num">${esc(tp.tr_end_date)}</td>
                  <td class="num">Rs. ${Number(tp.amount).toLocaleString()}</td>
                  <td>${badge(tp.state)}</td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  // ---------------------------------------------------------------------------
  // Interactive Actions & Modals
  // ---------------------------------------------------------------------------
  window.ERP = {
    async studentAction(id, action) {
      try {
        await apiCall(`/api/students/${id}/action`, "POST", { action });
        toast(`Student action '${action}' completed.`);
        await loadBootstrap();
      } catch (err) {
        toast(err.message, "error");
      }
    },

    async payslipAction(id, action) {
      try {
        await apiCall(`/api/fees/payslips/${id}/action`, "POST", { action });
        toast(`Payslip '${action}' completed.`);
        await loadBootstrap();
      } catch (err) {
        toast(err.message, "error");
      }
    },

    async attendanceAction(id, action) {
      try {
        await apiCall(`/api/attendance/daily/${id}/action`, "POST", { action });
        toast(`Attendance '${action}' completed.`);
        await loadBootstrap();
      } catch (err) {
        toast(err.message, "error");
      }
    },

    async leaveAction(id, action) {
      try {
        await apiCall(`/api/attendance/leaves/${id}/action`, "POST", { action });
        toast(`Leave request '${action}' completed.`);
        await loadBootstrap();
      } catch (err) {
        toast(err.message, "error");
      }
    },

    async assignmentAction(id, action) {
      try {
        await apiCall(`/api/assignments/student/${id}/action`, "POST", {
          action,
          submit_assign: "homework_submission.pdf",
          file_name: "homework_submission.pdf",
        });
        toast(`Assignment '${action}' completed.`);
        await loadBootstrap();
      } catch (err) {
        toast(err.message, "error");
      }
    },

    async examResultAction(id, action) {
      try {
        await apiCall(`/api/exam-results/${id}/action`, "POST", { action });
        toast(`Exam result '${action}' completed.`);
        await loadBootstrap();
      } catch (err) {
        toast(err.message, "error");
      }
    },

    async issueAction(id, action) {
      try {
        await apiCall(`/api/library/issues/${id}/action`, "POST", { action });
        toast(`Library book issue '${action}' completed.`);
        await loadBootstrap();
      } catch (err) {
        toast(err.message, "error");
      }
    },

    async eventRegAction(id, action) {
      try {
        await apiCall(`/api/events/registrations/${id}/action`, "POST", { action });
        toast(`Event registration '${action}' completed.`);
        await loadBootstrap();
      } catch (err) {
        toast(err.message, "error");
      }
    },

    async hostelAction(id, action) {
      try {
        await apiCall(`/api/hostel/residents/${id}/action`, "POST", { action });
        toast(`Hostel action '${action}' completed.`);
        await loadBootstrap();
      } catch (err) {
        toast(err.message, "error");
      }
    },

    openNewStudentModal() {
      const d = state.data.school;
      openModal(
        "New Student Admission",
        `
        <div class="form-row">
          <label>First Name</label>
          <input name="student_name" required placeholder="e.g. Ahsan" />
        </div>
        <div class="form-row">
          <label>Middle &amp; Last Name</label>
          <input name="last" required placeholder="e.g. Raza" />
        </div>
        <div class="form-row">
          <label>Date of Birth (Must satisfy School Required Age)</label>
          <input type="date" name="date_of_birth" value="2012-05-15" required />
        </div>
        <div class="form-row">
          <label>Gender</label>
          <select name="gender">
            <option value="male">Male</option>
            <option value="female">Female</option>
          </select>
        </div>
        <div class="form-row">
          <label>Class / Standard</label>
          <select name="standard_id">
            ${d.standards.map((s) => `<option value="${s.id}">${esc(s.display_name)}</option>`).join("")}
          </select>
        </div>
        <div class="form-row">
          <label>Email</label>
          <input type="email" name="email" placeholder="student@greenfield.edu" />
        </div>
        `,
        async (formData) => {
          await apiCall("/api/students", "POST", {
            student_name: formData.get("student_name"),
            middle: "",
            last: formData.get("last"),
            date_of_birth: formData.get("date_of_birth"),
            gender: formData.get("gender"),
            standard_id: Number(formData.get("standard_id")),
            school_id: d.schools[0].id,
            year_id: d.years[0].id,
            email: formData.get("email"),
            auto_admit: true,
          });
          toast("Student admitted and roll number assigned!");
        }
      );
    },

    openAssignRollModal() {
      const d = state.data.school;
      openModal(
        "Assign Roll Numbers Wizard",
        `
        <div class="form-row">
          <label>Class / Standard</label>
          <select name="standard_id">
            ${d.standards.map((s) => `<option value="${s.id}">${esc(s.display_name)}</option>`).join("")}
          </select>
        </div>
        <div class="form-row">
          <label>Medium</label>
          <select name="medium_id">
            ${d.mediums.map((m) => `<option value="${m.id}">${esc(m.name)}</option>`).join("")}
          </select>
        </div>
        `,
        async (formData) => {
          const res = await apiCall("/api/school/assign-roll-no", "POST", {
            standard_id: Number(formData.get("standard_id")),
            medium_id: Number(formData.get("medium_id")),
          });
          toast(`Roll numbers assigned for ${res.updated} students.`);
        }
      );
    },

    openPromoteModal() {
      const d = state.data.school;
      openModal(
        "Move / Promote Standards Wizard",
        `
        <div class="form-row">
          <label>Promote Students From Academic Year</label>
          <select name="academic_year_id">
            ${d.years.map((y) => `<option value="${y.id}">${esc(y.display_name)}</option>`).join("")}
          </select>
        </div>
        `,
        async (formData) => {
          const res = await apiCall("/api/school/move-standards", "POST", {
            academic_year_id: Number(formData.get("academic_year_id")),
          });
          toast(`Promoted ${res.moved} students to next sequenced academic year.`);
        }
      );
    },

    openNewTeacherModal() {
      const d = state.data.school;
      openModal(
        "Add Faculty Teacher",
        `
        <div class="form-row">
          <label>Full Name</label>
          <input name="name" required placeholder="e.g. Prof. Salman Haider" />
        </div>
        <div class="form-row">
          <label>Department</label>
          <input name="department" value="Science &amp; Mathematics" required />
        </div>
        <div class="form-row">
          <label>Work Email</label>
          <input type="email" name="work_email" placeholder="salman@greenfield.edu" />
        </div>
        <div class="form-row">
          <label>Phone</label>
          <input name="phone_numbers" placeholder="0300-5556677" />
        </div>
        `,
        async (formData) => {
          await apiCall("/api/teachers", "POST", {
            name: formData.get("name"),
            department: formData.get("department"),
            work_email: formData.get("work_email"),
            phone_numbers: formData.get("phone_numbers"),
            school_id: d.schools[0].id,
          });
          toast("Teacher created!");
        }
      );
    },

    openNewPayslipModal() {
      const students = state.data.school.students.filter((s) => s.state === "done");
      const structs = state.data.fees.structures;
      const today = new Date().toISOString().slice(0, 10);
      openModal(
        "Generate Student Fee Payslip",
        `
        <div class="form-row">
          <label>Student</label>
          <select name="student_id">
            ${students.map((s) => `<option value="${s.id}">${esc(s.student_name)} (${esc(s.pid)})</option>`).join("")}
          </select>
        </div>
        <div class="form-row">
          <label>Fee Structure</label>
          <select name="fees_structure_id">
            ${structs.map((st) => `<option value="${st.id}">${esc(st.name)} (Rs. ${st.total_amount})</option>`).join("")}
          </select>
        </div>
        <div class="form-row">
          <label>Description</label>
          <input name="name" value="Monthly Tuition Fee Slip" required />
        </div>
        <div class="form-row">
          <label>Slip Date</label>
          <input type="date" name="date" value="${today}" required />
        </div>
        `,
        async (formData) => {
          await apiCall("/api/fees/payslips", "POST", {
            student_id: Number(formData.get("student_id")),
            fees_structure_id: Number(formData.get("fees_structure_id")),
            name: formData.get("name"),
            date: formData.get("date"),
          });
          toast("Payslip generated and confirmed!");
        }
      );
    },

    openNewAttendanceModal() {
      const d = state.data.school;
      const today = new Date().toISOString().slice(0, 10);
      openModal(
        "Create Daily Attendance Roll Call",
        `
        <div class="form-row">
          <label>Class / Standard</label>
          <select name="standard_id">
            ${d.standards.map((s) => `<option value="${s.id}">${esc(s.display_name)}</option>`).join("")}
          </select>
        </div>
        <div class="form-row">
          <label>Teacher</label>
          <select name="user_id">
            ${d.teachers.map((t) => `<option value="${t.id}">${esc(t.name)}</option>`).join("")}
          </select>
        </div>
        <div class="form-row">
          <label>Date (Must be &lt;= Today)</label>
          <input type="date" name="date" value="${today}" required />
        </div>
        `,
        async (formData) => {
          await apiCall("/api/attendance/daily", "POST", {
            standard_id: Number(formData.get("standard_id")),
            user_id: Number(formData.get("user_id")),
            date: formData.get("date"),
          });
          toast("Daily attendance sheet generated!");
        }
      );
    },

    openNewLeaveModal() {
      const students = state.data.school.students.filter((s) => s.state === "done");
      const today = new Date().toISOString().slice(0, 10);
      openModal(
        "New Student Leave Request",
        `
        <div class="form-row">
          <label>Leave Title / Reason</label>
          <input name="name" required placeholder="e.g. Medical Appointment" />
        </div>
        <div class="form-row">
          <label>Student</label>
          <select name="student_id">
            ${students.map((s) => `<option value="${s.id}">${esc(s.student_name)} (${esc(s.pid)})</option>`).join("")}
          </select>
        </div>
        <div class="form-row">
          <label>Start Date</label>
          <input type="date" name="start_date" value="${today}" required />
        </div>
        <div class="form-row">
          <label>End Date</label>
          <input type="date" name="end_date" value="${today}" required />
        </div>
        `,
        async (formData) => {
          await apiCall("/api/attendance/leaves", "POST", {
            name: formData.get("name"),
            student_id: Number(formData.get("student_id")),
            start_date: formData.get("start_date"),
            end_date: formData.get("end_date"),
          });
          toast("Leave request created!");
        }
      );
    },

    openNewAssignmentModal() {
      const d = state.data.school;
      const today = new Date().toISOString().slice(0, 10);
      openModal(
        "Assign Class Homework (Fan-out to All Class Students)",
        `
        <div class="form-row">
          <label>Assignment Title</label>
          <input name="name" required placeholder="e.g. Chapter 5 Programming Lab" />
        </div>
        <div class="form-row">
          <label>Class / Standard</label>
          <select name="standard_id">
            ${d.standards.map((s) => `<option value="${s.id}">${esc(s.display_name)}</option>`).join("")}
          </select>
        </div>
        <div class="form-row">
          <label>Subject</label>
          <select name="subject_id">
            ${d.subjects.map((sub) => `<option value="${sub.id}">${esc(sub.name)}</option>`).join("")}
          </select>
        </div>
        <div class="form-row">
          <label>Teacher</label>
          <select name="teacher_id">
            ${d.teachers.map((t) => `<option value="${t.id}">${esc(t.name)}</option>`).join("")}
          </select>
        </div>
        <div class="form-row">
          <label>Assign Date</label>
          <input type="date" name="assign_date" value="${today}" required />
        </div>
        <div class="form-row">
          <label>Due Date</label>
          <input type="date" name="due_date" value="${today}" required />
        </div>
        `,
        async (formData) => {
          await apiCall("/api/assignments/teacher", "POST", {
            name: formData.get("name"),
            standard_id: Number(formData.get("standard_id")),
            subject_id: Number(formData.get("subject_id")),
            teacher_id: Number(formData.get("teacher_id")),
            assign_date: formData.get("assign_date"),
            due_date: formData.get("due_date"),
            type_submission: "hardcopy",
            auto_activate: true,
          });
          toast("Homework assigned and distributed to class students!");
        }
      );
    },

    openNewBookModal() {
      const lib = state.data.library;
      openModal(
        "Add New Library Book",
        `
        <div class="form-row">
          <label>Book Title</label>
          <input name="name" required placeholder="e.g. Clean Architecture" />
        </div>
        <div class="form-row">
          <label>Unique ISBN</label>
          <input name="isbn" required placeholder="e.g. 978-0-13-449416-6" />
        </div>
        <div class="form-row">
          <label>Quantity Available</label>
          <input type="number" name="qty_available" value="4" min="1" required />
        </div>
        `,
        async (formData) => {
          await apiCall("/api/library/books", "POST", {
            name: formData.get("name"),
            isbn: formData.get("isbn"),
            qty_available: Number(formData.get("qty_available")),
            author_id: lib.authors[0]?.id,
            rack_id: lib.racks[0]?.id,
          });
          toast("Book added to Library catalog!");
        }
      );
    },

    openNewIssueModal() {
      const lib = state.data.library;
      openModal(
        "Issue Library Book to Card",
        `
        <div class="form-row">
          <label>Book</label>
          <select name="book_id">
            ${lib.books.map((b) => `<option value="${b.id}">${esc(b.name)} (Avail: ${b.books_available})</option>`).join("")}
          </select>
        </div>
        <div class="form-row">
          <label>Library Card</label>
          <select name="card_id">
            ${lib.cards.map((c) => `<option value="${c.id}">${esc(c.card_name)} (${esc(c.code)})</option>`).join("")}
          </select>
        </div>
        `,
        async (formData) => {
          await apiCall("/api/library/issues", "POST", {
            book_id: Number(formData.get("book_id")),
            card_id: Number(formData.get("card_id")),
            auto_issue: true,
          });
          toast("Book issued and stock updated!");
        }
      );
    },

    openNewEventModal() {
      const today = new Date().toISOString().slice(0, 10);
      openModal(
        "Create School Event",
        `
        <div class="form-row">
          <label>Event Name</label>
          <input name="name" required placeholder="e.g. Inter-School Coding Hackathon" />
        </div>
        <div class="form-row">
          <label>Event Type</label>
          <select name="event_type">
            <option value="intra">Intra-School</option>
            <option value="inter">Inter-School</option>
          </select>
        </div>
        <div class="form-row">
          <label>Start Date</label>
          <input type="date" name="start_date" value="${today}" required />
        </div>
        <div class="form-row">
          <label>End Date</label>
          <input type="date" name="end_date" value="${today}" required />
        </div>
        `,
        async (formData) => {
          await apiCall("/api/events", "POST", {
            name: formData.get("name"),
            event_type: formData.get("event_type"),
            start_date: formData.get("start_date"),
            end_date: formData.get("end_date"),
          });
          toast("School event created!");
        }
      );
    },

    openNewEventRegModal() {
      const events = state.data.event.events;
      const students = state.data.school.students.filter((s) => s.state === "done");
      openModal(
        "Register Student in Event",
        `
        <div class="form-row">
          <label>Event</label>
          <select name="event_id">
            ${events.map((e) => `<option value="${e.id}">${esc(e.name)}</option>`).join("")}
          </select>
        </div>
        <div class="form-row">
          <label>Student</label>
          <select name="part_name_id">
            ${students.map((s) => `<option value="${s.id}">${esc(s.student_name)} (${esc(s.pid)})</option>`).join("")}
          </select>
        </div>
        `,
        async (formData) => {
          await apiCall("/api/events/registrations", "POST", {
            event_id: Number(formData.get("event_id")),
            part_name_id: Number(formData.get("part_name_id")),
            auto_confirm: true,
          });
          toast("Student registered for event!");
        }
      );
    },

    openNewHostelResidentModal() {
      const h = state.data.hostel;
      const students = state.data.school.students.filter((s) => s.state === "done");
      openModal(
        "Allocate Hostel Room to Student",
        `
        <div class="form-row">
          <label>Student</label>
          <select name="student_id">
            ${students.map((s) => `<option value="${s.id}">${esc(s.student_name)} (${esc(s.gender)})</option>`).join("")}
          </select>
        </div>
        <div class="form-row">
          <label>Hostel</label>
          <select name="hostel_info_id">
            ${h.hostels.map((ht) => `<option value="${ht.id}">${esc(ht.name)} (${esc(ht.type)})</option>`).join("")}
          </select>
        </div>
        <div class="form-row">
          <label>Room</label>
          <select name="room_id">
            ${h.rooms.map((rm) => `<option value="${rm.id}">${esc(rm.room_no)} (Avail: ${rm.availability})</option>`).join("")}
          </select>
        </div>
        <div class="form-row">
          <label>Duration (Months)</label>
          <input type="number" name="duration" value="6" min="1" required />
        </div>
        `,
        async (formData) => {
          await apiCall("/api/hostel/residents", "POST", {
            student_id: Number(formData.get("student_id")),
            hostel_info_id: Number(formData.get("hostel_info_id")),
            room_id: Number(formData.get("room_id")),
            duration: Number(formData.get("duration")),
            auto_reserve: true,
          });
          toast("Hostel room reserved!");
        }
      );
    },

    openNewTransportRegModal() {
      const tr = state.data.transport;
      const students = state.data.school.students.filter((s) => s.state === "done");
      openModal(
        "Register Student on Transport Route",
        `
        <div class="form-row">
          <label>Student</label>
          <select name="student_id">
            ${students.map((s) => `<option value="${s.id}">${esc(s.student_name)} (${esc(s.pid)})</option>`).join("")}
          </select>
        </div>
        <div class="form-row">
          <label>Transport Route</label>
          <select name="route_id">
            ${tr.routes.map((r) => `<option value="${r.id}">${esc(r.name)} (Rs. ${r.amount}/mo)</option>`).join("")}
          </select>
        </div>
        <div class="form-row">
          <label>Vehicle</label>
          <select name="vehicle_id">
            ${tr.vehicles.map((v) => `<option value="${v.id}">${esc(v.license_plate)} (${v.participant_count}/${v.seats} seats)</option>`).join("")}
          </select>
        </div>
        <div class="form-row">
          <label>Months</label>
          <input type="number" name="registration_month" value="2" min="1" required />
        </div>
        `,
        async (formData) => {
          await apiCall("/api/transport/registrations", "POST", {
            student_id: Number(formData.get("student_id")),
            route_id: Number(formData.get("route_id")),
            vehicle_id: Number(formData.get("vehicle_id")),
            registration_month: Number(formData.get("registration_month")),
            auto_confirm: true,
          });
          toast("Student registered on transport vehicle!");
        }
      );
    },

    openTransferVehicleModal() {
      const tr = state.data.transport;
      openModal(
        "Transfer Vehicle Wizard (transfer.vehicle)",
        `
        <div class="form-row">
          <label>Active Transport Participant</label>
          <select name="participant_id">
            ${tr.participants
              .map(
                (p) =>
                  `<option value="${p.id}">${esc(p.student_name)} — Current: ${esc(p.license_plate)}</option>`
              )
              .join("")}
          </select>
        </div>
        <div class="form-row">
          <label>Target Vehicle</label>
          <select name="new_vehicle_id">
            ${tr.vehicles
              .map(
                (v) =>
                  `<option value="${v.id}">${esc(v.license_plate)} (${v.participant_count}/${v.seats} seats)</option>`
              )
              .join("")}
          </select>
        </div>
        `,
        async (formData) => {
          await apiCall("/api/transport/transfer-vehicle", "POST", {
            participant_id: Number(formData.get("participant_id")),
            new_vehicle_id: Number(formData.get("new_vehicle_id")),
          });
          toast("Participant transferred to new vehicle!");
        }
      );
    },
  };

  // ---------------------------------------------------------------------------
  // ---------------------------------------------------------------------------
  // Strangler-Fig Legacy Bridge (Phase 1)
  // Exposes legacy tab renderers & modal actions to the new ES module shell
  // ---------------------------------------------------------------------------
  window.ERP_LEGACY = {
    setData(bootstrapData) {
      state.data = bootstrapData;
    },
    renderTab(tabName, bootstrapData) {
      if (bootstrapData) state.data = bootstrapData;
      state.tab = tabName;
      if (!state.data) {
        return '<div class="panel"><div class="panel-body">Loading...</div></div>';
      }
      switch (tabName) {
        case "dashboard":  return renderDashboard();
        case "fees":       return renderFees();
        case "assignment": return renderAssignment();
        case "timetable":  return renderTimetable();
        case "exam":       return renderExam();
        case "library":    return renderLibrary();
        case "event":      return renderEvent();
        case "hostel":     return renderHostel();
        case "transport":  return renderTransport();
        default:           return renderDashboard();
      }
    },
  };
})();
