# Neuro-Symbolic Conversational Restaurant Agent

A restaurant question-answering and recommendation assistant built with a
neuro-symbolic pipeline. The application combines semantic retrieval and
optional local language-model assistance with deterministic Answer Set
Programming (ASP) validation, so recommendations are grounded in the
restaurant's menu and policy data.

## Features

- Streamlit chat interface for natural-language restaurant questions.
- Menu lookup for prices, calories, ingredients, dietary tags, and allergens.
- Semantic search over menu items, policies, FAQs, allergy guidance, reviews,
  and restaurant descriptions.
- Constraint-aware recommendations for:
  - vegetarian and vegan requirements;
  - allergies and ingredients to avoid;
  - budget limits;
  - calorie limits;
  - preferred ingredients.
- ASP validation with explanations for rejected menu items.
- Deterministic fallback mode when Ollama is unavailable or disabled.
- Optional Ollama integration for intent extraction and final response
  generation.
- Conversation-level order state for multi-turn interactions.

## Architecture

The main request flow is:

```text
User question
    |
    v
Intent and constraint extraction
    |
    +--> Direct database lookup for simple detail, price, and policy questions
    |
    +--> Retrieval query construction
              |
              v
       ChromaDB semantic retrieval
              |
              v
       ASP constraint validation
              |
              v
       Ranking of valid items
              |
              v
       Grounded response generation
```

The language model is used for structure and wording only. Menu facts are
loaded from the relational database dump and knowledge files. The ASP layer
performs the strict checks that embeddings cannot express reliably, such as
budget, allergy, ingredient, dietary, and calorie constraints.

## Project structure

| Path | Purpose |
| --- | --- |
| `streamlit_app.py` | Streamlit web interface |
| `decision_step.py` | Routes direct lookups and recommendation requests |
| `intent_extractor.py` | Extracts intent and user constraints |
| `rag_pipeline.py` | Builds retrieval queries and retrieves candidate items |
| `semantic_retrieval.py` | Embedding model and ChromaDB search |
| `asp_reasoner.py` | Builds and evaluates ASP facts and rules |
| `asp_rules.lp` | ASP rules for strict constraint validation |
| `ranking_step.py` | Ranks validated recommendations |
| `response_step.py` | Generates grounded final responses |
| `retrieve.py` | Loads and queries structured restaurant data |
| `build_documents.py` | Converts database and text sources into JSONL documents |
| `DataSources/` | Restaurant SQL dump and supporting knowledge files |
| `vectordb/` | Local persistent ChromaDB storage |
| `test_*.py` | Unit and integration tests |

## Requirements

- Python 3.10 or newer is recommended.
- Windows, macOS, or Linux.
- Ollama is optional. It is only required when using model-assisted
  extraction or final answer generation.

Python dependencies are listed in
[`requirements.txt`](requirements.txt).

## Installation

From the project directory, create and activate a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks script activation, run the commands from a Command Prompt
instead:

```bat
py -m venv .venv
.\.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Optional Ollama setup

Install Ollama from [ollama.com](https://ollama.com), start the Ollama
service, and pull the configured model:

```powershell
ollama pull llama3.1
```

The application uses these environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server base URL |
| `LLM_MODEL` | `llama3.1` | Ollama model name |
| `NLU_FORCE_FALLBACK` | unset | Set to `1` to disable Ollama and use deterministic rules |

For example, to run without an LLM:

```powershell
$env:NLU_FORCE_FALLBACK = "1"
```

The Streamlit sidebar also includes a toggle for using the LLM for the final
answer. The deterministic mode remains available when the toggle is off.

## Build the retrieval documents

The application can generate the document store automatically when needed.
To build it explicitly:

```powershell
python build_documents.py
```

This reads `DataSources/restaurant_conversational_agent_db.sql` and the
supporting text files, then writes:

```text
DataSources/documents.jsonl
```

The first semantic-search run may download the
`sentence-transformers/all-MiniLM-L6-v2` embedding model. ChromaDB stores the
resulting local index under `vectordb/`.

To rebuild the vector index after changing source data:

```powershell
python semantic_retrieval.py "vegetarian meal" --rebuild
```

## Run the web application

```powershell
streamlit run streamlit_app.py
```

Streamlit will print a local URL, normally
`http://localhost:8501`.

Example questions:

- `Can you recommend a vegetarian meal under Rs.1500?`
- `I have a peanut allergy. What dishes are safe for me?`
- `What is the price of a Margherita Pizza?`
- `Do you offer any student discounts?`
- `Show me the full menu`

## Command-line usage

Run the complete decision pipeline:

```powershell
python decision_step.py "I want a vegetarian meal under Rs. 1500 without peanuts."
```

Run retrieval only:

```powershell
python rag_pipeline.py "I want a cheap vegetarian meal." -k 5
```

Run semantic search directly:

```powershell
python semantic_retrieval.py "peanut allergy safe dishes" -k 3
```

Run ASP reasoning directly:

```powershell
python asp_reasoner.py "I want a vegetarian meal under Rs. 1500 without peanuts."
```

## Testing

The test suite uses Python's built-in `unittest` framework. Run all tests with:

```powershell
python -m unittest discover -p "test_*.py" -v
```

Individual test modules can also be run directly:

```powershell
python -m unittest test_rag_pipeline.py -v
python -m unittest test_asp_reasoner.py -v
python -m unittest test_decision_step.py -v
```

Most tests use deterministic fixtures and mock LLM clients, so an Ollama
server is not required for the test suite.

## Data and grounding

The application uses:

- `DataSources/restaurant_conversational_agent_db.sql` for structured menu,
  allergen, ingredient, and policy data.
- Restaurant knowledge text files in `DataSources/` for policies, FAQs,
  allergy guidance, descriptions, discounts, and reviews.
- `DataSources/documents.jsonl` as the generated document representation used
  by semantic retrieval.
- `asp_rules.lp` for strict recommendation and policy rules.

The vector store is a derived local artifact. If it is removed, the documents
and index can be regenerated using the commands above.

## Notes

- Currency conversion rates used by the ASP prototype are documented in
  `asp_reasoner.py` and are illustrative research-prototype rates.
- Do not commit API keys, local environment files, virtual environments, or
  generated logs.
- The application is a research prototype and should not be treated as a
  substitute for confirming allergy information with restaurant staff.

## License

No license file is currently included in this repository. Add an explicit
license before distributing the project outside its intended research
context.
