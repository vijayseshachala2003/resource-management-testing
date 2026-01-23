import streamlit as st
import pandas as pd
from datetime import datetime, date, time as dt_time

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(page_title="Attendance Management System", layout="wide")

# -----------------------------
# SESSION STATE INIT
# -----------------------------
if "role" not in st.session_state:
    st.session_state.role = "User"

if "clock" not in st.session_state:
    st.session_state.clock = {
        "is_clocked_in": False,
        "mode": "WFH",
        "clock_in_time": None,
        "last_clock_event": None,
    }

if "attendance_logs" not in st.session_state:
    st.session_state.attendance_logs = []

if "leave_requests" not in st.session_state:
    st.session_state.leave_requests = []

if "user_name" not in st.session_state:
    st.session_state.user_name = "Employee"

if "user_project" not in st.session_state:
    st.session_state.user_project = "Project A"

if "shift_start" not in st.session_state:
    st.session_state.shift_start = dt_time(10, 0)  # 10:00 AM

if "shift_end" not in st.session_state:
    st.session_state.shift_end = dt_time(19, 0)  # 7:00 PM

if "weekoffs" not in st.session_state:
    st.session_state.weekoffs = ["Saturday", "Sunday"]

# -----------------------------
# HELPERS
# -----------------------------
def fmt_time_only(dt):
    return dt.strftime("%I:%M:%S %p") if dt else ""

def secs_to_hhmmss(s: int) -> str:
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h:02d}h {m:02d}m {sec:02d}s"

def now_local():
    return datetime.now()

def calc_days(start_d: date, end_d: date) -> int:
    return (end_d - start_d).days + 1

def clock_in(mode: str):
    clk = st.session_state.clock
    if clk["is_clocked_in"]:
        return
    clk["mode"] = mode
    clk["is_clocked_in"] = True
    clk["clock_in_time"] = now_local()
    clk["last_clock_event"] = f"Clock-in ({mode}) at {fmt_time_only(clk['clock_in_time'])}"

def clock_out():
    clk = st.session_state.clock
    if not clk["is_clocked_in"] or clk["clock_in_time"] is None:
        return

    out_time = now_local()
    duration = int((out_time - clk["clock_in_time"]).total_seconds())
    duration = max(0, duration)

    st.session_state.attendance_logs.insert(0, {
        "user": st.session_state.user_name,
        "project": st.session_state.user_project,
        "date": str(date.today()),
        "mode": clk["mode"],
        "clock_in": fmt_time_only(clk["clock_in_time"]),
        "clock_out": fmt_time_only(out_time),
        "duration": secs_to_hhmmss(duration),
        "status": "PENDING",
        "admin_note": "",
    })

    clk["is_clocked_in"] = False
    clk["clock_in_time"] = None
    clk["last_clock_event"] = f"Clock-out at {fmt_time_only(out_time)} (Worked {secs_to_hhmmss(duration)})"

def get_live_duration():
    clk = st.session_state.clock
    if clk["is_clocked_in"] and clk["clock_in_time"] is not None:
        elapsed = int((now_local() - clk["clock_in_time"]).total_seconds())
        return max(0, elapsed)
    return 0

def add_leave_request(user, project, leave_type, start_d, end_d, half_day_type, reason, proof_attached):
    rid = f"LR-{len(st.session_state.leave_requests)+1:04d}"
    
    if leave_type == "Full Day":
        days = calc_days(start_d, end_d)
        is_unpaid = days > 2
        display_days = f"{days} day(s)"
    else:
        days = 0.5
        is_unpaid = False
        display_days = f"0.5 day ({half_day_type})"
    
    st.session_state.leave_requests.insert(0, {
        "id": rid,
        "user": user,
        "project": project,
        "leave_type": leave_type,
        "start_date": str(start_d),
        "end_date": str(end_d) if leave_type == "Full Day" else str(start_d),
        "half_day_type": half_day_type if leave_type == "Half Day" else "-",
        "days": display_days,
        "unpaid": "Yes" if is_unpaid else "No",
        "reason": reason,
        "proof_attached": "Yes" if proof_attached else "No",
        "status": "PENDING",
        "admin_reason": "",
        "created_at": now_local().strftime("%Y-%m-%d %I:%M %p"),
    })
    return rid

# -----------------------------
# TOP BAR
# -----------------------------
col1, col2, col3 = st.columns([3, 5, 2])

with col1:
    st.markdown("### 📋 Attendance Management")

with col2:
    st.text_input("Search", placeholder="Search employees, requests...", label_visibility="collapsed", key="search_box")

with col3:
    st.selectbox("Role", ["User", "Admin"], key="role", label_visibility="collapsed")

st.divider()

# -----------------------------
# USER PROFILE (for Users only)
# -----------------------------
if st.session_state.role == "User":
    with st.expander("👤 My Profile", expanded=False):
        col_a, col_b = st.columns(2)
        with col_a:
            st.session_state.user_name = st.text_input("Name", value=st.session_state.user_name)
        with col_b:
            st.session_state.user_project = st.text_input("Project", value=st.session_state.user_project)

# -----------------------------
# NAVIGATION
# -----------------------------
if st.session_state.role == "User":
    nav = st.tabs(["ATTENDANCE", "LEAVE"])
else:
    nav = st.tabs(["PROJECT APPROVALS", "LEAVE APPROVALS", "SETTINGS"])

# =============================
# USER - ATTENDANCE TAB
# =============================
if st.session_state.role == "User":
    with nav[0]:
        st.subheader("⏰ Clock In/Out")
        
        col_left, col_right = st.columns([1, 1])
        
        with col_left:
            box = st.container(border=True)
            with box:
                now = now_local()
                st.markdown(f"### {now.strftime('%I:%M:%S %p')}")
                st.caption(now.strftime("%A, %d %B %Y"))
                st.markdown("---")
                
                mode = st.radio("Mode", ["WFH", "Onsite"], horizontal=True, key="clock_mode")
                
                if st.session_state.clock["is_clocked_in"]:
                    st.success(f"✅ Clocked-in ({st.session_state.clock['mode']})")
                    st.caption(f"Since: {fmt_time_only(st.session_state.clock['clock_in_time'])}")
                    live_duration = get_live_duration()
                    st.metric("Working Duration", secs_to_hhmmss(live_duration))
                    
                    if st.button("🔴 Clock Out", type="primary", use_container_width=True):
                        clock_out()
                        st.rerun()
                else:
                    st.info("⏸️ Not clocked-in")
                    if st.button("🟢 Clock In", type="primary", use_container_width=True):
                        clock_in(mode)
                        st.rerun()
                
                if st.session_state.clock["last_clock_event"]:
                    st.markdown("---")
                    st.caption(f"Last event: {st.session_state.clock['last_clock_event']}")
                
                st.markdown("---")
                st.caption(f"⏰ Shift: {st.session_state.shift_start.strftime('%I:%M %p')} - {st.session_state.shift_end.strftime('%I:%M %p')}")
                st.caption(f"🏖️ Week-offs: {', '.join(st.session_state.weekoffs)}")
        
        with col_right:
            st.markdown("### 📊 My Attendance Logs")
            
            if st.session_state.attendance_logs:
                df = pd.DataFrame(st.session_state.attendance_logs)
                my_logs = df[df["user"] == st.session_state.user_name].copy()
                
                if not my_logs.empty:
                    # Status filter tabs
                    status_tabs = st.tabs(["All", "Pending", "Approved", "Rejected"])
                    
                    with status_tabs[0]:
                        st.dataframe(
                            my_logs[["date", "mode", "clock_in", "clock_out", "duration", "status", "admin_note"]],
                            use_container_width=True,
                            hide_index=True
                        )
                    
                    with status_tabs[1]:
                        pending = my_logs[my_logs["status"] == "PENDING"]
                        if not pending.empty:
                            st.dataframe(
                                pending[["date", "mode", "clock_in", "clock_out", "duration"]],
                                use_container_width=True,
                                hide_index=True
                            )
                        else:
                            st.info("No pending attendance logs.")
                    
                    with status_tabs[2]:
                        approved = my_logs[my_logs["status"] == "APPROVED"]
                        if not approved.empty:
                            st.dataframe(
                                approved[["date", "mode", "clock_in", "clock_out", "duration", "admin_note"]],
                                use_container_width=True,
                                hide_index=True
                            )
                        else:
                            st.info("No approved attendance logs.")
                    
                    with status_tabs[3]:
                        rejected = my_logs[my_logs["status"] == "REJECTED"]
                        if not rejected.empty:
                            st.dataframe(
                                rejected[["date", "mode", "clock_in", "clock_out", "duration", "admin_note"]],
                                use_container_width=True,
                                hide_index=True
                            )
                        else:
                            st.info("No rejected attendance logs.")
                else:
                    st.info("No attendance logs yet.")
            else:
                st.info("No attendance logs yet. Clock in to start tracking.")

# =============================
# USER - LEAVE TAB
# =============================
if st.session_state.role == "User":
    with nav[1]:
        st.subheader("🏖️ Apply for Leave")
        
        col_left, col_right = st.columns([1, 1])
        
        with col_left:
            box = st.container(border=True)
            with box:
                st.markdown("#### Leave Request Form")
                
                leave_type = st.radio("Leave Type", ["Full Day", "Half Day"], horizontal=True, key="leave_type_radio")
                
                if leave_type == "Full Day":
                    col_a, col_b = st.columns(2)
                    with col_a:
                        start_d = st.date_input("From Date", value=date.today(), min_value=date.today(), key="start_date")
                    with col_b:
                        end_d = st.date_input("To Date", value=date.today(), min_value=date.today(), key="end_date")
                    
                    days = calc_days(start_d, end_d)
                    if days > 2:
                        st.warning(f"⚠️ {days} days leave will be marked as **Non-Paid Leave**")
                    else:
                        st.info(f"ℹ️ {days} day(s) - Paid Leave")
                    
                    half_day_type = None
                else:
                    start_d = st.date_input("Date", value=date.today(), min_value=date.today(), key="half_day_date")
                    end_d = start_d
                    half_day_type = st.radio("Half Day Type", ["First Half", "Second Half"], horizontal=True, key="half_day_type_radio")
                    st.info("ℹ️ 0.5 day - Paid Leave")
                
                reason = st.text_area("Reason", height=100, placeholder="Enter reason for leave...")
                proof = st.file_uploader("Upload Proof (Optional)", type=["png", "jpg", "jpeg", "pdf"], accept_multiple_files=False)
                
                if st.button("✉️ Submit Leave Request", type="primary", use_container_width=True):
                    if not reason.strip():
                        st.error("❌ Reason is required.")
                    elif leave_type == "Full Day" and end_d < start_d:
                        st.error("❌ End date must be >= start date.")
                    else:
                        rid = add_leave_request(
                            user=st.session_state.user_name,
                            project=st.session_state.user_project,
                            leave_type=leave_type,
                            start_d=start_d,
                            end_d=end_d,
                            half_day_type=half_day_type,
                            reason=reason.strip(),
                            proof_attached=(proof is not None),
                        )
                        st.success(f"✅ Leave request submitted: **{rid}**")
                        st.balloons()
                        st.rerun()
        
        with col_right:
            st.markdown("### 📜 My Leave History")
            if st.session_state.leave_requests:
                df = pd.DataFrame(st.session_state.leave_requests)
                my_leaves = df[df["user"] == st.session_state.user_name].copy()
                if not my_leaves.empty:
                    # Filter tabs for leave status
                    status_tabs = st.tabs(["All", "Pending", "Approved", "Rejected"])
                    
                    with status_tabs[0]:
                        st.dataframe(
                            my_leaves[["id", "leave_type", "start_date", "end_date", "half_day_type", "days", "unpaid", "reason", "status", "admin_reason", "created_at"]],
                            use_container_width=True,
                            hide_index=True
                        )
                    
                    with status_tabs[1]:
                        pending_leaves = my_leaves[my_leaves["status"] == "PENDING"]
                        if not pending_leaves.empty:
                            st.dataframe(
                                pending_leaves[["id", "leave_type", "start_date", "end_date", "half_day_type", "days", "unpaid", "reason", "created_at"]],
                                use_container_width=True,
                                hide_index=True
                            )
                        else:
                            st.info("No pending leave requests.")
                    
                    with status_tabs[2]:
                        approved_leaves = my_leaves[my_leaves["status"] == "APPROVED"]
                        if not approved_leaves.empty:
                            st.dataframe(
                                approved_leaves[["id", "leave_type", "start_date", "end_date", "half_day_type", "days", "unpaid", "admin_reason", "created_at"]],
                                use_container_width=True,
                                hide_index=True
                            )
                        else:
                            st.info("No approved leaves.")
                    
                    with status_tabs[3]:
                        rejected_leaves = my_leaves[my_leaves["status"] == "REJECTED"]
                        if not rejected_leaves.empty:
                            st.dataframe(
                                rejected_leaves[["id", "leave_type", "start_date", "end_date", "half_day_type", "days", "unpaid", "reason", "admin_reason", "created_at"]],
                                use_container_width=True,
                                hide_index=True
                            )
                        else:
                            st.info("No rejected leaves.")
                    
                    # Leave Balance Summary
                    st.markdown("---")
                    st.markdown("#### 📊 Leave Balance Summary")
                    balance_col1, balance_col2, balance_col3 = st.columns(3)
                    
                    approved_count = len(my_leaves[my_leaves["status"] == "APPROVED"])
                    pending_count = len(my_leaves[my_leaves["status"] == "PENDING"])
                    
                    with balance_col1:
                        st.metric("Total Leaves", "20 days", help="Annual leave quota")
                    with balance_col2:
                        st.metric("Used", f"{approved_count} days", help="Approved leaves")
                    with balance_col3:
                        remaining = max(0, 20 - approved_count)
                        st.metric("Remaining", f"{remaining} days", help="Available leaves")
                else:
                    st.info("No leave history yet.")
            else:
                st.info("No leave history yet.")

# =============================
# ADMIN - PROJECT APPROVALS (Attendance)
# =============================
if st.session_state.role == "Admin":
    with nav[0]:
        st.subheader("✅ Project Approvals - Attendance Logs")
        
        if not st.session_state.attendance_logs:
            st.info("No attendance logs yet.")
        else:
            df = pd.DataFrame(st.session_state.attendance_logs)
            
            # Filters
            st.markdown("### 🔍 Filters")
            filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
            
            with filter_col1:
                projects = ["All"] + sorted(df["project"].unique().tolist())
                selected_project = st.selectbox("Project", projects, key="att_project_filter")
            
            with filter_col2:
                users = ["All"] + sorted(df["user"].unique().tolist())
                selected_user = st.selectbox("User", users, key="att_user_filter")
            
            with filter_col3:
                statuses = ["All", "PENDING", "APPROVED", "REJECTED"]
                selected_status = st.selectbox("Status", statuses, key="att_status_filter")
            
            with filter_col4:
                selected_date = st.date_input("Date", value=None, key="att_date_filter")
            
            # Apply filters
            filtered_df = df.copy()
            if selected_project != "All":
                filtered_df = filtered_df[filtered_df["project"] == selected_project]
            if selected_user != "All":
                filtered_df = filtered_df[filtered_df["user"] == selected_user]
            if selected_status != "All":
                filtered_df = filtered_df[filtered_df["status"] == selected_status]
            if selected_date:
                filtered_df = filtered_df[filtered_df["date"] == str(selected_date)]
            
            st.markdown("---")
            
            # Pending Approvals
            pending = filtered_df[filtered_df["status"] == "PENDING"].copy()
            
            st.markdown("### 🔔 Pending Attendance Approvals")
            if pending.empty:
                st.success("No pending attendance logs.")
            else:
                st.dataframe(
                    pending[["user", "project", "date", "mode", "clock_in", "clock_out", "duration"]],
                    use_container_width=True,
                    hide_index=True
                )
                
                st.markdown("#### Bulk/Individual Actions")
                
                action_col1, action_col2 = st.columns([2, 1])
                
                with action_col1:
                    # Individual approval
                    st.markdown("##### Individual Approval")
                    indices = pending.index.tolist()
                    display_options = [f"{pending.loc[i, 'user']} - {pending.loc[i, 'date']} - {pending.loc[i, 'clock_in']} to {pending.loc[i, 'clock_out']}" for i in indices]
                    
                    if display_options:
                        selected_display = st.selectbox("Select Entry", display_options, key="att_select_entry")
                        selected_idx = indices[display_options.index(selected_display)]
                        
                        admin_note = st.text_area("Admin Note (Optional)", height=80, placeholder="Add note...", key="att_admin_note")
                        
                        ind_col1, ind_col2 = st.columns(2)
                        with ind_col1:
                            if st.button("✅ Approve Selected", use_container_width=True, type="primary", key="att_approve_ind"):
                                st.session_state.attendance_logs[selected_idx]["status"] = "APPROVED"
                                st.session_state.attendance_logs[selected_idx]["admin_note"] = admin_note.strip()
                                st.success("✅ Entry approved.")
                                st.rerun()
                        
                        with ind_col2:
                            if st.button("❌ Reject Selected", use_container_width=True, key="att_reject_ind"):
                                st.session_state.attendance_logs[selected_idx]["status"] = "REJECTED"
                                st.session_state.attendance_logs[selected_idx]["admin_note"] = admin_note.strip()
                                st.success("❌ Entry rejected.")
                                st.rerun()
                
                with action_col2:
                    # Bulk approval
                    st.markdown("##### Bulk Actions")
                    st.caption(f"{len(pending)} pending entries")
                    
                    if st.button("✅ Approve All Pending", use_container_width=True, type="primary", key="att_approve_bulk"):
                        for idx in indices:
                            st.session_state.attendance_logs[idx]["status"] = "APPROVED"
                            st.session_state.attendance_logs[idx]["admin_note"] = "Bulk approved"
                        st.success(f"✅ {len(pending)} entries approved.")
                        st.rerun()
                    
                    if st.button("❌ Reject All Pending", use_container_width=True, key="att_reject_bulk"):
                        for idx in indices:
                            st.session_state.attendance_logs[idx]["status"] = "REJECTED"
                            st.session_state.attendance_logs[idx]["admin_note"] = "Bulk rejected"
                        st.success(f"❌ {len(pending)} entries rejected.")
                        st.rerun()
            
            # All Records
            st.markdown("---")
            st.markdown("### 📊 All Attendance Records")
            st.dataframe(
                filtered_df[["user", "project", "date", "mode", "clock_in", "clock_out", "duration", "status", "admin_note"]],
                use_container_width=True,
                hide_index=True
            )

# =============================
# ADMIN - LEAVE APPROVALS
# =============================
if st.session_state.role == "Admin":
    with nav[1]:
        st.subheader("✅ Leave Approvals")
        
        if not st.session_state.leave_requests:
            st.info("No leave requests yet.")
        else:
            df = pd.DataFrame(st.session_state.leave_requests)
            
            # Filters
            st.markdown("### 🔍 Filters")
            filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
            
            with filter_col1:
                projects = ["All"] + sorted(df["project"].unique().tolist())
                selected_project = st.selectbox("Project", projects, key="leave_project_filter")
            
            with filter_col2:
                users = ["All"] + sorted(df["user"].unique().tolist())
                selected_user = st.selectbox("User", users, key="leave_user_filter")
            
            with filter_col3:
                statuses = ["All", "PENDING", "APPROVED", "REJECTED"]
                selected_status = st.selectbox("Status", statuses, key="leave_status_filter")
            
            with filter_col4:
                leave_types = ["All", "Full Day", "Half Day"]
                selected_type = st.selectbox("Leave Type", leave_types, key="leave_type_filter")
            
            # Apply filters
            filtered_df = df.copy()
            if selected_project != "All":
                filtered_df = filtered_df[filtered_df["project"] == selected_project]
            if selected_user != "All":
                filtered_df = filtered_df[filtered_df["user"] == selected_user]
            if selected_status != "All":
                filtered_df = filtered_df[filtered_df["status"] == selected_status]
            if selected_type != "All":
                filtered_df = filtered_df[filtered_df["leave_type"] == selected_type]
            
            st.markdown("---")
            
            # Pending Requests
            pending = filtered_df[filtered_df["status"] == "PENDING"].copy()
            
            st.markdown("### 🔔 Pending Leave Requests")
            if pending.empty:
                st.success("No pending leave requests.")
            else:
                st.dataframe(
                    pending[["id", "user", "project", "leave_type", "start_date", "end_date", "half_day_type", "days", "unpaid", "reason", "proof_attached"]],
                    use_container_width=True,
                    hide_index=True
                )
                
                st.markdown("#### Take Action")
                req_ids = pending["id"].tolist()
                selected_id = st.selectbox("Select Request ID", req_ids, key="leave_select_id")
                
                admin_reason = st.text_area("Admin Reason (Optional)", height=80, placeholder="Enter reason for approval/rejection (optional)...", key="leave_admin_reason")
                
                action_col1, action_col2 = st.columns(2)
                with action_col1:
                    if st.button("✅ Approve", use_container_width=True, type="primary", key="leave_approve"):
                        for r in st.session_state.leave_requests:
                            if r["id"] == selected_id:
                                r["status"] = "APPROVED"
                                r["admin_reason"] = admin_reason.strip()
                        st.success(f"✅ {selected_id} approved.")
                        st.rerun()
                
                with action_col2:
                    if st.button("❌ Reject", use_container_width=True, key="leave_reject"):
                        for r in st.session_state.leave_requests:
                            if r["id"] == selected_id:
                                r["status"] = "REJECTED"
                                r["admin_reason"] = admin_reason.strip()
                        st.success(f"❌ {selected_id} rejected.")
                        st.rerun()
            
            # All Requests History
            st.markdown("---")
            st.markdown("### 📊 All Leave Requests")
            st.dataframe(
                filtered_df[["id", "user", "project", "leave_type", "start_date", "end_date", "half_day_type", "days", "unpaid", "status", "admin_reason", "created_at"]],
                use_container_width=True,
                hide_index=True
            )

# =============================
# ADMIN - SETTINGS
# =============================
if st.session_state.role == "Admin":
    with nav[2]:
        st.subheader("⚙️ Settings - Default Shift & Week-offs")
        
        box = st.container(border=True)
        with box:
            st.markdown("#### Set Default Shift Timings")
            
            col_a, col_b = st.columns(2)
            with col_a:
                shift_start = st.time_input("Shift Start Time", value=st.session_state.shift_start, key="shift_start_input")
            with col_b:
                shift_end = st.time_input("Shift End Time", value=st.session_state.shift_end, key="shift_end_input")
            
            st.markdown("#### Set Week-offs")
            weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            weekoffs = st.multiselect("Select Week-off Days", weekdays, default=st.session_state.weekoffs, key="weekoffs_input")
            
            if st.button("💾 Save Settings", type="primary", use_container_width=True):
                st.session_state.shift_start = shift_start
                st.session_state.shift_end = shift_end
                st.session_state.weekoffs = weekoffs
                st.success("✅ Settings saved successfully!")
                st.rerun()
            
            st.markdown("---")
            st.info(f"Current Shift: {st.session_state.shift_start.strftime('%I:%M %p')} - {st.session_state.shift_end.strftime('%I:%M %p')}")
            st.info(f"Current Week-offs: {', '.join(st.session_state.weekoffs)}")