import streamlit as st
from ortools.sat.python import cp_model
from supabase import create_client, Client

# --- חיבור מאובטח ל-Supabase ---
# הקוד מנסה למשוך סודות מהענן. אם לא מצליח (למשל במחשב מקומי), הוא ינסה ערכים ריקים
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
except:
    # אופציונלי: כאן אפשר לשים מפתחות לשימוש מקומי במחשב בלבד
    url = "https://jnxkieepzwenqzipanew.supabase.co"
    key = "sb_publishable__NSTZNqt12HMdRVavsPQWw_46i7z6zX"

if not url or not key:
    print("Error: Supabase secrets not found.")
else:
    supabase: Client = create_client(url, key)

def run_scheduler():
    print("--- מתחיל בתהליך השיבוץ ---")

    # שליפת נתונים
    employees = supabase.table("employees").select("*").execute().data
    requirements = supabase.table("shift_requirements").select("*").execute().data
    availability = supabase.table("availability").select("*").execute().data
    
    # מיפוי דרישות ייחודיות (ימים ומשמרות שצריך לאייש)
    shifts_keys = list(set((r['day'], r['shift_type']) for r in requirements))
    
    # מיפוי אילוצים (מתי עובד לא יכול)
    unavailable_map = {}
    for a in availability:
        if not a['is_available']:
            unavailable_map[(a['employee_id'], a['day'], a['shift_type'])] = True

    model = cp_model.CpModel()
    work = {}
    
    # יצירת משתנים בינאריים לכל עובד/משמרת
    for emp in employees:
        for day, shift_type in shifts_keys:
            work[emp['id'], day, shift_type] = model.NewBoolVar(f"work_{emp['id']}_{day}_{shift_type}")

    # אילוץ 1: עמידה בדרישות (כמות עובדים לכל תפקיד במשמרת)
    for req in requirements:
        needed_role = req['role_needed']
        needed_qty = req['quantity']
        target_day = req['day']
        target_shift = req['shift_type']
        
        relevant_employees = [e for e in employees if e['role'] == needed_role]
        # הסכום של כל העובדים בתפקיד X במשמרת הזו חייב להיות שווה לדרישה
        model.Add(sum(work[e['id'], target_day, target_shift] for e in relevant_employees) == needed_qty)

    # אילוץ 2: כיבוד אילוצי זמינות (אם עובד לא יכול -> 0)
    for emp in employees:
        for day, shift_type in shifts_keys:
            if (emp['id'], day, shift_type) in unavailable_map:
                model.Add(work[emp['id'], day, shift_type] == 0)

    # אילוץ 3: מקסימום משמרות בשבוע
    for emp in employees:
        total_shifts = sum(work[emp['id'], d, s] for d, s in shifts_keys)
        model.Add(total_shifts <= emp['max_shifts'])

    # אילוץ 4: מניעת כפילויות באותו יום (עובד לא יעשה בוקר וערב באותו יום)
    unique_days = set(s[0] for s in shifts_keys)
    for emp in employees:
        for day in unique_days:
            # רשימת כל המשמרות שקיימות ביום הספציפי הזה
            day_shifts = [s[1] for s in shifts_keys if s[0] == day]
            if len(day_shifts) > 1:
                # הסכום של המשמרות באותו יום חייב להיות קטן או שווה ל-1
                model.Add(sum(work[emp['id'], day, shift] for shift in day_shifts) <= 1)

    # הרצת הפותר
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
        
        # שמירה לדאטה בייס
        # קודם מנקים את השיבוץ הישן
        supabase.table("schedule_assignments").delete().neq("id", 0).execute()
        
        if assignments_to_save:
            supabase.table("schedule_assignments").insert(assignments_to_save).execute()
        return True
    else:
        print("לא נמצא פתרון")
        return False
