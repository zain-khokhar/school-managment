# ADVANCEMENT_PLAN — School Management ERP ko Enterprise-Grade banane ka Evidence-Based Plan

> **Status:** PLAN ONLY (v2, revised). Koi source code nahi badla gaya. Aapki approval ka intezar hai.
> **Zaban:** Roman Urdu (technical terms, file names, identifiers English mein).
> **Tareekh:** 2026-11-06 | **Repo:** `E:\Projects\school-managment` | **Git HEAD:** `09e89d9`

---

## Table of Contents

1. [Is document ke baare mein (v1 se kya badla)](#1-is-document-ke-baare-mein)
2. [Meri samajh (6-8 lines)](#2-meri-samajh)
3. [Code Audit — sirf verified evidence](#3-code-audit--sirf-verified-evidence)
4. [School ek organization ke taur par](#4-school-ek-organization-ke-taur-par)
5. [Research aur Benchmark](#5-research-aur-benchmark)
6. [Gap Analysis table](#6-gap-analysis-table)
7. [Signature Ideas (Pakistani school ke liye)](#7-signature-ideas-pakistani-school-ke-liye)
8. [Offline vs Internet — saaf strategy](#8-offline-vs-internet--saaf-strategy)
9. [Design Direction](#9-design-direction)
10. [Technical Approach](#10-technical-approach)
11. [Phased Roadmap (realistic)](#11-phased-roadmap-realistic)
12. [Verification Plan](#12-verification-plan)
13. [Honest Comparison with Odoo](#13-honest-comparison-with-odoo)
14. [Risks aur Open Decisions](#14-risks-aur-open-decisions)
15. [Self-Check Checklist](#15-self-check-checklist)
16. [Top 10 things to do first](#16-top-10-things-to-do-first)

---

## 1. Is document ke baare mein

### 1.1 File ka naam

Pehla plan `ENTERPRISE_PLAN.md` ke naam se artifact folder mein save hua tha, project root mein nahi. Ab ek hi master file hai: **`ADVANCEMENT_PLAN.md`** (project root). `ENTERPRISE_PLAN.md` ab **superseded** hai, usay ignore karein.

### 1.2 v1 mein kya ghalat ya unverified tha (imandari se)

| # | v1 ka claim | Asal haal (code se verified) | Saboot |
|---|---|---|---|
| 1 | "Dashboard sirf placeholder cards hain" | Dashboard par 4 **real** KPI cards aur ek students table hai. Charts, alerts aur trends nahi hain. Yaani "placeholder" ghalat tha, "thin" sahi hai. | `desktop_app/ui/app.js:165-248`, `school_service.py:1260-1293` |
| 2 | "Database mein indexes nahi hain" | **10 indexes maujood hain.** Yeh claim bilkul ghalat tha. | `desktop_app/database.py:836-845` |
| 3 | "Odoo offline nahi, hamara offline hai (Odoo = cloud only)" | Ghalat. Is repo mein khud Odoo 18 local chalane ka setup hai. Odoo on-premise ho sakta hai. Hamara asal farq "ek `.exe` jo bina server ke chale" hai. | `docker-compose.yml`, `odoo.conf` |
| 4 | "Parent Portal in-app view" | Server sirf `127.0.0.1` par bind hai, to parents/phones usay reach hi nahi kar sakte. Is conflict ko v1 ne ignore kiya. | `run_desktop.py` (`make_server("127.0.0.1", ...)`), `api.py:57-62` |
| 5 | "Mobile/tablet responsive hoga" | Current CSS mein **ek bhi `@media` rule nahi** (na print ke liye). Responsive "improve" nahi, **naya** kaam hai. | `desktop_app/ui/styles.css` (grep: 0 `@media`) |
| 6 | "WhatsApp Business API (Twilio/WATI)" | Bina research ke likha tha. Cost, approval aur internet dependency nazar-andaaz thi. Section 8 mein sahi approach hai. | Section 8 |
| 7 | "Odoo Education = ~\$400/user/year" | Odoo ka Standard plan ≈ **\$31.10/user/month** (≈ \$373/year), Custom ≈ **\$61/user/month** (≈ \$732/year). Yeh figures third-party sites se hain, odoo.com se directly verify nahi hui. Odoo ke paas "Education app" nahi, OpenEduCat jaisa alag ecosystem hai. | Section 5.1 |
| 8 | "6-8 hafte" | Unrealistic. Section 11.3 mein hisaab hai. | Section 11 |
| 9 | Odoo comparison mein "Full ✅" ticks | Zyada tar ticks bina scoring ke the. Ab har area ka score hai. | Section 13 |
| 10 | "Koi Settings panel nahi / Student 360 nahi" | **Sahi tha.** Sidebar mein 11 hi entries hain, koi Settings nahi. Student detail screen bhi nahi. | `desktop_app/ui/index.html` (11 `data-tab`), `app.js` (koi detail view nahi) |

### 1.3 Meri assumptions (agar ghalat hon to bata dein)

| ID | Assumption | Kyun |
|---|---|---|
| **A1** | **Asal product `desktop_app/` hai** (Flask + SQLite + `.exe`), aur `school/ exam/ school_fees/ ...` (Odoo 18 addons) "server edition" ya reference model hain. UI/UX ka kaam pehle `desktop_app/ui/` mein hoga. | `SchoolManagementERP.spec` `run_desktop.py` ko `.exe` banata hai; Odoo is machine par installed nahi (`import odoo` fail), is liye wahan kuch test nahi ho sakta. Desktop ke 11 tests pass hote hain. |
| **A2** | Target school: 300 se 1500 students, 1 campus, 1 se 3 computers (kuch purane), internet kabhi aata kabhi jata. | Pakistani private school ka typical size (andaaza, verify nahi). |
| **A3** | Staff ki zaban mix hai: Urdu bolte hain, English UI aur Urdu print dono chahiye. | Section 7 aur 9. |
| **A4** | Currency PKR, academic year Apr-Mar ya Aug-Jul dono ho sakte hain (configurable). | School-specific. |

### 1.4 Aap ke faisle ke liye 3 sawal (blocker nahi, magar plan inhi par tikta hai)

1. **D1:** Kya A1 theek hai (desktop_app primary)? Agar aap ka maqsad Odoo addons ko enterprise banana hai, to plan ka 60% badal jayega.
2. **D2:** Kya ek hi computer par chalne wala "single-PC edition" kaafi hai, ya shuru se school ke **LAN** (2-3 PC aur teachers ke phones) chahiye? Section 8 dono ka raasta batata hai.
3. **D3:** Kya Urdu UI (RTL) pehle release mein chahiye, ya pehle sirf Urdu **prints** (voucher, report card)? Meri recommendation: pehle prints.

---

## 2. Meri samajh

1. Aap ek **intermediate** school software ko aisa product banana chahte hain jo ek paid Odoo-level product jaisa premium lage, magar uski **apni pehchaan** ho (copy nahi).
2. Asli test technical nahi, insani hai: ek **teacher, fee clerk ya principal** bina training ke use kar sake.
3. Sirf achha dikhna kaafi nahi: software school ki **productivity** barhaye. Yaani data ek baar enter ho, kaam khud ho, aur "kya zaroori hai" khud samne aaye.
4. Purani kaam ki cheezein (modules, tests, folder structure, coding pattern) **barqarar** rahein. Naya kaam usi structure mein fit ho, **koi monolithic file na ho**, aur performance (pagination, lazy loading) ka khayal ho.
5. Har feature par 3 sawal ka jawab chahiye: school ka kaunsa insaan, kaunsa kaam tez ya ghalti-mukt, aur hum naap kaise karenge.
6. Plan **evidence-based** ho: har baat kisi asli file se, aur jo verify na ho wo saaf likha ho. Imandaar comparison, khaas kar Odoo (~\$400) ke saath.
7. Abhi sirf **plan** chahiye. Code ko haath nahi lagana, aur implementation se pehle aap ki approval chahiye.

---

## 3. Code Audit — sirf verified evidence

> Har point ke saath file reference hai. **Verify nahi hua** wali cheezein 3.7 mein alag likhi hain.

### 3.1 Tech stack aur folder structure

| Hissa | Kya hai | Saboot |
|---|---|---|
| Odoo addons | 10 modules: `school`, `school_fees`, `school_attendance`, `assignment`, `timetable`, `exam`, `library`, `school_event`, `school_hostel`, `school_transport`. 9 modules version `18.0.1.0.0` hain; **`library` version `17.0.1.0.0` hai** (`library/__manifest__.py:5`). | har module ka `__manifest__.py` |
| Module dependencies | `school` depends on `hr, crm, account`. `exam` depends on `school, timetable`. `school_fees`, `assignment`, `timetable`, `school_hostel` depend on `school`. `school_attendance` depends on `school, hr`. `library` depends on `school, stock, delivery, purchase`. `school_event` depends on `school, event`. `school_transport` depends on `school, fleet`. | manifests |
| Desktop app | Flask + SQLite (WAL) + vanilla JS, `pywebview` window, PyInstaller `.exe`. | `run_desktop.py`, `requirements.txt`, `SchoolManagementERP.spec` |
| Desktop structure | `desktop_app/{api.py, database.py, exceptions.py, services/, ui/}`; services: ek class per module (`SchoolService`, `FeesService`, ...). | `desktop_app/` listing |
| UI | `ui/index.html` (CSP `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;`), `ui/app.js` (**1752 lines**), `ui/styles.css` (**516 lines**). | `index.html:6` meta CSP; line counts |
| Tests | `tests/test_all_modules.py` (**11 tests, sab pass: 11 passed in 16.90s**); har Odoo module mein apna `tests/`. | maine `pytest tests -q` chalaya |
| DevOps | `docker-compose.yml` (postgres:16 + odoo:18.0), `odoo.conf`. | files |
| Docs | `README.md` mein sirf ek line: `# school-managment`. | `README.md` |

### 3.2 Do products ek repo mein

| | **Odoo addons (10 modules)** | **desktop_app** |
|---|---|---|
| Models | `student.student`, `school.teacher`, `school.parent`, `school.standard`, `academic.year`, `student.certificate`, `student.document`, ... (29 `_name` models sirf `school/models/school.py` mein, plus `student.py`, `teacher.py`, `parent.py`) | 69 SQLite tables (`database.py` `SCHEMA_SQL`, 69 `CREATE TABLE IF NOT EXISTS`) |
| UI | form/list/kanban views (XML) | 11-tab vanilla JS app |
| Roles | 5 groups: Administrator, Teacher, Student, Parent, In Admission + record rules | **Koi login ya role nahi.** |
| Reports | 21 report XML files (ID card, leaving certificate, payslip, fees register, exam result, timetable, hostel receipt...) | **Koi print/PDF nahi** (`window.print` = 0 hits; sirf ek Excel export `/api/attendance/export-xlsx`) |
| Runnable yahan? | **Nahi** (`import odoo` fail, Odoo installed nahi) | **Haan**, tests pass |

Saboot: `school/security/school_security.xml` (groups, rules), `*/report/*.xml`, `database.py`, `app.js`.

### 3.3 Modules, pages, roles, flows (desktop UI)

* **11 sidebar tabs:** Dashboard + 10 modules (`index.html`, `data-tab`). Naam "1. School & Students", "2. School Fees" jaise numbered technical labels.
* **15 "New ..." modals** (`app.js`: `openNewStudentModal` ... `openTransferVehicleModal`).
* **25 API URLs UI se call hote hain** (`app.js` ke `apiCall(...)`), magar **backend mein 5 routes aur 2 service-level features aise hain jin ka UI hi nahi** (baqi 2 unmatched routes: `/api/health` infra hai, `export-xlsx` link se use hota hai):

| Backend route / service | UI mein? | Asar |
|---|---|---|
| `POST /api/exams`, `/api/exams/<id>/action` | Nahi | UI se exam banta hi nahi |
| `POST /api/exam-subjects/<id>` (marks update) | Nahi | **Teacher UI se marks enter nahi kar sakta** |
| `POST /api/timetables` | Nahi | Timetable sirf seed data se dikhta hai |
| `POST /api/library/cards` | Nahi | Library card UI se nahi banta |
| `POST /api/transport/registrations/<id>/action` | Nahi | Transport state change UI se nahi |
| `AttendanceService.action_present / action_absent` | **Route hi nahi** (`api.py` mein exposed nahi) | **Teacher UI se absent mark nahi kar sakta.** Sheet banti hai to default **sab present**; absent sirf pehle se approved leave se hota hai (`attendance_service.py:214-215`). |
| `FeesService.create_fees_register` / `fees_register_confirm` (class-wise bulk billing) | **Route aur UI nahi** (`fees_service.py:144-246` aur `list_fees_registers` `api.py:110` mein hain, magar `api.py` mein `POST` route aur `app.js` mein UI nahi) | Service logic tayyar hai, magar UI na hone se ek class ke 40 bachon ki fee = 40 baar modal |

> Yeh sab se bara audit finding hai: **UI wo kaam hi nahi karta jo school ka rozmarra hai.**

### 3.4 Measurements (maine khud chalaya, temp DB par, source nahi badla)

| Test | Result |
|---|---|
| `pytest tests -q` | **11 passed in 16.90s** |
| `/api/bootstrap`, 3 students (seed data) | **~334 ms, 24 KB** |
| `/api/bootstrap`, ~200 students | **~850-1270 ms, 179 KB** |
| `/api/bootstrap`, ~1000 students | **~5.4-5.8 sec, 800 KB** (har baar) |
| Ek student admit karna (create + admission_done) | ~0.1 sec/student (800 students = 79.7 sec) |

**Kyun yeh bara masla hai:** `app.js` har save/action ke baad `loadBootstrap()` dobara chalata hai (`app.js:1743`, aur har action handler). Yaani 1000 students wale school mein **har click ke baad ~5 sec ka intezar.** Aur `matchesFilter` har row ko `JSON.stringify` karke search karta hai (`app.js:99-103`), aur har keystroke par poora tab dobara render hota hai (`app.js:1725-1728`).

> Note: yeh timing mere computer par hai, school ke purane PC par aur buri hogi. Phase 0 mein purane PC par dobara naapna hai.

### 3.5 Kya achha hai, kya kamzor, kya missing

**Achha hai (rakhna hai):**

| Cheez | Saboot | Kyun achhi |
|---|---|---|
| Service-class-per-module pattern | `desktop_app/services/*.py` | Saaf separation. Naya kaam isi pattern par. |
| Business rules (seat limit, unique attendance, overlap check, leave to absent auto-sync) | `school_service.py` (`Seats of class ... are full`), `attendance_service.py:158-167, 202-215`, `timetable_service.py:118-144` | Odoo se aaye rules mehfooz. |
| SQLite WAL, foreign keys, 10 indexes | `database.py:836-845, 879-911` | Foundation theek hai. |
| Localhost-only server + Host check | `run_desktop.py`, `api.py:57-62` | Default mein safe. |
| Tabular numerals, CSS variables, toast, `esc()` XSS escape | `styles.css:2-53`, `app.js:26-56` | Achhi buniyaad. |
| Odoo reports (ID card, certificates, payslip, timetable, result) | `*/report/*.xml` | Re-use ho sakte hain. |
| Test suite + `--self-test` flag | `tests/`, `run_desktop.py:run_self_test` | Regression safety. |

**Kamzor:**

| Cheez | Saboot | Asar |
|---|---|---|
| `app.js` ek monolith (1752 lines, sab 11 modules + modals + state) | `app.js` | Maintain/test mushkil. Rules ka 800-line ceiling toota hua. |
| Dusri badi files: `school_service.py` (1,294 lines), `database.py` (964), `api.py` (614); Odoo XML views bhi bade (`library_view.xml` ~1.7K, `student_view.xml` ~1.5K) | line counts | Split chahiye (XML view files par rule narm, magar >1000 par bhi dekhna). |
| Sab data ek `bootstrap` call mein, koi pagination nahi | `api.py:87-153` | Section 3.4. |
| `renderSchool()` apne andar `renderDashboard()` bhi render karta hai (duplicate students table) | `app.js:253-258` | Faltu render + confusing page. |
| Hard-coded values: `school_id = d.schools[0].id`, `year_id = d.years[0].id`, DOB default `2012-05-15`, middle name discard (`middle: ""`) | `app.js:1196-1208` | Ghalat year/school assign hone ka khatra; DOB default se galat data. |
| Assignment submit mein **fake file naam** `homework_submission.pdf` hard-coded | `app.js:1107-1113` | Asal submission nahi, sirf demo. |
| Student/fee selector 1000-option `<select>` dropdown | `app.js:1307-1309` | Search ke bina use na-mumkin. |
| `payslip` mein `due_date` column hi nahi | `database.py:330-349` | **"Defaulter kitne din se"** compute nahi ho sakta. |
| Exam mein **rank/position** nahi (0 grep hits) | `exam_service.py`, `database.py` | Report card ka core part missing. |
| Koi **late fee, discount, sibling concession, installment, voucher/challan** (grep: sirf library `penalty`) | `school_fees.py`, `fees_service.py`, `database.py` | Pakistani fee flow ka core missing. |
| Koi WhatsApp/SMS/notification (grep mein sirf `school.py:1108` ek message string) | grep | Parents se rabta manual. |
| Koi login/role/audit-log/backup/migration/schema-version (grep) | `desktop_app/` | Data safety aur accountability zero. `ALTER TABLE` / `user_version` / `backup` ka koi code nahi. |
| 500 error par `str(exc)` client ko jata hai | `api.py:72-74` | Internal details leak. |
| Accessibility: sirf ek `:focus` rule (search box), koi `aria-*`/`role`/`tabindex`/keyboard shortcut | `styles.css:217`, `app.js` (0 hits) | Keyboard/screen-reader use nahi. |
| Chhote fonts (11-12.5px table/button) | `styles.css:102,144,155,193,245,260,313,342,374,399,463` | Poora din dekhne walon (40+ saal ke staff) ke liye thaka dene wala. |
| UI mein tech jargon: "10-Module SQLite Engine", "SQLite WAL Mode • Offline Ready", "100% Domain Logic Active" | `index.html:18, 92, 102` | Staff ko iski zaroorat nahi, trust nahi barhata. |
| Odoo vocabulary: "Payslip", "Standard", "PID", "Validate & Sync Sheet", "Reset to Draft", "Pay Full" | `app.js:205, 261, 340, 383, 441-442, 1186, 1220, 1345` | Pakistani school mein "Fee Voucher", "Class", "GR No", "Submit" bolte hain. |
| Empty/loading/error states: sirf ek "Loading SQLite WAL Engine..." jab data nil ho; khaali table par koi message nahi | `app.js:120-123`, har `render*` | Naya user ko pata nahi chalta kya karna hai. |
| `odoo.conf`: `addons_path` kisi aur ke Downloads folder ka (`c:\Users\Axtron content\Downloads\school managment`), `admin_passwd = admin` | `odoo.conf` | Stale path + kamzor master password. |
| Odoo views mein **0 graph, 0 pivot, 0 dashboard**, calendar sirf exam mein (2) | view-type scan, `*/views/*.xml` | Analytics poori missing. |
| Translations (`i18n`) sirf `library` mein (fr, ru, sv). **Urdu kahin nahi.** | `library/i18n/` | Urdu support zero. |
| Responsive/print CSS: 0 `@media` | `styles.css` | Tablet aur print dono nahi. |

**Missing (naya banana hai):** Section 6 ki table mein tafseel.

### 3.6 Odoo-side par kya verify nahi hua

Odoo environment yahan nahi hai, is liye mene Odoo views/reports ko sirf **padha aur count kiya**, chalaya nahi. Jo bhi "Odoo side par kaam karta hai" wo **unverified** hai (3.7).

### 3.7 Jo main verify nahi kar saka

1. Odoo addons install/run honge ya nahi (Odoo nahi hai).
2. Odoo-side attendance form (`school_attendance/views/school_attendance_view.xml`) mein `action_present`/`action_absent` aur `is_present`/`is_absent` XML mein maujood hain (verified), magar Odoo runtime na hone se uska live behavior run karke verify nahi kiya.
3. School ke asli staff ki raaye, kaam ka waqt, school ka size (assumption A2).
4. Seed data sirf 3 students ka hai, is liye real-world data quality (Urdu naam, duplicate naam) test nahi hui.
5. Odoo ki sahi qeematein odoo.com se (sirf secondary sources mile).
6. `pywebview` purane Windows 7/8 par chalta hai ya nahi, aur RTL Urdu usmein theek render hoti hai ya nahi.
7. PyInstaller `.exe` ka asli size/startup time (mene build nahi kiya).

---

## 4. School ek organization ke taur par

> **Imandari ka note:** is section ke "waqt" wale andaaze **assumptions** hain (mere general ilm se), kisi school se naape nahi gaye. Phase 0 mein 2-3 asli school staff ke saath stopwatch se **baseline** naapna zaroori hai (Section 12). Jo cheezein code se verified hain unke saath file reference hai.

### 4.1 Users aur unka asli kaam

| Role | Kaun | Ek line mein asli kaam | Abhi software mein? |
|---|---|---|---|
| **Principal / Admin** | Principal, owner, vice-principal | Roz ek nazar mein school ki haalat; fees ki wasooli; staff ki haziri; faisley | Sirf 4 KPI cards (`app.js:165-190`); koi role/login nahi |
| **Class Teacher** | Apni class ka ustaad | Roz haziri; absent bachon ke gharon se rabta; class ka result | Haziri **mark nahi ho sakti** (3.3) |
| **Subject Teacher** | Mazmoon ka ustaad | Homework dena/check karna; paper ke marks dena | Marks entry UI nahi; assignment fake submit (3.5) |
| **Accounts / Fee clerk** | Counter par baithne wala | Fee wasool karna, receipt dena, baqaya (defaulters) ki list, month-end hisaab | Ek-ek student ka modal; receipt nahi; due date nahi |
| **Front desk / Admissions** | Reception | Inquiry, admission form, documents, class ki seat, ID card | 6-field modal; guardian/CNIC/documents nahi |
| **Exam in-charge** | Exam coordinator | Date sheet, paper schedule, marks collection, result, report card, rank | Exam UI se banta nahi; marks entry nahi; rank nahi |
| **Parent** | Walid/Walida/Guardian | Bache ki haziri, fee, result, notice; PTM mein jana | **Koi access nahi** |
| **Student** | Talib-e-ilm | Time table, homework, result | Koi access nahi (Odoo `group_school_student` hai, desktop mein nahi) |
| **IT / Owner** (bonus) | School ka mushtarik admin | Backup, users, settings | Koi settings/backup nahi |

### 4.2 Daily / Weekly / Term kaam

| Role | Roz (Daily) | Hafta (Weekly) | Term / Saal (Termly) |
|---|---|---|---|
| **Principal** | Aaj ki haziri %, aaj ki wasooli, aaj kaun teacher ghair-hazir | Fee baqaya trend, class-wise haziri, pending approvals | Result analysis, admission targets, budget vs wasooli |
| **Class Teacher** | Haziri (subah), absent parents ko call, leave requests | Homework diary, weak students ki list | Report card remarks, promotion list |
| **Subject Teacher** | Apni periods, homework dena | Class test marks | Mid/final paper marks, re-check |
| **Fee clerk** | Voucher par payment, receipt, aaj ka cash tally | Defaulters ki call/message list | Monthly vouchers generate (poori school), annual fee, arrears, concession, saal ka close |
| **Front desk** | Inquiries, admissions, visitor | Documents pending chase | New session admission drive, ID cards, SLC/leaving certificates |
| **Exam in-charge** | Date sheet/hall duties | Test schedule | Term exams: schedule, marks collect, ranks, report cards, gazette |
| **Parent** | Bache ko bhejna, notice dekhna | Homework dekhna | PTM, report card, fee voucher |

### 4.3 Waqt aur accuracy kahan zaya hoti hai

| # | Zaya (waste) | Kahan hota hai | Code mein saboot | Software kaise khatam karega |
|---|---|---|---|---|
| W1 | **Ek hi data baar baar likhna** (bache ka naam/father ka phone register, fee register, result register, ID card) | Admission, fee, result, ID, certificates | Admission mein guardian field hi nahi; `students_parents_rel` table hai magar UI use nahi karta | **Ek baar enter, har jagah use** (family record) |
| W2 | **Haziri register paper par**, phir kisi aur ko Excel mein dalna | Subah ke 10-15 min per class (andaza A) | Absent mark ka route nahi (3.3) | Tablet par ek-tap haziri, default sab present, sirf absent tap; khud sheet aur % ban jaye |
| W3 | **Fee defaulters dhoondna** (register palatna, kaun kitne mahine se baqaya) | Month-end | `payslip` mein `due_date` nahi (`database.py:330-349`); koi defaulters view nahi | Auto "baqaya list" (kitne din, kitni raqam), ek click message |
| W4 | **Fee vouchers haath se ya Excel se** | Har mahine poori school | Class-wise bulk billing UI nahi (6 clicks x 40 = ~240 clicks) | Ek click: poori class/school ke vouchers generate + print |
| W5 | **Calculator se result** (total, %, grade, rank) aur galtiyan | Term end | Grade calc maujood (`exam_service.py`), **rank nahi**, marks UI nahi | Marks grid mein enter -> total/%/grade/rank khud; ghalat marks (max se zyada) rok do |
| W6 | **Report card haath se likhna/chhapna** | Term end, 2-3 din (andaza A) | Print nahi (0 `window.print`) | Template se bulk print, ek click poori class |
| W7 | **Parents ko call/message ek ek karke** | Daily absent, fee, notices | Messaging code nahi (grep) | Ready-to-send messages ki queue (Section 8) |
| W8 | **Parents ke sawal** ("fee kitni baaqi hai?", "result kab?") | Phone/counter par | Koi parent view nahi | Printed summary + WhatsApp par PDF/image |
| W9 | **Ghalat/duplicate admission** (same bacha do baar, ghalat class) | Reception | Duplicate check sirf seat/naam level par; DOB default `2012-05-15` save ho jata hai (`app.js:1176`) | CNIC/B-Form + father mobile + DOB se duplicate warning; DOB blank default |
| W10 | **Data kho jana** (power cut, PC kharab) | Hamesha ka dar | Backup code nahi (grep) | Autosave + roz ka backup + integrity check |
| W11 | **Ek hi PC par kaam** (sab baari baari) | Fee counter aur office | Localhost-only, login nahi | Login/roles, phir LAN (D2) |
| W12 | **Principal ko poochna padta hai** ("aaj kitni fee aayi?") | Poora din | Dashboard sirf total (`school_service.py:1269-1274`), "aaj" ka concept nahi | "Aaj" aur "is hafte" ke numbers, alerts |

### 4.4 Software waste kaise khatam karega (5 usool)

| Usool | Is project mein matlab |
|---|---|
| **Enter once, reuse everywhere** | Family record (walid ka naam, phone, CNIC) admission mein ek baar; fee voucher, SMS, ID card, report card sab usi se. |
| **Automate repetitive** | Monthly vouchers, haziri %, rank, grade, baaqaya, birthday/notice messages khud. |
| **Surface, don't hunt** | Har role ki home par "aaj kya zaroori hai" (defaulters, unmarked attendance, pending leaves, marks baaqi). |
| **Prevent errors before they happen** | Max marks se zyada na likh sako; duplicate admission warning; "Pay" se pehle raqam confirm; seat full pehle batao. |
| **Speed up communication** | Message templates (Urdu/Roman Urdu), ek click wa.me, queue. |

### 4.5 Asli duniya ki pabandiyan (constraints)

| Constraint | Asar | Plan ka jawab |
|---|---|---|
| **Purane/low-end PC** (2-4 GB RAM, HDD) | Heavy framework/animations dhimay | Vanilla JS modules (no React), lazy loading, pagination, kam animation, `prefers-reduced-motion`. Phase 0 mein purane PC par timing. |
| **Teachers phone/tablet par** | Abhi `127.0.0.1` only + no responsive CSS | Phase 3 ke baad LAN mode (login ke baad), responsive/touch UI |
| **Internet kabhi nahi** | Cloud feature kaam na kare | Section 8: offline-first + outbox |
| **Load-shedding / achanak band hona** | Data corrupt/kho jana | SQLite WAL (maujood), draft autosave, roz backup, startup par `PRAGMA integrity_check` |
| **Printing** (A4 laser, thermal receipt, ID card) | Printer drivers/page size | HTML + `@media print`, A4 aur 80mm receipt dono templates; Odoo ke report XML ko reference banana |
| **Zaban** | Staff Urdu bolta hai; parents ke liye Urdu print | Prints pehle Urdu/English dono; UI Urdu (RTL) baad mein (D3); vocabulary theek karna |
| **Staff tech-saavy nahi** | Training ka waqt/budget nahi | Section 9: role-wise saada UI, first-run checklist, in-app "yeh kya hai" hints |
| **Data privacy** (bachon ka data, CNIC) | Leak/misuse | Login, audit log, backup passphrase, kuch bhi bahar nahi bheja jata bina ijazat |

---

## 5. Research aur Benchmark

> **Source ka note:** niche ka research `search_web` se hua, jo vendor/blog summaries deta hai. Isko **"claim"** samjhen, "verified fact" nahi. Odoo ki qeematein odoo.com se directly verify nahi hui.

### 5.1 Odoo kya karta hai (aur kya "premium" lagta hai)

| Pehlu | Odoo ka tareeqa (claims + mera ilm) | Is project ke liye sabaq |
|---|---|---|
| **Pricing** | Standard ≈ \$31.10/user/month yearly (≈ \$373/yr), Custom ≈ \$61/user/month (≈ \$732/yr) (secondary sources). "~\$400" ≈ Standard ka ek user ka saal. **Aksar school ke liye 10-30 users** = \$3,700-\$11,000+/saal, plus implementation. | Hamari asli competition "Odoo ki qeemat" nahi, "ek chhote Pakistani school ke budget" hai. |
| **Education** | Odoo ke core mein school app nahi; OpenEduCat jaisa alag ecosystem hai: admission, timetable (clash check), fee (installments, sibling discount, reminders), parent portal, exam, library/hostel/transport. | Hamare paas library/hostel/transport pehle se hain (mazbooti). Admission pipeline/portal/analytics kamzori. |
| **Navigation** | App switcher + breadcrumbs + search facets/filters/group-by; ek hi view pattern (list/form/kanban/pivot/graph/calendar). | **Consistency** hi "premium" lagti hai. Hum ek list pattern aur ek form pattern banayenge. |
| **Form pattern** | Status bar (Draft -> Confirmed -> Done) upar, smart buttons, chatter (activity log), save-indicator. | Status bar + activity timeline (audit log se) lenge, chatter nahi (zaroorat nahi). |
| **Premium feel kyun** | Consistent spacing, instant search, keyboard shortcuts, inline editing, quick create, saaf empty states. | Yehi "boring" cheezein asli farq daalti hain, animation nahi. |

### 5.2 Pakistani school ERPs (market ko samajhna)

Common features jo vendors advertise karte hain (claims): **3/4-part bank challan**, 1BILL/1LINK/JazzCash/EasyPaisa payments, **WhatsApp fee reminders aur haziri alerts**, board-wise result cards (Federal/Punjab/Sindh/KPK/Cambridge), **Urdu RTL interface**, PKR pricing. (Misaal ke taur par: PakEducate, PakEduSystem, Skoo, Edflo, School Sahulat. Maine in products ko chalaya nahi.)

**Seekha:** Pakistan mein "premium" ka matlab Odoo jaisi polish se zyada **local workflow** hai: challan, WhatsApp, Urdu, result card. Yahan hum Odoo ko beat kar sakte hain (Section 13).

### 5.3 UX principles aur unka is project par asar

| Principle | Is project mein kahan lagta hai | Concrete badlaav |
|---|---|---|
| **Cognitive load / Hick's law** (zyada options = der) | Sidebar mein 11 flat numbered items (`index.html`) | Role ke hisaab se 4-7 items; Teacher ko sirf 4 (Aaj, Haziri, Marks, Homework) |
| **Progressive disclosure** | Admission modal mein 6 fields, magar asal admission ko 20+ fields chahiye | 3-step wizard: Bacha -> Walid/Guardian -> Class + Fee plan; baqi fields "mazeed maloomat" mein |
| **Recognition over recall** | Teacher ko student ID (`PID`) yaad nahi hota, chehra/naam/walid ka naam yaad hota hai | Search: naam, walid ka naam, mobile, GR No; photo thumbnail |
| **Smart defaults / satisficing** (log pehla theek-sa option le lete hain) | `years[0]` aur `schools[0]` aur DOB `2012-05-15` default (`app.js:1176, 1196-1208`) | Current academic year khud; DOB khali; galat default ka nuqsan sab se zyada |
| **Slips vs mistakes** (thakawat mein mis-click) | `Pay Full` ek click par paise mark kar deta hai (`app.js:383`) | Raqam dikhao + confirm; **Undo** (30 sec) toast; raat ko "aaj ka cash tally" |
| **Fitts's law / touch targets** | `.btn-xs` 11.5px font (`styles.css:397-399`) | Min 40px (behtar 44px) hit area, haziri par bade rows |
| **Visual hierarchy / F-pattern scanning** | Dashboard par sab cards barabar | Sab se zaroori number top-left, baaqi neeche; rang sirf maani ke liye |
| **Consistency** | Har tab apni table, apne button ke naam | Ek `DataTable` aur ek `FormWizard` component sab jagah |
| **Error/empty/loading states** | Sirf ek "Loading SQLite WAL Engine..." (`app.js:121`) | Har screen: skeleton, saaf khaali-halat + agla qadam, error + dobara koshish |
| **Accessibility (WCAG)** | Sirf search par focus ring | Focus ring har jagah, keyboard shortcuts, rang ke saath icon/text (rang-andhe 8% mard) |
| **Onboarding** | Naye school ko seed data milta hai, koi guide nahi | First-run checklist: School naam -> Classes -> Fee plan -> Students import -> Haziri try karo |
| **Fatigue / all-day use** | Safed `#f8fafc` + chhota text (`styles.css`) | Garm kaghazi background, 14px base text, kam glare |

### 5.4 Skills jo maine use/read kiye

| Skill | Kya liya | Is plan mein kahan |
|---|---|---|
| `frontend-design-direction` (ECC) | "Evidence contract + content states table (loading/empty/error/partial/success/permission)", "palette ek hue family par mabni na ho", "cards ke andar cards nahi" | Section 9.3, 9.4 |
| `make-interfaces-feel-better` (ECC) | Tabular numerals, 40-44px hit area, `transition: all` nahi, concentric radius, text-wrap | Section 9.2 |

> Maine koi external code/skill download ya run **nahi** kiya. Github se skill download ki zaroorat nahi padi.

---

## 6. Gap Analysis table

> **Priority:** Impact (H/M/L) vs Effort (S = 1-3 din, M = 1-2 hafte, L = 2+ hafte). **P0** = pehle (impact H, effort S/M), **P1** = core, **P2** = baad mein, **NO** = nahi banayenge.

| ID | Area | Kya hai (evidence) | Kya missing hai | Kyun zaroori (productivity) | Kahan (module/page/files) | Kaise banega | Priority |
|---|---|---|---|---|---|---|---|
| G1 | **Haziri marking** | Service `action_present/absent` (`attendance_service.py:246+`), sheet banti hai (default sab present) | Route + UI jo absent mark kare | Haziri roz ka sab se bara kaam; abhi kaam hi nahi karta | `routes/attendance_routes.py` (new), `ui/js/attendance/*` | Class grid: tap = absent; bulk `POST /api/attendance/daily/<id>/lines` (ek call mein sab) | **P0 (H/S)** |
| G2 | **Pagination / lazy loading** | `GET /api/bootstrap` sab kuch deta hai: 5.5 s, 800 KB @1000 students | Server-side pagination + search, slim bootstrap | Har click par 5 sec = software "dead" lagta hai | `api.py` -> `routes/*`, `database.py` helper `paginate()`, `ui/js/core/api.js` | `GET /api/students?page=&q=&class=`; bootstrap sirf lookups; targeted refresh (sirf badli hui cheez) | **P0 (H/M)** |
| G3 | **Login, roles, audit** | Odoo mein 5 groups; desktop mein **kuch nahi** | Local users, PIN/password, role permissions, audit log | Accountability (kisne fee mark ki?), role-based screens, LAN ki shart | `services/auth_service.py`, `routes/auth_routes.py`, tables `app_user`, `role`, `audit_log` | Salted hash (`hashlib.pbkdf2_hmac`, har user ka apna salt), session token, decorator `@require_role`; audit har write par | **P0 (H/M)** |
| G4 | **Fee workflow (core)** | Payslip modal (1 student), `Pay Full`, `due_amount` | Bulk class billing, **voucher/challan**, partial payment UI, receipt, `due_date`, defaulters list, daily cash tally | Fee clerk ka sab kaam; paisa = sab se ghalti-sensitive | `services/fees_service.py` (extend), `routes/fees_routes.py`, `ui/js/fees/*`, new column `due_date` | Fee Register (class-wise) generate; voucher HTML print; payment with amount + confirm + undo window; defaulters query | **P0 (H/M)** |
| G5 | **Fee rules** | `penalty` sirf library mein | Sibling concession, scholarship, late fee, installments, vacation fee | Pakistani fee structure ka asli hissa | `fees_service.py`, tables `fee_concession`, `fee_rule` | Rules table; voucher generate hote waqt apply | P1 (H/M) |
| G6 | **Admission desk** | 6-field modal, auto-admit | Guardian/CNIC/B-Form, documents checklist, duplicate check, fee plan, ID card, inquiry stage | Reception ka kaam; W1/W9 | `ui/js/school/admission_wizard.js`, `school_service.py` (extend), `student.document` reference | 3-step wizard; duplicate check by (CNIC / father mobile + DOB) | P1 (H/M) |
| G7 | **Exam & report card** | Grade calc, results listing, `/api/exam-subjects` route | Exam create UI, marks-entry grid, **rank**, remarks, print report card, gazette | Term-end sab se bada dard (W5/W6) | `exam_service.py` (add `compute_ranks`), `ui/js/exam/*`, `print/report_card.js` | Spreadsheet-style grid (Tab/Enter navigation), Excel paste, validation `<= max` | P1 (H/L) |
| G8 | **Timetable** | List only (`renderTimetable`), overlap check logic (`timetable_service.py:118-144`) | Create UI, visual week grid, teacher "aaj ki periods", substitution, Ramazan bell schedule | Teacher/Principal ko roz chahiye | `ui/js/timetable/*`, `timetable_service.py` | Grid view (read), create via cell click; reuse overlap check | P1 (M/M) |
| G9 | **Role dashboards** | 4 KPI cards + students table | Principal/Teacher/Fee home with alerts | "Surface, don't hunt" | `services/dashboard_service.py` (new), `ui/js/dashboard/*` | 1 query per card, cached 60 sec; alerts rules | **P0 (H/M)** |
| G10 | **Search** | `JSON.stringify` filter, har keystroke par poora re-render | Global search (naam, walid, mobile, GR No), Ctrl+K, debounce | Counter par sab se tez kaam | `routes/search_routes.py`, `ui/js/core/search.js` | SQLite FTS5 ya indexed LIKE; debounce 200 ms | **P0 (H/S)** |
| G11 | **Printing** | Odoo report XMLs (21 files), desktop par 0 print | Voucher, receipt (A4 + 80mm), report card, ID card, certificates | Paper abhi bhi school ki zaroorat | `ui/print/*.css`, `ui/js/print/*`, Odoo XML se layout reference | HTML + `@media print`; `window.print()` | **P0 (H/M)** |
| G12 | **Communication** | Odoo mein 2 mail templates (admission, fee reminder) | Message templates, outbox, wa.me links, circulars | W7/W8 | `services/outbox_service.py`, table `outbox_message` | Section 8 | P1 (H/M) |
| G13 | **Backup / migration** | `ALTER TABLE`/`backup`/`user_version` = 0 | Backup/restore, schema version, integrity check | Data safety; naye columns (e.g. `due_date`) ke liye zaroori | `database.py` split -> `db/{connection,schema,migrate}.py`, `services/backup_service.py` | `PRAGMA user_version` + numbered migrations | **P0 (H/S)** |
| G14 | **Urdu** | `i18n` sirf library (fr/ru/sv) | Urdu prints, phir Urdu UI, vocabulary fix | Staff aur parents ki zaban | `ui/i18n/{en,ur}.js`, `ui/fonts/` (bundled) | Pehle prints, label dictionary, baad mein RTL | P1 (M/M) prints; P2 UI |
| G15 | **Import / Export** | Sirf attendance Excel export | Students/fees Excel import, har list ka export | School ke paas data Excel mein hota hai | `services/import_service.py`, `xlsxwriter` (already in `requirements.txt`) + `openpyxl` (naya, license check) | Template download -> upload -> preview -> confirm | P1 (H/M) |
| G16 | **Parent access** | Kuch nahi | Printed summary, PDF share, (baad mein) portal | W8 | `print/parent_sheet.js` | Section 8 | P1 (M/S) sheet; P2 portal |
| G17 | **UI components** | `panel`, `kpi-card`, `badge`, `toast`, `modal` | DataTable, FormWizard, EmptyState, Skeleton, ConfirmDialog, StatusBar | Consistency + states | `ui/js/components/*` | Section 10.2 | **P0 (H/M)** |
| G18 | **Accessibility/responsive** | 0 `@media`, 1 focus rule | Focus, keyboard, touch, responsive, print CSS | All-day use, tablets | `ui/css/*` | Section 9 | P0/P1 |
| G19 | **Homework** | Assignment list, fake submit | Real attach, class diary, submission status | Teacher/parent | `assignment_service.py`, `ui/js/assignment/*` | Diary view; file attach via local folder | P2 (M/M) |
| G20 | **Library/Hostel/Transport** | Seeded, list + few modals | Library card UI, transport action UI | Chhote gaps | `ui/js/library/*`, `ui/js/transport/*` | Existing routes ko UI dena | P2 (L/S) |
| G21 | **Calendar** | Koi holiday/calendar table nahi (69 tables mein nahi) | Academic calendar, holidays, Ramazan schedule | Haziri aur fee ko holiday-aware banane ke liye | `services/calendar_service.py`, table `calendar_day` | Month grid + holiday import | P1 (M/M) |
| G22 | **Settings / onboarding** | Koi settings tab nahi | School profile, grading scheme, fee heads, backup | Naye school ke liye zaroori | `ui/js/settings/*`, `services/settings_service.py`, table `school_setting` | First-run checklist | P1 (M/S) |
| G23 | **Code health** | `app.js` 1752, `school_service.py` 1294, `database.py` 964, `api.py` 614 | Split + tests for new routes | Maintainability, no monolith rule | Section 10 | Refactor **behavior badle bina**, tests pehle green | P0 (M/M) |
| G24 | **Odoo-side analytics** | 0 graph/pivot/dashboard views | Graph/pivot views | Sirf agar D1 = Odoo | `*/views/*.xml` | Add `<graph>`/`<pivot>` | P3 (depends on D1) |
| G25 | **Staff HR/payroll** | `school` `depends hr` (Odoo) | Teacher salary/attendance | Scope se bahar | - | **NAHI banayenge** (alag product, Odoo `hr` bhi ismein behtar). Sirf teacher ki "ghair-hazir" flag Principal dashboard ke liye. | **NO** |

---

## 7. Signature Ideas (Pakistani school ke liye)

> Har idea ka maqsad: kaunsa insaan, kaunsa kaam, kaise naapenge. Sab **offline** chalte hain.

### S1. "Chalan-Ready" — 3-hissa fee voucher engine

| | |
|---|---|
| **Kya** | Class ya poori school ke liye ek click mein vouchers; har voucher ke 3 copy (School / Bank / Parent), serial number, due date, baaqaya (arrears) alag line mein, QR/barcode (serial). Payment voucher number likh kar ya scan kar ke mark. |
| **Kis ke liye** | Fee clerk, Principal |
| **Kyun (justification)** | Pakistani vendors ke 3/4-part challan advertise karne se pata chalta hai yeh standard hai (Section 5.2, claim). Hamare code mein voucher/challan hai hi nahi (grep). Month-end ka sab se bara bojh yehi hai (W4). |
| **Kaise naapenge** | 40 bachon ke vouchers: abhi ~240 clicks -> target **2 clicks, < 30 sec generate + print dialog**. |
| **Offline** | Haan, sirf print. |
| **Kahan** | `fees_service.py` (extend), `ui/print/voucher.*`, `ui/js/fees/*` |

### S2. "Khandani Khata" — Family-first search aur family ledger

| | |
|---|---|
| **Kya** | Bachon ko **family** se jorna (walid ka naam, mobile, CNIC). Search "Ali ke abbu" ya mobile number se poora khandan aur unke saare bachon ka ek hisaab. Bhai-behan ka ek hi voucher, sibling concession khud. |
| **Kis ke liye** | Fee clerk, Front desk |
| **Kyun** | Pakistan mein walid counter par aate hain, bache ka nahi, family ke naam se. `students_parents_rel` aur `school_parent` tables pehle se hain (`database.py` table list) magar UI use nahi karta, yaani data model tayyar, faida zaya. |
| **Naapna** | Walid ke counter par pohnchne se payment tak: abhi (search by PID, dropdown 1000 options) -> target **< 20 sec, 3 clicks**. |
| **Offline** | Haan. |
| **Kahan** | `routes/family_routes.py`, `ui/js/family/*` |

### S3. "Mehfooz Mode" — Load-shedding-proof data safety

| | |
|---|---|
| **Kya** | (1) Har form ka draft har 5 sec autosave (bijli chali jaye to wapas milay). (2) Roz band karte waqt ek click "Aaj ka backup" (USB ya dusra folder), aur reminder "kal ka backup nahi hua". (3) Startup par `PRAGMA integrity_check` aur kharabi par aakhri backup se restore ka option. |
| **Kis ke liye** | Principal/Owner (jo data kho jane se darte hain) |
| **Kyun** | Backup/restore/migration ka code zero hai (grep). Bijli ke achanak band hone ka masla Pakistan mein aam hai (mera general ilm, school-wise verify karna). WAL mode (`database.py:911`) maujood hai, yaani buniyaad bani hui hai. |
| **Naapna** | "Power-cut test": form bharte waqt PC band; wapas khulne par draft mile (target **>= 95% fields recover**). |
| **Offline** | Haan. |

### S4. "Bhejne ke liye Tayyar" — API ke bagair WhatsApp

| | |
|---|---|
| **Kya** | Har alert (absent, fee baaqaya, result tayyar, notice) ek **tayyar paigham** ban kar queue mein aata hai (Urdu/Roman Urdu template, naam aur raqam bhari hui). Clerk "Bhejo" dabata hai to uske apne WhatsApp mein `wa.me/92...?text=...` khulta hai; wo Send dabata hai, phir "Bhej diya" tick. |
| **Kis ke liye** | Class teacher, Fee clerk |
| **Kyun** | Parents WhatsApp par hain. Official WhatsApp Business API ka kharcha/approval/internet chahiye aur unofficial automation se number ban ho sakta hai. `wa.me` click-to-chat ek documented tareeqa hai, **koi API key nahi, koi kharcha nahi, ToS ka masla nahi**. Insaan loop mein rehta hai. |
| **Naapna** | 15 absent bachon ke gharon ko paigham: abhi (alag se phone par type) -> target **< 2 min**. |
| **Kamzori (imandari)** | Fully automatic nahi; delivery ka confirmation nahi milta. Sirf "tayyar aur ek-click" hai. |
| **Offline** | Queue offline banti hai; bhejna internet par (phone ke WhatsApp se). |

### S5. "Urdu Natija" — Bilingual report card aur result gazette

| | |
|---|---|
| **Kya** | Report card Urdu + English dono mein, rank, remarks templates ("Mehnat mein behtari ki gunjaish hai"), term-wise aur annual cumulative; marks entry **spreadsheet grid** jis mein Excel se paste ho sake. |
| **Kis ke liye** | Exam in-charge, Subject teachers |
| **Kyun** | Term end ka sab se bada kaam (W5/W6, assumption). Code mein rank (0 hits) aur marks entry UI (`/api/exam-subjects` route hai, UI nahi) dono missing. Teachers ke marks aksar Excel/notebook mein hote hain. |
| **Naapna** | 40 bachon ke 6 subjects (240 marks): enter + report cards print: target **< 20 min** (baseline Phase 0 mein). |
| **Offline** | Haan. |

### S6. "Pakistani Calendar" — Eid/Ramazan/Garmiyon ki chhutti aware

| | |
|---|---|
| **Kya** | Academic calendar mein holidays (Eid, Muharram, 14 Aug, Garmiyon ki chhutti), Ramazan mein chhote periods ka alag bell schedule. Haziri holiday par nahi maangi jati; fee vouchers chhutti ke mahino ke liye configurable (vacation fee, ya skip). |
| **Kis ke liye** | Principal, Exam in-charge, Fee clerk |
| **Kyun** | 69 tables mein holiday/calendar table nahi (verify kiya). Ramazan timings aur summer vacation har school mein hoti hain. Is ke bagair haziri % aur fee ghalat. |
| **Naapna** | Ramazan switch: timetable badalna abhi (har class manually) -> target **1 click**. |
| **Offline** | Haan. Holiday list shuru mein manually (lunar dates har saal badalte hain, auto nahi). |

### S7. "PTM Sheet" — Parent-Teacher Meeting ka ek-safha

| | |
|---|---|
| **Kya** | Har bache ka A5 ek page: haziri %, fee ki halat, aakhri result, 2-3 line teacher remark, QR (voucher serial). Poori class ke sheets ek click mein print. |
| **Kis ke liye** | Class teacher, Principal; parents (jo paper dekhna chahte hain) |
| **Kyun** | PTM abhi bhi kaghaz par hoti hai (A2). Parent portal internet maangta hai (Section 8), yeh offline parent-facing feature hai. `student_news`/`student_reminder`/`student_descipline`/`student_award` tables pehle se maujood (table list), yaani remarks ka data model hai. |
| **Naapna** | PTM taiyari: 40 bachon ki maloomat jama karna abhi (har ek ka register) -> target **< 5 min**. |
| **Offline** | Haan. |

### S8 (UX signature). "Aaj Ka Din" — har role ki home

| | |
|---|---|
| **Kya** | Har role ki pehli screen ek sawal ka jawab: **"Aaj mujhe kya karna hai?"** Teacher: aaj ki periods + haziri baaqi; Fee clerk: aaj ke due, baaqaya; Principal: aaj ki wasooli, haziri %, masail. Koi chart sirf sajawat ke liye nahi. |
| **Kyun** | "Surface, don't hunt" (4.4). Abhi dashboard par library stock aur hostel/transport counts hain (`app.js:180-189`) jo principal ke roz ke faislon mein kam kaam aate hain. |
| **Naapna** | Teacher ki login se haziri start tak: abhi **kaam hi nahi** -> target **<= 3 clicks**. |

> **Jo idea main ne rad kiya:** (1) AI chatbot — offline school mein faida kam, kharcha/risk zyada. (2) Biometric/RFID haziri — hardware ke bagair test mumkin nahi, **NO** (hardware dependency). (3) Online payment gateway (1LINK/JazzCash) — merchant agreement aur internet chahiye, Phase 5+ mein dekhenge, ab nahi.

---

## 8. Offline vs Internet — saaf strategy

### 8.1 Usool: **Offline-first, internet-optional**

> Software ka core kabhi internet ka mohtaj nahi. Internet wali cheezein **add-on** hain jo queue (outbox) se chalti hain. Internet chala jaye to koi kaam rukta nahi, sirf "bhejna" intezar karta hai.

### 8.2 Layers

| Layer | Kya | Internet? | Phase |
|---|---|---|---|
| **L0** | Poora core: students, fees, haziri, exam, print, backup | Kabhi nahi | 1-4 |
| **L1 — Outbox (queue)** | `outbox_message` table: har paigham `queued -> ready -> sent/failed`; banner "3 paigham bhejne baaqi" | Queue offline banti hai | 3 |
| **L2 — Bhejna** | (a) WhatsApp: `wa.me` click-to-chat (insaan Send dabata hai); (b) Email: SMTP, internet par khud; (c) SMS gateway: **optional**, baad mein | Sirf bhejte waqt | 3 / 5 |
| **L3 — Parent access (bina internet)** | Printed PTM Sheet (S7), voucher PDF/image jo clerk WhatsApp par bhej de, ID/QR | Nahi | 3 |
| **L4 — Parent Portal (live)** | LAN-only read-only kiosk ya internet par snapshot | Haan | **5+ (sirf demand dikhe to)** |

### 8.3 `outbox_message` ka design (naya table)

| Column | Matlab |
|---|---|
| `id`, `channel` (`whatsapp`/`email`/`sms`), `to_name`, `to_phone`/`to_email` | Kis ko |
| `template_code`, `payload_json`, `body_text` | Kya (render shuda text save, taa ke baad mein bhi wohi bheje) |
| `status` (`queued`/`ready`/`sent`/`failed`/`cancelled`), `attempts`, `last_error` | Halat |
| `due_at`, `created_at`, `sent_at`, `created_by` | Waqt aur kis ne |
| `student_id`, `family_id` (nullable) | Link |

**Qawaid:** (1) Duplicate rokna (same student + template + din). (2) Pakistani mobile format validate (`03xx-xxxxxxx` ya `+92...`) **enter karte waqt**, bhejte waqt nahi. (3) WhatsApp ka status `sent` sirf clerk ke "Bhej diya" tick par (hum delivery nahi jaan sakte, yeh saaf likha ho).

### 8.4 Failure modes

| Halat | Kya hoga |
|---|---|
| Internet band | Paigham `queued` rehte hain, banner dikhta hai; kaam nahi rukta |
| Internet aaya | Email khud nikalta hai; WhatsApp ke liye "Tayyar: 12" badge, clerk bhejta hai |
| Bijli gayi | Draft autosave + WAL; restart par recover |
| Ghalat number | Entry par hi warning |
| Do PC (D2) | Ek "server PC" hi data ka maalik; baaqi browser se. **Pehle login (Phase 1), phir LAN.** |

### 8.5 Security ki ahem hadd

Abhi server `127.0.0.1` par bind hai aur `check_local_host` wahi rokta hai (`api.py:57-62`). **LAN/portal ke liye is hadd ko dheela karna** ek **security-sensitive** faisla hai. Mera plan: (1) pehle login/roles/audit (G3) banen, (2) phir **aap ki wazahat se** `0.0.0.0` bind option (default OFF, settings mein ek switch), (3) bachon ka data kabhi cloud par **bina school ki likhi ijazat** nahi jata. Is ke bagair main yeh hadd nahi chhedunga.

### 8.6 Parent Portal ke baare mein imandari

Live Parent Portal sab se mehnga aur sab se risky feature hai (internet, security, privacy, support). Mera mashwara: **S7 (PTM Sheet) + S4 (WhatsApp tayyar) + PDF share** pehle; portal tab banayen jab 3+ schools khud maangein. Isko roadmap mein Phase 5 par rakha hai, "optional".

---

## 9. Design Direction

### 9.1 Pehchaan (Visual identity): **"Kaghaz aur Siyahi"** (Paper & Ink)

| | |
|---|---|
| **Concept** | School ka asli rozmarra **register-book** hai: kaghaz, siyahi, mohar (stamp). UI isi ko digital banata hai: garm kaghazi background, siyahi jaisa text, registers jaisi saaf lakeeron wali tables, aur status ke liye "mohar" jaise chips. |
| **Tone** | Pur-sukoon, kaam-kaaji, dost jaisa. Na corporate-cold, na kids-cartoon. |
| **Yaadgaar cheez (memorable detail)** | **Register-style tables** (halki ruled lines, sticky header) aur **"mohar" status chips** (icon + lafz, sirf rang nahi). Teachers ko yeh kaghazi register jaisa pehchana hua lagega, yaani training kam. |
| **Kyun navy+green nahi** | (1) Navy+green "education software" ka sab se aam look hai aur Odoo/zyada tar products jaisa hota hai: pehchaan nahi banti. (2) Current UI generic slate-navy sidebar + neela accent hai (`styles.css:6-14`: `#0f172a`, `#2563eb`), yaani aam SaaS look. (3) Green ko hum **sirf "kamyab/paid"** ke maani ke liye bachate hain, taa ke ek hi rang ke do maani na hon. (4) Garm background poora din dekhne mein thakawat kam karne ke liye chuna (design maqsad hai, naapa nahi; Section 12 ke usability check mein A/B se dekhenge). |

### 9.2 Palette (contrast maine calculate kiya, WCAG formula se)

| Token | Hex | Kaam | Contrast (verified) |
|---|---|---|---|
| `--kaghaz` (canvas) | `#F6F1E7` | Page background | - |
| `--surface` | `#FFFFFF` | Cards, tables, forms | - |
| `--siyahi` (text) | `#231F1C` | Mukhya text | **14.53** vs canvas, **16.35** vs white |
| `--siyahi-soft` | `#6B6259` | Doosra/muted text | **5.30** vs canvas, **5.97** vs white |
| `--chai` (primary) | `#8A4B16` | Primary button, active tab | safed text par **6.78**; hover `#733C10` par **8.81** |
| `--neel` | `#2F6690` | Links, selection, **focus ring**, info | **5.45** vs canvas, **6.13** vs white |
| `--haldi` | `#E2A32B` | Highlight, sidebar active bar, "tawajjo" | **6.93** vs sidebar |
| `--surkh` (danger) | `#B3261E` | Delete/ghalti | safed text par **6.54** |
| `--pista` (success text) | `#2F5A14` on `#E4EED8` | "Wasool/Paid/Mukammal" | **6.76** |
| warning text | `#6B4500` on `#FBEBC4` | Der/baaqaya | **7.18** |
| danger text | `#8C1D18` on `#F9DEDC` | Nakaam/ghalat | **7.17** |
| info text | `#1F4A6E` on `#DCEAF4` | Maloomat | **7.56** |
| `--sidebar` | `#2A2420` | Sidebar (garm siyah, navy nahi) | text `#E9E1D3` par **11.79**; muted `#B9AD9B` par **6.94** |
| input border | `#8C8274` | Fields (zaroori UI hadd) | **3.78** vs white, **3.35** vs canvas (>= 3:1 WCAG non-text) |
| rule line | `#E3DAC9` | Table ki halki lakeerein (sajawati) | 1.39 (sirf sajawat, maani nahi) |

**Qawaid:** (1) Har status = **icon + lafz + rang** (rang-andhe 8% mardon ke liye, aur B/W print ke liye). (2) Primary button ek screen par **sirf ek**. (3) Hue-family ek hi par na tike: chai (garm) + neel (thanda) + haldi (accent) multi-dimensional rakha (skill `frontend-design-direction` ki hidayat).

### 9.3 Typography, spacing, icons, components

| Cheez | Faisla | Wajah |
|---|---|---|
| **Latin UI font** | System stack (`Segoe UI`, ...) **bundle nahi**, jaise pehle hai (`styles.css:38`) | Purane PC par zero download, sab se tez, offline |
| **Urdu font** | **Noto Naskh Arabic** (UI + print) bundle, **Noto Nastaliq Urdu** sirf print headings. Dono `ui/fonts/` mein local (CSP `default-src 'self'` aur offline ki wajah se CDN mumkin nahi: `index.html` meta) | Naskh chhote text mein parhne mein asaan; Nastaliq roayati magar bara aur ooncha. **File size/licence (OFL) Phase 0 mein check** (abhi verify nahi) |
| **Sizes** | Base **14px** (abhi 13.5px aur 11-12.5px ke bohot hisse), table text 14px, row **44px**, minimum 13px (11px khatam), KPI 28-32px | 40+ saal ke staff aur poore din ki padhai |
| **Numbers** | `tabular-nums` (pehle se `styles.css:47-53`) | Raqam ek doosre ke neeche seedhi |
| **Line-height** | Latin 1.5, Urdu 1.9 | Urdu ke diacritics ko jagah |
| **Spacing** | 4px grid: 4/8/12/16/24/32; card padding 16-20 | Sukoon, scan karna asaan |
| **Touch/click** | >= **40px** hit area, touch par **44px** (haziri rows) | Fitts's law; skill `make-interfaces-feel-better` |
| **Icons** | Inline **SVG sprite** `ui/img/icons.svg` (Lucide: ISC licence, **Phase 0 mein licence text parh kar confirm**); har icon ke saath lafz | CSP: icon-font/CDN nahi; kam size |
| **Buttons** | Primary (chai fill), Secondary (outline), Quiet (text), Danger (sirf confirm ke andar) | Ek ahem action wazeh |
| **Cards** | Cards ke **andar cards nahi**; halka border, subtle shadow; radius 8px (andar ka 4px, concentric) | Skill hidayat |
| **Tables** | Register-style, sticky header, row hover, selection checkbox, "ginti" (X of Y), pagination 50 | Consistency; performance |
| **Motion** | 120-150ms, sirf `opacity/transform`; `transition: all` kabhi nahi; `prefers-reduced-motion` ka khayal | Purane PC, aur dhyan na bhatke |
| **Focus** | `--neel` 2px ring har interactive cheez par | Keyboard users |

### 9.4 Alfaaz ki safai (vocabulary)

| Abhi (Odoo-zaban) | Naya (school ki zaban) | Saboot |
|---|---|---|
| Payslip | **Fee Voucher** | `app.js:340` ("Student Fee Payslips & Invoices") |
| Standard | **Class** | `app.js:261` ("School Standards & Seat Capacity"), modal labels `Class / Standard` (`app.js:1186, 1220, 1345, 1420`) — *(table headers `app.js:208, 267, 351, 417` mein pehle hi `Class` hai)* |
| PID | **GR No / Admission No** | `app.js:205` |
| Validate & Sync Sheet | **Haziri jama karein** | `app.js:441` |
| Reset to Draft | **Dobara kholein** | `app.js:442` |
| Pay Full | **Poori raqam wasool karein** (+ confirm) | `app.js:383` |
| Save & Validate | **Mehfooz karein** | `index.html` modal button |
| "10-Module SQLite Engine", "100% Domain Logic Active" | **Hata dein** | `index.html:18, 102` |
| Draft / Confirm / Done states | **Adhoora / Taiyar / Mukammal** (chips) | `badge()` `app.js:36-47` |

### 9.5 Navigation aur layout role ke hisaab se

> Abhi sab ko wohi 11 tabs (`index.html`). Naya: **role ke hisaab se 4-6 items**, aur har role ki pehli screen "Aaj Ka Din" (S8).

| Role | Sidebar (zyada se zyada) | Pehli screen | Sab se aam 3 kaam aur kitne click |
|---|---|---|---|
| **Principal/Admin** | Aaj - School (Students, Teachers) - Fees - Academics - Settings | Aaj Ka Din (Principal) | Aaj ki wasooli dekhna (**0**), baaqaya list (**1**), kisi class ki haziri (**2**) |
| **Class/Subject Teacher** | Aaj - Haziri - Marks - Homework | Aaj Ka Din (Teacher) | Haziri lena (**<= 5**), marks bharna (**<= 4 + typing**), homework dena (**<= 4**) |
| **Fee clerk** | Aaj - Fee Counter - Vouchers - Baaqaya - Reports | Fee Counter (search autofocus) | Fee wasool (**<= 5**), class vouchers (**<= 5**), baaqaya paigham (**<= 3 + send**) |
| **Front desk** | Aaj - Admissions - Students - Documents | Aaj Ka Din (Front desk) | Naya admission (**<= 10**), student dhoondna (**type + Enter**), ID card print (**<= 3**) |
| **Exam in-charge** | Aaj - Exams - Marks - Report Cards - Timetable | Aaj Ka Din (Exam) | Exam banana (**<= 6**), marks ki progress (**1**), report cards print (**<= 4**) |
| **Parent/Student** | (Phase 5, optional) | Printed PTM Sheet / PDF | - |

**Bar-bar nazar aane wali cheezein (top bar):** Global search (Ctrl+K), "+ Naya" quick-create menu, **Outbox badge** ("12 paigham tayyar"), **Backup nishaan** ("Aakhri backup: aaj 2:10 PM", ek din se purana ho to haldi), user menu.

**Role models:** Odoo ke maujooda 5 groups (`school/security/school_security.xml`: administrator, teacher, student, parent, in_admission) ko base rakhte hain; naye `fee_clerk`, `front_desk`, `exam_incharge` desktop mein add honge. Odoo ke groups ko badalna scope se bahar (D1).

### 9.6 Placement rule: har card/widget ka jawaz

> Rule: koi card "khaali jagah bharne" ke liye nahi. Har ek ka **kaam, kis ke liye, kaunsa faisla/action, kyun is jagah, aur 3 halat (khali, load ho raha, ghalti)** likha hai. Skill `frontend-design-direction` ke content-state table se.

#### (A) Principal — "Aaj Ka Din"

| # | Card | Maqsad | Kis ke liye | Faisla/Action | Jagah aur kyun | Khali | Loading | Error |
|---|---|---|---|---|---|---|---|---|
| P1 | **Aaj ki wasooli** (Rs, kal ke muqable) | Paisay ki sehat | Principal, Owner | "Kya aaj wasooli theek hai?" | **Top-left**: F-pattern mein pehla jo nazar parta hai; paisa sab se ahem | "Aaj abhi koi wasooli nahi" + "Fee Counter kholen" | Same size ka skeleton (layout nahi hilega) | "Aaj ki wasooli load nahi hui. Dobara koshish" + Retry |
| P2 | **Aaj ki haziri %** + "N classes ki haziri baaqi" | Class-wise haziri ka jaiza | Principal | Kisi teacher ko yaad dilana | Top, P1 ke bagal mein: paisa + haziri = do roz ke ahem number | "Haziri abhi shuru nahi hui" | Skeleton | Retry |
| P3 | **Fee baaqaya** (kul raqam, kitne bache, 30+ din wale) | Wasooli ki zaroorat | Principal, Fee clerk | Baaqaya list kholna | Top, tisra number | "Koi baaqaya nahi, shabash" (positive state) | Skeleton | Retry |
| P4 | **Tawajjo talab** (action list: haziri na lagi wali classes, pending leaves, marks baaqi, backup nahi hua) | **Exceptions** dikhana | Principal | Har row par ek-click action | **Mukhya wide column (left)**: Principal ka kaam exceptions sambhalna hai, isliye sab se zyada jagah | "Sab theek hai" + haan aaj ki tareekh | Skeleton rows | Row-level error, baaqi dikhein (partial) |
| P5 | **Class-wise haziri strip** (chhote bars) | Kaun si class mein masla | Principal | Class par click -> uski haziri | P4 ke neeche, compact | "Haziri ka data nahi" | Skeleton bars | Retry |
| P6 | **Agle 7 din** (exam, event, chhutti) | Taiyari | Principal, Exam in-charge | Date sheet/event kholna | **Right column**: sirf reference, faisla nahi, is liye kam ahmiyat | "Agle 7 din koi event nahi" | Skeleton | Retry |
| P7 | Aaj ke naye admissions/inquiries | Growth | Principal, Front desk | Admission desk kholna | Right, neeche (kam daily-critical) | "Aaj koi naya admission nahi" | Skeleton | Retry |

> **Jo cheez home se hata di (jaanbujh kar):** Library stock aur Hostel/Transport counts (`app.js:180-189`), yeh roz ke faislon mein nahi aate, apne apne module mein rahenge.

#### (B) Teacher — "Aaj Ka Din"

| # | Card | Maqsad | Faisla/Action | Jagah aur kyun | Khali | Loading | Error |
|---|---|---|---|---|---|---|---|
| T1 | **Haziri baaqi hai** (bara button "Haziri lo — Class 9-A") | Roz ka pehla kaam | 1 tap se haziri start | **Top, sab se bara**: yehi pehla kaam hai | "Aaj ki haziri lag chuki" (hari tick, band) | Skeleton | "Class ki fehrist load nahi hui" + Retry |
| T2 | **Aaj ki periods** (timeline) | Kahan jana hai | Period par click -> class | Left, time-order mein (natural) | "Aaj koi period nahi / chhutti" | Skeleton | Retry |
| T3 | **Meri class ke absent** | Follow-up | "Paigham tayyar karo" | Right, haziri ke baad hi relevant | "Aaj sab hazir" | Skeleton | Retry |
| T4 | **Marks baaqi hain** (exam, kitne bache baaqi) | Term ka kaam | Marks grid kholna | Neeche, kam urgent | "Koi marks baaqi nahi" | Skeleton | Retry |
| T5 | **Homework due** | Diary | Homework dena/dekhna | Neeche | "Aaj koi homework due nahi" | Skeleton | Retry |

#### (C) Fee Counter (Fee clerk ki screen)

| # | Hissa | Maqsad | Faisla/Action | Jagah aur kyun | Khali | Loading | Error |
|---|---|---|---|---|---|---|---|
| F1 | **Bari search box** (autofocus): naam / walid / mobile / GR / voucher no | Dhoondna (recognition) | Type + Enter | **Sab se upar, bari**: counter par pehla qadam hamesha dhoondna hai | "Naam, mobile ya voucher number likhein" | Chhota spinner box ke andar | "Search nahi chali" + Retry |
| F2 | **Family card**: walid ka naam, saare bache, har ek ka baaqaya | "Is khandan ka kitna baaqi?" | Voucher chunna | F1 ke neeche, left: search ka natija | "Is naam ka koi nahi. Naya admission?" | Skeleton | Retry |
| F3 | **Payment panel**: raqam (default = poora), tareeqa (cash/bank), confirm | Paisa wasool karna | **Confirm** (slip rokne ke liye) | Right, F2 ke bagal: kaam ka natija natija ke saath | "Pehle voucher chunein" (disabled) | - | "Wasooli darj nahi hui. Paisa nahi kata" + Retry |
| F4 | **Receipt preview + Print** (A4 / 80mm) | Parent ko sabot | Print | F3 ke neeche | - | - | "Print window nahi khuli" |
| F5 | **Aaj ka tally** (cash/bank, kitni receipts) | Din ke end ka hisaab | Cash gin kar milana | **Right chhota**, hamesha nazar mein par dhyan na bhatkaye | "Aaj abhi 0" | Skeleton | Retry |
| F6 | **Aakhri wasooli ko wapas karein (Undo, 30 sec)** | Galti sudharna | Undo | F3 ke paas toast mein | Hidden jab koi nahi | - | "Undo nahi ho saka" |

#### (D) Haziri sheet (Teacher/Tablet)

| # | Hissa | Maqsad | Faisla/Action | Jagah aur kyun | Khali | Loading | Error |
|---|---|---|---|---|---|---|---|
| A1 | **Header**: Class, tareekh, teacher | Sahi sheet ki tasdeeq | - | Top, chhota | - | Skeleton | - |
| A2 | **Live ginti**: Hazir / Ghair-hazir / Chhutti | Foran feedback | - | Top-right, sticky | 0/0/0 | - | - |
| A3 | **Students ka grid** (photo, roll, naam, **bara tap target 44px+**) | Absent mark karna | Tap = absent, dobara tap = hazir | Beech mein, sab se bara hissa | "Is class mein abhi koi student nahi" | Skeleton grid | "Fehrist load nahi hui" + Retry |
| A4 | **Sab hazir (default)** pehle se | Kam se kam tap | - | Default state | - | - | - |
| A5 | **Sticky bottom bar**: "Jama karein" + Undo | Kaam khatam | Submit | **Sab se neeche sticky**: hamesha pohonch mein | Disabled jab kuch change na ho | Spinner | "Jama nahi hui. Data mehfooz hai, dobara dabayein" |
| A6 | Chhutti wale bache **pehle se pre-marked** (approved leave se) | Dobara kaam nahi | Sirf tasdeeq | A3 mein badge | - | - | - |

> Maujooda logic `attendance_service.py:214-215` (approved leave => absent) rakha jayega, sirf UI/route banenge.

#### (E) Admission wizard aur (F) Marks grid (mukhtasar)

| Screen | Hissa | Maqsad | Jagah/Kyun | Khali/Loading/Error |
|---|---|---|---|---|
| **Admission** | Step 1 Bacha (naam, DOB (**khali default**), gender, B-Form) | Pehchaan | Pehla, kam fields | Inline validation; loading skeleton; error "Pehle se is B-Form/walid-mobile+DOB se bacha maujood: [dekhein]" |
| | Step 2 Walid/Guardian (naam, mobile, CNIC) | Family record (S2) | Doosra | Pehle se family mile to "Isi khandan se jorein" |
| | Step 3 Class + Fee plan + documents checklist | Seat aur fee | Teesra | "Seat full" **pehle** hi dikhao (abhi admit par hi error aata hai: `school_service.py:801`) |
| | Summary + "Mehfooz karein" + "Voucher aur ID card print" | Mukammal | Aakhri | Draft autosave |
| **Marks grid** | Subject columns, rows = bache, Tab/Enter navigation | Marks bharna | Beech, spreadsheet jaisa | Max se zyada marks: row laal + foran message; "32/40 mukammal" progress upar; Excel paste |

### 9.7 End-to-end flows: pehle/baad click ginti

> **"Pehle" ginti code se hai** (har dropdown = 2 clicks: kholna + chunna). Waqt ke "pehle" ke numbers Phase 0 mein stopwatch se. **Imandari:** kuch flows mein clicks kam nahi hote, magar kaam mukammal ya mehfooz hota hai, wo saaf likha hai.

| # | Flow | **Pehle** (code se) | **Baad** (target) | Imandari ka note |
|---|---|---|---|---|
| F1 | **Haziri, 40 bache, 3 absent** | Tab (1) + "+ New Daily Attendance" (1) + class (2) + teacher (2) + Save (1) + "Validate & Sync" (1) = **8 clicks**, **magar absent mark ho hi nahi sakta** (route nahi) | Aaj Ka Din -> "Haziri lo" (1) + 3 absent tap (3) + Jama (1) = **5 clicks**, **< 60 sec** | Sab se bara farq: abhi kaam adhoora hai |
| F2 | **Poori class (40) ke fee vouchers** | Har bache: "+ Generate" (1) + student (2) + structure (2) + Save (1) = 6 x 40 = **~240 clicks** | Fee -> Class vouchers (1) + class (2) + Generate (1) + Print (1) = **~5 clicks** | 98% kam |
| F3 | **Counter par fee wasooli** | Fees tab (1) + search box (1) + type + "Pay Full" (1) = **3 clicks** (receipt nahi, partial nahi, confirm nahi, sirf bache ke naam se) | Search (autofocus, type + Enter (1)) + voucher (1) + "Wasool" (1) + confirm (1) + print receipt (1) = **5 clicks** | **Clicks barhte hain**, magar confirm (galti se bachao), receipt, partial, family search milte hain |
| F4 | **Naya admission** | "+ New Student Admission" (1) + naam (1) + last (1) + DOB (>=1) + gender (2) + class (2) + email (1) + Save (1) = **~10 clicks**, magar guardian/CNIC/documents/fee plan **capture nahi** | 3-step wizard = **~14-16 interactions** par mukammal record + voucher + ID card | Zyada qadam, **zyada mukammal data**; "Quick admission" (min fields) ka option |
| F5 | **Marks, 40 bache x 1 subject** | **UI se mumkin nahi** | Exam -> subject (2) + 40 marks (Tab, 0 clicks) + Save (1) = **~3 clicks + typing**; Excel paste = 3 clicks | Naya kaam |
| F6 | **Report cards, class 40** | **Mumkin nahi** (print/rank nahi) | Exam -> class -> Report cards -> Print = **4 clicks** | Naya kaam |
| F7 | **Baaqaya walon ko paigham (15 families)** | Defaulter list nahi; poori payslip list haath se chhaanni | Baaqaya (1) + "30+ din" filter (1) + "Sab ke paigham tayyar" (1) + har family ka "Bhejo" (15) = **18 clicks**, ~**2 min** | WhatsApp ka Send insaan dabata hai |
| F8 | **Principal: "aaj kitni fee aayi?"** | Dashboard ka figure **ab tak ki kul wasooli** hai (`SUM(paid_amount)`, `school_service.py:1269-1271`), "aaj" nahi: **jawab nahi milta** | **0 clicks** (home par) | - |
| F9 | **Walid poochte hain "fee kitni baaqi?"** | Fees tab (1) + filter (1) + bache ka naam type (sirf bache ke naam se) = **2 clicks + type** | Search (walid/mobile) type + Enter (1) + family card (1) = **2 clicks** | Walid ke naam se bhi chalega |

### 9.8 Baaqi Screens — Mukammal Placement Tables aur Click Flows (Revision v3)

> **Design Token Constraint:** In tamam screens mein sirf **"Kaghaz aur Siyahi"** ke maujooda tokens (`--kaghaz`, `--surface`, `--siyahi`, `--siyahi-soft`, `--chai`, `--pista-bg/text`, `--zafraan`, `--surkh`, `--neel`, `--rule-line`) istemal honge. Koi naya rang nahi.

#### (G) Student 360° Profile (`screens/school/student-profile.js` — Phase 2/3)

* **Khandani Khata (S2) aur PTM Sheet (S7) se rabt:** Header mein walid/guardian ke naam aur mobile par click karne se seedha **Khandani Khata (S2)** drawer/screen khulti hai jahan us walid ke tamam bachon ka mushtarik fee khata dikhta hai. Top-right action bar mein **"🖨️ PTM 1-Pager (S7)"** button hai jo isi screen ke 4 data sources (Attendance %, Fee Baaqaya, Last Exam Rank/Weak Subject, Teacher Remark) ko jod kar ek single A4 half-sheet print nikalta hai.

| # | Card / Widget | Maqsad (Purpose) | Kaunsa User | Faisla / Action | Jagah aur Kyun (Position) | Khali (Empty) | Loading | Error |
|---|---|---|---|---|---|---|---|---|
| S360-1 | **Identity Header** (Photo, Full Name, Class-Section, GR No `pid`, Roll No, Status Chip, Guardian link -> S2, PTM Print -> S7) | Bache ki fori pehchaan aur khandan/print actions | Principal, Teacher, Fee Clerk, Front Desk | Admit/Alumni status badalna, S2 kholna, S7 print karna | **Sab se upar (Full-width sticky header)**: har tab par bache ki pehchaan nazar aani chahiye | Photo na ho to initials avatar (`--chai` bg); GR `—` | Header skeleton bar | "Student record nahi mila" + Back to list |
| S360-2 | **Odoo-Style Smart-Button Strip** (6 chips: Haziri %, Fee Baaqaya PKR, Last Result/Rank, Library Books, Transport Route, Hostel Room) | Ek nazar mein bache ke 6 pehluon ka khulasa (recognition over recall) | Principal, Class Teacher, Parent (PTM) | Kisi chip par click -> niche wahi tab khul jaye | **Header ke foran neeche (Horizontal strip)**: F-pattern ki doosri line; tab khole bagair jawab milta hai | `Haziri: —`, `Fee: Rs. 0`, `Library: 0`, `Bus: No`, `Hostel: No` | 6 shimmer pills | `⚠️` icon + tooltip "Load nahi hua" |
| S360-3 | **Tab 1 — Profile & Family** (Personal details, B-Form, DOB, Address, Sibling cards via S2) | Bunyadi maloomat aur behan-bhaiyon ka rabt | Front Desk, Admin | Edit profile, Sibling link karna | **Default active tab (Left 65% column)**: sab se aam maloomat pehle | "Koi behan/bhai linked nahi — [+ Link Sibling]" | Form skeleton | "Profile load nahi hua" + Retry |
| S360-4 | **Tab 2 — Fees & Challans** (Ledger summary, payslip table, partial payment history, "+ Wasooli" button) | Is bache ka poora mali hisaab | Fee Clerk, Principal | Fee wasool karna, Challan print karna | **2nd Tab**: paisa doosra sab se ahem sawal hai | "Is bache ka abhi koi fee voucher nahi bana" | 4-row table skeleton | "Fee khata load nahi ho saka" + Retry |
| S360-5 | **Tab 3 — Attendance Calendar** (Mahana heatmap + leaves list + absent dates) | Ghair-haziri ka pattern dekhna (maslan har Jummah absent) | Class Teacher, Principal | Leave approve karna, parent ko message | **3rd Tab**: PTM aur discipline ke liye | "Is mahine abhi کوئی haziri darj nahi" | Calendar grid skeleton | "Haziri history load nahi hui" |
| S360-6 | **Tab 4 — Exams & Progress** (Term-wise marksheets, subject bar chart, class rank, weak subject badge) | Taleemi behtari ya girawat pakarna | Teacher, Exam In-charge, Principal | Report card print karna, re-evaluation | **4th Tab**: term-end par zaroori | "Abhi koi exam result mojood nahi" | Table skeleton | "Exam results load nahi hue" |
| S360-7 | **Tab 5 — Documents & Certificates** (B-Form scan, Birth cert, Leaving Certificate / Character Cert generator) | Kaghazat ki tasdeeq aur SLC jari karna | Front Desk, Principal | Document checklist tick karna, Certificate print | **5th Tab**: admission aur leaving ke waqt | "Koi document tick nahi hua — Checklist dekhein" | Skeleton rows | "Documents load nahi hue" |
| S360-8 | **Activity Timeline (`audit_log`)** (Kisne kab admission kiya, fee li, class badli) | Accountability aur mukammal tareekh | Principal / Admin | Ghalat tabdeeli pakarna | **Right-hand column (35% width, desktop par hamesha nazar mein)**: Odoo chatter pattern | "Abhi tak koi sargarmi darj nahi hui" | 3 timeline shimmer lines | "Audit log load nahi ho saka" |

---

#### (H) Timetable — Weekly Grid + "Aaj Ki Periods" (`screens/timetable/weekly-grid.js` — Phase 4)

| # | Card / Widget | Maqsad | Kaunsa User | Faisla / Action | Jagah aur Kyun | Khali | Loading | Error |
|---|---|---|---|---|---|---|---|---|
| TT-1 | **View Switcher & Filters** (Class toggle / Teacher toggle, Class dropdown, "+ Naya Period" button, "🌙 Ramazan Timing" toggle S6) | Class ya Teacher ke hisaab se timetable dekhna | Exam/Timetable In-charge, Teacher, Principal | View badalna, Ramazan mode on karna | **Top toolbar**: pehle context chunein | "Pehle class ya teacher chunein" | Skeleton bar | - |
| TT-2 | **"Aaj Ki Periods" Strip (Today's Live Strip)** (Abhi kaunsa period chal raha hai, kaun teacher kis class mein hai, kaun ghair-hazir teacher ka period khali hai) | Roz subah substitution (mutabadil teacher) lagana | Principal, Academic Coordinator, Teacher | Khali period mein substitute teacher assign karna | **Top panel (Weekly grid se upar)**: rozana ka sab se fori kaam "aaj abhi kya ho raha hai" hai | "Aaj chhutti hai / Koi period scheduled nahi" | 6 period cards shimmer | "Aaj ka schedule load nahi hua" |
| TT-3 | **Weekly 2D Grid** (Columns: Peer se Hafta; Rows: Period 1..8 + Break; Cell: Subject, Teacher, Room, Clash indicator `--surkh`) | Haftawar time table banana aur clash rokna | Timetable In-charge, Teacher | Cell click karke period add/edit karna; clash foran dekhna | **Main center workspace (Full width)**: 2D matrix ko poori chaurai chahiye | "Is class ka timetable abhi khali hai — [+ Period Add Karein]" | 6x8 grid shimmer | "Timetable load nahi ho saka" + Retry |
| TT-4 | **Clash & Workload Warning Banner** (Agar ek teacher ya room ek hi waqt do jagah ho to `--danger-bg` alert) | Ghalat timetable save hone se rokna (poka-yoke) | Timetable In-charge | Clash hal karna (`timetable_service.py:118-144` rule) | **Grid ke bilkul upar (sirf clash hone par dikhe)**: ghalti foran samne aaye | Hidden jab 0 clashes hon | - | Inline validation error |

---

#### (I) Exam In-Charge Home & Front Desk Home (`screens/dashboard/` — Phase 2)

| Screen | # | Card / Widget | Maqsad | Kaunsa User | Faisla / Action | Jagah aur Kyun | Khali | Loading | Error |
|---|---|---|---|---|---|---|---|---|---|
| **Exam Home** | EX-1 | **Active Exam Progress KPI Strip** (Active Exams, Marks Pending Classes, Result Ready Classes, Re-eval Requests) | Term exam ki tayyari aur marks collection ki raftar dekhna | Exam In-charge | Kis teacher ko marks ke liye yaad-dihani karani hai | **Top row (4 cards)**: F-pattern start | `0 Active Exams — [+ Naya Exam Banayein]` | 4 KPI skeletons | Retry |
| **Exam Home** | EX-2 | **Pending Marks Matrix** (Class x Subject grid: Green `--pista-bg` = जमा, Amber `--warn-bg` = adhoora, Grey = shuru nahi) | Ek nazar mein pata chale kaunsa ustaad peeche hai | Exam In-charge | Cell click -> seedha us subject ki Marks Grid khule | **Center-left (65% width)**: exam ke dino mein asli kaam yahi hai | "Tamam subjects ke marks mukammal hain ✓" | Matrix skeleton | "Matrix load nahi hua" |
| **Exam Home** | EX-3 | **Quick Exam Actions & Print Queue** ("+ Naya Exam", "Ranks Calculate Karein", "Gazette Print", "Bulk Report Cards") | 1-click term-end operations | Exam In-charge | Ranks generate aur report cards print karna | **Right column (35% width)**: frequent tools | Disabled jab tak marks complete na hon | - | Toast error |
| **Front Desk Home** | FD-1 | **Admission & Seat Availability Strip** (Aaj ke Inquiries/Admissions, Khali Seats कुल, Pending Documents count, ID Cards to Print) | Reception par baithay bande ko seat aur pending kaghazat dikhana | Front Desk / Admission Clerk | Walid ko foran batana ke kis class mein seat hai | **Top row (4 cards)**: walid ke pehle sawal ka jawab | `0 Admissions Today` | 4 KPI skeletons | Retry |
| **Front Desk Home** | FD-2 | **Class-Wise Seat Meter Table** (Har class: Capacity, Enrolled, Remaining Seats bar `--pista-text` / `--surkh` jab full) | Admission se pehle seat check (taake step 3 par ja kar seat full na nikle) | Front Desk | "+ Admit in this Class" button seedha row mein | **Center-left (60% width)**: reception ka rozana ka reference | "Koi class nahi bani" | Table skeleton | "Seat data load nahi hua" |
| **Front Desk Home** | FD-3 | **Incomplete Admissions & Pending Documents Queue** (Wo bache jo `draft` mein hain ya B-Form/CNIC baqi hai) | Adhoore admissions mukammal karwana | Front Desk | Click -> Admission Wizard usi step se khule | **Right column (40% width)**: follow-up list | "Tamam admissions mukammal hain ✓" | 4-row skeleton | Retry |

---

#### (J) Settings + First-Run Checklist (`screens/settings/settings.js` — Phase 2)

| # | Card / Widget | Maqsad | Kaunsa User | Faisla / Action | Jagah aur Kyun | Khali | Loading | Error |
|---|---|---|---|---|---|---|---|---|
| SET-1 | **First-Run Setup Checklist Banner** (5 qadam: 1. School Naam/Logo, 2. Academic Year, 3. Classes & Seats, 4. Fee Structure, 5. Pehla Backup — progress bar `3/5 mukammal`) | Naye school ko bina training ke 15 min mein software chalu karwana | Owner / Admin / Principal | Step par click -> wahi modal/section khule; 5/5 hone par hide ho sake | **Settings (aur Admin Home) ke sab se upar**: onboarding friction khatam karta hai | `0/5 — Aaiye school setup shuru karein` | Progress shimmer | - |
| SET-2 | **School Identity & Print Header Card** (School Name, Campus, Phone, Logo upload, Chalan Bank Account title/number) | Vouchers, Receipts aur Report Cards par school ka asli naam chhapna | Admin / Principal | Save school profile (`school_setting` table) | **Left column, Top**: sab se pehla setup | Default seed values pre-filled | Form skeleton | "Save nahi ho saka" |
| SET-3 | **Bilingual Print & Parent UI Toggle (D3 Faisla)** (`[x] Parents ke Vouchers, Receipts aur Report Cards par English ke neeche Urdu line dikhayein`) | Aap ke D3 faisle ke mutabiq: system English mein rahe, magar parent-facing prints/views mein English ke neeche Urdu tarjuma aaye | Admin / Principal | 1-click toggle (`localStorage` + `school_setting`) | **Left column, Middle**: D3 ka markazi control | Default: OFF (English only) | - | - |
| SET-4 | **Academic Calendar & Ramazan Mode (S6)** (Current Session selector, Working Days, Ramazan/Winter period timings) | Saal aur auqat-e-kar ka intezam | Admin / Principal | Active year badalna, Ramazan timing enable karna | **Left column, Bottom** | Current year selected | Skeleton | "Year update fail" |
| SET-5 | **Backup, Restore & Database Health Card** ("💾 Abhi Backup Lein", Auto-backup folder path, Last backup timestamp, `PRAGMA integrity_check` status badge, Recovery Code print) | Bijli jane ya PC kharab hone ke dar (W10) ka ilaj | Admin / Owner | 1-click `.sqlite3` backup copy + integrity check | **Right column, Top (Prominent `--pista-bg` border)**: data hifazat sab se ahem hai | `⚠️ Abhi tak koi backup nahi liya gaya!` | "Checking DB..." spinner | "Backup fail — disk space check karein" |
| SET-6 | **Users, Roles & PIN Lock Management** (Staff list, Role: Principal/Teacher/Fee Clerk/Front Desk, PIN reset) | Ek ya zyada PC par har bande ka alag role | Admin / Principal | Naya user banana, PIN reset karna | **Right column, Bottom** | Sirf default Admin user | Table skeleton | "User save nahi hua" |

---

#### (K) Outbox / Templates / Circulars (`screens/outbox/outbox.js` — Phase 5)

| # | Card / Widget | Maqsad | Kaunsa User | Faisla / Action | Jagah aur Kyun | Khali | Loading | Error |
|---|---|---|---|---|---|---|---|---|
| OUT-1 | **Connectivity & Queue Status Bar** (Internet status indicator, `Queued: 14`, `Ready to Send: 14`, `Sent Today: 38`, "🖨️ Print Fallback Slips" button) | Offline-first aur WhatsApp ke darmiyan pul (Section 8) | Fee Clerk, Front Desk, Admin | Jab internet na ho to parchi print kar lein; internet aaye to WhatsApp bhejein | **Sab se upar**: user ko foran pata ho internet hai ya offline mode | `Queue khali hai — 0 pending paighamat` | Bar skeleton | `⚠️ Offline Mode — Paighamat mehfooz hain, internet aane par bheje ja sakenge` |
| OUT-2 | **Outbox Message Queue Table** (Recipient Walid Name, Mobile `03XX`, Category: Absent/Fee Due/Circular, Preview text English+Urdu, Action: `[💬 WhatsApp Kholo]` + `[✓ Sent Mark Karein]`) | Bina paid API ke `wa.me` deep-link se 1-click par pre-typed message bhejna | Fee Clerk, Class Teacher | `WhatsApp Kholo` click -> WhatsApp Web/Desktop pre-filled khule | **Main center panel (65% width)**: rozana 15-20 messages yahan se jayenge | "Koi paigham queue mein nahi" | 6-row skeleton | "Invalid mobile number (`--surkh` badge)" |
| OUT-3 | **Bilingual Message Templates Editor** (3 ready templates: 1. Ghair-Haziri Ittila, 2. Fee Baaqaya Yaad-dihani, 3. PTM / Chhutti Circular — `{student_name}`, `{amount}`, `{date}` placeholders ke saath) | Har baar message type karne se nijat; English + Urdu (D3) dono | Admin, Principal | Template edit aur save karna | **Right panel (35% width, Tab 1)**: queue ke saath hi template dikhe | 3 default Pakistani school templates pre-loaded | Skeleton | "Template save nahi hua" |
| OUT-4 | **Circular / Notice Generator** (Class/Whole School chunein, Notice title + matn, Action: `[Queue for WhatsApp]` ya `[🖨️ A4 Notice Sheet Print (4 per page)]`) | Chhutti ya PTM ki ittila poori school ko dena (online ya kaghaz par) | Principal, Front Desk | Circular jari karna | **Right panel (Tab 2)** | "Naya circular likhein" | - | "Print/Queue fail" |

---

#### (L) Library, Hostel, Transport — Kya Rahega, Kya Hatega, aur Kyun (Phase 4/5 Cleanup)

> **Usool (Constraint #3 & #4):** Jo features kaam ke hain unhein rakho aur behtar karo; jo Odoo ke bhaari enterprise modules (`fleet`, `stock`, `purchase`) ki wajah se be-maqsad pecheeda hain unhein simple karo.

| Module | **Kya Rahega (Stays & Improved)** | **Kya Hatega / Chhupaya Jayega (Removed from UI & Why)** | Placement Table (Jo hissa rahega) |
|---|---|---|---|
| **Library** (`library_service.py`) | 1. **Book Catalog Table** (Title, Author, ISBN, Total vs Available copies)<br>2. **Quick Issue / Return Panel** (Student GR/Name search -> Book select -> Issue / Return in 2 clicks)<br>3. **Overdue & Fine List** (`penalty` calculation jo `library_service.py` mein pehle se hai) | **Hatega:** Alag se `Library Card` banane ka laazmi qadam (UI mein student ka `PID / GR No` hi uska library card hoga; backend mein auto-card ban jayega taa ke librarian ka waqt bache). Purchase/Stock supplier fields UI se hatenge. | **Top:** 3 KPIs (Available Books, Issued, Overdue). **Left 60%:** Books & Availability Table. **Right 40%:** Quick Issue/Return Form + Overdue returns list. *(Empty/Loading/Error states via standard `DataTable` component)*. |
| **Hostel** (`HostelService`) | 1. **Hostel & Room Capacity Grid** (Hostel name, Room No, Capacity vs Occupied beds, Monthly Rent)<br>2. **Resident Allocation & Fee Status** (Student, Room, Admission Date, Paid/Unpaid chip) | **Hatega:** Chhote day-schools (jin ke paas hostel nahi) ke liye Settings mein `[ ] Enable Hostel Module` toggle hoga. Jab OFF ho to sidebar se Hostel chhup jayega taake UI saaf rahe. | **Top:** Occupancy bar (Beds Total / Occupied / Free). **Left 50%:** Rooms Grid with bed meter. **Right 50%:** Residents table + 1-click `Allocate Room` & `Mark Paid`. |
| **Transport** (`TransportService`) | 1. **Routes & Vehicles Panel** (Route Name, Monthly Fare PKR, Vehicle Plate, Driver Name & Mobile `03XX`, Seats filled/total)<br>2. **Student Bus Registration List** (Student, Route, Vehicle, Fee status) | **Hatega:** Complex `Transfer Vehicle Wizard (transfer.vehicle)` alag modal ke bajaye seedha student row mein dropdown se vehicle change ho sakega. | **Top:** Routes summary cards (Driver phone + seat meter). **Bottom Full-Width:** Registered Bus Riders table with route filter & `Print Bus List (Driver Copy)`. |

---

#### (M) Admission Wizard (Expanded) aur (N) Marks Grid (Expanded) — Section 9.6(E/F) ka Mukammal Roop (Phase 4)

##### (M) Admission Wizard (`screens/school/admission-wizard.js` — 3 Steps + Quick Mode)

| # | Step / Card | Maqsad | Kaunsa User | Faisla / Action | Jagah aur Kyun | Khali | Loading | Error |
|---|---|---|---|---|---|---|---|---|
| ADM-0 | **Mode Toggle Header** (`[⚡ Quick Admission (30 sec)]` vs `[📋 Mukammal Admission Wizard (3 Steps)]` + Draft Autosave indicator) | Rush ke waqt 5-field quick entry; aam waqt mein poora record | Front Desk / Admission Clerk | Mode chunna | **Modal/Screen Top Header** | Default: Wizard (ya pichli pasand) | - | - |
| ADM-1 | **Step 1: Talib-e-Ilm ki Pehchaan** (First/Last Name, Gender, **DOB [blank default, W9 fix]**, B-Form/Bay-Form No `XXXXX-XXXXXXX-X`, Photo capture/upload) | Bache ki bunyadi pehchaan aur duplicate check | Front Desk | Type B-Form ya DOB -> live duplicate check | **Wizard Step 1 (Center Card)**: sab se pehle bacha kaun hai | Blank inputs with format masks | "Duplicate check ho raha hai..." | `⚠️ Is B-Form ya Naam+DOB se "Hamza Khan (PID/0001)" pehle se mojood hai — [Profile Dekhein]` |
| ADM-2 | **Step 2: Walid / Guardian & Khandani Khata (S2)** (Walid Mobile `03XX-XXXXXXX` **[pehla field]**, Walid Name, CNIC, Profession, Address) | Mobile number dalte hi pehle se mojood behan-bhai dhoondna (W1 fix) | Front Desk | Mobile enter -> agar family mile to 1-click `Auto-fill Family & Apply Sibling Concession` | **Wizard Step 2**: mobile pehla field is liye ke us se baqi 4 fields khud bhar jate hain | "Walid ka mobile likhein (sibling auto-detect hoga)" | "Khandan dhoonda ja raha hai..." | Invalid mobile/CNIC format inline message |
| ADM-3 | **Step 3: Class, Live Seat Meter & Documents** (Class dropdown **with live remaining seats**, Academic Year [current pre-selected], Fee Structure preview, Sibling Discount checkbox, Documents Checklist: B-Form copy, Photos, Previous SLC) | Seat full hone ki ghalti Step 3 se pehle rokna (`school_service.py:801` fix) | Front Desk | Class chunna aur documents tick karna | **Wizard Step 3**: final confirmation se pehle seat aur fee tay karna | Class chunein | Seat count shimmer | `🚫 Grade 9-A mein seats full hain (35/35) — doosra section chunein` |
| ADM-4 | **Completion Summary & 1-Click Prints** (`[✓ Admission Mukammal Karein]`, `[🖨️ Admission Form + Pehla Fee Challan Print]`, `[🪪 ID Card Print]`) | Admission ke foran baad walid ko challan aur receipt dena | Front Desk | Save & Print | **Wizard Footer / Success State** | - | "Admission darj ho raha hai..." | "Save nahi hua — aap ka form draft mein mehfooz hai, dobara dabayein" |

##### (N) Spreadsheet Marks Grid (`screens/exam/marks-grid.js` — Phase 4)

| # | Card / Widget | Maqsad | Kaunsa User | Faisla / Action | Jagah aur Kyun | Khali | Loading | Error |
|---|---|---|---|---|---|---|---|---|
| MRK-1 | **Context Bar & Progress Meter** (Exam selector, Class selector, Subject selector, Max Marks `100` / Passing `35` badge, Progress pill: `32 / 40 Entered`, `[📋 Paste from Excel]` button) | Teacher ko batana ke kis paper ke marks lag rahe hain aur kitne baaqi hain | Subject Teacher, Exam In-charge | Subject chunna ya Excel column paste karna | **Top sticky bar**: hamesha nazar mein rahe ke max marks kitne hain | "Pehle Exam, Class aur Subject chunein" | Bar shimmer | - |
| MRK-2 | **Keyboard-First Marks Table** (Columns: Roll No, GR No, Student Name, **Obtained Marks Input**, `[Absent]` checkbox, Auto `%`, Auto `Grade` chip, Auto `Pass/Fail` badge) | Bina mouse chhuye `Enter` / `Tab` / `Arrow Down` se 40 bachon ke marks 2 minute mein bharna | Subject Teacher | Number type -> `Enter` -> agli row par focus; live grade calculation | **Center full-height table**: spreadsheet ergonomics | "Is class mein is exam ke liye koi student enrolled nahi" | 15-row skeleton | **Poka-Yoke:** Agar `Obtained > Max Marks` (maslan 105/100) ya `< 0` likha to cell foran `--danger-bg` laal ho jaye + message `"Marks 0 aur 100 ke darmiyan hone chahiye"` aur Save ruk jaye |
| MRK-3 | **Live Class Summary & Rank Preview Strip** (Class Average %, Highest Marks, Pass/Fail count, `[💾 Save Draft]`, `[✓ Finalize & Compute Ranks]`) | Jama karne se pehle teacher ko poori class ka nateeja dikhana | Subject Teacher, Exam In-charge | Draft save karna ya Finalize karke ranks nikalna | **Sticky bottom bar**: Haziri sheet (A5) jaisa hi familiar pattern | `0 Entered` | "Saving..." spinner | "Marks save nahi ho sake — local draft mehfooz hai, dobara koshish karein" |

---

#### 9.9 Baaqi Screens ke Click Counts (Before vs After) aur Phase Mapping

| # | Flow | **Pehle (Current Code)** | **Baad (Target Design)** | Phase | Section 11 Effort par Asar |
|---|---|---|---|---|---|
| **F10** | **Student ki mukammal haalat dekhna** (Haziri + Fee + Result + Siblings) | 4 alag tabs (`School`, `Fees`, `Attendance`, `Exam`) mein ja kar 4 baar naam search karna = **~12 clicks + 4 searches** | Student row click -> **Student 360°** smart-button strip par 6 jawab foran = **1 click** | **Phase 2** (core shell) + **Phase 3** (fee/family tabs) | Phase 2 mein pehle se `3 hafte` rakhe hain; Student 360° read-only view isi mein fit hoga (**+0 extra weeks**, kyunke existing endpoints use honge) |
| **F11** | **Timetable banana aur aaj ka khali period dekhna** | `POST /api/timetables` ka UI hi nahi (**mumkin nahi**) | `Timetable` -> cell click -> Subject/Teacher select -> Save = **4 clicks**; "Aaj Ki Periods" strip = **0 clicks** | **Phase 4** | Phase 4 ke `7 hafte` mein G8 pehle se shamil hai (**effort unchanged**) |
| **F12** | **Naye school ki pehli baar setup + Bilingual print on karna** | Koi Settings screen nahi (**mumkin nahi**) | `Settings` (1) -> First-run checklist step ya Bilingual toggle (1) -> Save (1) = **3 clicks** | **Phase 2** | Phase 2 ke `3 hafte` (G22) mein pehle se shamil (**effort unchanged**) |
| **F13** | **Offline paigham queue se WhatsApp bhejna** | Koi messaging/outbox nahi (**mumkin nahi**) | `Outbox` (1) -> `[💬 WhatsApp Kholo]` (1) -> WhatsApp Send (1) = **3 clicks per parent** (zero typing) | **Phase 5** | Phase 5 ke `4 hafte` (G12 + S4) mein pehle se shamil (**effort unchanged**) |
| **F14** | **Library kitab issue karna** | pehle Library Card modal (5 clicks) + Issue modal (6 clicks) = **11 clicks** | `Library` -> Quick Issue panel mein Student GR + Book select -> Issue = **3 clicks** | **Phase 4** (minor polish) | Sirf UI simplification hai (**+0 extra weeks**) |
| **F15** | **Mukammal Admission (with Sibling auto-fill + Seat check)** | 6-field modal (~10 clicks), guardian/B-Form/documents capture hi nahi hote, seat full aakhir mein fail hota hai | **Quick mode:** 5 clicks; **Full 3-Step Wizard:** Walid mobile se sibling auto-fill + live seat check + Challan print = **~12 clicks** | **Phase 1** (Quick Modal) + **Phase 4** (Full 3-Step Wizard) | Phase 1 mein Quick Modal ban chuka; Phase 4 ke `7 hafte` mein G6 wizard pehle se shamil hai (**effort unchanged**) |
| **F16** | **40 bachon ke Marks enter karna + Rank** | `POST /api/exam-subjects/<id>` ka UI hi nahi (**mumkin nahi**) | `Exams` -> `Marks Grid` (2 clicks) -> 40 marks via `Enter` key (0 mouse clicks) -> `Finalize` (1 click) = **3 clicks + typing (< 3 min)** | **Phase 4** | Phase 4 ke `7 hafte` (G7 + S5) mein pehle se shamil (**effort unchanged**) |

> **Section 11 Effort Summary Check:** In 7 baaqi screens ke تفصیلی placement tables banane se **Section 11.3 ka kul hisaab (27 dev weeks base / ~34 weeks with 25% buffer) nahi badalta**, kyunke yeh tamam screens pehle hi Phase 2 (`3w`), Phase 3 (`6w`), Phase 4 (`7w`), aur Phase 5 (`4w`) ke scope (`G3, G6, G7, G8, G9, G12, G22`) mein shamil theen — ab unka per-widget design aur empty/loading/error contract bhi mukammal taur par lock ho gaya hai.

---

## 10. Technical Approach

### 10.1 File-size / zimmedari ka usool (guideline)

| Qisam | Mansooba (target) | Hadd (hard max) | Qaida |
|---|---|---|---|
| JS module | <= 200 lines | 300 | Ek file = ek screen ya ek component |
| JS function | <= 40 lines | 50 | Early return, gehra nesting nahi (> 3) |
| Python service | <= 400 | 600 | Ek aggregate (jaise `fees`) ek file |
| Python route module | <= 250 | 350 | Sirf HTTP <-> service ka pul, business logic nahi |
| CSS file | <= 250 | 350 | Ek concern (tokens / layout / components / per-screen) |
| SQL migration | ek tabdeeli | - | `NNNN_name.sql` |
| Tests | Naya feature = naya test file | - | Pehle test (RED), phir code |

**Maujooda khilaf-warziyan** (3.5): `app.js` 1752, `school_service.py` 1294, `database.py` 964, `api.py` 614. **Strangler-fig tareeqa**: naya kaam naye chhote files mein, purani file ki screens aik ek kar ke nikalti jati hain, **big-bang rewrite nahi**, har qadam par `pytest` aur `--self-test` green.

### 10.2 Maujooda structure mein naya kaam kahan jata hai (kuch move nahi, sirf izafa)

```
desktop_app/
  api.py              # chhota hota jayega: create_app() = composition root, error handlers, register_*_routes()
  database.py         # Database class wahin; SCHEMA_SQL/migrations bahar nikalte hain (Phase 0)
  exceptions.py       # as is
  db/                 # NEW  schema/<module>.sql, migrate.py, migrations/NNNN_*.sql   (PRAGMA user_version)
  routes/             # NEW  <module>_routes.py -> register_<module>_routes(app, svc)   (maujooda service-class pattern ke saath)
  services/           # maujooda; NEW: auth, audit, dashboard, search, family, outbox, backup, calendar, import, settings
  validation.py       # NEW  route boundary par input checks
  ui/
    index.html        # sirf shell
    css/              # NEW  tokens.css base.css layout.css components.css print.css + screens/*.css
    js/
      core/           # api.js state.js router.js dom.js format.js i18n.js
      components/     # data-table.js form-wizard.js empty-state.js skeleton.js confirm-dialog.js status-chip.js kpi-card.js toast.js search-box.js
      screens/<module>/   # dashboard, attendance, fees, exam, school, timetable ...
      print/          # voucher.js receipt.js report-card.js ptm-sheet.js id-card.js
    fonts/  img/icons.svg  i18n/{en,ur}.js
    app.js            # patli loader jab tak migration mukammal na ho, phir hata di jayegi
tests/
  test_all_modules.py     # maujooda, nahi chhedna
  desktop/test_<feature>.py   # NEW per feature
```

**Maujooda pattern ke saath fit:** (1) service class `XService(db)` ka pattern wahi; (2) `create_app(db, seed)` ab bhi composition root; (3) `ui/` ko `SchoolManagementERP.spec` poora bundle karta hai (`datas=[('desktop_app/ui', 'desktop_app/ui')]`, verified), is liye naye folders khud shamil; (4) CSP `script-src 'self'` same-origin `type="module"` ko rokta nahi.

### 10.3 Data model badlaav (SQLite, `PRAGMA user_version` migrations se)

| Naya / badla | Maqsad | Note |
|---|---|---|
| `app_user`, `audit_log` | Login, role, kisne kya kiya | G3 |
| `student_payslip` + `due_date`, `voucher_no`, `arrears` | Baaqaya din, challan | `ALTER TABLE ... ADD COLUMN` migration; abhi columns nahi (`database.py:330-349`) |
| **`fee_payment`** (`payslip_id`, `amount`, `mode`, `ref`, `paid_at`, `received_by`, `reversed_at`) | **Partial payment, Undo, cash tally** | Abhi sirf ek `paid_amount` hai, koi payment history nahi (verified schema). **Naya `amount` INTEGER (paisa mein)**: maujooda money columns `REAL` hain (`total/paid_amount/due_amount`, `database.py:341-343`), yaani float rounding ka khatra; purane data ka migration alag test ke saath |
| `fee_concession`, `fee_rule` | Sibling/scholarship/late fee | G5. Pehle Odoo `school_fees.py` ke rules parho (re-use) |
| `family` (+ `student_student.family_id`) **ya** maujooda `school_parent`/`students_parents_rel` ka re-use | Khandani Khata (S2) | **Faisla Phase 2 ke spike mein: pehle maujooda tables re-use, naya table sirf zaroorat par** |
| `calendar_day` | Chhutti/Ramazan (S6) | G21 |
| `outbox_message` | Paigham queue (Section 8) | G12 |
| `school_setting` | School profile, grading, fee heads | G22 |
| `exam_result` + `rank` | Rank | Compute + store |

### 10.4 Performance (naapne wale hadf)

| Hadaf | Kaise |
|---|---|
| Server-side pagination (page = 50) + `q` search; `bootstrap` sirf lookups | G2 |
| Action ke baad **sirf badli cheez refresh** (har click par poora `loadBootstrap()` nahi) | `ui/js/core/state.js` |
| Search `debounce 200ms`; `JSON.stringify` filter khatam | G10 |
| Screens lazy: dynamic `import()` | JS module split |
| Dashboard 1 query per card, **60 sec cache** | `dashboard_service.py` |
| Har naye SQL par `EXPLAIN QUERY PLAN`; naye filters par index | Section 12 |
| Fonts `font-display: swap`; Latin system font | 9.3 |
| **Budgets** (1000 students, purana PC par bhi naapna): list < 300 ms, search < 150 ms, dashboard < 500 ms, pehla paint < 2 s | Abhi: bootstrap **5.4-5.8 s** (3.4) |

> Maujooda `list_*` functions mein N+1 queries hain ya nahi, **maine audit nahi kiya** (3.7); Phase 0 ki profiling mein dekhenge.

### 10.5 Security

| Cheez | Plan |
|---|---|
| Login | `hashlib.pbkdf2_hmac` + per-user salt, 5 ghalat koshishon par lockout, session token |
| Authorization | Har route par `@require_role(...)`, **deny-by-default** (abhi koi check nahi) |
| Audit | Har write par `audit_log` (kaun, kab, kya, pehle/baad) |
| Error handling | Detail **log file** mein, client ko aam paigham (abhi `str(exc)` leak: `api.py:72-74`) |
| Input validation | `validation.py` route boundary par |
| CSRF/LAN | Login ke baad hi, session token header; `0.0.0.0` bind **aap ki izazat ke bagair nahi** (8.5) |
| CSP | Abhi inline `onclick=` ki wajah se `script-src 'unsafe-inline'`; event delegation par aa kar `unsafe-inline` hatana |
| Backup | Optional passphrase; PII bahar nahi |
| Odoo hygiene | `odoo.conf` ka stale `addons_path` aur `admin_passwd = admin` theek karna (agar Odoo use ho, D1) |

### 10.6 Testing aur TDD

* **Python:** har naye service method ka pehle test (RED), phir code (GREEN); route integration `create_app(db, seed=False)` + Flask test client (maujooda pattern `tests/test_all_modules.py`); `pytest-cov` (already `requirements.txt`) se naye code par **>= 80%**.
* **JS:** pure modules (`format.js`, validators) par `node --test` (naya tool nahi, Node mein built-in); UI scenarios ke liye Playwright (Section 12), **agar aap ki ijazat ho** (naya dev-dependency).
* **Regression:** maujooda 11 tests har phase ke baad **green** rahenge; `python run_desktop.py --self-test` bhi.

---

## 11. Phased Roadmap (realistic)

### 11.1 Kaam karne ka tareeqa (har phase mein)

Aap ke rules ke mutabiq har phase ka chakkar: **plan** (planner) -> **TDD** (tdd-guide: pehle test, RED) -> **implement** (GREEN) -> **review** (code-reviewer) -> **security-reviewer** (jahan login, paisa, files, input ho) -> **verification gate** (Section 12) -> aap ki approval. *Is planning ke dauran maine ek fact-checker subagent chalaya (Section 15); implementation mein baqi agents chalenge.*

### 11.2 Phases

#### Phase 0 — Buniyaad aur Baseline (2 hafte)

| | |
|---|---|
| **Maqsad** | Kuch naya banane se pehle **naapna** aur **data ko mehfooz karna**. |
| **Features** | (1) Baseline measurements (12.2) (2) `db/` migrations + `PRAGMA user_version` + `scripts/make_fixture.py` (1000/2000 students ka test DB) (3) Backup/restore + `PRAGMA integrity_check` (4) `api.py` ko `routes/` mein baantna (**behavior badle bina**) (5) 500-error handler theek (`api.py:72-74`) (6) asli `README.md` (7) Font/icon/library licence check + **ES-module `pywebview` par chalta hai ya nahi** test (8) `scripts/check_file_sizes.py` (9) `odoo.conf` safai (agar D1 mein Odoo) |
| **Screens** | Koi naya nahi, sirf "Backup" button |
| **Files** | `desktop_app/db/*`, `desktop_app/routes/*`, `services/backup_service.py`, `tests/desktop/{test_backup,test_migrations,test_routes_golden}.py`, `scripts/*`, `README.md` |
| **Dependencies** | D1-D3 ke jawab; ek purana PC; 2-3 staff ka 1 ghanta |
| **Risks** | Refactor se route tootna (**golden-file tests** pehle likhe jayen); purane webview mein ES modules na chalna (fallback: build-time bundle); staff ka waqt na milna |
| **Effort** | 8-10 working days (1 dev) |
| **Definition of Done** | Baseline sheet bhari aur commit; fixture 1000/2000 students DB < 5 min mein bane; migration seeded DB ki copy par chale aur data barabar; backup + restore + **kharab DB ki drill** pass; `api.py` < 150 lines, har route file <= 250; **11 purane tests + `--self-test` + golden tests green**; file-size check pass; README mein run/test/build steps |

#### Phase 1 — "Kaam chalne lage" (4-5 hafte)

| | |
|---|---|
| **Maqsad** | Roz ka kaam (haziri, dhoondna, list) **kaam kare aur tez ho**; naye look ki buniyaad. |
| **Features** | G1 haziri route + UI; G2 pagination + targeted refresh + slim bootstrap; G10 global search (Ctrl+K); G17/G18 design tokens + shell (sidebar/topbar) + components (DataTable, StatusChip, EmptyState, Skeleton, ConfirmDialog, Toast, FormWizard ka dhancha); focus/keyboard/responsive basics; **vocabulary fix**; jargon strings hatana; chhote bachaw: "Pay" par confirm, DOB default khali, `years[0]`/`schools[0]` ki jagah current year/school |
| **Screens** | Students list, Attendance, shell (baqi tabs naye shell mein, abhi redesign nahi) |
| **Files** | `ui/css/*`, `ui/js/core/*`, `ui/js/components/*`, `ui/js/screens/{school,attendance}/*`, `routes/{school,attendance}_routes.py`, `services/search_service.py`, `school_service.py` (paginated list), tests |
| **Dependencies** | Phase 0 mukammal |
| **Risks** | Aadhi migration se do UI ek saath (mitigation: **tab-ba-tab strangler**, purani tabs `app.js` se chalti rahein); ES-module compatibility (Phase 0 ka nateeja) |
| **Effort** | 4-5 hafte |
| **Definition of Done** | **F1: 5 naye teachers, bina madad, <= 5 clicks, <= 60 sec** (12.3); 1000 students par list < 300 ms, search < 150 ms (purane PC par); koi action poora `bootstrap` dobara nahi mangta; har naye component ki 3 halatein (khali/load/ghalti) dikhai ja sakti hain; keyboard-only haziri chalti hai; contrast script pass; purane tests green; naye code par coverage >= 80% |

#### Phase 2 — Roles, Audit, "Aaj Ka Din" (3 hafte)

| | |
|---|---|
| **Maqsad** | Har banda sirf apna kaam dekhe; har tabdeeli ka hisaab; har role ki home "aaj kya karna hai". |
| **Features** | G3 login/roles/audit (+ **recovery code**, setup par chhapa hua, taa ke school admin ka PIN bhool kar bahar na ho jaye); G9 dashboards (Principal, Teacher, Fee clerk, Front desk, Exam v1) + `dashboard_service.py`; G22 settings + first-run checklist; backup nishaan top bar mein |
| **Screens** | Login, Aaj Ka Din x5, Settings |
| **Files** | `services/{auth,audit,dashboard,settings}_service.py`, `routes/{auth,dashboard,settings}_routes.py`, `ui/js/screens/{dashboard,settings,login}/*`, tables `app_user`, `audit_log`, `school_setting` |
| **Dependencies** | Phase 1 (components, pagination) |
| **Risks** | Admin lock-out (recovery code); permissions ke chhed (deny-by-default test har route par); dashboard queries dheemi |
| **Effort** | 3 hafte |
| **Definition of Done** | R-P1 pass (principal 10 sec mein 3 sawal); **har route par deny-by-default test**; **har POST audit_log likhe** (test); lockout test; `security-reviewer` ki sign-off; dashboard < 500 ms (1000 students); logs mein secrets nahi |

#### Phase 3 — Paisa: Fee engine, Family, Print (6 hafte)

| | |
|---|---|
| **Maqsad** | Fee clerk ka kaam **tez, durust aur chhapa hua**. |
| **Features** | G4 (class-wise bulk vouchers, partial payment, `due_date`, defaulters, daily tally, Undo 30 sec); G5 (sibling concession, scholarship, late fee, vacation fee); S1 Chalan-Ready (3-hissa voucher, serial/QR); S2 Khandani Khata (family search + ledger); G11 print infra (A4 aur 80mm receipt, `@media print`) |
| **Screens** | Fee Counter, Vouchers, Baaqaya, Reports, Receipt/Voucher print |
| **Files** | `services/{fees,family}_service.py`, `routes/{fees,family}_routes.py`, `ui/js/screens/fees/*`, `ui/js/print/{voucher,receipt}.js`, `ui/css/print.css`, tables `fee_payment`, `fee_concession`, `fee_rule`, `student_payslip` columns |
| **Dependencies** | Phase 2 (roles/audit, **paisa audit ke bina nahi**), Phase 0 migrations |
| **Risks** | **Paisa ki durustgi** (existing money `REAL` hai: float rounding, 10.3); purane payslips ka `paid_amount` -> `fee_payment` data-migration; har school ke fee rules alag (configurable rules ka pecheeda hona); printers ka farq |
| **Effort** | 6 hafte (+1 hafta pilot feedback) |
| **Definition of Done** | F2 <= 5 clicks / < 30 sec; F3, F7, F9 pass; R-F1..R-F4 pass; **200 random payments ka tally paisa-ba-paisa barabar**; migration purane DB par data safe; security-review (paisa); do alag printers par voucher/receipt QA |

#### Phase 4 — Taleem: Exam, Timetable, Calendar, Admission, Import (7 hafte)

| | |
|---|---|
| **Maqsad** | Term-end aur admission season ka bojh kam. |
| **Features** | G7 + S5 (exam create UI, marks grid, rank, Urdu/English report card); G8 (timetable grid, create, substitution); G21 + S6 (calendar, holidays, Ramazan schedule); G6 (admission wizard, duplicate check, documents); G15 (Excel import/export, preview + error report); S7 (PTM sheet) |
| **Screens** | Exams, Marks grid, Report Cards, Timetable, Calendar, Admission wizard, Import |
| **Files** | `services/{exam,timetable,calendar,import}_service.py` (extend/new), `routes/*`, `ui/js/screens/{exam,timetable,calendar,school}/*`, `ui/js/print/{report-card,ptm-sheet,id-card}.js`, `ui/fonts/*` |
| **Dependencies** | Phase 1 (components), Phase 3 (print infra, family) |
| **Risks** | Report card ka format har board/school ka alag (**template system + kam az kam 2 asli schools ke nunay**); Urdu print fonts; Excel messy data; rank ties |
| **Effort** | 7 hafte (+1 hafta pilot) |
| **Definition of Done** | R-E1, R-D1 pass; Urdu/English report card ka visual QA (screenshot diff); rank tie rule documented + test; import 1000 rows < 60 sec + error report; timetable clash test; F4-F6 pass |

#### Phase 5 — Rabta: Outbox, WhatsApp-ready, Urdu UI (4 hafte)

| | |
|---|---|
| **Maqsad** | Parents se rabta tez aur bina API ke. |
| **Features** | G12 + S4 (outbox, templates, `wa.me`, circulars, SMTP email); G14 (Urdu RTL UI, 5 core screens); G16 (PDF/image share) |
| **Screens** | Outbox, Templates, Circulars, Urdu mode |
| **Files** | `services/outbox_service.py`, `routes/outbox_routes.py`, `ui/js/screens/outbox/*`, `ui/i18n/{en,ur}.js`, `ui/css/rtl.css`, table `outbox_message` |
| **Dependencies** | Phase 3 (vouchers/baaqaya), Phase 2 (roles) |
| **Risks** | RTL layout bugs; `wa.me` mein Urdu text ki URL-encoding; paigham ka spam lagna |
| **Effort** | 4 hafte |
| **Definition of Done** | R-C1 pass; Urdu/emoji wale link ka encoding test; outbox dedupe test; 5 core screens ka Urdu screenshot review; F7 pass |

#### Phase 6 — Optional (sirf demand aur aap ki ijazat par; schedule nahi)

LAN mode (login ke baad), parent portal snapshot, payment gateway (1LINK/JazzCash), Odoo-side graph/pivot. Har ek **6+ hafte**, aur har ek ki alag security aur privacy review.

### 11.3 Kya "6-8 hafte" haqeeqat-pasand hai? **Nahi.**

| Phase | Effort (1 dev) |
|---|---|
| P0 | 2 hafte |
| P1 | 5 hafte |
| P2 | 3 hafte |
| P3 | 6 hafte |
| P4 | 7 hafte |
| P5 | 4 hafte |
| **Jama** | **27 hafte** |
| + 25% buffer (galat andaaze, bug, refactor) | **~34 hafte** |
| + 3 pilot feedback cycle (1-2 hafte) | **~38 hafte** |

* **1 developer:** ~8-9 mahine. **2 developers** (parallel mein sirf ~1.6x speed-up, kyunke P3-P5 ek doosre par depend karte hain): **~5-6 mahine.**
* **"6-8 hafte" sirf P0 + P1 ke barabar hai**, yaani "kaam chalne lage" wala milestone, **enterprise product nahi**. Pehle plan ka 6-8 hafte ka dawa **ghalat tha**.
* Yeh andaaze maine apne tajurbe aur code ke size se lagaye hain; **Phase 0 ka baseline** aur P1 ki asli raftar dekh kar dobara hisaab hoga.

### 11.4 Dependencies ka naqsha

| Phase | Kis par depend | Kyun |
|---|---|---|
| P0 | D1-D3 | Faisla ke bagair ghalat jagah kaam |
| P1 | P0 | Migrations, routes, fixtures |
| P2 | P1 | Components, pagination |
| P3 | P2, P0 | Paisa **audit/roles ke bagair nahi**; migrations |
| P4 | P1, P3 | Components, print infra, family |
| P5 | P2, P3 | Roles, vouchers/baaqaya |
| P6 | P2 + aap ki ijazat | Security |

### 11.5 Har phase ka mushtarik "Definition of Done"

1. Naye code par tests (RED -> GREEN), coverage >= 80%.
2. **11 purane tests + `--self-test` green.**
3. File-size/zimmedari guideline (10.1) ki khilaf-warzi nahi (script se).
4. `code-reviewer` ke CRITICAL/HIGH masail band; jahan zaroori `security-reviewer` ki sign-off.
5. Section 12 ke us phase ke acceptance criteria **evidence ke saath** (`docs/verification/phase-N/`: screenshots, timing CSV).
6. Backup/restore us version par bhi chala kar dekha.
7. Chhota changelog + README update.
8. **Aap ki approval** agle phase se pehle.

---

## 12. Verification Plan

### 12.1 Usool

Har phase ke baad "kaam karta hai" ka faisla **naapa hua evidence** se, ehsas se nahi. Naap **purane PC par** aur (jab LAN aaye to) tablet par. Evidence `docs/verification/phase-N/` mein (naya folder, sirf screenshots/CSV).

### 12.2 Baseline aur hadaf (before / after)

> "Abhi" ka column: jahan code se saabit hai wahan likha; baaqi **Phase 0 mein stopwatch se bharenge** ("TBD").

| # | Metric | Kaise naapen | **Abhi** | **Hadaf** | Phase |
|---|---|---|---|---|---|
| M1 | **Naya teacher 40 bachon ki haziri (3 absent) bina madad** | Stopwatch, 5 teachers, 2-line hidayat, pehli koshish | **Mumkin nahi** (absent mark ka route nahi) | **<= 60 sec, <= 5 clicks, >= 90% bina madad kamyab** | P1 |
| M2 | Fee counter par wasooli (walid pohonchne se receipt tak) | Stopwatch, 3 clerks | TBD (receipt hi nahi) | **<= 30 sec** receipt ke saath | P3 |
| M3 | Ek class (40) ke vouchers | Clicks + stopwatch | **~240 clicks** (code se) | **<= 5 clicks, < 30 sec** | P3 |
| M4 | Principal ka jawab: "aaj kitni fee aayi, haziri kitni?" | Stopwatch, 3 principals | **Jawab nahi** (`SUM(paid_amount)` = ab tak ki kul, `school_service.py:1269-1271`) | **<= 10 sec**, 0 clicks | P2 |
| M5 | Mukammal admission (guardian + documents) | Stopwatch, 3 front-desk | Mumkin nahi (guardian/docs capture nahi) | **<= 4 min** + duplicate warning | P4 |
| M6 | Marks entry 40 bache x 1 subject | Stopwatch | **Mumkin nahi** (UI nahi) | **<= 3 min** | P4 |
| M7 | Report cards class (40) | Stopwatch | **Mumkin nahi** | **<= 2 min** | P4 |
| M8 | `bootstrap`/list @1000 students (mere PC par) | Script + DevTools | **5.4-5.8 s, 800 KB** | List **< 300 ms**, search **< 150 ms**, dashboard **< 500 ms** | P1/P2 |
| M9 | Purane PC par wohi | Wohi script, 2-4 GB RAM PC | TBD | Wohi budgets (10% slack) | P1 |
| M10 | Bijli-cut drill (form bharte waqt process kill) | Manual | Draft nahi, data ka koi backup nahi | **>= 95% fields wapas**; restore **<= 10 min** | P0/P1 |
| M11 | Accessibility | Contrast script, keyboard-only, DevTools touch size, Windows 125%/150% scaling, `1024x680` (webview `min_size`, `run_desktop.py`) | Sirf search par focus | **WCAG AA text 4.5:1**, **core 3 flows keyboard se**, touch **>= 40px** | har phase |
| M12 | Regression | `pytest tests` + `--self-test` + golden files | 11 pass | **hamesha 11+ pass** | har phase |
| M13 | Code health | `check_file_sizes.py` | 4 badi files | Naya code limit ke andar; purani files ghat'ti hui | har phase |

### 12.3 Role-wise test scenarios

| ID | Role | Scenario | Pass ka mayar | Phase |
|---|---|---|---|---|
| **R-T1** | Teacher (naya) | Login -> apni class ki haziri, 3 absent, jama | <= 60 sec, <= 5 clicks, koi madad nahi | P1/P2 |
| R-T2 | Teacher | Galti se absent laga diya -> jama se pehle Undo; jama ke baad usi din tabdeeli | Undo kaam kare; tabdeeli par `audit_log` entry | P2 |
| R-T3 | Teacher | 40 bachon ke marks; max se zyada likhna | Zyada marks **rok diye jayen**, row laal, paigham saaf | P4 |
| R-T4 | Teacher | Doosre role ka route/screen kholna | **403** + saaf paigham; screen hi nazar na aaye | P2 |
| **R-F1** | Fee clerk | Walid ke **mobile** se family dhoondna (3 bache, 2 voucher), poori fee wasool, receipt print | <= 30 sec; tally mein shamil | P3 |
| R-F2 | Fee clerk | Partial payment, 30 sec ke andar Undo; baad mein Undo | Pehle Undo ho; baad mein sirf admin, audit ke saath | P3 |
| R-F3 | Fee clerk | Class ke vouchers do baar generate | Duplicate nahi bante (maujooda `UNIQUE(student_id, date, state)` `database.py:348` + naye rules ka test) | P3 |
| R-F4 | Fee clerk/Principal | 200 random payments ke baad "aaj ka tally" | Receipts ke jama se **paisa-ba-paisa barabar** | P3 |
| **R-P1** | Principal | Home se 3 jawab: aaj ki wasooli, haziri %, baaqaya | <= 10 sec bina click | P2 |
| R-P2 | Principal | "Tawajjo talab" se leave approve karna | <= 2 clicks | P2 |
| **R-D1** | Front desk | Naya admission; wohi B-Form/walid-mobile+DOB dobara | Duplicate warning; seat full **step 3 se pehle** pata chale | P4 |
| **R-E1** | Exam in-charge | Exam banana, marks lena, rank (tie), Urdu+English report card print | Rank tie ka qaida document+test; print screenshot diff theek | P4 |
| R-A1 | Admin/Owner | Backup; DB kharab (fake corruption); restore; purane version se migration | Data barabar; restore <= 10 min | P0 |
| R-C1 | Fee clerk | Internet band: paigham queue; wapas aane par `ready`; ghalat number; duplicate | Queue mehfooz; duplicate/ghalat number **rok diye** | P5 |
| R-S1 | Security | Bina login access; `q` mein SQL injection string; naam mein `<script>`; 5 ghalat PIN | 401/403; query parameterized; `esc()` se safe; lockout | P2+ |
| R-X1 | Koi bhi | Form bharte waqt process kill | Restart par draft wapas | P1 |

### 12.4 Usability check (non-technical users ke saath)

* **Kitne log:** har role-group ke **5 asli staff** (chhote usability tests mein 5 log aam taur par zyada tar masail pakar lete hain, yeh ek heuristic hai, guarantee nahi).
* **Tareeqa:** task-based, "zor se sochein" (think-aloud), **sirf 2 line ki hidayat** ("training nahi"), screen record + stopwatch.
* **Naapna:** kamyabi %, waqt, ghalti ki ginti, madad ki darkhwast, aur **SUS score (hadaf >= 75)**.
* **Rang ka A/B:** 30 min parhai ke baad "aankhein thaki?" ka sawalnama (garm palette vs purana safed), taa ke 9.1 ka dawa saabit ho.
* **Faisla:** agar koi role-group ka kamyabi < 80%, to agla phase nahi shuru hota, pehle wo screen theek.

### 12.5 "Kya ye mehnat ke laiq hai?" check

Har phase ke baad ek line ka hisaab: `(bacha hua waqt per kaam) x (kaam kitni baar) x (kitne log)` = **mahine ke ghantay bache**; Phase 0 ke baseline se. Agar kisi feature ka bachat < uski maintenance ki qeemat, to usay **rok dein ya hata dein**.

### 12.6 Tooling

`pytest` + `pytest-cov` (pehle se `requirements.txt` mein), `node --test` (pure JS), `EXPLAIN QUERY PLAN`, DevTools (Lighthouse a11y), contrast script, `check_file_sizes.py`. **Playwright** (UI scenarios) naya dev-dependency hai, **aap ki ijazat ke baad**.

---

## 13. Honest Comparison with Odoo

> **Zaroori note:** yeh scores **meri subjective raaye** hain, kisi test se nahi nikle. Odoo ko maine **chalaya nahi** (is machine par installed nahi), us ke scores mere ilm aur research (Section 5) par mabni hain. "Baad" wale scores **hadaf** hain, jo Section 12 ke tests se saabit ya radd honge. Scale 0-10: 0 = hai hi nahi, 5 = kaam chalau, 8 = achha, 10 = behtareen.

### 13.1 Area ke hisaab se score

| Area | **Odoo** (+ OpenEduCat) | **Abhi** | **P1 ke baad** | **P3 ke baad** | **P5 ke baad** | Hum kahan |
|---|---|---|---|---|---|---|
| Core school features | 8 | 4 | 5 | 6 | 7 | **Peeche** (LMS, online admission, multi-campus nahi) |
| Polish / look | 8 | 3 | 5 | 7 | 8 | **Barabar** (design par mehnat se) |
| Ease for non-tech staff | 6 | 3 | 5 | 7 | 8 | **Aage** (khaas kaam, kam menus) |
| Automation | 7 | 2 | 3 | 6 | 7 | Barabar |
| Reporting / analytics | 8 | 2 | 3 | 5 | 6 | **Peeche**: custom pivot/report builder kabhi nahi |
| Customization | 9 | 3 | 3 | 4 | 4 | **Hamesha peeche** (Studio, python ecosystem) |
| Performance @1000 students | 7 | 3 | 7 | 7 | 7 | Barabar (local SQLite) |
| Offline / low-end PC | 3 | 8 | 8 | 8 | 8 | **Aage** |
| Pakistan localisation (challan, Urdu print, WhatsApp, Ramazan) | 3 | 1 | 2 | 6 | 8 | **Aage** |
| Security / roles / audit | 9 | 1 | 1 | 6 | 7 | **Peeche** (ACL ki gehraai, 2FA, multi-company) |
| Mobile / tablet | 7 | 0 | 2 | 3 | 5 | **Peeche** (koi native app/parent app nahi) |
| Accounting depth | 10 | 2 | 2 | 4 | 4 | **Hamesha peeche** (fee ledger hai, accounting nahi; jaan-boojh kar) |
| Ecosystem / support / updates | 10 | 1 | 1 | 2 | 2 | **Peeche** (bus-factor ek developer) |

### 13.2 Wazan wala jama (do nazariye)

| Nazariya | Odoo | Abhi | P1 | P3 | P5 |
|---|---|---|---|---|---|
| **Chhota Pakistani private school** (localisation 15%, ease 20%, offline 8%, core 20%...) | 6.34 | 2.91 | 4.18 | 6.20 | **7.20** |
| **Aam bara institute** (security 12%, reporting 15%, automation 15%, customization 8%, localisation 5%...) | 7.42 | - | - | - | **6.72** |

*(Wazan: pehle row ke liye core 20, ease 20, localisation 15, automation 10, reporting 8, performance 7, offline 8, security 6, customization 3, mobile 3. Doosre ke liye core 25, ease 10, localisation 5, automation 15, reporting 15, performance 5, offline 2, security 12, customization 8, mobile 3.)*

### 13.3 Seedha jawab: kya hum compete kar sakte hain?

1. **Chhote/darmiyane Pakistani private school (300-1500 bache) ke liye: haan, P5 ke baad Odoo ke barabar ya thora behtar**, kyunke teen cheezein humare haq mein hain: **offline (ek `.exe`), Pakistani workflow (challan, Urdu, WhatsApp, Ramazan), aur school-staff ke liye saada UI.** Magar 7.20 vs 6.34 ka farq **mere subjective scoring ki ghalti (±1) ke andar** hai, is liye isko "jeet" na kahen, "barabari" kahen.
2. **Aam bara/multi-campus institute ke liye: nahi.** Wahan Odoo jeetega (7.42 vs 6.72): security ki gehraai, analytics, customization, accounting, ecosystem.
3. **Jo hum kabhi nahi pakar payenge:** custom report/pivot builder, Studio, accounting ki gehraai, ecosystem aur support ka size. Isko chhupana nahi, **product ki hadd** batana.
4. **"\$400 ki qeemat justify hogi?"** P3-P5 ke baad **chhote school ke liye haan** (Odoo ke 10-30 users = \$3.7K-\$11K+/saal + implementer ke muqable mein bachat), **lekin sirf agar** (a) Phase 1-3 ke usability gates pass hon, (b) kam az kam 2-3 asli schools mein pilot ho, (c) support ka koi intezam ho. Warna "Odoo-level" polish ka dawa **nahi** karna chahiye.
5. **Sab se bara khatra** technical nahi: **ek developer, 8-9 mahine, aur asli schools ke feedback ke bagair andaaza.** Isi liye pehle P0-P1, phir pilot, phir aage.

---

## 14. Risks aur Open Decisions

### 14.1 Risk register

| # | Risk | Imkan | Asar | Bachao |
|---|---|---|---|---|
| R1 | Scope creep (ek developer, bohot features) | Ziyada | Ziyada | Phase gates, "NO" list (G25, biometric, chatbot), P6 optional |
| R2 | Purane Windows/`pywebview` mein ES modules ya RTL nahi chalte | Darmiyana | Ziyada | **P0 mein test**; fallback: build-time bundle |
| R3 | Refactor se purana behavior tootna | Darmiyana | Ziyada | Golden-file tests pehle, 11 tests + `--self-test`, strangler |
| R4 | Asli data seed se bohot alag (Urdu naam, duplicates, 2000 students) | Ziyada | Darmiyana | 1000/2000 fixtures, ek school ka anonymized copy (ijazat ke saath) |
| R5 | **Paisa float rounding** (maujooda money `REAL`, `database.py:341-343`) | Ziyada | Ziyada | Naye columns INTEGER (paisa), purane ka migration, reconciliation test |
| R6 | Auth se admin lock-out | Darmiyana | Ziyada | Setup par recovery code, `R-A1` drill |
| R7 | LAN/portal ki security | Darmiyana | Ziyada | Pehle auth, default OFF, aap ki izazat, security review |
| R8 | Purane school DBs ka migration | Darmiyana | Ziyada | `user_version` migrations, backup lazmi pehle |
| R9 | Staff ki mazahmat/aadat | Ziyada | Darmiyana | Role-wise saada UI, "Quick admission", purane words ka mapping, pilot |
| R10 | Printer/layout ka farq | Ziyada | Darmiyana | A4 + 80mm templates, 2 printers par QA |
| R11 | Fonts/icons/library licences | Kam | Darmiyana | P0 mein licence parhna (Noto OFL, Lucide ISC: **abhi verify nahi**), koi code bina padhe nahi |
| R12 | Estimates bina baseline ke | Ziyada | Darmiyana | P0 baseline, dobara hisaab |
| R13 | Do products (Odoo + desktop) ka drift | Darmiyana | Darmiyana | D1 par faisla; Odoo ko "behavior spec" maan kar chhoda |

### 14.2 Open decisions (aap se)

| ID | Sawal | Meri sifarish |
|---|---|---|
| **D1** | Primary product `desktop_app` ya Odoo? | `desktop_app` (A1) |
| **D2** | Single-PC ya shuru se LAN? | Single-PC pehle, LAN P6 mein (login ke baad) |
| **D3** | Urdu UI pehle ya Urdu prints pehle? | Prints pehle (P3-P4), UI P5 |
| **D4** | Kya aap ka koi asli school pilot ke liye taiyar hai (2-3 staff, 1 purana PC)? | Zaroori: iske bagair baseline aur usability gate nahi ho sakte |
| **D5** | Naye dev-dependencies (Playwright, `openpyxl`) ki ijazat? | Haan, sirf dev/import ke liye, licence check ke baad |
| **D6** | Server ko `0.0.0.0` par bind karne ki ijazat (kab aur kis shart par)? | Sirf login+audit ke baad, default OFF |

---

## 15. Self-Check Checklist

### 15.1 Aap ke 10 original steps — kya sab cover hue?

| # | Step (aap ki hidayat) | Covered? | Kahan |
|---|---|---|---|
| 1 | Meri samajh, 6-8 lines | Haan (7 lines) | Section 2 |
| 2 | Audit: tech stack, structure, modules, models, roles, flows, UI patterns; achha/kamzor/missing, **asli files ke saath** | Haan | Section 3 (+ errata 1.2) |
| 3 | School ko organization ke taur par samajhna: roles, daily/weekly/term, waqt kahan zaya, software kaise khatam kare, signature ideas, constraints | Haan | Section 4 aur 7 |
| 4 | Research aur benchmark: Odoo, doosre ERPs, UX principles **project par laagu** karke | Haan (limitation likhi) | Section 5 |
| 5 | Gap table (7 columns) | Haan | Section 6 |
| 6 | Design direction: identity, palette, role-wise navigation, **placement rule**, flows (clicks pehle/baad) | Haan | Section 9 |
| 7 | Technical approach: files, components, data model, performance, security, monolith se bachna | Haan | Section 10 |
| 8 | Phased roadmap: goal, features, screens, files, dependencies, risks, effort, DoD | Haan | Section 11 |
| 9 | Verification plan: acceptance, role scenarios, before/after, performance, a11y, regression, usability | Haan | Section 12 |
| 10 | Honest Odoo comparison, area-wise scores | Haan | Section 13 |

### 15.2 Aap ke revision ke 8 gaps — kya band hue?

| # | Gap | Band? | Kahan |
|---|---|---|---|
| 1 | Missing sections: school analysis, per-card placement table, before/after clicks, Top 10 | Haan | 4, 9.6, 9.7, 16 |
| 2 | Evidence, guesses nahi; unverified claims hata do | Haan: v1 ke 10 ghalat/unverified points ki list, jo verify nahi hua wo alag | 1.2, 3.7, 15.3 |
| 3 | >= 5 signature ideas (Pakistani) + naya rang | Haan: 7 ideas + 1 UX signature, "Kaghaz aur Siyahi" palette | 7, 9.1-9.2 |
| 4 | Offline vs internet conflict | Haan: outbox, `wa.me`, PDF/print fallback, portal baad mein | 8 |
| 5 | Imandar Odoo comparison, score | Haan: area-wise scores, do wazan, jahan peeche hain wo likha | 13 |
| 6 | Realistic roadmap: risks, dependencies, effort, DoD, 6-8 hafte par raaye | Haan: **27 hafte (~34 buffer ke saath)**; 6-8 hafte unrealistic | 11 |
| 7 | Verification: role scenarios, before/after (jaise 40 bache < 60 sec) | Haan | 12 |
| 8 | Self-check aur "jo verify na hua" | Haan | 15 |

### 15.3 Jo main **verify nahi kar saka** (mukammal list)

1. Odoo addons install/run hote hain ya nahi (Odoo is machine par nahi). Odoo-side views/reports ka sirf **count** kiya, **chalaya nahi**.
2. Odoo-side attendance form (`school_attendance/views/school_attendance_view.xml`) mein `action_present`/`action_absent` XML mein maujood hain, magar Odoo runtime na hone se live behavior verify nahi hua.
3. Odoo ki qeematein odoo.com se directly (secondary sources ke figures: \$31.10 aur \$61/user/month).
4. Pakistani vendors (PakEducate, Skoo, Edflo, ...) ke features: sirf **unke marketing claims**, maine in products ko chalaya nahi.
5. Asli school ka size, staff ka asli kaam ka waqt, aur 4.3 ke "andaza" (A) wale waqt: **sab assumptions**.
6. Mere naapay hue 334 ms / ~1 s / ~5.5 s numbers **sirf mere computer par, sirf `/api/bootstrap` ke**; purane PC par aur hoga. Baqi routes ki raftar naapi nahi.
7. Maujooda `list_*` functions mein N+1 queries hain ya nahi.
8. `pywebview` ka purane Windows par chalna, RTL Urdu ka render, ES modules ka chalna.
9. Noto fonts aur Lucide icons ki **licence terms** aur file sizes (mera ilm: OFL aur ISC, **parh kar confirm nahi kiya**).
10. PyInstaller `.exe` ka size/startup (build nahi kiya).
11. Seed data sirf 3 students ka hai; asli data ki quality (Urdu naam, duplicates) test nahi hui.
12. Section 13 ke saare scores subjective hain; Odoo ke scores bhi (Odoo ko chalaya nahi).
13. Roman Urdu wording ki asli school staff se jaanch (kuch alfaaz, jaise "Khandani Khata", unhein samajh na aaye to badlenge).

### 15.4 Independent fact-check ka nateeja

Maine ek independent **Plan Fact-Checker** subagent (`code-explorer`) chalaya jis ne is plan ke **91 concrete claims** ko repo ki asli files aur line numbers se mila kar check kiya:

* **87 claims (95.6%) bilkul exact nikle:** 69 SQLite tables, 15 modals, 25 UI API calls, 10 indexes, 11 sidebar tabs, 29 `_name` models in `school.py`, 21 report XMLs, 2 mail templates, hard-coded `2012-05-15`, `schools[0]`, `years[0]`, `homework_submission.pdf`, route gap mapping, aur tamam line numbers (`styles.css:217`, `app.js:383, 441-442, 1107-1113`, `school.py:1108`, `attendance_service.py:214-215`, waghaira).
* **4 cheezein subagent ne pakdin, aur maine unhein is file mein foran theek kar diya:**
  1. **Module versions (Section 3.1):** 9 modules `18.0.1.0.0` hain, magar `library/__manifest__.py:5` mein `"version": "17.0.1.0.0"` hai -> **theek kar diya**.
  2. **"Standard" vocabulary (Section 9.4):** Table headers (`app.js:208, 267, 351, 417`) mein pehle hi `<th>Class</th>` hai; lafz "Standard" panel title (`app.js:261`) aur modal select labels (`app.js:1186, 1220, 1345, 1420`) mein hai -> **theek kar diya**.
  3. **CSP meta tag (Section 3.1):** `index.html:6` mein `default-src 'self'` ke saath `script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;` bhi hai -> **poora string likh diya**.
  4. **Runtime benchmark (Section 3.4):** 1000-student benchmark repo ki kisi checked-in file se nahi balki mere live temp-DB run se aaya tha -> Section 3.4 aur 15.3 (#6) mein wazeh hai ke Phase 0 mein `scripts/make_fixture.py` commit hoga.
* **Mazeed 2 nuqte jo maine khud verify karke behtar kiye:**
  5. `FeesService.create_fees_register` aur `fees_register_confirm` (`fees_service.py:144-246`) Python service mein maujood hain; sirf Flask `POST` route aur UI missing hai (Section 3.3 update kiya).
  6. `school_attendance/views/school_attendance_view.xml` mein `action_present`/`action_absent` XML mein maujood hain (Section 3.7 aur 15.3 update kiye).

### 15.5 Is plan ki apni kamzoriyan

* **Time ke andaaze** sab se kamzor hissa hain (11.3): koi baseline nahi, ek developer maan kar likha.
* **UI mockups nahi banaye**, sirf tables/layout ka matn: asli screens dekh kar hi "Odoo-level" ka faisla hoga. (Plan ke baad **P1 ki ek screen ka prototype** sab se pehle dikhana behtar hoga.)
* **Pakistani school ke asli workflow** maine research aur aam ilm se likhe, kisi school mein baith kar nahi. D4 (pilot) is liye zaroori hai.
* Maine **koi code chalaya nahi** siwaye read-only checks, tests aur temp DB par timing (source mein koi tabdeeli nahi). Git `status` saaf hai (sirf yeh `ADVANCEMENT_PLAN.md` nayi file).

---

## 16. Top 10 things to do first

> Tartib: pehle **faisle aur hifazat**, phir **sab se bara hole**, phir **raftar aur look**, phir **paisa**.

| # | Kaam | Kyun pehle | Effort | Phase |
|---|---|---|---|---|
| 1 | **D1-D4 ke jawab dein** (primary product, LAN?, Urdu pehle?, pilot school) | Poora plan inhi par tikta hai; D4 ke bagair baseline nahi | 0 (aap ka waqt) | - |
| 2 | **Baseline naapna**: purana PC + 2-3 staff stopwatch + 1000/2000-student fixture | "Behtar hua" tab hi kehne ke laiq jab "pehle kya tha" maloom ho | 2-3 din | P0 |
| 3 | **Backup/restore + `PRAGMA user_version` migrations + integrity check** | Kuch badalne se pehle school ka data mehfooz; naye columns (`due_date`) ki shart | 3-4 din | P0 |
| 4 | **`api.py` ko `routes/` mein baantna** (behavior-preserving, golden tests) + 500-error leak fix (`api.py:72-74`) | Monolith todna; naya kaam saaf jagah | 3 din | P0 |
| 5 | **Haziri marking route + UI** (G1) | Sab se bara hole: **abhi teacher absent mark hi nahi kar sakta** | ~1 hafta | P1 |
| 6 | **Pagination + search + targeted refresh** (G2/G10) | 1000 students par har click 5.5 sec (naapa hua) | ~1.5 hafte | P1 |
| 7 | **Design tokens + shell + component kit (khali/load/ghalti) + vocabulary fix** ("Payslip" -> "Fee Voucher" ...) | Pehchaan aur consistency ki buniyaad; "Odoo-level" ka asli aghaaz | ~1.5 hafte | P1 |
| 8 | **Login/roles/audit + recovery code** (G3) | Paisa aur LAN se pehle accountability | ~1 hafte | P2 |
| 9 | **"Aaj Ka Din" (Principal + Teacher)** | Sab se zyada nazar aane wali screen; "dhoondna nahi, dikhao" ka saboot | ~1 hafte | P2 |
| 10 | **Fee Counter spike**: `fee_payment` (paisa INTEGER), `due_date`, class-wise vouchers, receipt | Sab se zyada faida aur sab se zyada risk: jald shuru karke seekhna | ~1 hafte spike | P3 |

---

## Approval

**Is plan par aap ki approval ka intezar hai. Koi source code nahi badla gaya.** Mushwara: pehle **#1 (D1-D4)** ka jawab dein, phir main **Phase 0** se shuru karunga aur har phase ke baad Section 12 ke evidence ke saath wapas aunga.

*Ghalti ya ghalat reference milay to bata dein, Section 15.4 ki tarah usay theek karunga.*
