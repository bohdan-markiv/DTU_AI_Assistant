import streamlit as st
from openaiwrapper import OpenAIWrapper

st.set_page_config(page_title="AI Assistant", layout="centered")
st.title("🤖 Chat with My Assistant")

# Initialize wrapper and session state
if "wrapper" not in st.session_state:
    st.session_state.wrapper = OpenAIWrapper()
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

wrapper = st.session_state.wrapper

# User input
user_input = st.chat_input("Ask me anything...")

if user_input:
    # Show user message immediately
    st.session_state.chat_history.append(
        {"role": "user", "content": user_input})
    st.session_state.chat_history.append(
        {"role": "assistant", "content": "__thinking__"})  # Temporary placeholder

    # Force immediate re-render with the updated chat history
    st.rerun()

# Find and handle the thinking placeholder (if any)
for idx, msg in enumerate(st.session_state.chat_history):
    with st.chat_message(msg["role"]):
        if msg["content"] == "__thinking__":
            with st.spinner("Thinking..."):
                response = wrapper.write_message(
                    st.session_state.chat_history[-2]["content"])
                if response:
                    st.session_state.chat_history[idx]["content"] = response.value
                else:
                    st.session_state.chat_history[idx]["content"] = "Sorry, I couldn't generate a response."
                st.rerun()
        else:
            st.markdown(msg["content"])
