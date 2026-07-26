# The Jobfather

<p align="left">
  <img src="assets/logo.png" width="500">
</p>


<h2 align="left">
  <em><b>“I'm gonna get them an offer they can't refuse.”</b></em>
</h2>


A Python-based human-in-the-loop agentic tool for job searching, tracking, and workflow automation.

Still a work in progress.

## Fit Assessment Pipeline

Assesses job fit via a 7-step LangGraph pipeline:

1. **Classify Role** — breaks the role into % categories (coding, stakeholder, data engineering, consulting, research)
2. **Translate Experience** — maps CV/profile elements to role-specific relevance
3. **Analyze Gaps** — identifies missing skills as hard/soft/negotiable gaps
4. **Assess Hiring Risk** — evaluates risk per area (technical interview, domain knowledge, seniority, etc.)
5. **Analyze Career Trajectory** — 2–3 year outlook and strategic fit
6. **Build Application Story** — crafts narrative, pitch, and interview risk prep
7. **Produce Assessment** — generates dimension scores, overall recommendation, and stitches all intermediate output into the final result

Each step has a dedicated LLM call with a focused prompt, feeding into the next. The enriched output (role breakdown, gaps, story, etc.) is persisted to SQLite alongside dimension scores.