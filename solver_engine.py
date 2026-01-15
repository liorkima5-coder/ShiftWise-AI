from ortools.sat.python import cp_model
from supabase import create_client, Client

# --- עדכן מפתחות כאן ---
url = st.secrets["https://jnxkieepzwenqzipanew.supabase.co"]
key = st.secrets["sb_publishable__NSTZNqt12HMdRVavsPQWw_46i7z6zX"]
supabase: Client = create_client(url, key)

def run_scheduler():
    print("--- מתחיל בתהליך השיבוץ (גרסה עברית) ---")

    employees = supabase.table("employees").select("*").execute().data
    requirements = supabase.table("shift_requirements").select("*").execute().data
    availability = supabase.table("availability").select("*").execute().data
    
    # שליפת ימים ומשמרות מהדרישות שהמשתמש הגדיר
    # לדוגמה: אם המשתמש הגדיר רק 'שישי'-'בוקר', אז רק זה יהיה ברשימה
    shifts_keys = list(set((r['day'], r['shift_type']) for r in requirements))
    
    unavailable_map = {}
    for a in availability:
        if not a['is_available']:
            unavailable_map[(a['employee_id'], a['day'], a['shift_type'])] = True

    model = cp_model.CpModel()
    work = {}
    
    for emp in employees:
        for day, shift_type in shifts_keys:
            work[emp['id'], day, shift_type] = model.NewBoolVar(f"work_{emp['id']}_{day}_{shift_type}")

    # אילוץ 1: עמידה בדרישות (כמות עובדים)
    for req in requirements:
        needed_role = req['role_needed']
        needed_qty = req['quantity']
        target_day = req['day']
        target_shift = req['shift_type']
        
        relevant_employees = [e for e in employees if e['role'] == needed_role]
        model.Add(sum(work[e['id'], target_day, target_shift] for e in relevant_employees) == needed_qty)

    # אילוץ 2: זמינות
    for emp in employees:
        for day, shift_type in shifts_keys:
            if (emp['id'], day, shift_type) in unavailable_map:
                model.Add(work[emp['id'], day, shift_type] == 0)

    # אילוץ 3: מקסימום משמרות
    for emp in employees:
        total_shifts = sum(work[emp['id'], d, s] for d, s in shifts_keys)
        model.Add(total_shifts <= emp['max_shifts'])

    # אילוץ 4: עובד לא יכול לעבוד כפול באותו יום (בוקר + ערב)
    unique_days = set(s[0] for s in shifts_keys)
    for emp in employees:
        for day in unique_days:
            day_shifts = [s[1] for s in shifts_keys if s[0] == day]
            if len(day_shifts) > 1:
                model.Add(sum(work[emp['id'], day, shift] for shift in day_shifts) <= 1)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print("נמצא פתרון!")
        assignments_to_save = []
        for emp in employees:
            for day, shift_type in shifts_keys:
                if solver.Value(work[emp['id'], day, shift_type]) == 1:
                    assignments_to_save.append({
                        "employee_id": emp['id'],
                        "day": day,
                        "shift_type": shift_type,
                        "role_assigned": emp['role']
                    })
        
        supabase.table("schedule_assignments").delete().neq("id", 0).execute()
        if assignments_to_save:
            supabase.table("schedule_assignments").insert(assignments_to_save).execute()
        return True
    else:
        print("לא נמצא פתרון")
        return False