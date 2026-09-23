import uuid

import streamlit as st

from api_client import BackendError, send_message

st.set_page_config(page_title="Weather Advisory", page_icon="☁️", layout="centered")
st.title("Weather Advisory")
st.caption("Live weather guidance grounded in written safety policies")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.subheader("Session")
    st.code(st.session_state.session_id)
    if st.button("Start new session"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

for item in st.session_state.messages:
    with st.chat_message(item["role"]):
        st.markdown(item["content"])
        if item.get("details"):
            st.caption(item["details"])

message = st.chat_input("Ask about an outdoor activity and city...")
if message:
    st.session_state.messages.append({"role": "user", "content": message})
    with st.chat_message("user"):
        st.markdown(message)
    with st.chat_message("assistant"):
        try:
            result = send_message(st.session_state.session_id, message)
            st.markdown(result.get("answer", "No response returned."))
            details = []
            if result.get("sop_id"):
                details.append(f"SOP: {result['sop_id']} · {result.get('sop_name')} · severity: {result.get('severity')}")
            if result.get("weather"):
                weather = result["weather"]
                details.append(f"Observed at {weather.get('time', 'reported time')}: {weather['temperature']}°C · wind {weather['wind_speed']} km/h · rain {weather['precipitation']} mm · rain probability {weather['precipitation_probability']}% · UV {weather['uv_index']}")
            if result.get("error"):
                details.append(f"Error: {result['error']}")
            if details:
                with st.expander("Evidence"):
                    st.caption("\n\n".join(details))
            st.session_state.messages.append({"role": "assistant", "content": result.get("answer", "No response returned."), "details": "\n".join(details)})
        except BackendError as exc:
            st.error(str(exc))
            st.session_state.messages.append({"role": "assistant", "content": str(exc)})
