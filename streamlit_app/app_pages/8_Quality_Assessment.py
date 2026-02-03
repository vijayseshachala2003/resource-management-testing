import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from typing import Optional, Dict, List
import requests
import time
from uuid import UUID

# Page config
st.set_page_config(page_title="Quality Assessment", layout="wide")

# API configuration
API_BASE_URL = "http://localhost:8000"

# =====================================================================
# AUTH CHECK & ROLE GUARD
# =====================================================================
from role_guard import get_user_role

if "token" not in st.session_state:
    st.warning("🔒 Please login first from the main page.")
    st.stop()

# Basic role check
role = get_user_role()
if not role or role not in ["USER", "ADMIN", "MANAGER"]:
    st.error("Access denied. Please log in.")
    st.stop()

# =====================================================================
# HELPER FUNCTIONS
# =====================================================================
def authenticated_request(method: str, endpoint: str, params: Optional[Dict] = None, json_data: Optional[Dict] = None):
    """Make authenticated API request"""
    token = st.session_state.get("token")
    if not token:
        return None
    
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.request(
            method=method,
            url=f"{API_BASE_URL}{endpoint}",
            headers=headers,
            params=params,
            json=json_data,
            timeout=30
        )
        if response.status_code >= 400:
            st.error(f"API Error: {response.status_code} - {response.text}")
            return None
        return response.json()
    except Exception as e:
        st.error(f"Request failed: {str(e)}")
        return None

@st.cache_data(ttl=300)
def get_user_name_mapping() -> Dict[str, str]:
    """Fetch all users and create UUID -> name mapping"""
    users = authenticated_request("GET", "/admin/users/", params={"limit": 1000})
    if not users:
        return {}
    return {str(user["id"]): user["name"] for user in users}

@st.cache_data(ttl=300)
def get_user_email_mapping() -> Dict[str, str]:
    """Fetch all users and create UUID -> email mapping"""
    users = authenticated_request("GET", "/admin/users/", params={"limit": 1000})
    if not users:
        return {}
    return {str(user["id"]): user.get("email", "") for user in users}

@st.cache_data(ttl=300)
def get_project_name_mapping() -> Dict[str, str]:
    """Fetch all projects and create UUID -> name mapping"""
    projects = authenticated_request("GET", "/admin/projects/", params={"limit": 1000})
    if not projects:
        return {}
    return {str(project["id"]): project["name"] for project in projects}

# =====================================================================
# HEADER
# =====================================================================
st.title("⭐ Quality Assessment")
st.markdown("Manually assess quality ratings for users on specific dates")
st.markdown("---")

# =====================================================================
# MODE SELECTOR
# =====================================================================
mode = st.radio(
    "Assessment Mode",
    ["Individual Assessment", "Bulk Upload"],
    horizontal=True,
    key="quality_mode"
)

st.markdown("---")

if mode == "Individual Assessment":
    # =====================================================================
    # INDIVIDUAL ASSESSMENT FORM
    # =====================================================================
    st.markdown("### 📝 Individual Quality Assessment")
    
    # Get mappings
    user_map = get_user_name_mapping()
    user_email_map = get_user_email_mapping()
    project_map = get_project_name_mapping()
    
    if not user_map or not project_map:
        st.error("⚠️ Unable to load users or projects. Please check your connection.")
        st.stop()
    
    # Create user options with email display: "Name (email)"
    user_options_display = {}
    for user_id, user_name in user_map.items():
        email = user_email_map.get(user_id, "")
        if email:
            display_name = f"{user_name} ({email})"
        else:
            display_name = user_name
        user_options_display[display_name] = user_id
    
    # Create reverse mapping for project
    project_id_to_name = {v: k for k, v in project_map.items()}
    
    # Form fields
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # User selection with email
        user_display_list = sorted(user_options_display.keys())
        selected_user_display = st.selectbox("Select User", user_display_list)
        selected_user_id = user_options_display.get(selected_user_display)
    
    with col2:
        # Project selection
        project_options = sorted(project_map.values())
        selected_project_name = st.selectbox("Select Project", project_options)
        selected_project_id = project_id_to_name.get(selected_project_name)
    
    with col3:
        # Date selection
        selected_date = st.date_input("Assessment Date", value=date.today())
    
    # Quality rating
    col4, col5 = st.columns(2)
    
    with col4:
        rating = st.selectbox(
            "Quality Rating",
            ["GOOD", "AVERAGE", "BAD"],
            help="GOOD: High quality work\nAVERAGE: Acceptable quality\nBAD: Poor quality requiring improvement"
        )
    
    with col5:
        quality_score = st.number_input(
            "Quality Score (0-10)",
            min_value=0.0,
            max_value=10.0,
            value=7.0,
            step=0.1,
            help="Numeric score from 0 (poor) to 10 (excellent). Optional but recommended."
        )
    
    # Accuracy and Critical Rate
    col6, col7 = st.columns(2)
    
    with col6:
        accuracy = st.number_input(
            "Accuracy (%)",
            min_value=0.0,
            max_value=100.0,
            value=None,
            step=0.1,
            help="Percentage of work completed correctly (0-100%). Optional."
        )
    
    with col7:
        critical_rate = st.number_input(
            "Critical Rate (%)",
            min_value=0.0,
            max_value=100.0,
            value=None,
            step=0.1,
            help="Percentage of critical tasks handled successfully (0-100%). Optional."
        )
    
    # Notes
    notes = st.text_area(
        "Assessment Notes (Optional)",
        placeholder="Add any additional comments about the quality assessment...",
        height=100
    )
    
    # Submit button
    if st.button("💾 Save Quality Assessment", type="primary", use_container_width=True):
        if not selected_user_id or not selected_project_id:
            st.error("Please select both user and project.")
        else:
            with st.spinner("Submitting quality assessment..."):
                payload = {
                    "user_id": selected_user_id,
                    "project_id": selected_project_id,
                    "metric_date": str(selected_date),
                    "rating": rating,
                    "quality_score": float(quality_score) if quality_score else None,
                    "accuracy": float(accuracy) if accuracy is not None else None,
                    "critical_rate": float(critical_rate) if critical_rate is not None else None,
                    "notes": notes if notes.strip() else None
                }
                
                result = authenticated_request("POST", "/admin/metrics/user_daily/quality", json_data=payload)
                
                if result:
                    st.success(f"✅ Quality assessment saved successfully!")
                    st.balloons()
                    # Clear cache to refresh data
                    get_user_name_mapping.clear()
                    get_user_email_mapping.clear()
                    get_project_name_mapping.clear()
                    # Force rerun to refresh the table
                    time.sleep(0.5)
                    st.rerun()
    
    # =====================================================================
    # EXISTING ASSESSMENTS VIEW
    # =====================================================================
    st.markdown("---")
    st.markdown("### 📋 Recent Quality Assessments")
    
    # Fetch existing assessments
    if selected_user_id and selected_project_id:
        params = {
            "user_id": selected_user_id,
            "project_id": selected_project_id,
            "start_date": str(selected_date - timedelta(days=30)),
            "end_date": str(selected_date + timedelta(days=1))
        }
        
        quality_data = authenticated_request("GET", "/admin/metrics/user_daily/quality-ratings", params=params)
        
        if quality_data:
            df_quality = pd.DataFrame(quality_data)
            df_quality["metric_date"] = pd.to_datetime(df_quality["metric_date"]).dt.date
            
            # Format for display
            df_quality["quality_rating"] = df_quality["quality_rating"].apply(
                lambda x: {"GOOD": "✅ Good", "AVERAGE": "⚠️ Average", "BAD": "❌ Bad"}.get(x, x) if x else "Not Assessed"
            )
            
            if "quality_score" in df_quality.columns:
                df_quality["quality_score"] = df_quality["quality_score"].apply(
                    lambda x: f"{x:.1f}" if x is not None else "N/A"
                )
            
            if "accuracy" in df_quality.columns:
                df_quality["accuracy"] = df_quality["accuracy"].apply(
                    lambda x: f"{x:.1f}%" if x is not None else "N/A"
                )
            
            if "critical_rate" in df_quality.columns:
                df_quality["critical_rate"] = df_quality["critical_rate"].apply(
                    lambda x: f"{x:.1f}%" if x is not None else "N/A"
                )
            
            display_cols = ["metric_date", "quality_rating", "quality_score", "accuracy", "critical_rate", "source", "notes"]
            display_cols = [col for col in display_cols if col in df_quality.columns]
            
            st.dataframe(
                df_quality[display_cols].sort_values("metric_date", ascending=False),
                use_container_width=True,
                height=300
            )
        else:
            st.info("No quality assessments found for this user/project combination in the last 30 days.")

else:
    # =====================================================================
    # BULK UPLOAD
    # =====================================================================
    st.markdown("### 📤 Bulk Quality Assessment Upload")
    
    st.markdown("""
    **CSV Format Required:**
    - `user_email`: User's email address
    - `project_code`: Project code
    - `metric_date`: Date in YYYY-MM-DD format
    - `rating`: Quality rating (GOOD, AVERAGE, or BAD)
    - `quality_score` (optional): Numeric score 0-10
    - `accuracy` (optional): Accuracy percentage 0-100
    - `critical_rate` (optional): Critical rate percentage 0-100
    - `work_role` (optional): Work role (will be fetched from project_members if not provided)
    - `notes` (optional): Assessment notes
    
    **Example CSV:**
    ```csv
    user_email,project_code,metric_date,rating,quality_score,accuracy,critical_rate,notes
    user@example.com,PROJ001,2024-01-15,GOOD,8.5,95.0,88.5,Excellent work quality
    user2@example.com,PROJ002,2024-01-15,AVERAGE,6.0,75.0,70.0,Acceptable quality
    ```
    """)
    
    uploaded_file = st.file_uploader(
        "Upload CSV File",
        type=["csv"],
        help="Upload a CSV file with quality assessments"
    )
    
    if uploaded_file:
        # Preview CSV
        try:
            df_preview = pd.read_csv(uploaded_file)
            st.markdown("#### 📄 CSV Preview")
            st.dataframe(df_preview.head(10), use_container_width=True)
            
            if st.button("📤 Upload Quality Assessments", type="primary", use_container_width=True):
                # Reset file pointer
                uploaded_file.seek(0)
                
                with st.spinner("Uploading quality assessments..."):
                    files = {"file": (uploaded_file.name, uploaded_file, "text/csv")}
                    token = st.session_state.get("token")
                    headers = {"Authorization": f"Bearer {token}"}
                    
                    try:
                        response = requests.post(
                            f"{API_BASE_URL}/admin/bulk_uploads/quality",
                            files=files,
                            headers=headers,
                            timeout=60
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            st.success(f"✅ Successfully uploaded {result.get('inserted', 0)} quality assessments!")
                            
                            if result.get("errors"):
                                st.warning(f"⚠️ {len(result['errors'])} errors encountered:")
                                with st.expander("View Errors"):
                                    for error in result["errors"]:
                                        st.text(error)
                            
                            st.balloons()
                            st.cache_data.clear()
                        else:
                            st.error(f"❌ Upload failed: {response.status_code} - {response.text}")
                    except Exception as e:
                        st.error(f"❌ Upload error: {str(e)}")
        
        except Exception as e:
            st.error(f"❌ Error reading CSV file: {str(e)}")

# =====================================================================
# FOOTER
# =====================================================================
st.markdown("---")
st.markdown("*Quality Assessment | Quality ratings are manually assessed and separate from productivity*")
