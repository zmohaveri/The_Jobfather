import argparse
import json
import sys
from pathlib import Path
from typing import Optional

base_path = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(base_path))

from src.agents.job_extractor import get_job_posting_from_url, get_structured_job
from src.agents.job_fit_assessor import assess_fit
from src.db.job_db_io import save_assessment, save_job
from src.schemas.user_profile import UserProfile


def ingest_job_from_url(
    url: str,
    profile_path: str | Path = "src/profile/profile_data.json",
) -> dict:
    raw = _fetch(url)
    if raw["status"] == "error":
        return raw

    job = _extract(raw["data"])
    if job["status"] == "error":
        return job

    saved = _persist_job(job["data"])
    if saved["status"] == "error":
        return saved

    profile = _load_profile(profile_path)
    if profile["status"] == "error":
        return profile

    assessment = _assess(job["data"], profile["data"])
    if assessment["status"] == "error":
        return assessment

    persisted = _persist_assessment(assessment["data"])
    if persisted["status"] == "error":
        return persisted

    return {
        "status": "success",
        "url": url,
        "job": job["data"].model_dump(mode="json"),
        "assessment": assessment["data"].model_dump(mode="json", exclude_none=True),
    }


def _fetch(url: str) -> dict:
    try:
        raw = get_job_posting_from_url(url)
        return {"status": "ok", "data": raw}
    except ValueError as e:
        return {"status": "error", "step": "fetch", "error": str(e)}


def _extract(raw: str) -> dict:
    try:
        job = get_structured_job(raw)
        return {"status": "ok", "data": job}
    except Exception as e:
        return {"status": "error", "step": "extract", "error": str(e)}


def _persist_job(job) -> dict:
    try:
        save_job(job)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "step": "save_job", "error": str(e)}


def _load_profile(profile_path: str | Path) -> dict:
    path = Path(profile_path)
    if not path.is_absolute():
        path = base_path / path
    try:
        with open(path, "r", encoding="utf-8") as f:
            profile = UserProfile.model_validate(json.load(f))
        return {"status": "ok", "data": profile}
    except Exception as e:
        return {"status": "error", "step": "load_profile", "error": str(e)}


def _assess(job, profile) -> dict:
    try:
        assessment = assess_fit(job, profile)
        return {"status": "ok", "data": assessment}
    except Exception as e:
        return {"status": "error", "step": "assess", "error": str(e)}


def _persist_assessment(assessment) -> dict:
    try:
        save_assessment(assessment)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "step": "save_assessment", "error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Fetch a job posting from a URL, extract it, assess fit, and persist everything to the database."
    )
    parser.add_argument(
        "urls", type=str, nargs="+",
        help="Job posting URL(s) to ingest.",
    )
    parser.add_argument(
        "--profile", "-p", type=str, default="src/profile/profile_data.json",
        help="Path to the user profile JSON. Defaults to src/profile/profile_data.json.",
    )
    args = parser.parse_args()

    for url in args.urls:
        result = ingest_job_from_url(url, profile_path=args.profile)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print()


if __name__ == "__main__":
    main()
