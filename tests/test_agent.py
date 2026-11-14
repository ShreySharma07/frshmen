"""The agent chat (api/src/agent.py, POST /api/agent/chat) against Postgres, with a scripted Gemini.
Needs PG_TEST_URL, like tests/test_api.py."""

import json
from datetime import datetime, timezone

import psycopg
import pytest

from test_api import ASHA, PG, TOKEN, app_client, publish, records, reset

pytestmark = pytest.mark.skipif(not PG, reason="set PG_TEST_URL to a throwaway Postgres database")

FOUNDER_EMAIL = "ana@pinecone.io"
FOUNDER_PHONE = "+1 555 0100"


def text(t):
    return {"candidates": [{"content": {"role": "model", "parts": [{"text": t}]}}]}


def call(name, **args):
    return {"candidates": [{"content": {"role": "model", "parts": [{"functionCall": {"name": name, "args": args}}]}}]}


class Gemini:
    """Answers in order; keeps every request body so tests can see what the model was sent."""

    def __init__(self, *answers, status=200):
        self.answers, self.status, self.sent = list(answers), status, []

    async def __call__(self, url, headers, body):
        self.sent.append(json.loads(body))
        if self.status != 200:
            return self.status, {"error": {"message": "quota"}}
        return 200, self.answers.pop(0)


@pytest.fixture
def client():
    reset()
    publish(records(), datetime.now(timezone.utc))
    with psycopg.connect(PG, autocommit=True) as conn:
        conn.execute("INSERT INTO auth.users (id) VALUES (%s)", (ASHA,))
        conn.execute("INSERT INTO students (id, name, yoe, resume_text) VALUES (%s, 'Asha', 0, 'Python, PyTorch, RAG.')", (ASHA,))
        conn.execute("INSERT INTO contacts (kind, name, company, title, email, phone, yc_batch, notes, source) VALUES "
                     "('founder', 'Ana Diaz', 'Pinecone', 'Co-founder', %s, %s, 'W19', 'vector search', 'test'), "
                     "('hr', 'Ravi K', 'Pinecone', 'Recruiter', NULL, NULL, NULL, NULL, 'test')", (FOUNDER_EMAIL, FOUNDER_PHONE))
    c = app_client()

    async def verify(token):
        return ASHA if token == "asha-token" else None

    c.app.state.auth = verify
    return c


def ask(client, gemini, message="Hi", history=()):
    client.app.state.fit = ("key", gemini)
    return client.post("/api/agent/chat", headers=TOKEN,
                       json={"messages": [*history, {"role": "user", "text": message}]})


def ana_id():
    with psycopg.connect(PG) as conn:
        return conn.execute("SELECT id FROM contacts WHERE name = 'Ana Diaz'").fetchone()[0]


def test_plain_answer_counts_one_message(client):
    res = ask(client, Gemini(text("Hello Asha.")))
    assert res.status_code == 200
    assert res.json() | {"model": None} == {"reply": "Hello Asha.", "cards": [], "sources": [], "remaining": 19, "model": None}


def test_profile_and_history_reach_the_model(client):
    g = Gemini(text("ok"))
    ask(client, g, "And remote?", history=[{"role": "user", "text": "ML jobs?"}, {"role": "model", "text": "Here are some."}])
    sent = g.sent[0]
    assert "Asha" in sent["systemInstruction"]["parts"][0]["text"] and "PyTorch" in sent["systemInstruction"]["parts"][0]["text"]
    assert [c["role"] for c in sent["contents"]] == ["user", "model", "user"]


def test_search_jobs_tool_returns_cards_and_feeds_the_answer(client):
    g = Gemini(call("search_jobs", company="Pinecone", band="5-8"), text("Pinecone has these."))
    body = ask(client, g, "Pinecone jobs?").json()
    jobs = body["cards"][0]["jobs"]
    assert body["cards"][0]["type"] == "jobs" and all(j["company"] == "Pinecone" for j in jobs) and jobs
    assert all(j["url"].startswith("http") for j in jobs)
    response = g.sent[1]["contents"][-1]["parts"][0]["functionResponse"]
    assert response["name"] == "search_jobs" and response["response"]["jobs"]
    assert body["sources"] == [f"{len(jobs)} open jobs on Aventra"]


def test_people_and_draft_never_show_the_model_an_email_or_phone(client):
    g = Gemini(call("find_people", company="pinecone"),
               call("prepare_draft", contact_id=ana_id(), subject="PyTorch new grad", body="Hi Ana, ..."),
               text("Draft ready."))
    body = ask(client, g, "Write to Pinecone's founder").json()
    people, draft = body["cards"]
    assert [p["name"] for p in people["people"]] == ["Ana Diaz", "Ravi K"]
    assert all("email" not in p and "phone" not in p for p in people["people"])
    assert draft["to"] == FOUNDER_EMAIL and draft["reveals_left"] == 4
    assert draft["gmail_url"].startswith("https://mail.google.com/mail/?view=cm") and "ana%40pinecone.io" in draft["gmail_url"]
    everything_sent = json.dumps(g.sent)
    assert FOUNDER_EMAIL not in everything_sent and FOUNDER_PHONE not in everything_sent
    assert FOUNDER_PHONE not in json.dumps(body)
    with psycopg.connect(PG) as conn:
        assert conn.execute("SELECT COUNT(*) FROM contact_reveals").fetchone() == (1,)


def test_email_reveals_stop_at_five_a_day(client):
    with psycopg.connect(PG, autocommit=True) as conn:
        for _ in range(5):
            conn.execute("INSERT INTO contact_reveals (student_id, contact_id) VALUES (%s, %s)", (ASHA, ana_id()))
    g = Gemini(call("prepare_draft", contact_id=ana_id(), subject="s", body="b"), text("ok"))
    draft = ask(client, g).json()["cards"][0]
    assert (draft["to"], draft["gmail_url"], draft["reveals_left"]) == (None, None, 0)
    assert g.sent[1]["contents"][-1]["parts"][0]["functionResponse"]["response"]["draft"] == "daily email limit reached"


def test_suggest_startups_joins_founders_with_open_jobs(client):
    g = Gemini(call("suggest_startups"), text("Try Pinecone."))
    card = ask(client, g).json()["cards"][0]
    assert card["type"] == "startups"
    assert [s["company"] for s in card["startups"]] == ["Pinecone"] and card["startups"][0]["founder"] == "Ana Diaz"


def test_unknown_tool_is_reported_to_the_model_not_crashed(client):
    g = Gemini(call("delete_everything"), text("Sorry."))
    assert ask(client, g).status_code == 200
    assert "no tool named" in json.dumps(g.sent[1])


def test_twenty_messages_a_day_and_failures_do_not_count(client):
    assert ask(client, Gemini(status=429)).status_code == 503
    with psycopg.connect(PG, autocommit=True) as conn:
        assert conn.execute("SELECT COUNT(*) FROM agent_messages").fetchone() == (0,)
        for _ in range(20):
            conn.execute("INSERT INTO agent_messages (student_id) VALUES (%s)", (ASHA,))
    res = ask(client, Gemini(text("x")))
    assert res.status_code == 429 and "20" in res.json()["detail"]["message"]


def test_needs_sign_in_switch_and_a_last_user_turn(client):
    assert client.post("/api/agent/chat", json={"messages": [{"role": "user", "text": "hi"}]}).status_code in (401, 404)
    client.app.state.fit = ("key", Gemini(text("x")))
    assert client.post("/api/agent/chat", json={"messages": [{"role": "user", "text": "hi"}]}).status_code == 401
    assert client.post("/api/agent/chat", headers=TOKEN, json={"messages": [{"role": "model", "text": "hi"}]}).status_code == 422
