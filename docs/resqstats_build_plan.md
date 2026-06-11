# ResQStats — Complete A-to-Z Build Plan (Easy Wording)

> **One line:** The data platform Karachi's ambulance networks (Edhi, Chhipa, Rescue 1122) should have — tracking every emergency from call to hospital, showing response times by area, and answering "where should the next ambulance be stationed?"

---

## PART 1 — WHY (your interview story)

Edhi runs one of the world's largest volunteer ambulance networks. Chhipa too. But their operations are paper-and-phone era — nobody can answer basic questions:

- How long does an ambulance take to reach Lyari vs. Defence?
- Which areas of Karachi are coverage "dead zones"?
- What time of day do emergencies spike, and is the fleet positioned for it?
- If you added ONE more ambulance station, where should it go?

**Your story:** "Ambulance response time decides who lives. Edhi saves thousands of lives a year with almost no data infrastructure. I built the operations platform their dispatch room should have — and because real dispatch data is private, I engineered a realistic simulator of Karachi's emergency patterns to power it."

No scraping. No fragile sources. You control everything.

---

## PART 2 — WHAT THE SYSTEM DOES (the data's journey)

```
[1] Simulator (Python)          — creates realistic emergency events
        ↓ streams events
[2] Kafka (Redpanda)            — the conveyor belt; never loses an event
        ↓
[3] Spark Streaming             — picks events off the belt, files them away
        ↓
[4] Data Lake (MinIO)           — bronze (raw) → silver (clean) folders, Parquet files
        ↓
[5] AI step (Groq, free)        — reads the caller's words, tags emergency type + severity
        ↓
[6] Warehouse (Snowflake)       — gold layer: clean tables ready for analysis
        ↓
[7] dbt                         — SQL models that compute the answers + quality tests
        ↓
[8] Dashboard (Evidence.dev)    — public website with maps and charts
    + Telegram alerts           — "response times in Korangi degraded 40% today"

[Airflow]                       — the manager: runs every step on schedule, retries failures
[Docker]                        — one command starts the whole system on any machine
[GitHub Actions]                — checks your code automatically on every change
```

---

## PART 3 — EACH PIECE EXPLAINED SIMPLY

### [1] The Simulator — your data factory
A Python program that plays out Karachi's emergencies like a video game running on its own:
- A map of Karachi's ~22 towns with realistic population weights (more incidents in dense Korangi than DHA Phase 8)
- Emergencies appear with realistic rhythms: road accidents spike Friday night, heat emergencies June afternoons, everything rises during rain
- A fleet of ~68 ambulances at 10 stations. When an emergency appears: the ambulance that can arrive first is assigned → drives there (travel time depends on distance + Karachi traffic by hour) → picks up patient → drives to nearest hospital → returns to station → free again
- Each step emits an event: `call_received`, `ambulance_dispatched`, `arrived_on_scene`, `departed_scene`, `arrived_hospital`, `ambulance_available`
- Each call includes a short text line (what the caller said — English/Roman Urdu templates) for the AI step later

Why this is impressive and not "fake": real dispatch data is confidential — simulation is exactly how real companies prototype these systems. And building a realistic simulator IS engineering: distributions, daily patterns, a moving fleet.

### [2] Kafka (via Redpanda, in Docker) — the conveyor belt
Emergencies are bursty — a bus accident creates many events at once. Kafka is a queue that receives events instantly and holds them safely until the next step is ready. Producer (simulator) and consumer (Spark) are decoupled: if one crashes, no data is lost. Redpanda = Kafka made easy to run (one container, same API).

### [3] Spark Structured Streaming — the worker on the belt
A Spark job continuously reads events from Kafka and writes them as Parquet files (a compressed column format — the industry standard) into the lake, organized into date folders. Spark checkpoints its progress, so if it crashes and restarts, nothing is lost or duplicated. You will demo this on purpose: kill it mid-run, restart, prove the data is intact. That demo is interview gold.

### [4] The Data Lake (MinIO, in Docker) — organized storage
MinIO is a free, self-hosted version of Amazon S3 (same API — so you're learning S3 for free). Two zones:
- **bronze/** — events exactly as they arrived. Never edited. Your "negatives roll."
- **silver/** — cleaned: events stitched into one row per incident (call → dispatch → scene → hospital with all timestamps), validated, junk removed.

### [5] The AI step (Groq — free LLM API)
Reads each call's text ("gari ka accident hua hai Shahrah-e-Faisal pe, banda behosh hai") and returns structured tags: `{type: road_accident, severity: critical}`. Rules you follow (and say in interviews):
- The AI only converts text → categories. **All numbers are computed by SQL/Python, never by the AI.**
- Because the simulator knows the TRUE type/severity of every incident, you can measure the AI's accuracy exactly (e.g., "93% correct on type, 88% on severity"). This evaluation habit impresses interviewers more than the AI itself.

### [6] Snowflake — the warehouse (gold layer)
Silver data is loaded into Snowflake (30-day free trial, $400 credit — enough for the whole project). This is where analysis happens fast. After the trial, switching to MotherDuck (permanently free) is a one-line dbt config change — mention that portability in interviews.

### [7] dbt — the answer-maker
SQL files, each producing one clean table:
- `fct_incidents` — one row per emergency, every timestamp and duration
- `mart_response_by_town` — median minutes-to-scene per town per month ⭐ headline table
- `mart_golden_hour` — % of critical patients reaching hospital within 60 minutes
- `mart_fleet_utilization` — % of time ambulances are busy, by station and hour
- `mart_coverage_gaps` — areas where response time is consistently worst
- `mart_station_optimizer` — "if you add one station, the best location is X" (re-run the simulator with a candidate station and compare — simple but very smart-looking)

dbt also runs automatic tests: response time can't be negative, severity must be one of four values, no duplicate incident IDs. Bad data = pipeline stops and alerts you.

### [8] Dashboard + Alerts
**Evidence.dev** builds a fast public website from SQL + markdown — hosted free on Vercel, so your resume carries a live link. Pages: Karachi response-time map (color-coded towns), golden-hour trend, fleet utilization heatmap (hour × station), coverage-gap ranking, "next station" recommendation.
**Telegram bot:** if today's response time in any town is much worse than its 30-day normal, post an alert. Shows you think about monitoring.

### The managers
- **Airflow** (in Docker): the scheduler — runs enrichment every few hours, dbt daily, retries failures, alerts on errors. The most job-posted orchestrator.
- **Docker Compose:** one file, one command (`docker compose up`) boots Kafka + MinIO (+ later Spark, Airflow) on any machine.
- **GitHub Actions:** every code change automatically runs lint + tests + a dbt build. Nothing broken reaches main.

---

## PART 4 — BUILD ORDER (6 weeks, each week ends with something working)

| Week | Build | Done when... |
|---|---|---|
| 1 | Simulator + Karachi map data + event schemas ✅ DONE | Simulator prints realistic events for a full simulated day |
| 2 | Docker Compose: Redpanda + MinIO ✅ DONE. Simulator → Kafka. Spark → bronze | Parquet files appear in MinIO, partitioned by date; kill/restart test passes |
| 3 | Silver: incident stitching + cleaning. AI tagging + accuracy eval vs ground truth | One clean row per incident, AI accuracy measured and written down |
| 4 | Snowflake load + all dbt models + tests | `dbt build` green; "slowest town last month?" answered in one query |
| 5 | Airflow DAGs + Telegram alerts | System runs 7 days untouched; a simulated bad day triggers an alert |
| 6 | Evidence dashboard on Vercel + README + dbt docs + CI | Live public link + architecture diagram + accuracy table + tradeoffs section |

---

## PART 5 — WHAT IT COSTS: ₨0

| Tool | Free how |
|---|---|
| Redpanda, Spark, MinIO, Airflow, dbt, Docker | Open source, run on your laptop (8 GB RAM workable, 16 GB comfortable) |
| Groq AI API | Free tier (rate-limited — batch your calls) |
| Snowflake | 30-day trial / $400 credit → then swap to MotherDuck (free) |
| Evidence + Vercel, Telegram, GitHub Actions | Free |

---

## PART 6 — RESUME BULLETS

> Built a streaming emergency-dispatch analytics platform (Kafka/Redpanda, Spark Structured Streaming, MinIO data lake, Snowflake, dbt, Airflow, Docker) simulating Karachi's ambulance network with exactly-once processing into a bronze/silver/gold lakehouse.

> Engineered an LLM enrichment layer (Llama via Groq) classifying bilingual emergency-call text into type/severity at 90%+ accuracy against simulator ground truth; all metrics computed in SQL, LLM restricted to text structuring.

> Modeled dispatch analytics in dbt (response time by area, golden-hour rate, fleet utilization, station-placement optimization) with automated quality tests, CI/CD, and a public geospatial dashboard.

---

## PART 7 — INTERVIEW Q&A YOU'LL NOW OWN

- "Why Kafka?" → bursty emergency events, producer/consumer decoupling, zero loss
- "What's exactly-once processing?" → your Spark checkpoint kill-restart demo
- "What's a medallion architecture?" → you built bronze/silver/gold and can say why raw stays immutable
- "How do you use LLMs in pipelines safely?" → extraction-only, eval against ground truth, measured accuracy
- "Walk me through a metric" → golden-hour rate: definition, SQL, edge cases (what if no hospital timestamp?)
- "Synthetic data — isn't that cheating?" → "Real dispatch data is confidential; simulation is how real teams prototype. My simulator encodes realistic Karachi patterns, and it gives me ground truth to validate against."
