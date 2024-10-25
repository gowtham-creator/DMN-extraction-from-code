import streamlit as st
from llama_index.core.llms import ChatMessage
import logging 
import time
from llama_index.ollama import Ollama

logging.basicConfig(level=logging.INFO)

if 'messages' not in st.session_state:
    st.session_state.messages = []