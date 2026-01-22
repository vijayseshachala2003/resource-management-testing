import streamlit as st
import pandas as pd
import math
from datetime import date
import requests

API_BASE_URL = "http://localhost:8000"
PAGE_SIZE = 10

def check_login():
    token = st.session_state.get("token")
    if not token:
        st.warning("Please login first.")
        st.stop()
    return token

def authenticated_request(method, endpoint, data=None):
    token = check_login()
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

# ---------------------------
# CONFIG
# ---------------------------
st.set_page_config(
    page_title="Admin Panel",
    layout="wide"
)

# ---------------------------
# STATE
# ---------------------------
if "items" not in st.session_state:
    st.session_state["items"] = []

if "page" not in st.session_state:
    st.session_state.page = 1

# # ---------------------------
# # HEADER
# # ---------------------------
st.title("Admin Panel")
st.caption("Get workforce overview with additional details...")

# ---------------------------
# KPI DATA (API-ready)
# ---------------------------
# Make request to the server
_ = check_login()
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
            ["None", "Present", "Absent", "Leave", "Unknown"],
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

st.divider()

# ===========================
# 🔘 ACTION BAR
# ===========================
action_col1, action_col2 = st.columns([1, 6])

with action_col1:
    fetch_clicked = st.button(
        "Apply Filters",
        width="content"
    )

# ===========================
# 📡 FETCH DATA
# ===========================
if fetch_clicked:
    payload = {
        "email": search_query.strip() if search_mode == "Email" and search_query else None,
        "name": search_query.strip() if search_mode == "Name" and search_query else None,
        "is_active": None if active_filter == None else active_filter == "Active",
        "work_role": None if contractor_filter == None else contractor_filter,
        "allocated": None if allocation_filter == None else allocation_filter == "Allocated",
        "status": None if status_filter == None else status_filter,
        "date": status_date.isoformat()
    }

    # 🔴 Replace with backend call
    response = authenticated_request("POST", "/admin/users/users_with_filter", data=payload)

    st.session_state["items"] = []  # placeholder
    st.session_state.page = 1

    st.info("Filters applied. Awaiting backend response.")

# ===========================
# 📋 RESULTS
# ===========================
items = st.session_state["items"]

if items:
    total_pages = math.ceil(len(items) / PAGE_SIZE)

    st.subheader("Results")

    # ---- Pagination Controls ----
    pcol1, pcol2, pcol3 = st.columns([1, 2, 1])

    with pcol1:
        if st.button("⬅ Prev", disabled=st.session_state.page == 1):
            st.session_state.page -= 1
            st.rerun()

    with pcol3:
        if st.button("Next ➡", disabled=st.session_state.page == total_pages):
            st.session_state.page += 1
            st.rerun()

    with pcol2:
        st.markdown(
            f"<div style='text-align:center'>"
            f"Page {st.session_state.page} / {total_pages}"
            f"</div>",
            unsafe_allow_html=True
        )

    # ---- Page Slice ----
    start = (st.session_state.page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    page_items = items[start:end]

    # ---- Table Header ----
    header_cols = st.columns([2.5, 2, 1.2, 1.4, 1.4, 1.5, 2.5])
    headers = [
        "Email",
        "Name",
        "Role",
        "Work Role",
        "Active",
        "Projects",
        "Actions",
    ]

    for col, h in zip(header_cols, headers):
        col.markdown(f"**{h}**")

    st.divider()

    # ---- Rows ----
    for user in page_items:
        row = st.columns([2.5, 2, 1.2, 1.4, 1.4, 1.5, 2.5])

        row[0].write(user["email"])
        row[1].write(user["name"])
        row[2].write(user["role"])
        row[3].write(user["work_role"])

        # Active badge
        if user["is_active"]:
            row[4].markdown("🟢 **Active**")
        else:
            row[4].markdown("🔴 **Inactive**")

        row[5].write(user["allocated_projects"])

        # ---- ACTIONS ----
        with row[6]:
            a1, a2, a3 = st.columns(3)

            with a1:
                if st.button(
                    "✏️",
                    key=f"edit-{user['id']}",
                    help="Edit user"
                ):
                    st.info(f"Edit user {user['id']} (open modal / navigate)")

            with a2:
                toggle_label = "Deactivate" if user["is_active"] else "Activate"
                if st.button(
                    "🔄",
                    key=f"toggle-{user['id']}",
                    help=toggle_label
                ):
                    st.info(
                        f"{toggle_label} user {user['id']} (API call here)"
                    )

            with a3:
                if st.button(
                    "🕒",
                    key=f"shift-{user['id']}",
                    help="Assign default shift"
                ):
                    st.info(
                        f"Assign default shift to user {user['id']}"
                    )

        st.divider()

elif fetch_clicked:
    st.warning("No users matched the filters.")

else:
    st.info("Apply filters to view users.")


