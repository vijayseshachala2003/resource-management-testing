import streamlit as st
import pandas as pd
import requests
from requests.exceptions import ConnectionError, Timeout, HTTPError
import math

API_BASE_URL = "http://localhost:8000"
PAGE_SIZE = 10

# --- HELPER FUNCTIONS ---
def authenticated_request(method, endpoint, data=None, file=None):
    # For authentication
    token = st.session_state.get("token")
    if not token:
        st.error("🔒 You are not logged in.")
        st.stop()
    
    headers = {"Authorization": f"Bearer {token}"}

    if file and data:
        st.error("Can't send both json and file payload")
        return None
    
    url = f"{API_BASE_URL}{endpoint}"

    try:
        response = None

        if file:
            files = {
                "file": (file.name, file.getvalue(), file.type)
            }
            with st.spinner("Uploading..."):
                response = requests.request(method, url, headers=headers, files=files)
        else:
            response = requests.request(method, url, headers=headers, data=data)

        if response.status_code >= 400:
            st.error(f"Error: {response.status_code}, {response.text}")
            return None
        return response.json()

    except Exception as e:
        st.error(f"Network error: '{e}'")
        return None

# --- CONFIGURATION ---
st.set_page_config(page_title="Users List", layout="wide")

# ---------------------------
# STATE
# ---------------------------

if "items" not in st.session_state:
    # st.session_state.items = []
    st.session_state["items"] = []

if "page" not in st.session_state:
    st.session_state.page = 1


st.title("Users List")

# ===========================
# FETCH USERS
# ===========================
with st.expander("Fetch Users", expanded=True):

    active_only = st.checkbox("Active users only")

    if st.button("Fetch users"):
        try:
            payload = {
                "active_only": active_only
            }

            with st.spinner("Fetching users..."):
                data = authenticated_request("POST", "/admin/bulk_uploads/list/users", data=payload)
                
                if not data:
                    st.error("Error occurred")

                if not isinstance(data, dict) or "items" not in data:
                    st.error("Invalid response format from server")
                    st.stop()

                items = data.get("items", [])

                if not isinstance(items, list):
                    st.error("Server returned invalid users list")
                    st.stop()

                # st.session_state.items = items
                st.session_state["items"] = items
                st.session_state.page = 1
                
                if not items:
                    st.info("No users found.")
                else:
                    st.success(f"Fetched {len(st.session_state["items"])} users")

        except ConnectionError:
            st.error("Cannot reach server. Is the backend running?")

        except Timeout:
            st.error("Server took too long to respond. Please try again.")

        except HTTPError as e:
            st.error(f"Server error ({res.status_code})")
            st.code(res.text)

        except ValueError:
            st.error("Server returned invalid JSON")


        except Exception as e:
            st.error("Unexpected error occurred")
            st.exception(e)

# ===========================
# PAGINATED RESULTS
# ===========================
items = st.session_state["items"]
if items:
    with st.expander("Results...", expanded=True):
        st.subheader(f"Users: {len(items)}", divider="blue", text_alignment="center")
        
        total_pages = math.ceil(len(st.session_state["items"]) / PAGE_SIZE)

        st.subheader("Results") 

        col1, col2, col3 = st.columns([1, 3, 1])

        with col1:
            if st.button("⬅ Prev", disabled=st.session_state.page == 1, width='stretch'):
                if st.session_state.page > 1: 
                    st.session_state.page -= 1
                st.rerun()

        with col3:
            if st.button("Next ➡", disabled=st.session_state.page == total_pages, width='stretch'):
                if st.session_state.page < total_pages:
                    st.session_state.page += 1
                st.rerun()

        with col2:
            st.markdown(
                f"<div style='text-align:center'>Page {st.session_state.page} / {total_pages}</div>",
                unsafe_allow_html=True
            )
           
        start = (st.session_state.page - 1) * PAGE_SIZE
        end = start + PAGE_SIZE
        page_items = items[start:end]
        df = pd.DataFrame(page_items)

        # enforce column order
        df = df[[
            "email",
            "name",
            "role",
            "is_active",
            "doj",
            "rpm_user_id",
            "soul_id",
            "work_role"
        ]]

        # prettify fields
        df["role"] = df["role"]
        df["is_active"] = df["is_active"].map({True: "Yes", False: "No"})

        try:
            st.dataframe(
                df,
                use_container_width=True,
                height=420
            )
        except Exception as e:
            st.error(f"Some error: '{e}'")


with st.expander("Bulk upload users (in .csv)"):
    uploaded_file = st.file_uploader(
            "Upload a CSV file",
            type=["csv"],
            accept_multiple_files=False
    )

    if uploaded_file:
        if uploaded_file.type != "text/csv" and uploaded_file.type != "application/vnd.ms-excel":
            st.error("Invalid file type. Please upload a .csv file")
            st.stop()

        if uploaded_file.size == 0:
            st.error("Empty file.")
        else:
            st.success("File attached.")
            if st.button("Upload"):
                response = authenticated_request("POST", "/admin/bulk_uploads/users", file=uploaded_file)
                
                if not response:
                    st.error("Error uploading file")
                else:
                    st.success(f"Inserted: {response["inserted"]}")
                    error = response["errors"]
                    error = "Error: None" if len(error) == 0 else "Errors: " + ', '.join(error)
                    st.warning(error)
    else:
        st.warning("Select a file.")
