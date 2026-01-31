import streamlit as st
import pandas as pd
from datetime import date
import requests
from role_guard import get_user_role

API_BASE_URL = "http://localhost:8000"

def authenticated_request(method, endpoint, data=None):
    token = st.session_state.get("token")
    
    if not token:
        st.warning("Please login first.")
        st.stop()
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.request(method, f"{API_BASE_URL}{endpoint}", headers=headers, json=data)
        if response.status_code >= 400:
            st.error(f"Error {response.status_code}: {response.text}")
            return None
        return response.json()
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

def rpm_id_to_display(rpm_id):
    if not rpm_id:
        return None
    return f"{rpm_id} — {rpm_id_to_name.get(rpm_id, '')}"

def get_rep_managers():
    return authenticated_request("GET", "/admin/users/reporting_managers")

def reset():
    st.session_state.all_edited_rows.clear()
    st.session_state.original_df = st.session_state.revert_df.copy(deep=True)
    st.session_state.editor_key += 1
    st.rerun()

# ---------------------------
# CONFIG
# ---------------------------
st.set_page_config(
    page_title="Admin Panel",
    layout="wide",
)

# Basic role check
from role_guard import get_user_role
role = get_user_role()
if not role or role not in ["ADMIN", "MANAGER"]:
    st.error("Access denied. Admin or Manager role required.")
    st.stop()

# ---------------------------
# STATE
# ---------------------------
if "items" not in st.session_state:
    st.session_state["items"] = []

if "all_edited_rows" not in st.session_state:
    st.session_state.all_edited_rows = {}

if "users" not in st.session_state:
    st.session_state.users = 0

if "editor_key" not in st.session_state:
    st.session_state.editor_key = 0

if "original_df" not in st.session_state:
    st.session_state.original_df = None

if "revert_df" not in st.session_state:
    st.session_state.revert_df = None

# # ---------------------------
# # HEADER
# # ---------------------------
st.title("Admin Panel")

# Make request to the server
response = authenticated_request("GET", "/admin/users/kpi_cards_info")

if not response:
    st.rerun()

users = "N/A" if not response["users"] else response["users"]
allocated = "N/A" if not response["allocated"] else response["allocated"]
unallocated = "N/A" if not response["unallocated"] else response["unallocated"]
contractors = "N/A" if not response["contractors"] else response["contractors"]
leave = "N/A" if not response["leave"] else response["leave"]

kpis = [
    {"title": "Total Users", "value": users, "color": "#2563EB"},
    {"title": "Contractors", "value": contractors, "color": "#7C3AED"},
    {"title": "Allocated", "value": allocated, "color": "#00cED1"},
    {"title": "Unallocated", "value": unallocated, "color": "#D97706"},
    {"title": "On Leave", "value": leave, "color": "#DC2626"},
]

# ---------------------------
# STYLES
# ---------------------------
st.markdown("""
<style>

.kpi-wrapper {
    overflow: hidden;
    border: 1px solid rgba(255,255,255,0.1);
    background: #0e1117;
}

.kpi-title-box {
    padding: 10px 14px;
    background: #111827;
    font-size: 17px;
    font-weight: 600;
    color: #9ca3af;
    text-align: center;
}

.kpi-value-box {
    padding: 14px;
    font-size: 32px;
    font-weight: 700;
    text-align: center;
}

</style>
""", unsafe_allow_html=True)

# ---------------------------
# RENDER KPI CARDS
# ---------------------------
st.subheader("Overview")

cols = st.columns(5)

for col, kpi in zip(cols, kpis):

    with col:
        st.markdown(
            f"""
            <div class="kpi-wrapper">
                <div class="kpi-title-box">
                    {kpi["title"]}
                </div>
                <div class="kpi-value-box" style="color:{kpi["color"]}">
                    {kpi["value"]}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

st.divider()

with st.container():
    c1, c2, c3, c4, c5, c6, c7 = st.columns(
        [1.2, 2.8, 1.4, 1.6, 1.6, 1.6, 1.8]
    )

    # ---- SEARCH MODE ----
    with c1:
        st.markdown("**Search by**")
        search_mode = st.selectbox(
            "",
            ["Email", "Name"],
            label_visibility="collapsed"
        )

    # ---- SEARCH INPUT ----
    with c2:
        st.markdown("&nbsp;")  # keeps height aligned

        search_query = st.text_input(
            "",
            placeholder=f"Enter {search_mode.lower()}",
            label_visibility="collapsed"
        )

    # ---- ACTIVE ----
    with c3:
        st.markdown("**Active**")
        active_filter = st.selectbox(
            "",
            ["None", "Active", "Inactive"],

            label_visibility="collapsed"
        )

    # ---- CONTRACTOR ----
    with c4:
        st.markdown("**Contractor**")
        contractor_filter = st.selectbox(
            "",
            ["None", "CONTRACTOR", "EMPLOYEE"],
            label_visibility="collapsed"
        )

    # ---- ALLOCATION ----
    with c5:
        st.markdown("**Allocation**")

        allocation_filter = st.selectbox(
            "",
            ["None", "Allocated", "Not allocated"],
            label_visibility="collapsed"
        )

    # ---- STATUS ----
    with c6:
        st.markdown("**Status**")
        status_filter = st.selectbox(
            "",
            ["None", "LATE", "PRESENT","ABSENT", "LEAVE", "OFF", "HOLIDAY", "UNKNOWN"],
            label_visibility="collapsed"
        )

    # ---- DATE ----
    with c7:
        st.markdown("**Date**")
        status_date = st.date_input(
            "",
            value=date.today(),
            label_visibility="collapsed"
        )

# ===========================
# 🔘 ACTION BAR
# ===========================
action_col1, action_col2 = st.columns([1, 6])

with action_col1:
    fetch_clicked = st.button(
        "Apply Filters",
        width="content"
    )

rpm_list = get_rep_managers() or []

rpm_id_to_name = {
    r["rpm_id"]: r["rpm_name"] for r in rpm_list
}

rpm_options = [
    f'{r["rpm_id"]} — {r["rpm_name"]}' for r in rpm_list
]

rpm_display_to_rpm_id = {
    f'{r["rpm_id"]} — {r["rpm_name"]}': r["rpm_id"] for r in rpm_list
}

# ===========================
# 📡 FETCH DATA
# ===========================
payload = None
if fetch_clicked: 
    payload = {
        "email": search_query.strip() if search_mode == "Email" and search_query else None,
        "name": search_query.strip() if search_mode == "Name" and search_query else None,
        "is_active": None if active_filter == "None" else active_filter == "Active",
        "work_role": None if contractor_filter == "None" else contractor_filter,
        "allocated": None if allocation_filter == "None" else allocation_filter == "Allocated",
        "status": None if status_filter == "None" else status_filter,
        "date": status_date.isoformat(),
    }

st.divider()

if payload:
    st.session_state.all_edited_rows.clear()
    with st.spinner():
        response = authenticated_request(
            "POST",
            "/admin/users/users_with_filter",
            data=payload
        )

    if not response:
        st.stop()
    
    st.session_state.items = response["items"]
    st.session_state.users = response["meta"]["total"]
    st.session_state.all_edited_rows.clear()
    st.session_state.editor_key += 1

# ===========================
# DATA TABLE
# ===========================
items = st.session_state["items"]

if items:
    st.subheader(f"Total Users: {st.session_state.users}")

    df = pd.DataFrame(items).set_index("id", drop=False)
    df = df[
        [
            "id",
            "name",
            "email",
            "role",
            "work_role",
            "is_active",
            "shift_id",
            "shift_name",
            "rpm_user_id",
            "allocated_projects",
            "today_status",
        ]
    ]
    df["rpm_user_id"] = df["rpm_user_id"].apply(
        lambda x: f"{x} — {rpm_id_to_name.get(x, '')}" if x else None
    )
    df.index = df.index.astype(str)
    
    st.session_state.original_df = df.copy(deep=True)
    st.session_state.revert_df = df.copy(deep=True)

# # ===========================
# # EDITABLE TABLE
# # ===========================
    edited_df = st.data_editor(
        df,
        # key="user_editor",
        key=f"user_editor_page_{st.session_state.editor_key}",
        use_container_width=True,
        hide_index=True,
        column_config={
            "id": st.column_config.TextColumn(
                "ID", disabled=True
            ),
            "name": st.column_config.TextColumn(
                "Name" 
            ),
            "email": st.column_config.TextColumn(
                "Email"
            ),
            "allocated_projects": st.column_config.NumberColumn(
                "Projects", disabled=True
            ),
            "today_status": st.column_config.TextColumn(
                "Status", disabled=True
            ),
            "role": st.column_config.SelectboxColumn(
                "Role",
                options=["ADMIN", "USER"]
            ),
            "shift_id": st.column_config.TextColumn(
                "Shift ID", disabled=True
            ),
            "shift_name": st.column_config.SelectboxColumn(
                "Shift Name",
                options=["GENERAL", "MORNING", "AFTERNOON",  "NIGHT"]
            ),
            "rpm_user_id": st.column_config.SelectboxColumn(
                "Reporting Manager ID",
                options=rpm_options,
            ),
            "work_role": st.column_config.SelectboxColumn(
                "Work Role",
                options=["CONTRACTOR", "EMPLOYEE"]
            ),
            "is_active": st.column_config.CheckboxColumn("Active"),
        },
    )

# # ===========================
# # DETECT CHANGES
# # ===========================
    EDITABLE_COLUMNS = [
        "name",
        "email",
        "role",
        "work_role",
        "is_active",
        "shift_name",
        "rpm_user_id"
    ]
    
    for user_id in edited_df.index:
        user_id = str(user_id)

        original = st.session_state.original_df.loc[user_id, EDITABLE_COLUMNS]
        edited = edited_df.loc[user_id, EDITABLE_COLUMNS]

        if not original.equals(edited):
            st.session_state.all_edited_rows[user_id] = edited_df.loc[user_id].to_dict()

# ===========================
# REMOVE REVERTED ROWS
# ===========================
    for user_id in list(st.session_state.all_edited_rows.keys()):
        if user_id in edited_df.index and user_id in st.session_state.original_df.index:
            if st.session_state.original_df.loc[user_id, EDITABLE_COLUMNS].equals(
                edited_df.loc[user_id, EDITABLE_COLUMNS]
            ):
                del st.session_state.all_edited_rows[user_id]

# ===========================
# HIGHLIGHT EDITED ROWS
# ===========================
    total_edits = len(st.session_state.all_edited_rows)

    if total_edits:
        st.warning(f"{total_edits} row(s) edited")
        st.markdown(
            """
            <style>
            div[data-testid="stDataEditor"] tbody tr {
                transition: background-color 0.2s;
            }
            </style>
            """,
            unsafe_allow_html=True
        )
# ===========================
# UPDATE BUTTON
# ===========================
    update, discard = st.columns([1, 5])

    with update:
        update_clicked = st.button(
            "Update Changes",
            disabled=len(st.session_state.all_edited_rows) == 0,
            width="content"
        )
    
    with discard:
        discard_updates = st.button(
            "Discard Updates",
            disabled=len(st.session_state.all_edited_rows) == 0,
            width="content"
        )

    if update_clicked:
        with st.spinner():
            to_send = {"updates": []}

            for user_id, row in st.session_state.all_edited_rows.items():
                changes = {}

                for col in EDITABLE_COLUMNS:

                    old = st.session_state.original_df.loc[user_id, col]
                    new = row[col]

                    if old != new:
                        if col == "rpm_user_id":
                            new = rpm_display_to_rpm_id.get(new)

                        changes[col] = new

                if changes:
                    to_send["updates"].append({
                        "id": user_id,
                        "changes": changes
                    })

            st.success("Ready to send these updates to backend")
            st.json(to_send)

            optimistic_df = edited_df.copy(deep=True)

            try:
                res = authenticated_request("PATCH", "/admin/users/bulk_update", data=to_send)

                if res:
                    if int(res["failed_count"]) == 0:

                        items = st.session_state["items"]

                        for upd in to_send["updates"]:
                            uid = upd["id"]
                            changes = upd["changes"]

                            for row in items:
                                if str(row["id"]) == uid:
                                    for k, v in changes.items():
                                        row[k] = v
                                    break

                        # Sync all state
                        st.session_state.items = items
                        st.session_state.original_df = pd.DataFrame(items).set_index("id", drop=False)
                        st.session_state.all_edited_rows.clear()
                        st.session_state.editor_key += 1

                        st.toast("Changes saved successfully")
                        st.rerun()
                    else:
                        st.error(f"Error: {', '.join(res['failed'])}")
                        st.stop()
            except Exception:
                st.error("Update failed. Reverting changes.")
                reset()

    if discard_updates:
        reset()
