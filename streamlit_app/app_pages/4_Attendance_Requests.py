import streamlit as st
from api import api_request
from datetime import datetime, date, timedelta, time
import pytz
import pandas as pd
from role_guard import get_user_role

st.set_page_config(page_title="Leave/WFH Requests", layout="wide")

# Basic role check
role = get_user_role()
if not role or role not in ["USER", "ADMIN", "MANAGER"]:
    st.error("Access denied. Please log in.")
    st.stop()

# ---------------- Helpers ----------------

def format_time_local(ts):
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts.replace("Z","+00:00"))
        local = dt.astimezone(pytz.timezone("Asia/Kolkata"))
        return local.strftime("%d %b %Y %I:%M %p")
    except:
        return str(ts)

def calc_days(start_d: date, end_d: date) -> int:
    return (end_d - start_d).days + 1

def fetch_projects(token):
    # Use session state to cache projects
    cache_key = "cached_projects"
    if cache_key not in st.session_state or st.session_state.get("refresh_projects", False):
        try:
            st.session_state[cache_key] = api_request("GET","/admin/projects/",token=token) or []
        except:
            st.session_state[cache_key] = []
        st.session_state["refresh_projects"] = False
    return st.session_state.get(cache_key, [])

def list_requests(token):
    # Use session state to cache requests
    cache_key = "cached_requests"
    if cache_key not in st.session_state or st.session_state.get("refresh_requests", False):
        try:
            st.session_state[cache_key] = api_request("GET","/attendance/requests",token=token) or []
        except:
            st.session_state[cache_key] = []
        st.session_state["refresh_requests"] = False
    return st.session_state.get(cache_key, [])

def invalidate_cache():
    """Call this when data changes (submit, cancel, etc.)"""
    st.session_state["refresh_requests"] = True
    st.session_state["refresh_projects"] = True

def create_request(token, payload):
    try:
        result = api_request("POST","/attendance/requests/",token=token,json=payload)
        if result:
            invalidate_cache()  # Clear cache after creating
        return result
    except Exception as e:
        st.error(f"Failed to create request: {str(e)}")
        return None

def cancel_request(token, req_id):
    try:
        result = api_request("DELETE",f"/attendance/requests/{req_id}",token=token)
        if result:
            invalidate_cache()  # Clear cache after canceling
        return True
    except Exception as e:
        st.error(f"Failed to cancel request: {str(e)}")
        return False

# ---------------- Auth ----------------

token = st.session_state.get("token")
if not token:
    st.warning("🔒 Please login first from the App page.")
    if st.button("➡️ Go to Login"):
        st.session_state.clear()
        st.rerun()
    st.stop()

# Initialize attendance_form_counter if not exists
if "attendance_form_counter" not in st.session_state:
    st.session_state["attendance_form_counter"] = 0

# ---------------- UI ----------------

st.title("🏖️ Leave/WFH Requests")
st.caption("Create, view and manage your leave/WFH requests")
st.markdown("---")

# Fetch data once at the top level (cached)
items = list_requests(token)
projects = fetch_projects(token)
proj_id_to_name = {p["id"]: p["name"] for p in projects}

# Fetch current user info to get weekoffs
def get_current_user_info(token):
    try:
        return api_request("GET", "/me/", token=token) or {}
    except:
        return {}

current_user = get_current_user_info(token)
# Handle both single value (old) and list (new) formats
weekoffs_data = current_user.get("weekoffs", ["SUNDAY"])
if isinstance(weekoffs_data, str):
    current_weekoffs = [weekoffs_data]  # Convert single value to list
elif isinstance(weekoffs_data, list):
    # Convert enum objects to strings if needed
    current_weekoffs = [str(w) if not isinstance(w, str) else w for w in weekoffs_data]
else:
    current_weekoffs = ["SUNDAY"]  # Default fallback

col_left, col_right = st.columns([1, 1])

# ==========================================================
# LEFT SIDE : CREATE REQUEST FORM
# ==========================================================

with col_left:
    # Calculate holidays taken (using cached data)
    st.markdown("### 📅 Holiday Summary")
    current_date = date.today()
    current_year = current_date.year
    current_month = current_date.month
    
    # Calculate holidays for year and month
    holidays_year = 0
    holidays_month = 0
    
    for req in items:
        # Check for approved LEAVE/FULL-DAY/HALF-DAY requests (case-insensitive status check)
        req_type = req.get("request_type", "")
        req_status = req.get("status", "")
        req_type_upper = str(req_type).upper().replace("-", "_") if req_type else ""  # Handle HALF-DAY -> HALF_DAY
        req_status_upper = str(req_status).upper() if req_status else ""
        
        # Count SICK_LEAVE, FULL_DAY, and HALF_DAY as holidays
        is_holiday_request = req_type_upper in ["SICK_LEAVE", "FULL_DAY", "HALF_DAY", "FULL-DAY", "HALF-DAY"]
        is_approved = req_status_upper == "APPROVED"
        
        if is_holiday_request and is_approved:
            try:
                # Parse dates - handle multiple formats
                start_date_str = req.get("start_date", "")
                end_date_str = req.get("end_date", "")
                
                start_d = None
                end_d = None
                
                # Parse start_date
                if isinstance(start_date_str, date):
                    start_d = start_date_str
                elif isinstance(start_date_str, str):
                    # Try ISO format first
                    try:
                        if "T" in start_date_str:
                            start_d = datetime.fromisoformat(start_date_str.split("T")[0]).date()
                        else:
                            start_d = datetime.fromisoformat(start_date_str).date()
                    except:
                        # Try other common formats
                        try:
                            start_d = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                        except:
                            pass
                
                # Parse end_date
                if isinstance(end_date_str, date):
                    end_d = end_date_str
                elif isinstance(end_date_str, str):
                    try:
                        if "T" in end_date_str:
                            end_d = datetime.fromisoformat(end_date_str.split("T")[0]).date()
                        else:
                            end_d = datetime.fromisoformat(end_date_str).date()
                    except:
                        try:
                            end_d = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                        except:
                            pass
                
                if start_d and end_d:
                    # Calculate days based on request type
                    if req_type_upper in ["HALF_DAY", "HALF-DAY"]:
                        # Half day counts as 0.5
                        days_count = 0.5
                    else:
                        # Full day (SICK_LEAVE or FULL_DAY)
                        days_count = calc_days(start_d, end_d)
                    
                    # Check if overlaps with current year
                    year_start_date = date(current_year, 1, 1)
                    year_end_date = date(current_year, 12, 31)
                    
                    if start_d <= year_end_date and end_d >= year_start_date:
                        # For half days, only count if the date is in current year
                        if req_type_upper in ["HALF_DAY", "HALF-DAY"]:
                            if year_start_date <= start_d <= year_end_date:
                                holidays_year += 0.5
                        else:
                            # Calculate days in current year for full day requests
                            overlap_start = max(start_d, year_start_date)
                            overlap_end = min(end_d, year_end_date)
                            if overlap_start <= overlap_end:
                                holidays_year += calc_days(overlap_start, overlap_end)
                    
                    # Check if overlaps with current month
                    month_start_date = date(current_year, current_month, 1)
                    # Get last day of current month
                    if current_month == 12:
                        month_end_date = date(current_year + 1, 1, 1) - timedelta(days=1)
                    else:
                        month_end_date = date(current_year, current_month + 1, 1) - timedelta(days=1)
                    
                    if start_d <= month_end_date and end_d >= month_start_date:
                        # For half days, only count if the date is in current month
                        if req_type_upper in ["HALF_DAY", "HALF-DAY"]:
                            if month_start_date <= start_d <= month_end_date:
                                holidays_month += 0.5
                        else:
                            # Calculate days in current month for full day requests
                            overlap_start = max(start_d, month_start_date)
                            overlap_end = min(end_d, month_end_date)
                            if overlap_start <= overlap_end:
                                holidays_month += calc_days(overlap_start, overlap_end)
            except Exception as e:
                # Skip invalid dates
                continue
    
    # Calculate leave balance for current month
    monthly_free_leaves = 2.0
    leaves_used_this_month = 0.0
    
    for req in items:
        req_type_check = req.get("request_type", "")
        req_status = req.get("status", "")
        req_type_upper = str(req_type_check).upper().replace("-", "_") if req_type_check else ""
        req_status_upper = str(req_status).upper() if req_status else ""
        
        # Count SICK_LEAVE, FULL_DAY, and HALF_DAY as leaves
        is_leave_request = req_type_upper in ["SICK_LEAVE", "FULL_DAY", "HALF_DAY", "FULL-DAY", "HALF-DAY"]
        is_approved = req_status_upper == "APPROVED"
        
        if is_leave_request and is_approved:
            try:
                start_date_str = req.get("start_date", "")
                end_date_str = req.get("end_date", "")
                
                start_d = None
                end_d = None
                
                if isinstance(start_date_str, date):
                    start_d = start_date_str
                elif isinstance(start_date_str, str):
                    try:
                        if "T" in start_date_str:
                            start_d = datetime.fromisoformat(start_date_str.split("T")[0]).date()
                        else:
                            start_d = datetime.fromisoformat(start_date_str).date()
                    except:
                        try:
                            start_d = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                        except:
                            pass
                
                if isinstance(end_date_str, date):
                    end_d = end_date_str
                elif isinstance(end_date_str, str):
                    try:
                        if "T" in end_date_str:
                            end_d = datetime.fromisoformat(end_date_str.split("T")[0]).date()
                        else:
                            end_d = datetime.fromisoformat(end_date_str).date()
                    except:
                        try:
                            end_d = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                        except:
                            pass
                
                if start_d and end_d:
                    # Check if overlaps with current month
                    month_start_date = date(current_year, current_month, 1)
                    if current_month == 12:
                        month_end_date = date(current_year + 1, 1, 1) - timedelta(days=1)
                    else:
                        month_end_date = date(current_year, current_month + 1, 1) - timedelta(days=1)
                    
                    if start_d <= month_end_date and end_d >= month_start_date:
                        if req_type_upper in ["HALF_DAY", "HALF-DAY"]:
                            if month_start_date <= start_d <= month_end_date:
                                leaves_used_this_month += 0.5
                        else:
                            overlap_start = max(start_d, month_start_date)
                            overlap_end = min(end_d, month_end_date)
                            if overlap_start <= overlap_end:
                                leaves_used_this_month += calc_days(overlap_start, overlap_end)
            except:
                continue
    
    remaining_leaves = monthly_free_leaves - leaves_used_this_month
    
    # Display holiday counters in first row
    holiday_col1, holiday_col2 = st.columns(2)
    with holiday_col1:
        year_display = f"{holidays_year:.1f}" if holidays_year % 1 != 0 else f"{int(holidays_year)}"
        st.metric("Holidays This Year", f"{year_display} days", help=f"Approved leave days in {current_year} (HALF-DAY = 0.5 days)")
    with holiday_col2:
        month_name = current_date.strftime("%B")
        month_display = f"{holidays_month:.1f}" if holidays_month % 1 != 0 else f"{int(holidays_month)}"
        st.metric("Holidays This Month", f"{month_display} days", help=f"Approved leave days in {month_name} {current_year} (HALF-DAY = 0.5 days)")
    
    st.markdown("---")
    
    # Display leave balance in separate section
    st.markdown("### 💼 Leave Balance")
    leave_col1, leave_col2 = st.columns(2)
    with leave_col1:
        st.metric(
            "Leaves Used This Month", 
            f"{leaves_used_this_month:.1f} days",
            help="Approved leave days in current month"
        )
    with leave_col2:
        remaining_display = f"{remaining_leaves:.1f}" if remaining_leaves % 1 != 0 else f"{int(remaining_leaves)}"
        delta_color = "normal" if remaining_leaves >= 0 else "inverse"
        st.metric(
            "Remaining Leaves", 
            f"{remaining_display} days",
            delta=f"{monthly_free_leaves:.1f} free/month",
            delta_color=delta_color,
            help="2 free leaves per month. Half-day = 0.5 days"
        )
    
    st.markdown("---")
    
    box = st.container(border=True)
    with box:
        st.markdown("#### 📝 New Request Form")
        
        # Request Type Selection - OUTSIDE form so it updates in real-time
        req_type = st.selectbox(
            "Request Type",
            ["SICK_LEAVE", "FULL-DAY", "HALF-DAY", "WFH", "REGULARIZATION", "SHIFT_CHANGE", "OTHER"],
            help="Select the type of leave/WFH request",
            key="req_type_selectbox"
        )
        
        # Date Range (outside the form so the UI updates immediately)
        col_a, col_b = st.columns(2)
        with col_a:
            start_date = st.date_input(
                "Start Date",
                value=st.session_state.get("start_date_input", date.today()),
                min_value=date.today(),
                key="start_date_input",
            )
        with col_b:
            is_half_day = req_type == "HALF-DAY"
            saved_end_date = st.session_state.get("end_date_input", start_date)
            default_end_date = saved_end_date if saved_end_date and saved_end_date >= start_date else start_date
            end_date = st.date_input(
                "End Date",
                value=default_end_date,
                min_value=start_date,
                disabled=is_half_day,
                key="end_date_input",
                help="Same as start date for HALF-DAY" if is_half_day else None,
            )
            if is_half_day:
                end_date = start_date

        # Days calculation for SICK_LEAVE and FULL-DAY types
        if start_date and end_date:
            if req_type in ["SICK_LEAVE", "FULL-DAY"]:
                days = calc_days(start_date, end_date)
                if days > 2:
                    st.warning(f"⚠️ {days} days leave will be marked as **Non-Paid Leave**")
                else:
                    st.info(f"ℹ️ {days} day(s) - Paid Leave")
            elif req_type == "HALF-DAY":
                st.info("ℹ️ 0.5 day - Half Day Leave")

        # Use form to enable automatic clearing
        with st.form("attendance_request_form", clear_on_submit=True):
            # Time fields - only for SHIFT_CHANGE and REGULARIZATION
            start_time = None
            end_time = None

            if req_type in ["SHIFT_CHANGE", "REGULARIZATION"]:
                st.markdown("#### ⏰ Time Details")
                time_col1, time_col2 = st.columns(2)
                with time_col1:
                    start_time_key = f"start_time_input_{st.session_state['attendance_form_counter']}"
                    start_time = st.time_input(
                        "Start Time",
                        value=time(9, 0),  # Default 9:00 AM
                        help="Select the start time for your shift/regularization",
                        key=start_time_key
                    )
                with time_col2:
                    end_time_key = f"end_time_input_{st.session_state['attendance_form_counter']}"
                    end_time = st.time_input(
                        "End Time",
                        value=time(18, 0),  # Default 6:00 PM
                        help="Select the end time for your shift/regularization",
                        key=end_time_key
                    )

                # Validation: end time should be after start time
                if start_time and end_time:
                    if end_time <= start_time:
                        st.warning("⚠️ End time should be after start time.")

            # Reason
            reason = st.text_area("Reason", height=100, placeholder="Enter reason for request...")

            # Submit Button
            submitted = st.form_submit_button("✉️ Submit Request", type="primary", use_container_width=True)
            
            if submitted:
                if not reason.strip():
                    st.error("❌ Reason is required.")
                elif not start_date:
                    st.error("❌ Start date is required.")
                elif not end_date:
                    st.error("❌ End date is required.")
                elif req_type != "HALF-DAY" and end_date < start_date:
                    st.error("❌ End date must be >= start date.")
                else:
                    # For HALF-DAY, ensure end_date equals start_date
                    if req_type == "HALF-DAY":
                        end_date = start_date
                    
                    # Validate time fields for SHIFT_CHANGE and REGULARIZATION
                    if req_type in ["SHIFT_CHANGE", "REGULARIZATION"]:
                        if not start_time or not end_time:
                            st.error("❌ Start time and end time are required for this request type.")
                        elif end_time <= start_time:
                            st.error("❌ End time must be after start time.")
                        else:
                            # Create payload with time fields
                            payload = {
                                "request_type": req_type,
                                "start_date": start_date.isoformat(),
                                "end_date": end_date.isoformat(),
                                "start_time": start_time.strftime("%H:%M:%S"),
                                "end_time": end_time.strftime("%H:%M:%S"),
                                "reason": reason.strip(),
                                "attachment_url": None
                            }
                            result = create_request(token, payload)
                            if result:
                                st.success("✅ Request submitted successfully!")
                                invalidate_cache()
                                # Increment counter to force fresh widget state on next render
                                # This ensures all form fields are cleared properly
                                st.session_state["attendance_form_counter"] += 1
                                # Rerun to refresh the form with cleared state
                                st.rerun()
                            else:
                                st.error("❌ Failed to submit request. Please try again.")
                    else:
                        # For other request types, no time fields
                        payload = {
                            "request_type": req_type,
                            "start_date": start_date.isoformat(),
                            "end_date": end_date.isoformat(),
                            "start_time": None,
                            "end_time": None,
                            "reason": reason.strip(),
                            "attachment_url": None
                        }
                        result = create_request(token, payload)
                        if result:
                            st.success("✅ Request submitted successfully!")
                            invalidate_cache()
                            # Increment counter to force fresh widget state on next render
                            # This ensures all form fields are cleared properly
                            st.session_state["attendance_form_counter"] += 1
                            # Rerun to refresh the form with cleared state
                            st.rerun()
                        else:
                            st.error("❌ Failed to submit request. Please try again.")

# ==========================================================
# RIGHT SIDE : REQUEST HISTORY
# ==========================================================

with col_right:
    st.markdown("### 📜 My Request History")
    
    # Use already fetched data (cached)
    
    if not items:
        st.info("No requests found. Create your first request using the form on the left.")
    else:
        # Convert to DataFrame for easier manipulation
        df_data = []
        for it in items:
            df_data.append({
                "id": it.get("id", ""),
                "request_type": it.get("request_type", "UNKNOWN"),
                "project": proj_id_to_name.get(it.get("project_id"), "—"),
                "start_date": it.get("start_date", ""),
                "end_date": it.get("end_date", ""),
                "reason": it.get("reason", ""),
                "status": it.get("status", "PENDING"),
                "requested_at": it.get("requested_at") or it.get("created_at", ""),
                "review_comment": it.get("review_comment", ""),
            })
        
        df = pd.DataFrame(df_data)
        
        # Status filter tabs
        status_tabs = st.tabs(["All", "Pending", "Approved", "Rejected"])
        
        with status_tabs[0]:
            display_df = df.copy()
            if not display_df.empty:
                st.dataframe(
                    display_df[["request_type", "project", "start_date", "end_date", "status", "requested_at"]],
                    use_container_width=True,
                    hide_index=True
                )
                
                # Show cancel buttons for pending requests in "All" tab too
                pending_in_all = display_df[display_df["status"] == "PENDING"].copy()
                if not pending_in_all.empty:
                    st.markdown("---")
                    st.markdown("#### ❌ Cancel Pending Requests")
                    for idx, row in pending_in_all.iterrows():
                        col_btn1, col_btn2 = st.columns([3, 1])
                        with col_btn1:
                            st.caption(f"{row['request_type']} - {row['start_date']} to {row['end_date']}")
                        with col_btn2:
                            if st.button("Cancel", key=f"cancel_all_{row['id']}", use_container_width=True):
                                if cancel_request(token, row['id']):
                                    st.success("✅ Request canceled successfully!")
                                    # Invalidate cache and rerun to update pending requests list
                                    invalidate_cache()
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to cancel request. Please try again.")
            else:
                st.info("No requests found.")
        
        with status_tabs[1]:
            pending_df = df[df["status"] == "PENDING"].copy()
            if not pending_df.empty:
                st.dataframe(
                    pending_df[["request_type", "project", "start_date", "end_date", "requested_at"]],
                    use_container_width=True,
                    hide_index=True
                )
                
                # Cancel buttons for pending requests
                st.markdown("#### Cancel Pending Requests")
                for idx, row in pending_df.iterrows():
                    col_btn1, col_btn2 = st.columns([3, 1])
                    with col_btn1:
                        st.caption(f"{row['request_type']} - {row['start_date']} to {row['end_date']}")
                    with col_btn2:
                        if st.button("Cancel", key=f"cancel_{row['id']}", use_container_width=True):
                            if cancel_request(token, row['id']):
                                st.success("✅ Request canceled successfully!")
                                # Invalidate cache and rerun to update pending requests list
                                invalidate_cache()
                                st.rerun()
                            else:
                                st.error("❌ Failed to cancel request. Please try again.")
            else:
                st.info("No pending requests.")
        
        with status_tabs[2]:
            approved_df = df[df["status"] == "APPROVED"].copy()
            if not approved_df.empty:
                st.dataframe(
                    approved_df[["request_type", "project", "start_date", "end_date", "review_comment", "requested_at"]],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No approved requests.")
        
        with status_tabs[3]:
            rejected_df = df[df["status"] == "REJECTED"].copy()
            if not rejected_df.empty:
                st.dataframe(
                    rejected_df[["request_type", "project", "start_date", "end_date", "review_comment", "requested_at"]],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No rejected requests.")
        
        # Request Summary Metrics
        st.markdown("---")
        st.markdown("#### 📊 Request Summary")
        summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
        
        with summary_col1:
            st.metric("Total", len(df), help="Total requests")
        with summary_col2:
            pending_count = len(df[df["status"] == "PENDING"])
            st.metric("Pending", pending_count, help="Awaiting approval")
        with summary_col3:
            approved_count = len(df[df["status"] == "APPROVED"])
            st.metric("Approved", approved_count, help="Approved requests")
        with summary_col4:
            rejected_count = len(df[df["status"] == "REJECTED"])
            st.metric("Rejected", rejected_count, help="Rejected requests")
    
    # Refresh Button
    if st.button("🔄 Refresh", use_container_width=True, key="refresh_attendance_requests"):
        invalidate_cache()
        st.info("🔄 Data refreshed. Please interact with the page to see updated data.")

