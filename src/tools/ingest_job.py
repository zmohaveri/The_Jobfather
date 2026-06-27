import argparse
import json
import sys
from pathlib import Path
from typing import Optional

base_path = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(base_path))

from src.agents.job_extractor import get_job_posting_from_url, get_structured_job
from src.agents.job_fit_assessor import assess_fit
from src.db.job_db_io import (
    get_assessment_by_url,
    get_job_by_url,
    save_assessment,
    save_job,
)
from src.schemas.user_profile import UserProfile


def ingest_job_from_url(
    url: str,
    profile_path: str | Path = "src/profile/profile_data.json",
    force_job: bool = False,
    force_assessment: bool = False,
) -> dict:
    existing_job = get_job_by_url(url)
    if existing_job is not None and not force_job:
        job = existing_job
    else:
        raw = _fetch(url)
        if raw["status"] == "error":
            return raw

        extracted = _extract(raw["data"])
        if extracted["status"] == "error":
            return extracted
        job = extracted["data"]

        persisted = _persist_job(job)
        if persisted["status"] == "error":
            return persisted

    existing_assessment = get_assessment_by_url(url)
    if existing_assessment is not None and not force_assessment:
        assessment = existing_assessment
    else:
        profile = _load_profile(profile_path)
        if profile["status"] == "error":
            return profile

        assessed = _assess(job, profile["data"])
        if assessed["status"] == "error":
            return assessed
        assessment = assessed["data"]

        persisted = _persist_assessment(assessment)
        if persisted["status"] == "error":
            return persisted

    return {
        "status": "success",
        "url": url,
        "job": job.model_dump(mode="json"),
        "assessment": assessment.model_dump(mode="json", exclude_none=True),
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
        "urls", type=str, nargs="*",
        help="Job posting URL(s) to ingest.",
    )
    parser.add_argument(
        "--urls-file", "-f", type=str,
        help="Path to a text file with one URL per line (blank lines and # comments ignored).",
    )
    parser.add_argument(
        "--profile", "-p", type=str, default="src/profile/profile_data.json",
        help="Path to the user profile JSON. Defaults to src/profile/profile_data.json.",
    )
    parser.add_argument(
        "--force-job", action="store_true", default=False,
        help="Re-fetch and re-extract the job posting even if it already exists in DB.",
    )
    parser.add_argument(
        "--force-assessment", action="store_true", default=False,
        help="Re-assess fit even if an assessment already exists in DB.",
    )
    parser.add_argument(
        "--force", action="store_true", default=False,
        help="Equivalent to --force-job --force-assessment.",
    )
    args = parser.parse_args()

    all_urls = list(args.urls)
    if args.urls_file:
        path = Path(args.urls_file)
        if not path.is_absolute():
            path = base_path / path
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    all_urls.append(stripped)

    if not all_urls:
        parser.print_usage()
        print("error: provide at least one URL or use --urls-file")
        sys.exit(1)

    force_job = args.force or args.force_job
    force_assessment = args.force or args.force_assessment

    for url in all_urls:
        result = ingest_job_from_url(
            url,
            profile_path=args.profile,
            force_job=force_job,
            force_assessment=force_assessment,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print()


if __name__ == "__main__":
    main()
