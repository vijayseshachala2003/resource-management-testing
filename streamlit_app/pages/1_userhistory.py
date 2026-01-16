import streamlit as st
from api import api_request

st.title("Work History")

token = st.session_state.get("token")

with st.spinner("Loading history..."):
    try:
        data = api_request(
            "GET",
            "/me",
            token=token
        )

        if not data:
            st.info("No history found")
        else:
            st.dataframe(data)

    except Exception as e:
        st.error(str(e))
