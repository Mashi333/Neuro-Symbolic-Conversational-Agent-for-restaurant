import streamlit as st

from decision_step import agent_answer
from llm_client import get_llm_client
from order_state import OrderState

st.set_page_config(
    page_title="Restaurant Data Query Assistant",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded",
)

EXAMPLE_QUERIES = [
    "Can you recommend a vegetarian meal under Rs.1500?",
    "I have a peanut allergy. What dishes are safe for me?",
    "Are there any low-calorie meal options?",
    "What is the price of a Margherita Pizza?",
    "Which meals are suitable for vegans?",
    "Do you offer any student discounts?",
    "Show me the full menu",
]

st.markdown(
    """
<style>
    .stApp {
        background-image:
            radial-gradient(circle at 12% 8%, rgba(255, 158, 84, 0.16), transparent 42%),
            radial-gradient(circle at 88% 4%, rgba(255, 99, 132, 0.13), transparent 40%),
            linear-gradient(180deg, #12100f 0%, #191512 100%);
    }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] {
        background: rgba(28, 24, 21, 0.92);
        border-right: 1px solid rgba(255, 255, 255, 0.08);
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 { color: #ffb37a; }

    .hero {
        padding: 1.6rem 1.8rem;
        margin-bottom: 1.2rem;
        border-radius: 1.1rem;
        border: 1px solid rgba(255, 179, 122, 0.28);
        background: linear-gradient(
            120deg,
            rgba(255, 158, 84, 0.20) 0%,
            rgba(255, 99, 132, 0.14) 55%,
            rgba(0, 0, 0, 0) 100%
        );
    }
    .hero-kicker {
        font-size: 0.74rem;
        letter-spacing: 0.22em;
        text-transform: uppercase;
        color: #ffca9a;
        margin-bottom: 0.35rem;
    }
    .hero-title {
        font-size: 2.15rem;
        font-weight: 700;
        line-height: 1.15;
        color: #fff7f0;
        margin: 0 0 0.45rem 0;
    }
    .hero-sub { font-size: 0.95rem; color: #d8cdc4; margin: 0; }

    .chip-row { display: flex; flex-wrap: wrap; gap: 0.45rem; margin-top: 0.9rem; }
    .chip {
        font-size: 0.78rem;
        padding: 0.3rem 0.7rem;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.07);
        border: 1px solid rgba(255, 255, 255, 0.12);
        color: #e7ded7;
    }

    .stat-card {
        padding: 0.75rem 0.9rem;
        border-radius: 0.8rem;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.09);
        text-align: center;
    }
    .stat-value { font-size: 1.45rem; font-weight: 700; color: #ffb37a; }
    .stat-label {
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.09em;
        color: #b9ada4;
    }

    [data-testid="stChatMessage"] {
        background: rgba(255, 255, 255, 0.045);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 0.9rem;
        padding: 0.35rem 0.7rem;
        margin-bottom: 0.7rem;
    }
    [data-testid="stChatInput"] textarea { border-radius: 999px; }
    .stButton > button {
        border-radius: 0.7rem;
        border: 1px solid rgba(255, 179, 122, 0.3);
        background: rgba(255, 255, 255, 0.05);
        color: #f0e6de;
        text-align: left;
        font-size: 0.85rem;
    }
    .stButton > button:hover {
        border-color: #ffb37a;
        color: #ffffff;
        background: rgba(255, 179, 122, 0.14);
    }
</style>
""",
    unsafe_allow_html=True,
)


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### Explore")
        st.caption("Tap a question to run it instantly.")
        for i, example in enumerate(EXAMPLE_QUERIES):
            if st.button(example, key=f"example_{i}", use_container_width=True):
                st.session_state.pending_prompt = example

        st.divider()
        st.markdown("### Session")
        turns = len(st.session_state.get("messages", [])) // 2
        st.markdown(
            f"""
<div class="stat-card">
    <div class="stat-value">{turns}</div>
    <div class="stat-label">Questions asked</div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.toggle(
            "Use the LLM for the final answer",
            value=st.session_state.get("use_llm", False),
            key="use_llm",
            help="Requires the Ollama server. When off, the agent "
            "uses the deterministic template fallback.",
        )
        if st.button("Clear conversation", use_container_width=True):
            st.session_state.messages = []
            st.session_state.pop("pending_prompt", None)
            st.session_state["order"].clear()
            st.rerun()


def render_hero() -> None:
    st.markdown(
        """
<div class="hero">
    <div class="hero-kicker">Neuro-Symbolic Restaurant Agent</div>
    <h1 class="hero-title">Ask anything about the menu</h1>
    <p class="hero-sub">
        Prices, calories, allergens, dietary tags, ingredients and restaurant policies,
        answered from the connected database.
    </p>
    <div class="chip-row">
        <span class="chip">Menu &amp; prices</span>
        <span class="chip">Allergens</span>
        <span class="chip">Vegan / Vegetarian</span>
        <span class="chip">Calories</span>
        <span class="chip">Policies &amp; discounts</span>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_answer(answer: str) -> None:
    with st.chat_message("assistant", avatar="🍽️"):
        st.markdown(answer)


if "messages" not in st.session_state:
    st.session_state.messages = []

if "order" not in st.session_state:
    st.session_state.order = OrderState()

render_sidebar()
render_hero()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

pending = st.session_state.pop("pending_prompt", None)
prompt = st.chat_input("Ask about menu items, policies, allergens, etc.") or pending

if prompt:
    prompt = prompt.strip()
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.spinner("Querying the restaurant database..."):
            use_llm = st.session_state.get("use_llm", False)
            result = agent_answer(
                prompt,
                k=8,
                llm=get_llm_client() if use_llm else None,
                order=st.session_state.get("order"),
            )

        st.session_state.messages.append(
            {"role": "assistant", "content": result["answer"]}
        )
        render_answer(result["answer"])

        with st.expander("How did the agent decide?"):
            constraints = result.get("constraints", {})
            st.markdown(
                f"**Decision:** `{result['decision']}`  ·  "
                f"**LLM used:** `{result['llm_used']}`"
            )
            if result["decision"] == "direct":
                st.markdown(
                    "Answered directly from the database keyword lookup "
                    "(lookup question, no retrieval/ASP loop needed)."
                )
            elif result["decision"] == "recommend":
                valid = result.get("valid", [])
                invalid = result.get("invalid", [])
                st.markdown(
                    f"**ASP kept {len(valid)} of {len(valid) + len(invalid)} "
                    f"candidate items**, then ranked by relevance."
                )
                if invalid:
                    st.markdown("Dropped by ASP with reasons:")
                    st.markdown(
                        "\n".join(
                            f"- **{r['item_name']}** — {', '.join(r['reasons'])}"
                            for r in invalid
                        )
                    )
            else:
                blockers = result.get("blockers", [])
                st.markdown("ASP failure diagnosis per constraint:")
                st.markdown(
                    "\n".join(
                        f"- **{b['label'].title()}** ({b['user_value']}) "
                        f"blocked {b['blocked_n']} item(s)"
                        for b in blockers
                    )
                )

if not st.session_state.messages:
    st.caption("Try one of the example questions in the sidebar to get started.")