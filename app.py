from flask import Flask, request, render_template_string, redirect, url_for
from datetime import datetime
import os, json

from planner_ai import (
    generate_fake_data, train_model, predict_time, generate_schedule, load_tasks,
    save_tasks, load_prefs, save_prefs, load_subjects, save_subjects,
    retrain_model, load_exams, save_exams,
    build_exam_model, prepare_exam_tasks
)

app = Flask(__name__)

# ---------------- Models ----------------
_task_df = generate_fake_data()
task_model = train_model(_task_df)

# ---------------- Helpers ----------------
SCHEDULES_FILE = "saved_schedules.json"
MAX_SAVED_SCHEDULES = 5

def load_saved_schedules():
    if os.path.exists(SCHEDULES_FILE):
        try:
            with open(SCHEDULES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_all_schedules(schedules):
    with open(SCHEDULES_FILE, "w", encoding="utf-8") as f:
        json.dump(schedules, f, default=str, indent=2)

def add_saved_schedule(name, items):
    schedules = load_saved_schedules()
    if len(schedules) >= MAX_SAVED_SCHEDULES:
        return False, "You can only save up to 5 schedules."
    new_id = (max([s["id"] for s in schedules], default=0) + 1) if schedules else 1
    schedules.append({
        "id": new_id,
        "name": name if name.strip() else f"Schedule {new_id}",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "items": items
    })
    save_all_schedules(schedules)
    return True, "Saved."

def delete_saved_schedule(schedule_id):
    schedules = load_saved_schedules()
    schedules = [s for s in schedules if int(s.get("id", 0)) != int(schedule_id)]
    save_all_schedules(schedules)

def refresh_all_saved_schedules():
    """Re-generate and overwrite all saved schedules with latest data/state."""
    schedules = load_saved_schedules()
    if not schedules:
        return
    prefs = load_prefs()
    subjects = load_subjects()
    tasks = load_tasks(task_model)
    exams = load_exams()
    exam_model = build_exam_model(subjects)
    exam_prep = prepare_exam_tasks(exams, subjects, exam_model)
    regenerated = generate_schedule(tasks + exam_prep, prefs)
    for s in schedules:
        s["items"] = regenerated
        s["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_all_schedules(schedules)

def format_hours(hours):
    if hours is None:
        return "N/A"
    h = int(hours)
    m = int(round((hours - h) * 60 / 5) * 5)
    if m == 60:
        h += 1
        m = 0
    return f"{h} hours {m} minutes"

# ---------------- Template ----------------
HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Smart Study Planner</title>
  <meta charset="utf-8">
  <style>
    body { font-family: Arial, sans-serif; max-width: 900px; margin: auto; padding: 12px; }
    h1, h2, h3 { color: #054a91; margin: 8px 0; }
    label { font-weight: 600; margin-top: 8px; display: block; }
    input[type=number], select, input[type=date], input[type=text] {
      width: 100%; max-width: 420px; padding: 6px; margin-top: 2px;
      font-size: 14px; border: 1px solid #cbd3dd; border-radius: 4px;
    }
    input[type=submit], button {
      margin-top: 10px; background-color: #054a91; border: none;
      color: white; padding: 8px 16px; font-size: 14px; border-radius: 4px; cursor: pointer;
    }
    input[type=submit]:hover, button:hover { background-color: #063b72; }
    ul, ol { margin-top: 8px; margin-left: 22px; }
    .success-message { color: #087f23; font-weight: 700; }
    .warning { color: #b00020; font-weight: 700; }
    .tabs { display: flex; gap: 8px; margin: 10px 0; }
    .tab-btn { background: #e7effa; color: #054a91; border: 1px solid #cbd3dd; padding: 6px 12px; border-radius: 4px; cursor: pointer; }
    .tab-btn.active { background: #054a91; color: #fff; }
    .section { display: none; border: 1px solid #e5e9ef; padding: 12px; border-radius: 6px; background: #fbfcfe; }
    .section.active { display: block; }
    .schedule-table { width: 100%; border-collapse: collapse; margin-top: 14px; }
    .schedule-table th, .schedule-table td { border: 1px solid #e0e6ee; padding: 8px; font-size: 14px; }
    .schedule-table th { background: #f4f7fb; text-align: left; }
    .muted { color: #5a6775; font-size: 13px; }
    .grid { display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }
    .row { display: flex; gap: 10px; align-items: center; }
    .badge { background: #e7effa; color: #054a91; padding: 2px 8px; border-radius: 10px; margin-left: 6px; font-size: 12px; }
    .note { font-size: 12px; color: #5a6775; }
  </style>
  <script>
    function showTab(id) {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
      const btn = document.getElementById(id + '-btn');
      const sec = document.getElementById(id);
      if (btn) btn.classList.add('active');
      if (sec) sec.classList.add('active');
    }
    function addSubjectField() {
      const numSubjects = document.getElementById('num_subjects').value;
      const container = document.getElementById('subjects_container');
      container.innerHTML = '';
      for(let i=1; i <= numSubjects; i++){
        container.innerHTML += `
          <h4>Subject ${i}</h4>
          <label>Name:</label>
          <input name="subject_name_${i}" required>
          <label>Difficulty (1-10):</label>
          <input name="difficulty_${i}" type="number" min="1" max="10" required>
          <label>Desired Grade:</label>
          <select name="desired_grade_${i}">
            <option>A or above</option><option>B</option><option>C</option><option>D and below D</option>
          </select>
          <label>Current Grade:</label>
          <select name="current_grade_${i}">
            <option>A or above</option><option>B</option><option>C</option><option>D and below D</option>
          </select>
        `;
      }
    }
    function toggleCompletedInput(selectElem, taskId) {
      var div = document.getElementById("time_input_" + taskId);
      div.style.display = selectElem.value === "yes" ? "block" : "none";
    }
    function toggleExamProgress(examId) {
      var div = document.getElementById("exam_progress_" + examId);
      div.style.display = (div.style.display === "none" || div.style.display === "") ? "block" : "none";
    }
    window.addEventListener('DOMContentLoaded', () => {
      showTab('{{ default_tab|default("tasks") }}');
      const tasksBtn = document.getElementById('tasks-btn');
      const examsBtn = document.getElementById('exams-btn');
      if (tasksBtn) tasksBtn.onclick = function(ev){ ev.preventDefault(); showTab('tasks'); history.replaceState(null,'', '?tab=tasks'); };
      if (examsBtn) examsBtn.onclick = function(ev){ ev.preventDefault(); showTab('exams'); history.replaceState(null,'', '?tab=exams'); };
    });
  </script>
</head>
<body>
  <h1>Smart Study Planner</h1>

  {% if not prefs or show_pref_form %}
  <h2>Set Your Study Preferences</h2>
  <form method="POST" action="/">
    <label>Daily Study Hours:</label>
    <input name="daily_study_hours" type="number" min="0" step="0.5" value="{{ prefs.daily_study_hours if prefs else '' }}" required>
    <label>Hours per Subject Daily:</label>
    <input name="hours_per_subject" type="number" min="0" step="0.5" value="{{ prefs.hours_per_subject if prefs else '' }}" required>
    <label>Available Study Time per Day:</label>
    <input name="available_study_time" type="number" min="0" step="0.5" value="{{ prefs.available_study_time if prefs else '' }}" required>
    <label>How Many Subjects Do You Take:</label>
    <input id="num_subjects" name="num_subjects" type="number" min="1" value="{{ prefs.num_subjects if prefs else 1 }}" onchange="addSubjectField()" required>

    <div id="subjects_container">
      {% if subjects and prefs %}
        {% for i in range(1, (prefs.num_subjects|int) + 1) %}
          <h4>Subject {{ i }}</h4>
          <label>Name:</label>
          <input name="subject_name_{{ i }}" value="{{ subjects[i-1].name }}" required>
          <label>Difficulty (1-10):</label>
          <input name="difficulty_{{ i }}" type="number" min="1" max="10" value="{{ subjects[i-1].difficulty }}" required>
          <label>Desired Grade:</label>
          <select name="desired_grade_{{ i }}">
            <option {% if subjects[i-1].desired_grade == 'A or above' %}selected{% endif %}>A or above</option>
            <option {% if subjects[i-1].desired_grade == 'B' %}selected{% endif %}>B</option>
            <option {% if subjects[i-1].desired_grade == 'C' %}selected{% endif %}>C</option>
            <option {% if subjects[i-1].desired_grade == 'D and below D' %}selected{% endif %}>D and below D</option>
          </select>
          <label>Current Grade:</label>
          <select name="current_grade_{{ i }}">
            <option {% if subjects[i-1].current_grade == 'A or above' %}selected{% endif %}>A or above</option>
            <option {% if subjects[i-1].current_grade == 'B' %}selected{% endif %}>B</option>
            <option {% if subjects[i-1].current_grade == 'C' %}selected{% endif %}>C</option>
            <option {% if subjects[i-1].current_grade == 'D and below D' %}selected{% endif %}>D and below D</option>
          </select>
        {% endfor %}
      {% endif %}
    </div>

    <input type="submit" name="save_prefs" value="{% if prefs_saved %}Saved Preferences{% else %}Next{% endif %}">
  </form>
  {% if prefs_saved %}<p class="success-message">Preferences saved successfully!</p>{% endif %}

  {% else %}
  <h2>Your Study Preferences</h2>
  <p>Daily Study Hours: {{ prefs.daily_study_hours }}, Hours per Subject: {{ prefs.hours_per_subject }}, Available Time: {{ prefs.available_study_time }}, Subjects: {{ prefs.num_subjects }}</p>
  {% if subjects %}
    <ul>
      {% for s in subjects %}
        <li>{{ s.name }} — Difficulty: {{ s.difficulty }}, Desired: {{ s.desired_grade }}, Current: {{ s.current_grade }}</li>
      {% endfor %}
    </ul>
  {% endif %}
  <form method="POST" action="/">
    <input type="hidden" name="edit_prefs" value="true">
    <button type="submit">Edit Preferences</button>
  </form>

  <div class="tabs">
    <button id="tasks-btn" class="tab-btn" type="button">Tasks</button>
    <button id="exams-btn" class="tab-btn" type="button">Exams</button>
  </div>

  <!-- Tasks Section -->
  <div id="tasks" class="section">
    <h2>Tasks</h2>
    <div class="grid">
      <div>
        <h3>Add Task</h3>
        <form method="POST" action="/">
          <label>Task Name:</label>
          <input name="task" required>
          <label>Deadline:</label>
          <input name="deadline" type="date" required>
          <label>Complexity (0-10):</label>
          <input name="complexity" type="number" min="0" max="10" required>
          <label>Predicted Hours Needed:</label>
          <input name="past_hours" type="number" min="0" step="0.5" required>
          <label>Minimum Hours to Study:</label>
          <input name="min_hours" type="number" min="0" step="0.5" required>
          <label>Priority:</label>
          <select name="priority" required>
            <option>high</option><option>medium</option><option>low</option>
          </select>
          <label>Subject:</label>
          <select name="subject_name" required>
            <option value="">-- Select a Subject --</option>
            {% for s in subjects %}
              <option value="{{ s.name }}">{{ s.name }}</option>
            {% endfor %}
          </select>
          <br>
          <input type="hidden" name="add_task" value="1">
          <input type="submit" value="Add Task">
        </form>
      </div>
      <div>
        <h3>Current Tasks</h3>
        {% if all_tasks %}
          <ol>
          {% for t in all_tasks %}
            <li>
              {{ t.name }} — Deadline: {{ t.deadline.date() }} — Priority: {{ t.priority }} — Subject: {{ t.matched_subject.name if t.matched_subject else 'None' }}
              <form method="POST" action="/" style="margin-top:6px;">
                <label>Is the task completed?</label>
                <select onchange="toggleCompletedInput(this, '{{ t.id }}')">
                  <option value="no" selected>No</option>
                  <option value="yes">Yes</option>
                </select>
                <div id="time_input_{{ t.id }}" style="display:none; margin-top:5px;">
                  <label>Time spent (round minutes to nearest 5):</label><br>
                  Hours: <input name="actual_hours" type="number" min="0" step="1" required>
                  Minutes: <input name="actual_minutes" type="number" min="0" max="59" step="5" required>
                  <input type="hidden" name="complete_task_id" value="{{ t.id }}">
                  <input type="submit" value="Submit Time">
                </div>
              </form>
            </li>
          {% endfor %}
          </ol>
        {% else %}
          <p class="muted">No tasks added yet.</p>
        {% endif %}
      </div>
    </div>

    <div class="row">
      {% if (all_tasks | length) > 0 or (exams | length) > 0 %}
      <form method="POST" action="/generate"><button type="submit">Generate Schedule</button></form>
      {% endif %}
      {% if saved_schedules and (saved_schedules|length) > 0 %}
        <form method="GET" action="/"><input type="hidden" name="tab" value="tasks"><input type="hidden" name="show_saved" value="1"><button type="submit">View Saved Schedules <span class="badge">{{ saved_schedules|length }}</span></button></form>
      {% endif %}
    </div>

    {% if show_schedule and schedule %}
      <h3>Generated Schedule</h3>
      <table class="schedule-table">
        <thead><tr><th>Date</th><th>Task</th><th>Planned Study Time</th><th>Note</th></tr></thead>
        <tbody>
        {% for item in schedule %}
          <tr>
            <td>{{ item.start }}</td>
            <td>{{ item.task }}</td>
            <td>{{ format_hours(item.hours) }}</td>
            <td class="{{ 'warning' if 'Warning' in item.daily_suggestion else '' }}">{{ item.daily_suggestion }}</td>
          </tr>
        {% endfor %}
        </tbody>
      </table>

      <div class="row">
        <form method="POST" action="/save_schedule">
          <input type="text" name="schedule_name" placeholder="Schedule name (optional)" style="max-width:300px;">
          <button type="submit" {% if saved_schedules and (saved_schedules|length) >= 5 %}disabled title="Max 5 saved schedules reached."{% endif %}>Save This Schedule</button>
          <span class="note">{% if saved_schedules and (saved_schedules|length) >= 5 %}You have reached the limit of 5 saved schedules.{% endif %}</span>
        </form>
        {% if saved_schedules and (saved_schedules|length) > 0 %}
          <form method="GET" action="/"><input type="hidden" name="tab" value="tasks"><input type="hidden" name="show_saved" value="1"><button type="submit">View Saved Schedules <span class="badge">{{ saved_schedules|length }}</span></button></form>
        {% endif %}
      </div>
    {% endif %}

    {% if show_saved and saved_schedules %}
      <h3>Saved Schedules</h3>
      <p class="note">Up to 5 schedules are stored. Any task/exam changes will update all saved schedules automatically.</p>
      <ol>
      {% for s in saved_schedules %}
        <li>
          <strong>{{ s.name }}</strong> <span class="note">(Created: {{ s.created_at }}, Updated: {{ s.updated_at }})</span>
          <form method="POST" action="/delete_schedule" style="display:inline;">
            <input type="hidden" name="schedule_id" value="{{ s.id }}">
            <button type="submit">Delete</button>
          </form>
          <table class="schedule-table" style="margin-top:8px;">
            <thead><tr><th>Date</th><th>Task</th><th>Time</th><th>Note</th></tr></thead>
            <tbody>
              {% for it in s.items %}
                <tr>
                  <td>{{ it.start }}</td>
                  <td>{{ it.task }}</td>
                  <td>{{ format_hours(it.hours) }}</td>
                  <td class="{{ 'warning' if 'Warning' in it.daily_suggestion else '' }}">{{ it.daily_suggestion }}</td>
                </tr>
              {% endfor %}
            </tbody>
          </table>
        </li>
      {% endfor %}
      </ol>
    {% endif %}
  </div>

  <!-- Exams Section -->
  <div id="exams" class="section">
    <h2>Exams</h2>
    <div class="grid">
      <div>
        <h3>Add Exam</h3>
        <form method="POST" action="/">
          <label>Exam Name:</label>
          <input name="exam_name" required>
          <label>Subject:</label>
          <select name="exam_subject" required>
            <option value="">-- Select a Subject --</option>
            {% for s in subjects %}
            <option value="{{ s.name }}">{{ s.name }}</option>
            {% endfor %}
          </select>
          <label>Exam Date:</label>
          <input name="exam_date" type="date" required>
          <label>Desired Grade:</label>
          <select name="exam_desired">
            <option>A or above</option><option>B</option><option>C</option><option>D and below D</option>
          </select>
          <label>Confidence (1=low, 5=high):</label>
          <select name="exam_confidence">
            <option>1</option><option>2</option><option>3</option><option>4</option><option>5</option>
          </select>
          <label>Hours already studied (progress):</label>
          <input name="exam_progress" type="number" min="0" step="0.5" value="0">
          <input type="hidden" name="add_exam" value="1">
          <input type="submit" value="Add Exam">
        </form>
      </div>
      <div>
        <h3>Upcoming Exams</h3>
        {% if exams %}
          <ol>
          {% for e in exams %}
            <li>
              {{ e.exam_name }} — {{ e.subject_name }} — Date: {{ e.exam_date.date() }} — Desired: {{ e.desired_grade }} — Confidence: {{ e.confidence }}
              <div class="muted">Progress: {{ e.progress_hours }} hours{% if e.completed %} — COMPLETED{% endif %}</div>
              <button type="button" onclick="toggleExamProgress('{{ e.id }}')">Update Progress / Complete</button>
              <div id="exam_progress_{{ e.id }}" style="display:none; margin-top:6px;">
                {% if not e.completed %}
                <form method="POST" action="/">
                  <label>Additional hours studied now:</label>
                  <input name="add_progress_hours" type="number" min="0" step="0.5" value="0">
                  <input type="hidden" name="update_exam_id" value="{{ e.id }}">
                  <input type="submit" value="Update Progress">
                </form>
                <form method="POST" action="/" style="margin-top:6px;">
                  <label>Mark exam completed — total actual hours spent:</label>
                  <input name="exam_actual_hours" type="number" min="0" step="0.5" required>
                  <input type="hidden" name="complete_exam_id" value="{{ e.id }}">
                  <input type="submit" value="Complete Exam">
                </form>
                {% else %}
                <div class="muted">This exam is completed.</div>
                {% endif %}
              </div>
            </li>
          {% endfor %}
          </ol>
        {% else %}
          <p class="muted">No exams added yet.</p>
        {% endif %}
      </div>
    </div>

    <div class="row">
      {% if (all_tasks | length) > 0 or (exams | length) > 0 %}
      <form method="POST" action="/generate"><button type="submit">Generate Schedule</button></form>
      {% endif %}
      {% if saved_schedules and (saved_schedules|length) > 0 %}
        <form method="GET" action="/"><input type="hidden" name="tab" value="exams"><input type="hidden" name="show_saved" value="1"><button type="submit">View Saved Schedules <span class="badge">{{ saved_schedules|length }}</span></button></form>
      {% endif %}
    </div>
  </div>

  {% endif %}
</body>
</html>
"""

# ---------------- Routes ----------------

@app.route('/', methods=['GET', 'POST'])
def home():
    global task_model
    prefs = load_prefs()
    subjects = load_subjects()
    exams = load_exams()
    all_tasks = [t for t in load_tasks(task_model) if not t.get('completed', False)] if prefs else []

    # Saved schedules controls
    saved_schedules = load_saved_schedules()
    show_saved = request.args.get('show_saved', '0') == '1'

    schedule = None
    show_schedule = False
    prefs_saved = False
    show_pref_form = False
    default_tab = request.args.get('tab', 'tasks')

    if request.method == 'POST':
        # Save preferences
        if 'save_prefs' in request.form:
            num_subjects = int(request.form.get('num_subjects', 1))
            new_subjects = []
            for i in range(1, num_subjects + 1):
                new_subjects.append({
                    'name': request.form.get(f'subject_name_{i}', f'Subject {i}'),
                    'difficulty': int(request.form.get(f'difficulty_{i}', 5)),
                    'desired_grade': request.form.get(f'desired_grade_{i}', 'B'),
                    'current_grade': request.form.get(f'current_grade_{i}', 'B')
                })
            new_prefs = {
                'daily_study_hours': float(request.form.get('daily_study_hours', 0)),
                'hours_per_subject': float(request.form.get('hours_per_subject', 0)),
                'available_study_time': float(request.form.get('available_study_time', 0)),
                'num_subjects': num_subjects
            }
            save_prefs(new_prefs)
            save_subjects(new_subjects)
            # Refresh saved schedules on preference updates too (optional)
            refresh_all_saved_schedules()
            return redirect(url_for('home', tab='tasks'))

        elif 'edit_prefs' in request.form:
            show_pref_form = True

        # Add Task
        elif 'add_task' in request.form:
            next_id = max([t['id'] for t in load_tasks(task_model)] + [0]) + 1
            task = request.form.get('task', '').strip()
            deadline = request.form.get('deadline', '')
            complexity = max(0, min(10, int(request.form.get('complexity', 0))))
            past_hours = max(0.0, float(request.form.get('past_hours', 0)))
            min_hours = max(0.0, float(request.form.get('min_hours', 0)))
            priority = request.form.get('priority', 'medium')
            subject_name = request.form.get('subject_name', None)

            matched_subject = next((s for s in subjects if s['name'] == subject_name), None)
            priority_num = {'high':3, 'medium':2, 'low':1}.get(priority, 2)
            predicted = predict_time(task_model, complexity, past_hours, priority_num, matched_subject)
            predicted_hours = max(min_hours, predicted)

            try:
                deadline_dt = datetime.strptime(deadline, "%Y-%m-%d")
            except Exception:
                deadline_dt = datetime.now()

            new_task = {
                'id': next_id, 'name': task, 'deadline': deadline_dt, 'hours': predicted_hours,
                'priority': priority, 'complexity': complexity, 'past_hours': past_hours,
                'min_hours': min_hours, 'matched_subject': matched_subject,
                'completed': False, 'actual_hours': None, 'completion_date': None
            }
            full = load_tasks(task_model) + [new_task]
            save_tasks(full)
            refresh_all_saved_schedules()
            return redirect(url_for('home', tab='tasks'))

        # Complete Task
        elif 'complete_task_id' in request.form:
            task_id = int(request.form.get('complete_task_id'))
            hours = int(request.form.get('actual_hours', 0))
            minutes = int(request.form.get('actual_minutes', 0))
            rounded_minutes = round(minutes / 5) * 5
            if rounded_minutes == 60:
                hours += 1
                rounded_minutes = 0
            actual_hours = hours + rounded_minutes / 60
            full = load_tasks(task_model)
            for t in full:
                if t['id'] == task_id:
                    t['completed'] = True
                    t['actual_hours'] = actual_hours
                    t['completion_date'] = datetime.now().date()
                    pr_num = {'high':3, 'medium':2, 'low':1}.get(t['priority'], 2)
                    task_model = retrain_model(task_model, {
                        'complexity': t['complexity'],
                        'past_hours': t['past_hours'],
                        'priority': pr_num,
                        'actual_hours': actual_hours
                    })
            save_tasks(full)
            refresh_all_saved_schedules()
            return redirect(url_for('home', tab='tasks'))

        # Add Exam
        elif 'add_exam' in request.form:
            exams_list = load_exams()
            next_eid = max([e['id'] for e in exams_list] + [0]) + 1
            exam_name = request.form.get('exam_name', '').strip()
            subj_name = request.form.get('exam_subject', '')
            exam_date = request.form.get('exam_date', '')
            desired = request.form.get('exam_desired', 'B')
            confidence = int(request.form.get('exam_confidence', 3))
            progress = max(0.0, float(request.form.get('exam_progress', 0.0)))
            try:
                exam_dt = datetime.strptime(exam_date, "%Y-%m-%d")
            except Exception:
                exam_dt = datetime.now()
            exams_list.append({
                'id': next_eid, 'subject_name': subj_name, 'exam_name': exam_name, 'exam_date': exam_dt,
                'desired_grade': desired, 'confidence': confidence, 'progress_hours': progress,
                'predicted_hours': 0.0, 'completed': False, 'actual_hours_spent': None
            })
            save_exams(exams_list)
            refresh_all_saved_schedules()
            return redirect(url_for('home', tab='exams'))

        # Update Exam Progress
        elif 'update_exam_id' in request.form:
            eid = int(request.form.get('update_exam_id'))
            add_p = max(0.0, float(request.form.get('add_progress_hours', 0.0)))
            exs = load_exams()
            for e in exs:
                if e['id'] == eid and not e.get('completed', False):
                    e['progress_hours'] = float(e.get('progress_hours', 0.0)) + add_p
            save_exams(exs)
            refresh_all_saved_schedules()
            return redirect(url_for('home', tab='exams'))

        # Complete Exam
        elif 'complete_exam_id' in request.form:
            eid = int(request.form.get('complete_exam_id'))
            actual = max(0.0, float(request.form.get('exam_actual_hours', 0.0)))
            exs = load_exams()
            for e in exs:
                if e['id'] == eid:
                    e['completed'] = True
                    e['actual_hours_spent'] = actual
            save_exams(exs)
            refresh_all_saved_schedules()
            return redirect(url_for('home', tab='exams'))

    # GET or after redirect
    show_saved = request.args.get('show_saved', '0') == '1'
    return render_template_string(
        HTML,
        prefs=prefs,
        subjects=subjects,
        exams=exams,
        all_tasks=all_tasks,
        schedule=None,
        show_schedule=False,
        saved_schedules=load_saved_schedules(),
        show_saved=show_saved,
        prefs_saved=prefs_saved,
        show_pref_form=show_pref_form,
        default_tab=request.args.get('tab', 'tasks'),
        format_hours=format_hours,
        range=range
    )

@app.route('/generate', methods=['POST'])
def generate():
    prefs = load_prefs()
    subjects = load_subjects()
    tasks = load_tasks(task_model)
    exams = load_exams()

    exam_model = build_exam_model(subjects)
    exam_prep_tasks = prepare_exam_tasks(exams, subjects, exam_model)

    all_for_schedule = tasks + exam_prep_tasks
    schedule = generate_schedule(all_for_schedule, prefs)

    return render_template_string(
        HTML,
        prefs=prefs,
        subjects=subjects,
        exams=exams,
        all_tasks=[t for t in tasks if not t.get('completed', False)],
        schedule=schedule,
        show_schedule=True,
        saved_schedules=load_saved_schedules(),
        show_saved=False,
        prefs_saved=False,
        show_pref_form=False,
        default_tab='tasks',
        format_hours=format_hours,
        range=range
    )

@app.route('/save_schedule', methods=['POST'])
def save_schedule():
    # We regenerate a fresh schedule now and persist it
    prefs = load_prefs()
    subjects = load_subjects()
    tasks = load_tasks(task_model)
    exams = load_exams()
    exam_model = build_exam_model(subjects)
    exam_prep_tasks = prepare_exam_tasks(exams, subjects, exam_model)
    current_schedule = generate_schedule(tasks + exam_prep_tasks, prefs)

    name = request.form.get("schedule_name", "").strip()
    ok, msg = add_saved_schedule(name if name else "Saved Schedule", current_schedule)
    # After save, show saved schedules list
    return redirect(url_for('home', tab='tasks', show_saved=1))

@app.route('/delete_schedule', methods=['POST'])
def delete_schedule():
    schedule_id = request.form.get("schedule_id", None)
    if schedule_id:
        delete_saved_schedule(schedule_id)
    return redirect(url_for('home', tab='tasks', show_saved=1))

if __name__ == "__main__":
    app.run(debug=True)
