import streamlit as st
from groq import Groq
client = Groq(api_key="gsk_XXXXXXXXXXXXXXXX")
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

print([m.id for m in client.models.list().data])

