# Hybrid RAG Travel Chatbot

A Flask app for exploring Vietnam through natural-language questions. Ask “Which destinations are good for trekking?” to see a recommendation alongside the matching records and their connections. The included hackathon dataset covers 360 entities across 10 cities, 150 attractions, 100 hotels, and 100 activities.

## Run the local demo

From the project directory on macOS or Linux, run

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp -n config.example.py config.py
APP_MODE=demo python app.py
```

Open [the chatbot](http://localhost:5050). Demo mode searches the bundled JSON by keyword overlap and displays descriptions and stored connections. It works without API keys. The [graph view](http://localhost:5050/graph-viz) opens the bundled interactive snapshot.

## Run cloud retrieval

Set `GEMINI_API_KEY`, `PINECONE_API_KEY`, `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD` in your environment or local `config.py`. Use a dedicated Pinecone index and Neo4j database. Keep credentials out of version control.

With the virtual environment active, load the dataset once and start Flask in cloud mode.

```sh
python load_to_neo4j.py
python pinecone_upload.py
APP_MODE=cloud python app.py
```

The uploader embeds one text per entity using Gemini and upserts batches of 16 into a 768-dimensional cosine index. The graph loader creates nodes first, then loads 370 directed connections. Both stores use the original dataset IDs.

For each question, the backend embeds the query, asks Pinecone for five matches, and uses their IDs to retrieve immediate neighbors from Neo4j. Gemini receives the matches and up to 15 relationship facts to compose the response. Each request is independent. The dataset describes places and connections and contains no live fares or schedules.

## Query the API

```sh
curl http://localhost:5050/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"Which places in Vietnam are good for trekking?"}'
```

The JSON response includes `answer`, `matches`, and `graph_facts`. A blank question returns HTTP 400.
