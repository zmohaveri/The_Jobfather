import json
import argparse
import sys
from pathlib import Path
from langchain.chat_models import init_chat_model
from langchain_core.prompts import PromptTemplate

base_path = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(base_path))

from src.agents.llm_config import LLM_MODEL, LLM_PROVIDER
from src.db.job_db_io import get_assessment_by_url, save_assessment
from src.schemas.structured_job import JobOpening
from src.schemas.user_profile import UserProfile
from src.schemas.job_fit_assessment import FitAssessment

llm = init_chat_model(LLM_MODEL, model_provider=LLM_PROVIDER)
structured_llm = llm.with_structured_output(FitAssessment)

RUBRIC = """
Score each dimension qualitatively using one of:
  exceptional, high, medium_high, medium, medium_low, low, poor

How to decide each score:

--- ROLE FIT (job_title + job_field vs desired_roles + avoided_roles + CV) ---
- exceptional: job_title is in desired_roles, job_field matches, CV confirms experience.
- high: Adjacent role (e.g. "AI Engineer" when user wants "ML Engineer"),
  or CV shows strong transferable experience.
- medium: Somewhat related field but title is a stretch.
- low: Mostly unrelated to the user's background.
- poor: job_title is in avoided_roles, or field is completely unrelated.

--- SKILL FIT (skills_and_tools vs user skills + CV) ---
Consider skill_urgency ("required" vs "nice to have") and skill_level.
- exceptional: All required skills match with good depth. Some nice-to-haves also match.
- high: Most required skills match. Minor gaps in less critical ones.
- medium_high: Core required skills match, several secondary ones missing.
- medium: ~half the required skills match.
- medium_low: Few required skills match. Significant upskilling needed.
- low: Most required skills missing.
- poor: Almost no skill overlap.

--- LOCATION FIT (location.* vs preferred_locations + avoided_locations) ---
Consider city, big_city_nearby (for commuting), country.
- exceptional: City is in preferred_locations.
- high: Not preferred, but big_city_nearby is a preferred location and commutable.
- medium: Not preferred, not avoided. Neutral.
- low: Not preferred, requires long commute or relocation.
- poor: City/country is in avoided_locations.

--- WORK MODE FIT (work_mode vs preferred_work_mode) ---
- exceptional: Exact match.
- high: Partial alignment (e.g. "Remote" vs "Hybrid").
- medium: Related but opposite leaning ("Hybrid" vs "On-site").
- low: Opposite preference.
- poor: Is a stated dealbreaker.

--- SENIORITY FIT (seniority vs user seniority + CV) ---
- exceptional: Exact match.
- high: One level off in an easier direction.
- medium: One level off in a harder direction (stretch but possible).
- medium_low: Two levels off.
- low/poor: Massive gap.

--- SALARY FIT (salary vs preferred_salary_min) ---
If salary is absent, salary_fit = null.
- exceptional: Comfortably above minimum.
- high: Starts at or slightly above minimum.
- medium: Straddles the minimum (range crosses it).
- low: Below minimum.
- poor: Far below minimum.

--- OVERALL ---
Role and skill fit are most important. Location and work mode are
important but negotiable. Salary and seniority are supporting signals.
A "poor" involving a dealbreaker or avoided role/location should
drop overall to at most "low" with recommendation "skip".
"""

PROMPT_TEMPLATE_STR = """
You are a job fit assessor. Evaluate how well this job posting
matches the user's profile. Be critical and realistic.

{rubric}

--- JOB POSTING (JobOpening) ---
{job_json}

--- USER PROFILE (UserProfile) ---
{profile_json}

Return a structured FitAssessment.
"""

prompt_template = PromptTemplate.from_template(PROMPT_TEMPLATE_STR)


def assess_fit(job: JobOpening, profile: UserProfile) -> FitAssessment:
    job_dict = job.model_dump(mode="json")
    profile_dict = profile.model_dump(mode="json")

    prompt = prompt_template.format(
        rubric=RUBRIC,
        job_json=json.dumps(job_dict, indent=2, ensure_ascii=False),
        profile_json=json.dumps(profile_dict, indent=2, ensure_ascii=False),
    )
    return structured_llm.invoke(prompt)


def main():
    parser = argparse.ArgumentParser(
        description="Assess how well a job posting fits your profile."
    )
    parser.add_argument(
        "--job", "-j", type=str, required=True,
        help="Path to a JSON file containing a JobOpening object.",
    )
    parser.add_argument(
        "--profile", "-p", type=str, required=True,
        help="Path to a JSON file containing a UserProfile object.",
    )
    parser.add_argument(
        "--save", "-s", action="store_true", default=False,
        help="Save the assessment to the database.",
    )
    parser.add_argument(
        "--no-overwrite", action="store_true", default=False,
        help="Skip saving if an assessment already exists for this job URL.",
    )
    args = parser.parse_args()

    with open(Path(args.job), "r", encoding="utf-8") as f:
        job = JobOpening.model_validate(json.load(f))

    with open(Path(args.profile), "r", encoding="utf-8") as f:
        profile = UserProfile.model_validate(json.load(f))

    assessment = assess_fit(job, profile)

    if args.save:
        if args.no_overwrite and get_assessment_by_url(assessment.url):
            print("Assessment already exists. Skipping save (--no-overwrite).\n")
        else:
            save_assessment(assessment)
            print("Assessment saved to database.\n")

    print(assessment.model_dump_json(indent=2, exclude_none=True))
    return assessment


if __name__ == "__main__":
    job_fit_assessment = main()
