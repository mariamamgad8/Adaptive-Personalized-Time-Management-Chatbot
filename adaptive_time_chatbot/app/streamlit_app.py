import streamlit as st
import pandas as pd
from chatbot.chatbot_engine import ChatbotEngine
from utils.helpers import format_schedule_table


st.set_page_config(page_title="Adaptive Time Management Chatbot", layout="wide")

st.title("Adaptive Personalized Time Management Chatbot")
st.write("Plan your week, report missed tasks, and recover from wasted time.")

DATA_USERS = "data/user_profiles.csv"
DATA_TASKS = "data/tasks.csv"
DATA_EVENTS = "data/fixed_events.csv"


@st.cache_data
def load_data():
    users = pd.read_csv(DATA_USERS)
    tasks = pd.read_csv(DATA_TASKS)
    events = pd.read_csv(DATA_EVENTS)
    return users, tasks, events


users_df, tasks_df_all, events_df_all = load_data()

if "chatbot" not in st.session_state:
    st.session_state.chatbot = ChatbotEngine()

if "selected_user_id" not in st.session_state:
    st.session_state.selected_user_id = None

if "user_profile" not in st.session_state:
    st.session_state.user_profile = None

if "tasks_df" not in st.session_state:
    st.session_state.tasks_df = pd.DataFrame()

if "fixed_events_df" not in st.session_state:
    st.session_state.fixed_events_df = pd.DataFrame()

if "current_schedule" not in st.session_state:
    st.session_state.current_schedule = None

if "messages" not in st.session_state:
    st.session_state.messages = []

st.sidebar.header("User Selection")

user_ids = users_df["user_id"].tolist()
selected_user_id = st.sidebar.selectbox("Choose user_id", user_ids)

if st.sidebar.button("Load User Data"):
    st.session_state.selected_user_id = selected_user_id
    st.session_state.user_profile = users_df[users_df["user_id"] == selected_user_id].iloc[0]
    st.session_state.tasks_df = tasks_df_all[tasks_df_all["user_id"] == selected_user_id].copy()
    st.session_state.fixed_events_df = events_df_all[events_df_all["user_id"] == selected_user_id].copy()
    st.session_state.current_schedule = None
    st.session_state.messages = []
    st.success(f"Loaded data for user {selected_user_id}")

if st.session_state.user_profile is not None:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("User Profile")
        profile_dict = dict(st.session_state.user_profile)
        st.json(profile_dict)

    with col2:
        st.subheader("Current Fixed Events")
        if st.session_state.fixed_events_df.empty:
            st.info("No fixed events found.")
        else:
            st.dataframe(st.session_state.fixed_events_df, use_container_width=True)

    st.subheader("Chat")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("Type your request here...")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})

        response = st.session_state.chatbot.process_message(
            user_message=user_input,
            user_profile=st.session_state.user_profile,
            tasks_df=st.session_state.tasks_df,
            fixed_events_df=st.session_state.fixed_events_df,
            current_schedule=st.session_state.current_schedule
        )

        st.session_state.tasks_df = response["updated_tasks_df"]
        st.session_state.fixed_events_df = response["updated_fixed_events_df"]
        st.session_state.current_schedule = response["updated_schedule"]

        st.session_state.messages.append({"role": "assistant", "content": response["text"]})

        st.rerun()

    st.subheader("Current Tasks")
    if st.session_state.tasks_df is not None and not st.session_state.tasks_df.empty:
        st.dataframe(st.session_state.tasks_df, use_container_width=True)
    else:
        st.info("No tasks found.")

    st.subheader("Generated Schedule")
    if st.session_state.current_schedule is not None and not st.session_state.current_schedule.empty:
        st.dataframe(format_schedule_table(st.session_state.current_schedule), use_container_width=True)
    else:
        st.info("No schedule generated yet.")

else:
    st.info("Select a user from the sidebar and click 'Load User Data'.")