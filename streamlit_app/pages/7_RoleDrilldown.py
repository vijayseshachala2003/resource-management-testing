import streamlit as st
import pandas as pd
from api import api_request
from datetime import date

st.set_page_config(page_title="Role Drilldown", layout="wide")

st.title("Role Drilldown Report")
st.caption("Project → Role → Attendance breakdown")

token = st.session_state.get("token")
if not token:
    st.warning("Please login first.")
    st.stop()

# ----------------------------
# Inputs
# ----------------------------
col1, col2, col3, col4 = st.columns(4)

with col1:
    project_id = st.text_input("Project ID")

with col2:
    role = st.text_input("Role (optional)")

with col3:
    status = st.selectbox("Status", ["", "PRESENT", "ABSENT", "LEAVE", "UNKNOWN"])

with col4:
    report_date = st.date_input("Date", value=date.today())

fetch = st.button("Fetch Data")

# ----------------------------
# Fetch Data
# ----------------------------
if fetch:

    params = {
        "project_id": project_id,
        "date": report_date.isoformat()
    }

    if role:
        params["role"] = role

    if status:
        params["status"] = status

    try:
        data = api_request(
            "GET",
            "/admin/role-drilldown",
            token=token,
            params=params
        )

        if not data:
            st.info("No data found for given filters.")
        else:
            df = pd.DataFrame(data)

            df = df.rename(columns={
                "user": "User",
                "email": "Email",
                "role": "Role",
                "attendance_status": "Attendance Status",
                "minutes_worked": "Minutes Worked",
                "first_in": "First In",
                "last_out": "Last Out",
                "productivity_score": "Productivity Score",
                "quality_rating": "Quality Rating"
            })

            st.dataframe(df, use_container_width=True)

            # ---------------- CSV Download ----------------
            csv = df.to_csv(index=False).encode("utf-8")

            st.download_button(
                "Download CSV",
                csv,
                file_name=f"role_drilldown_{report_date}.csv",
                mime="text/csv"
            )

    except Exception as e:
        st.error(f"Error fetching data: {e}")
