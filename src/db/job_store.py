import json
import sqlite3
from pathlib import Path
from typing import Optional, Iterable

from src.schemas.structured_job import (
    JobOpening,
    Location,
    LanguageSkill,
    Skill,
    RangedInt,
)


DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "jobs.db"


def _ensure_db_dir_exists(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Return a SQLite connection, creating the DB file and table if needed."""
    path = db_path or DB_PATH
    _ensure_db_dir_exists(path)
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
            language_skills_json TEXT,
            skills_and_tools_json TEXT
        )
        """
    )
    conn.commit()
    return conn


def save_job(job: JobOpening, db_path: Optional[Path] = None) -> None:
    """Insert or update a job in the DB, using URL as a unique key.

    Most simple JobOpening fields are mapped to dedicated columns.
    List / nested fields that are harder to flatten (language skills,
    skills_and_tools) are stored as JSON text.
    """
    conn = get_connection(db_path)
    try:
        location: Optional[Location] = job.location
        salary: Optional[RangedInt] = job.salary
        company_size: Optional[RangedInt] = job.company_size

        language_skills_json = (
            json.dumps([ls.model_dump() for ls in (job.language_skills_required or [])])
            if job.language_skills_required is not None
            else None
        )
        skills_and_tools_json = (
            json.dumps([sk.model_dump() for sk in (job.skills_and_tools or [])])
            if job.skills_and_tools is not None
            else None
        )

        with conn:
            conn.execute(
                """
                INSERT INTO jobs (
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
                    language_skills_json,
                    skills_and_tools_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    special_consideration = excluded.special_consideration,
                    language_skills_json = excluded.language_skills_json,
                    skills_and_tools_json = excluded.skills_and_tools_json
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
                    language_skills_json,
                    skills_and_tools_json,
                ),
            )
    finally:
        conn.close()


def get_job_by_url(url: str, db_path: Optional[Path] = None) -> Optional[JobOpening]:
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            SELECT
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
                language_skills_json,
                skills_and_tools_json
            FROM jobs
            WHERE url = ?
            """,
            (url,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return _row_to_jobopening(row)
    finally:
        conn.close()


def list_jobs(db_path: Optional[Path] = None) -> Iterable[JobOpening]:
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            SELECT
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
                language_skills_json,
                skills_and_tools_json
            FROM jobs
            ORDER BY id DESC
            """
        )
        for row in cursor:
            yield _row_to_jobopening(row)
    finally:
        conn.close()


def _row_to_jobopening(row: tuple) -> JobOpening:
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
        language_skills_json,
        skills_and_tools_json,
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

    language_skills = []
    if language_skills_json:
        try:
            for item in json.loads(language_skills_json):
                language_skills.append(LanguageSkill.model_validate(item))
        except Exception:
            language_skills = []

    skills_and_tools = []
    if skills_and_tools_json:
        try:
            for item in json.loads(skills_and_tools_json):
                skills_and_tools.append(Skill.model_validate(item))
        except Exception:
            skills_and_tools = []

    return JobOpening(
        url=url,
        job_title=job_title,
        job_field=job_field,
        company=company,
        company_sector=company_sector,
        location=location,
        job_ad_language=job_ad_language,
        language_skills_required=language_skills or None,
        work_mode=work_mode,
        skills_and_tools=skills_and_tools,
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
