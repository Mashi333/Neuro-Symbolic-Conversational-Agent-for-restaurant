import streamlit as st

from retrieve import get_answer


st.set_page_config(
    page_title="Restaurant Data Query Assistant",
    page_icon="🍽️",
    layout="centered",
)

st.title("Restaurant Data Query Assistant")
st.write(
    "Ask questions about restaurant policies, menu items, allergens, dietary types, ingredients, or other stored facts."
)

query = st.text_input("Enter your query", placeholder="For example: Can I bring outside food?")

if st.button("Get Answer", type="primary"):
    if not query.strip():
        st.warning("Please enter a query first.")
    else:
        answer = get_answer(query.strip())
        st.subheader("Answer")
        st.success(answer)
