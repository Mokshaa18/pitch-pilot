from typing import Any

import streamlit as st
from openai import APIError

from agent.agent import Agent, providers_from_env

MAX_QUESTIONS_PER_SESSION = 20

st.set_page_config(page_title="PitchPilot", page_icon="📺")
st.title("PitchPilot")
st.caption("Describe your space and viewing distance, and I'll recommend an LED video wall.")


def tool_steps(new_messages: list[dict[str, Any]]) -> list[str]:
    """The tool calls made while answering, as readable lines."""
    steps = []
    for message in new_messages:
        for call in message.get("tool_calls") or []:
            steps.append(f"`{call['function']['name']}({call['function']['arguments']})`")
    return steps


if "agent" not in st.session_state:
    try:
        st.session_state.agent = Agent(providers_from_env())
    except RuntimeError as error:
        st.error(str(error))
        st.stop()
    st.session_state.chat = []
    st.session_state.questions = 0

agent = st.session_state.agent

with st.sidebar:
    if st.button("New chat"):
        agent.reset()
        st.session_state.chat = []
        st.rerun()
    st.markdown(
        "Every number comes from a tested calculator, not the AI. "
        "The AI only interprets your request and explains the result."
    )

for entry in st.session_state.chat:
    with st.chat_message(entry["role"]):
        st.markdown(entry["content"])
        if entry.get("steps"):
            with st.expander("How this was calculated"):
                st.markdown("\n\n".join(entry["steps"]))

prompt = st.chat_input("e.g. My wall is 6 m by 3.4 m, people sit 3 m away")
if prompt:
    st.session_state.chat.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    steps: list[str] = []
    with st.chat_message("assistant"):
        if st.session_state.questions >= MAX_QUESTIONS_PER_SESSION:
            answer = "You've reached the question limit for this session. Please come back later."
        else:
            with st.spinner("Working it out..."):
                start = len(agent.messages)
                try:
                    answer = agent.ask(prompt)
                    steps = tool_steps(agent.messages[start:])
                    st.session_state.questions += 1
                except (APIError, RuntimeError) as error:
                    answer = f"Sorry, something went wrong: {error}"
        st.markdown(answer)
        if agent.last_provider:
            st.caption(f"Answered by {agent.last_provider}")
        if steps:
            with st.expander("How this was calculated"):
                st.markdown("\n\n".join(steps))

    st.session_state.chat.append({"role": "assistant", "content": answer, "steps": steps})