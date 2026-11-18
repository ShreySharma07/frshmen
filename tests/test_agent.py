"""The agent chat (api/src/agent.py, POST /api/agent/chat) against Postgres, with a scripted Gemini.
Needs PG_TEST_URL, like tests/test_api.py."""

import json
from datetime import datetime, timezone

import psycopg
import pytest
from test_api import ASHA, PG, TOKEN, app_client, publish, records, reset, usage_who

pytestmark = pytest.mark.skipif(not PG, reason="set PG_TEST_URL to a throwaway Postgres database")

FOUNDER_EMAIL = "ana@pinecone.io"
FOUNDER_PHONE = "+1 555 0100"
WHO = usage_who(ASHA, None)  # the test sign-in has no email: limits count against the user id
DRAFT = ("Hi Ana,\n\nI'm a 2026 CS graduate; Pinecone's vector search is what I build on.\n\n"
         "I built a RAG search over 10k papers in Python and PyTorch, cutting lookup time by 60%.\n\n"
         "Could we talk for 15 minutes about new-grad roles?\n\nThanks,\nAsha")


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
               call("prepare_draft", contact_id=ana_id(), subject="PyTorch new grad", body=DRAFT),
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
            conn.execute("INSERT INTO usage_events (who, kind) VALUES (%s, 'contact_reveal')", (WHO,))
    g = Gemini(call("find_people", company="Pinecone"), call("prepare_draft", contact_id=ana_id(), subject="s", body=DRAFT), text("ok"))
    draft = ask(client, g).json()["cards"][1]
    assert (draft["to"], draft["gmail_url"], draft["reveals_left"]) == (None, None, 0)
    assert g.sent[2]["contents"][-1]["parts"][0]["functionResponse"]["response"]["draft"] == "daily email limit reached"


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
        assert conn.execute("SELECT COUNT(*) FROM usage_events").fetchone() == (0,)
        for _ in range(20):
            conn.execute("INSERT INTO usage_events (who, kind) VALUES (%s, 'agent_message')", (WHO,))
    res = ask(client, Gemini(text("x")))
    assert res.status_code == 429 and "20" in res.json()["detail"]["message"]


def test_needs_sign_in_switch_and_a_last_user_turn(client):
    assert client.post("/api/agent/chat", json={"messages": [{"role": "user", "text": "hi"}]}).status_code in (401, 404)
    client.app.state.fit = ("key", Gemini(text("x")))
    assert client.post("/api/agent/chat", json={"messages": [{"role": "user", "text": "hi"}]}).status_code == 401
    assert client.post("/api/agent/chat", headers=TOKEN, json={"messages": [{"role": "model", "text": "hi"}]}).status_code == 422


OTHER = "00000000-0000-4000-8000-0000000000b0"


def connections(*rows):
    """(student, name, company) rows; returns their ids in order."""
    with psycopg.connect(PG, autocommit=True) as conn:
        return [conn.execute("INSERT INTO connections (student_id, name, company, position, linkedin) "
                             "VALUES (%s, %s, %s, 'Engineer', 'https://www.linkedin.com/in/x') RETURNING id", r).fetchone()[0]
                for r in rows]


def test_find_connections_sees_only_the_askers_own(client):
    with psycopg.connect(PG, autocommit=True) as conn:
        conn.execute("INSERT INTO auth.users (id) VALUES (%s)", (OTHER,))
        conn.execute("INSERT INTO students (id, name) VALUES (%s, 'Other')", (OTHER,))
    connections((ASHA, "Kiran Rao", "Razorpay"), (OTHER, "Someone Else", "Razorpay"), (ASHA, "Meena", "Zomato"))
    g = Gemini(call("find_connections", company="razorpay"), text("You know Kiran."))
    body = ask(client, g, "Who do I know at Razorpay?").json()
    card = body["cards"][0]
    assert card["type"] == "connections" and [p["name"] for p in card["people"]] == ["Kiran Rao"]
    assert "Someone Else" not in json.dumps(g.sent)
    assert body["sources"] == ["your LinkedIn connections"]


def test_find_connections_says_when_nothing_was_uploaded(client):
    g = Gemini(call("find_connections", company="razorpay"), text("Upload your connections."))
    assert ask(client, g).json()["cards"] == []
    assert "hasn't uploaded" in g.sent[1]["contents"][-1]["parts"][0]["functionResponse"]["response"]["note"]


def test_linkedin_message_only_to_the_askers_own_connection(client):
    with psycopg.connect(PG, autocommit=True) as conn:
        conn.execute("INSERT INTO auth.users (id) VALUES (%s)", (OTHER,))
        conn.execute("INSERT INTO students (id, name) VALUES (%s, 'Other')", (OTHER,))
    mine, theirs = connections((ASHA, "Kiran Rao", "Razorpay"), (OTHER, "Someone Else", "Razorpay"))
    g = Gemini(call("prepare_linkedin_message", connection_id=theirs, body="Hi"),
               call("prepare_linkedin_message", connection_id=mine, body="Hi Kiran, could you refer me?"),
               text("Ready."))
    cards = ask(client, g).json()["cards"]
    assert len(cards) == 1 and cards[0]["type"] == "linkedin"
    assert cards[0]["person"]["name"] == "Kiran Rao" and cards[0]["person"]["linkedin"].startswith("https://www.linkedin.com/")
    assert "error" in g.sent[1]["contents"][-1]["parts"][0]["functionResponse"]["response"]


class Overloaded(Gemini):
    """The first model answers 503 (Google overloaded); the next one works."""

    async def __call__(self, url, headers, body):
        self.sent.append((url, json.loads(body)))
        if len(self.sent) == 1:
            return 503, {"error": {"message": "overloaded"}}
        return 200, self.answers.pop(0)


def test_an_overloaded_model_falls_back_to_the_next(client):
    g = Overloaded(text("Hello."))
    res = ask(client, g)
    assert res.status_code == 200 and res.json()["reply"] == "Hello."
    assert g.sent[0][0] != g.sent[1][0]  # a different model the second time


def test_every_model_overloaded_says_busy_and_counts_nothing(client):
    res = ask(client, Gemini(status=503))
    assert res.status_code == 503 and "busy" in json.dumps(res.json())
    with psycopg.connect(PG) as conn:
        assert conn.execute("SELECT COUNT(*) FROM usage_events").fetchone() == (0,)


# --- Startups that fit, with or without openings (docs/decisions.md, 2026-11-16) ----------------

def add_startups(rows):
    """rows: (company, founder, one_liner or None, categories, skills, status)."""
    with psycopg.connect(PG, autocommit=True) as conn:
        for company, founder, builds, cats, skills, status in rows:
            conn.execute("INSERT INTO contacts (kind, name, company, source) VALUES ('founder', %s, %s, 'test')", (founder, company))
            conn.execute("INSERT INTO startup_profiles (key, name, one_liner, categories, skills, status, source) "
                         "VALUES (lower(%s), %s, %s, %s, %s, %s, %s)",
                         (company, company, builds, cats, skills, status, "yc-oss" if builds else None))
        conn.execute("UPDATE students SET target_roles = '{ai_ml}' WHERE id = %s", (ASHA,))


def startups_card(client, **args):
    g = Gemini(call("suggest_startups", **args), text("Here they are."))
    res = ask(client, g).json()
    return next(c for c in res["cards"] if c["type"] == "startups"), g


def test_startups_fit_without_openings_and_unknowns_come_last(client):
    add_startups([("Vectorly", "Mo Lee", "LLM evals for AI teams", ["ai_ml"], ["LLMs"], "Active"),
                  ("Bakeshop", "Jo Kim", "Software for bakeries", ["frontend"], [], "Active"),
                  ("Mystery Labs", "Al Roy", None, [], [], None),
                  ("Gone AI", "Ed Fox", "AI for lawyers", ["ai_ml"], [], "Inactive")])
    card, g = startups_card(client)
    names = [s["company"] for s in card["startups"]]
    # Pinecone (open jobs, no description yet) and Vectorly (no openings) fit; the bakery shares
    # nothing with an ai_ml profile; an inactive startup never shows; unknowns sort last.
    assert "Vectorly" in names and "Bakeshop" not in names and "Gone AI" not in names
    assert names.index("Vectorly") < names.index("Mystery Labs")
    vectorly = next(s for s in card["startups"] if s["company"] == "Vectorly")
    assert vectorly["open_jobs"] == 0 and vectorly["matched_kinds"] == ["ai_ml"] and vectorly["described"]
    assert not next(s for s in card["startups"] if s["company"] == "Mystery Labs")["described"]
    told = g.sent[1]["contents"][-1]["parts"][0]["functionResponse"]["response"]
    assert told["matched_against"]["kinds_of_work"] == ["ai_ml"] and "PyTorch" in told["matched_against"]["resume_skills"]


def test_startups_default_to_twelve_and_page_on(client):
    add_startups([(f"Agent{i:02d}", f"F{i}", "AI agents for support", ["ai_ml"], [], "Active") for i in range(30)])
    card, _ = startups_card(client)
    assert len(card["startups"]) == 12 and card["has_more"]
    more, g = startups_card(client, limit=100, offset=12)
    assert len(more["startups"]) <= 50 and more["offset"] == 12
    assert not {s["company"] for s in card["startups"]} & {s["company"] for s in more["startups"]}


def test_generic_draft_is_sent_back_for_a_rewrite(client):
    generic = "Dear Sir,\n\nI hope this finds you well. I am passionate about AI.\n\nRegards"
    g = Gemini(call("find_people", company="Pinecone"),
               call("prepare_draft", contact_id=ana_id(), subject="Opportunity", body=generic),
               call("prepare_draft", contact_id=ana_id(), subject="RAG grad for Pinecone", body=DRAFT),
               text("Draft ready."))
    res = ask(client, g).json()
    refused = g.sent[2]["contents"][-1]["parts"][0]["functionResponse"]["response"]
    assert "draft not shown" in refused["error"]
    assert [c["type"] for c in res["cards"]] == ["people", "draft"]


def test_long_or_projectless_drafts_are_refused():
    from agent import draft_problem
    assert "words" in draft_problem("word " * 151, ["Python"])
    assert "projects" in draft_problem("Hi Ana, could we talk about roles at Pinecone? Thanks, Asha", ["Python"])
    assert draft_problem(DRAFT, ["Python", "PyTorch", "RAG"]) is None
    assert draft_problem("Hi Ana, could we talk? Thanks, Asha", []) is None  # no resume skills to name


def test_people_carry_what_the_company_builds(client):
    with psycopg.connect(PG, autocommit=True) as conn:
        conn.execute("INSERT INTO startup_profiles (key, name, one_liner, source) VALUES ('pinecone', 'Pinecone', 'Vector database', 'yc-oss')")
    g = Gemini(call("find_people", company="Pinecone"), text("ok"))
    ask(client, g)
    people = g.sent[1]["contents"][-1]["parts"][0]["functionResponse"]["response"]["people"]
    assert people[0]["company_builds"] == "Vector database"


# --- The resume editor's "Ask agent to improve" (docs/decisions.md, 2026-11-16) ------------------

RESUME = "Asha Rao\nPROJECTS\nWorked on a RAG search in Python.\nEDUCATION\nB.Tech CS, 2026"


def improve(client, answer, text=RESUME):
    from test_api import gemini_reply

    g = Gemini(gemini_reply(answer))
    client.app.state.fit = ("key", g)
    return client.post("/api/agent/resume/improve", headers=TOKEN, json={"text": text}), g


def test_improve_rewords_within_the_resume_and_counts_one_message(client):
    res, g = improve(client, {"name": "Asha Rao", "note": "Stronger project line.", "sections": [
        {"heading": "PROJECTS", "lines": [{"text": "Built a RAG search in Python", "sources": [3]},
                                          {"text": "Served it on Kubernetes to 500 users", "sources": [3]}]},
        {"heading": "EDUCATION", "lines": [{"text": "B.Tech CS, 2026", "sources": [5]}]}]})
    assert res.status_code == 200
    body = res.json()
    lines = body["sections"][0]["lines"]
    assert lines[0]["text"] == "Built a RAG search in Python" and not lines[0]["kept_original"]
    assert lines[1]["kept_original"] and "Kubernetes" in lines[1]["reason"]  # an invented skill goes back
    assert "Asha Rao" in body["left_out"]  # the editor keeps lines the rewrite didn't use
    assert body["remaining"] == 19
    assert "Worked on a RAG search" in json.dumps(g.sent[0])  # the editor's text, not the saved resume


def test_improve_failure_is_not_counted(client):
    client.app.state.fit = ("key", Gemini(status=503))
    res = client.post("/api/agent/resume/improve", headers=TOKEN, json={"text": RESUME})
    assert res.status_code == 503
    with psycopg.connect(PG) as conn:
        assert conn.execute("SELECT COUNT(*) FROM usage_events").fetchone()[0] == 0


def test_improve_needs_text_and_sign_in(client):
    client.app.state.fit = ("key", Gemini())
    assert client.post("/api/agent/resume/improve", headers=TOKEN, json={"text": ""}).status_code == 422
    assert client.post("/api/agent/resume/improve", json={"text": RESUME}).status_code == 401


# --- Daily limits count the person, not the profile row (docs/decisions.md, 2026-11-18, H1) -------

def test_deleting_and_recreating_the_profile_keeps_the_limits(client):
    with psycopg.connect(PG, autocommit=True) as conn:
        for _ in range(20):
            conn.execute("INSERT INTO usage_events (who, kind) VALUES (%s, 'agent_message')", (WHO,))
        # What the Data API lets a person do with their own row (0004): delete it and insert it again.
        conn.execute("DELETE FROM students WHERE id = %s", (ASHA,))
        conn.execute("INSERT INTO students (id, name, yoe, resume_text) VALUES (%s, 'Asha', 0, 'Python')", (ASHA,))
    assert ask(client, Gemini(text("x"))).status_code == 429


def test_a_new_account_with_the_same_email_shares_the_limits(client):
    other = "00000000-0000-4000-8000-0000000000b2"
    with psycopg.connect(PG, autocommit=True) as conn:
        conn.execute("INSERT INTO auth.users (id) VALUES (%s)", (other,))
        conn.execute("INSERT INTO students (id, name, yoe) VALUES (%s, 'Asha again', 0)", (other,))
    accounts = {"first": (ASHA, "Asha.Rao@gmail.com"), "second": (other, "asharao+jobs@googlemail.com")}

    async def verify(token):
        uid, email = accounts[token]
        return {"id": uid, "email": email}

    client.app.state.auth = verify
    client.app.state.fit = ("key", Gemini(*[text("x")] * 20))
    for _ in range(20):
        assert client.post("/api/agent/chat", headers={"Authorization": "Bearer first"}, json={"messages": [{"role": "user", "text": "hi"}]}).status_code == 200
    res = client.post("/api/agent/chat", headers={"Authorization": "Bearer second"}, json={"messages": [{"role": "user", "text": "hi"}]})
    assert res.status_code == 429  # dots and +tags are the same Gmail inbox, so the same person


def test_the_reveal_log_outlives_the_account(client):
    g = Gemini(call("find_people", company="Pinecone"), call("prepare_draft", contact_id=ana_id(), subject="s", body=DRAFT), text("ok"))
    assert ask(client, g).json()["cards"][1]["to"] == FOUNDER_EMAIL
    with psycopg.connect(PG, autocommit=True) as conn:
        conn.execute("DELETE FROM students WHERE id = %s", (ASHA,))
        assert conn.execute("SELECT student_id, contact_id IS NOT NULL FROM contact_reveals").fetchall() == [(None, True)]
        assert conn.execute("SELECT COUNT(*) FROM usage_events WHERE kind = 'contact_reveal'").fetchone() == (1,)


def test_parallel_reveals_cannot_pass_the_limit(client):
    import asyncio

    import agent
    import asyncpg

    async def run():
        reset_reveals = "INSERT INTO usage_events (who, kind) SELECT $1, 'contact_reveal' FROM generate_series(1, 4)"
        conns = [await asyncpg.connect(PG) for _ in range(4)]
        try:
            await conns[0].execute(reset_reveals, WHO)
            from storage import PostgresDatabase

            tools = [agent.Tools(PostgresDatabase(c), ASHA, 0, {"resume_text": "Python, PyTorch, RAG."}, who=WHO) for c in conns]
            for t in tools:
                t.found.add(ana_id())  # as if find_people had listed her in each reply
            results = await asyncio.gather(*(t.prepare_draft(ana_id(), "s", DRAFT) for t in tools))
            return [t.cards[0]["to"] for t in tools], results
        finally:
            for c in conns:
                await c.close()

    to, _ = asyncio.run(run())
    assert sum(1 for x in to if x) == 1  # four at once, one reveal left: exactly one gets it


def test_emails_normalise_to_one_person():
    from usage import normalise, who

    assert normalise(" A.Sha+x@GoogleMail.com ") == normalise("asha@gmail.com") == "asha@gmail.com"
    assert normalise("Ravi.K+jobs@outlook.com") == "ravi.k@outlook.com"  # dots matter outside Gmail
    assert who("u1", "asha@gmail.com") == who("u2", "a.sha@gmail.com") != who("u1", None)
    assert who("u1", "asha@gmail.com", "k") != who("u1", "asha@gmail.com")  # keyed



# --- Harvesting contacts (docs/decisions.md, 2026-11-18, security M1) -----------------------------

def test_a_draft_only_reaches_someone_found_in_the_same_reply(client):
    # Asking for a contact id straight away (walking ids) gets no address and no reveal.
    g = Gemini(call("prepare_draft", contact_id=ana_id(), subject="s", body=DRAFT), text("ok"))
    res = ask(client, g).json()
    assert res["cards"] == []
    assert "find this person" in g.sent[1]["contents"][-1]["parts"][0]["functionResponse"]["response"]["error"]
    with psycopg.connect(PG) as conn:
        assert conn.execute("SELECT COUNT(*) FROM contact_reveals").fetchone() == (0,)


def test_one_contact_is_shown_at_most_three_times_a_day_across_everyone(client):
    with psycopg.connect(PG, autocommit=True) as conn:
        for _ in range(3):  # three other people already emailed her today
            conn.execute("INSERT INTO contact_reveals (student_id, contact_id) VALUES (NULL, %s)", (ana_id(),))
    g = Gemini(call("find_people", company="Pinecone"), call("prepare_draft", contact_id=ana_id(), subject="s", body=DRAFT), text("ok"))
    draft = ask(client, g).json()["cards"][1]
    assert draft["to"] is None and draft["held_back"] and draft["reveals_left"] == 5  # not counted against Asha
    assert "held back" in g.sent[2]["contents"][-1]["parts"][0]["functionResponse"]["response"]["draft"]


def test_the_site_stops_revealing_at_its_daily_cap(client, monkeypatch):
    import agent

    monkeypatch.setattr(agent, "SITE_DAILY", 2)
    with psycopg.connect(PG, autocommit=True) as conn:
        conn.execute("INSERT INTO contacts (kind, name, company, email, source) VALUES ('hr', 'Zed', 'Other', 'zed@other.io', 't')")
        zed = conn.execute("SELECT id FROM contacts WHERE name = 'Zed'").fetchone()[0]
        for _ in range(2):
            conn.execute("INSERT INTO contact_reveals (student_id, contact_id) VALUES (NULL, %s)", (zed,))
    g = Gemini(call("find_people", company="Pinecone"), call("prepare_draft", contact_id=ana_id(), subject="s", body=DRAFT), text("ok"))
    assert ask(client, g).json()["cards"][1]["held_back"]


def test_the_agent_never_sees_the_persons_email_or_phone(client):
    with psycopg.connect(PG, autocommit=True) as conn:
        conn.execute("UPDATE students SET resume_text = 'Asha Rao, asha@example.com, +91 98765 43210. Python, PyTorch.' WHERE id = %s", (ASHA,))
    g = Gemini(text("ok"))
    ask(client, g)
    system = g.sent[0]["systemInstruction"]["parts"][0]["text"]
    assert "asha@example.com" not in system and "98765" not in system and "Python, PyTorch" in system
