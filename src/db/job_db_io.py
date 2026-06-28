import argparse
import json
import sqlite3
from pathlib import Path
from typing import Optional, Iterable
from collections import defaultdict
from devtools import pprint

from src.schemas.structured_job import (
    JobOpening,
    Location,
    LanguageSkill,
    Skill,
    RangedInt,
)
from src.schemas.job_fit_assessment import FitAssessment, FitScore


DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "jobs.db"

VALID_STATUSES = frozenset({
    "discovered", "preparing", "applied", "interviewing",
    "rejected", "offer", "accepted", "archived"
})


def get_db(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Return a database connection. Creates the DB file and tables if they don't exist."""
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            job_title TEXT,
            job_field TEXT,
            company TEXT,
            company_sector TEXT,
            location_raw TEXT,
            location_city TEXT,
            location_big_city_nearby TEXT,
            location_country TEXT,
            job_ad_language TEXT,
            work_mode TEXT,
            seniority TEXT,
            company_culture TEXT,
            salary_min INTEGER,
            salary_max INTEGER,
            summary TEXT,
            company_size_min INTEGER,
            company_size_max INTEGER,
            point_of_contact TEXT,
            source TEXT,
            date_posted TEXT,
            special_consideration TEXT,
            status TEXT NOT NULL DEFAULT 'discovered',
            discovered_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS job_skills (
            job_url TEXT,
            skill TEXT,
            skill_level TEXT,
            skill_urgency TEXT,
            PRIMARY KEY (job_url, skill)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS job_languages (
            job_url TEXT,
            language TEXT,
            level_literal TEXT,
            level_infered TEXT,
            PRIMARY KEY (job_url, language)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS assessments (
            job_url                     TEXT PRIMARY KEY REFERENCES jobs(url),
            overall_score               TEXT,
            overall_explanation         TEXT,
            role_fit_score              TEXT,
            role_fit_explanation        TEXT,
            skill_fit_score             TEXT,
            skill_fit_explanation       TEXT,
            location_fit_score          TEXT,
            location_fit_explanation    TEXT,
            work_mode_fit_score         TEXT,
            work_mode_fit_explanation   TEXT,
            seniority_fit_score         TEXT,
            seniority_fit_explanation   TEXT,
            salary_fit_score            TEXT,
            salary_fit_explanation      TEXT,
            main_mismatch_reason        TEXT,
            matched_skills_json         TEXT,
            missing_key_skills_json     TEXT,
            recommendation              TEXT,
            reasoning                   TEXT,
            assessed_at                 TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()
    return conn


def save_job(job: JobOpening, db_path: Optional[Path] = None) -> None:
    conn = get_db(db_path)
    try:
        location: Optional[Location] = job.location
        salary: Optional[RangedInt] = job.salary
        company_size: Optional[RangedInt] = job.company_size

        with conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    url, job_title, job_field, company, company_sector,
                    location_raw, location_city, location_big_city_nearby, location_country,
                    job_ad_language, work_mode, seniority, company_culture,
                    salary_min, salary_max, summary,
                    company_size_min, company_size_max,
                    point_of_contact, source, date_posted, special_consideration
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    job_title = excluded.job_title,
                    job_field = excluded.job_field,
                    company = excluded.company,
                    company_sector = excluded.company_sector,
                    location_raw = excluded.location_raw,
                    location_city = excluded.location_city,
                    location_big_city_nearby = excluded.location_big_city_nearby,
                    location_country = excluded.location_country,
                    job_ad_language = excluded.job_ad_language,
                    work_mode = excluded.work_mode,
                    seniority = excluded.seniority,
                    company_culture = excluded.company_culture,
                    salary_min = excluded.salary_min,
                    salary_max = excluded.salary_max,
                    summary = excluded.summary,
                    company_size_min = excluded.company_size_min,
                    company_size_max = excluded.company_size_max,
                    point_of_contact = excluded.point_of_contact,
                    source = excluded.source,
                    date_posted = excluded.date_posted,
                    special_consideration = excluded.special_consideration
                """,
                (
                    job.url,
                    job.job_title,
                    job.job_field,
                    job.company,
                    job.company_sector,
                    location.location if location else None,
                    location.city if location else None,
                    location.big_city_nearby if location else None,
                    location.country if location else None,
                    job.job_ad_language,
                    job.work_mode,
                    job.seniority,
                    job.company_culture,
                    salary.minimum if salary else None,
                    salary.maximum if salary else None,
                    job.summary,
                    company_size.minimum if company_size else None,
                    company_size.maximum if company_size else None,
                    job.point_of_contact,
                    job.source,
                    job.date_posted.isoformat() if job.date_posted else None,
                    job.special_consideration,
                ),
            )

            conn.execute("DELETE FROM job_skills WHERE job_url = ?", (job.url,))
            for sk in (job.skills_and_tools or []):
                conn.execute(
                    "INSERT INTO job_skills VALUES (?, ?, ?, ?)",
                    (job.url, sk.skill, sk.skill_level, sk.skill_urgency),
                )

            conn.execute("DELETE FROM job_languages WHERE job_url = ?", (job.url,))
            for ls in (job.language_skills_required or []):
                conn.execute(
                    "INSERT INTO job_languages VALUES (?, ?, ?, ?)",
                    (job.url, ls.language, ls.level_literal, ls.level_infered),
            )
    finally:
        conn.close()


def _fetch_skills(conn: sqlite3.Connection, url: str) -> list[Skill]:
    return [
        Skill(skill=r[0], skill_level=r[1], skill_urgency=r[2])
        for r in conn.execute(
            "SELECT skill, skill_level, skill_urgency FROM job_skills WHERE job_url = ?",
            (url,),
        )
    ]


def _fetch_languages(conn: sqlite3.Connection, url: str) -> list[LanguageSkill]:
    return [
        LanguageSkill(language=r[0], level_literal=r[1], level_infered=r[2])
        for r in conn.execute(
            "SELECT language, level_literal, level_infered FROM job_languages WHERE job_url = ?",
            (url,),
        )
    ]


def get_job_by_url(url: str, db_path: Optional[Path] = None) -> Optional[JobOpening]:
    conn = get_db(db_path)
    try:
        row = conn.execute(
            """
            SELECT
                url, job_title, job_field, company, company_sector,
                location_raw, location_city, location_big_city_nearby, location_country,
                job_ad_language, work_mode, seniority, company_culture,
                salary_min, salary_max, summary,
                company_size_min, company_size_max,
                point_of_contact, source, date_posted, special_consideration
            FROM jobs WHERE url = ?
            """,
            (url,),
        ).fetchone()
        if row is None:
            return None

        skills = _fetch_skills(conn, url)
        languages = _fetch_languages(conn, url)
        return _row_to_jobopening(row, skills, languages)
    finally:
        conn.close()


def list_jobs(db_path: Optional[Path] = None) -> Iterable[JobOpening]:
    conn = get_db(db_path)
    try:
        rows = conn.execute(
            """
            SELECT
                url, job_title, job_field, company, company_sector,
                location_raw, location_city, location_big_city_nearby, location_country,
                job_ad_language, work_mode, seniority, company_culture,
                salary_min, salary_max, summary,
                company_size_min, company_size_max,
                point_of_contact, source, date_posted, special_consideration
            FROM jobs ORDER BY id DESC
            """
        ).fetchall()

        skills_by_url = defaultdict(list)
        for r in conn.execute(
            "SELECT job_url, skill, skill_level, skill_urgency FROM job_skills"
        ):
            skills_by_url[r[0]].append(
                Skill(skill=r[1], skill_level=r[2], skill_urgency=r[3])
            )

        langs_by_url = defaultdict(list)
        for r in conn.execute(
            "SELECT job_url, language, level_literal, level_infered FROM job_languages"
        ):
            langs_by_url[r[0]].append(
                LanguageSkill(language=r[1], level_literal=r[2], level_infered=r[3])
            )

        for row in rows:
            url = row[0]
            yield _row_to_jobopening(
                row, skills_by_url.get(url, []), langs_by_url.get(url, [])
            )
    finally:
        conn.close()


def _row_to_jobopening(
    row: tuple,
    skills: list[Skill] | None = None,
    languages: list[LanguageSkill] | None = None,
) -> JobOpening:
    (
        url,
        job_title,
        job_field,
        company,
        company_sector,
        location_raw,
        location_city,
        location_big_city_nearby,
        location_country,
        job_ad_language,
        work_mode,
        seniority,
        company_culture,
        salary_min,
        salary_max,
        summary,
        company_size_min,
        company_size_max,
        point_of_contact,
        source,
        date_posted,
        special_consideration,
    ) = row

    location = (
        Location(
            location=location_raw,
            city=location_city,
            big_city_nearby=location_big_city_nearby,
            country=location_country,
        )
        if any([location_raw, location_city, location_big_city_nearby, location_country])
        else None
    )

    salary = (
        RangedInt(minimum=salary_min, maximum=salary_max)
        if salary_min is not None or salary_max is not None
        else None
    )

    company_size = (
        RangedInt(minimum=company_size_min, maximum=company_size_max)
        if company_size_min is not None or company_size_max is not None
        else None
    )

    return JobOpening(
        url=url,
        job_title=job_title,
        job_field=job_field,
        company=company,
        company_sector=company_sector,
        location=location,
        job_ad_language=job_ad_language,
        language_skills_required=languages or [],
        work_mode=work_mode,
        skills_and_tools=skills or [],
        seniority=seniority,
        company_culture=company_culture,
        salary=salary,
        summary=summary,
        company_size=company_size,
        point_of_contact=point_of_contact,
        source=source,
        date_posted=None if date_posted is None else date_posted,
        special_consideration=special_consideration,
    )


def update_job_status(
    url: str, status: str, db_path: Optional[Path] = None
) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}"
        )
    conn = get_db(db_path)
    try:
        conn.execute("UPDATE jobs SET status = ? WHERE url = ?", (status, url))
        conn.commit()
    finally:
        conn.close()


def get_job_status(url: str, db_path: Optional[Path] = None) -> str | None:
    conn = get_db(db_path)
    try:
        row = conn.execute(
            "SELECT status FROM jobs WHERE url = ?", (url,)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def save_assessment(
    assessment: FitAssessment, db_path: Optional[Path] = None
) -> None:
    conn = get_db(db_path)
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO assessments (
                    job_url, overall_score, overall_explanation,
                    role_fit_score, role_fit_explanation,
                    skill_fit_score, skill_fit_explanation,
                    location_fit_score, location_fit_explanation,
                    work_mode_fit_score, work_mode_fit_explanation,
                    seniority_fit_score, seniority_fit_explanation,
                    salary_fit_score, salary_fit_explanation,
                    main_mismatch_reason,
                    matched_skills_json, missing_key_skills_json,
                    recommendation, reasoning
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_url) DO UPDATE SET
                    overall_score = excluded.overall_score,
                    overall_explanation = excluded.overall_explanation,
                    role_fit_score = excluded.role_fit_score,
                    role_fit_explanation = excluded.role_fit_explanation,
                    skill_fit_score = excluded.skill_fit_score,
                    skill_fit_explanation = excluded.skill_fit_explanation,
                    location_fit_score = excluded.location_fit_score,
                    location_fit_explanation = excluded.location_fit_explanation,
                    work_mode_fit_score = excluded.work_mode_fit_score,
                    work_mode_fit_explanation = excluded.work_mode_fit_explanation,
                    seniority_fit_score = excluded.seniority_fit_score,
                    seniority_fit_explanation = excluded.seniority_fit_explanation,
                    salary_fit_score = excluded.salary_fit_score,
                    salary_fit_explanation = excluded.salary_fit_explanation,
                    main_mismatch_reason = excluded.main_mismatch_reason,
                    matched_skills_json = excluded.matched_skills_json,
                    missing_key_skills_json = excluded.missing_key_skills_json,
                    recommendation = excluded.recommendation,
                    reasoning = excluded.reasoning,
                    assessed_at = datetime('now')
                """,
                (
                    assessment.url,
                    assessment.overall.score,
                    assessment.overall.explanation,
                    assessment.role_fit.score,
                    assessment.role_fit.explanation,
                    assessment.skill_fit.score,
                    assessment.skill_fit.explanation,
                    assessment.location_fit.score,
                    assessment.location_fit.explanation,
                    assessment.work_mode_fit.score,
                    assessment.work_mode_fit.explanation,
                    assessment.seniority_fit.score,
                    assessment.seniority_fit.explanation,
                    assessment.salary_fit.score if assessment.salary_fit else None,
                    assessment.salary_fit.explanation if assessment.salary_fit else None,
                    assessment.main_mismatch_reason,
                    json.dumps(assessment.matched_skills, ensure_ascii=False),
                    json.dumps(assessment.missing_key_skills, ensure_ascii=False),
                    assessment.recommendation,
                    assessment.reasoning,
                ),
            )
    finally:
        conn.close()


def get_assessment_by_url(
    url: str, db_path: Optional[Path] = None
) -> Optional[FitAssessment]:
    conn = get_db(db_path)
    try:
        row = conn.execute(
            """
            SELECT
                job_url,
                overall_score, overall_explanation,
                role_fit_score, role_fit_explanation,
                skill_fit_score, skill_fit_explanation,
                location_fit_score, location_fit_explanation,
                work_mode_fit_score, work_mode_fit_explanation,
                seniority_fit_score, seniority_fit_explanation,
                salary_fit_score, salary_fit_explanation,
                main_mismatch_reason,
                matched_skills_json, missing_key_skills_json,
                recommendation, reasoning,
                assessed_at
            FROM assessments WHERE job_url = ?
            """,
            (url,),
        ).fetchone()
        if row is None:
            return None
        return _row_to_assessment(row)
    finally:
        conn.close()


def _row_to_assessment(row: tuple) -> FitAssessment:
    (
        job_url,
        overall_score, overall_explanation,
        role_fit_score, role_fit_explanation,
        skill_fit_score, skill_fit_explanation,
        location_fit_score, location_fit_explanation,
        work_mode_fit_score, work_mode_fit_explanation,
        seniority_fit_score, seniority_fit_explanation,
        salary_fit_score, salary_fit_explanation,
        main_mismatch_reason,
        matched_skills_json, missing_key_skills_json,
        recommendation, reasoning,
        assessed_at,
    ) = row

    salary_fit = (
        FitScore(score=salary_fit_score, explanation=salary_fit_explanation)
        if salary_fit_score
        else None
    )

    matched_skills = json.loads(matched_skills_json) if matched_skills_json else []
    missing_key_skills = json.loads(missing_key_skills_json) if missing_key_skills_json else []

    return FitAssessment(
        url=job_url,
        overall=FitScore(score=overall_score, explanation=overall_explanation),
        role_fit=FitScore(score=role_fit_score, explanation=role_fit_explanation),
        skill_fit=FitScore(score=skill_fit_score, explanation=skill_fit_explanation),
        location_fit=FitScore(score=location_fit_score, explanation=location_fit_explanation),
        work_mode_fit=FitScore(score=work_mode_fit_score, explanation=work_mode_fit_explanation),
        seniority_fit=FitScore(score=seniority_fit_score, explanation=seniority_fit_explanation),
        salary_fit=salary_fit,
        main_mismatch_reason=main_mismatch_reason,
        matched_skills=matched_skills,
        missing_key_skills=missing_key_skills,
        recommendation=recommendation,
        reasoning=reasoning,
    )


def _fetch_status_map(conn: sqlite3.Connection) -> dict[str, str]:
    return {
        r[0]: r[1]
        for r in conn.execute("SELECT url, status FROM jobs")
    }


def main():
    parser = argparse.ArgumentParser(description="Inspect and manage the job database.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List all jobs")
    sub.add_parser("stats", help="Show summary statistics")

    get_parser = sub.add_parser("get", help="Get a job by URL")
    get_parser.add_argument("--url", "-u", required=True, help="Job posting URL")

    status_parser = sub.add_parser("status", help="Set job status")
    status_parser.add_argument("--url", "-u", required=True, help="Job posting URL")
    status_parser.add_argument(
        "--set", "-s", required=True,
        choices=sorted(VALID_STATUSES),
        help="New status"
    )

    assessment_parser = sub.add_parser("assessment", help="Get job fit assessment")
    assessment_parser.add_argument("--url", "-u", required=True, help="Job posting URL")

    args = parser.parse_args()

    if args.command == "list":
        conn = get_db()
        try:
            statuses = _fetch_status_map(conn)
        finally:
            conn.close()

        for job in list_jobs():
            s = statuses.get(job.url, "discovered")
            print(f"[{s}] {job.job_title} @ {job.company}")
            print(f"  {job.url}")
            print(f"  {job.job_field} | {job.work_mode} | {job.seniority}")
            if job.skills_and_tools:
                print(f"  Skills: {len(job.skills_and_tools)}")
            if job.language_skills_required:
                print(f"  Languages: {len(job.language_skills_required)}")
            print()

    elif args.command == "stats":
        jobs = list(list_jobs())
        conn = get_db()
        try:
            statuses = _fetch_status_map(conn)
        finally:
            conn.close()

        print(f"Total jobs: {len(jobs)}")
        fields = {}
        sources = {}
        by_status = {}
        for job in jobs:
            fields[job.job_field] = fields.get(job.job_field, 0) + 1
            sources[job.source] = sources.get(job.source, 0) + 1
            s = statuses.get(job.url, "discovered")
            by_status[s] = by_status.get(s, 0) + 1
        if fields:
            print(f"By field: {fields}")
        if sources:
            print(f"By source: {sources}")
        if by_status:
            print(f"By status: {by_status}")

    elif args.command == "get":
        job = get_job_by_url(args.url)
        if job:
            status = get_job_status(args.url)
            print(f"Status: {status or 'discovered'}")
            pprint(job)
        else:
            print("Job not found.")

    elif args.command == "status":
        status_before = get_job_status(args.url)
        if status_before is None:
            print("Job not found.")
            return
        update_job_status(args.url, args.set)
        print(f"Status updated: {status_before} → {args.set}")

    elif args.command == "assessment":
        assessment = get_assessment_by_url(args.url)
        if assessment:
            pprint(assessment)
        else:
            print("No assessment found for this job.")


if __name__ == "__main__":
    main()
