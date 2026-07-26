import json
import argparse
import sys
from pathlib import Path
from typing import TypedDict, Optional
from langchain.chat_models import init_chat_model
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, START, END

base_path = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(base_path))

from src.agents.llm_config import LLM_MODEL, LLM_PROVIDER
from src.db.job_db_io import get_assessment_by_url, save_assessment
from src.schemas.structured_job import JobOpening
from src.schemas.user_profile import UserProfile
from src.schemas.job_fit_assessment import (
    FitAssessment, FitScore,
    RoleBreakdown, TranslationMapping, GapItem, HiringRiskItem,
    ApplicationStory, MissingInformation,
    TranslationMappingList, GapItemList, HiringRiskItemList,
)

llm = init_chat_model(LLM_MODEL, model_provider=LLM_PROVIDER)
structured_llm = llm.with_structured_output(FitAssessment)
role_llm = llm.with_structured_output(RoleBreakdown)
translation_llm = llm.with_structured_output(TranslationMappingList)
gap_llm = llm.with_structured_output(GapItemList)
risk_llm = llm.with_structured_output(HiringRiskItemList)
story_llm = llm.with_structured_output(ApplicationStory)
missing_llm = llm.with_structured_output(MissingInformation)

# ── LangGraph State ──────────────────────────────────────────────────

class AssessmentState(TypedDict):
    job: JobOpening
    profile: UserProfile
    url: str
    role_breakdown: Optional[RoleBreakdown]
    translation: Optional[list[TranslationMapping]]
    gaps: Optional[list[GapItem]]
    risks: Optional[list[HiringRiskItem]]
    trajectory: Optional[str]
    story: Optional[ApplicationStory]
    assessment: Optional[FitAssessment]


# ── Prompts ──────────────────────────────────────────────────────────

ROLE_PROMPT = PromptTemplate.from_template("""
You are a job analyst. Look past the job title and figure out what this role
actually involves day-to-day. Break it into percentages.

The percentages should add up to 100.

Job Posting:
{job_json}

Return a RoleBreakdown with:
- coding_pct: hands-on coding
- stakeholder_pct: stakeholder management / communication
- data_engineering_pct: pipelines, infrastructure, data architecture
- consulting_pct: internal or external consulting / advisory
- research_pct: research, experimentation, exploration
- reasoning: why this breakdown
""")

TRANSLATION_PROMPT = PromptTemplate.from_template("""
You are a career translator. Map the user's CV and profile elements to what
this specific role needs. Don't take the job ad literally — translate.

Role Breakdown (from previous step):
{role_breakdown}

Job Posting:
{job_json}

User Profile:
{profile_json}

For each element from the user's CV or profile, explain:
- cv_element: the specific thing from their background
- maps_to: what it demonstrates that is relevant to this role
- confidence: high / medium / low

Return a list of TranslationMapping items.
""")

GAP_PROMPT = PromptTemplate.from_template("""
You are a gap analyst. Compare the user's translated experience against
the job requirements and identify what's missing.

Classify each gap as one of:
- hard: genuinely matters, difficult to compensate for
- soft: companies list it but rarely enforce it
- negotiable: could be learned on the job or substituted

Use the translation mappings to avoid repeating what the user already has.

Experience Translation:
{translation}

Job Posting:
{job_json}

User Profile:
{profile_json}

Return a list of GapItem with area, gap_type, and detail.
""")

RISK_PROMPT = PromptTemplate.from_template("""
You are a hiring advisor. Assess how risky each aspect of this application
is — put yourself in the hiring manager's shoes.

Areas to assess (use exact strings):
- technical_interview
- domain_knowledge
- german_communication
- seniority_expectations
- overall_hiring_risk

For each, assign a level (low / medium / high) and explain why.

Gaps Identified:
{gaps}

Job Posting:
{job_json}

User Profile:
{profile_json}

Return a list of HiringRiskItem with area, level, note.
""")

CAREER_PROMPT = PromptTemplate.from_template("""
You are a career strategist. Analyze where this role leads in 2-3 years.
Consider:
- Does this move the user toward architecture or away from it?
- Does this increase stakeholder exposure?
- Does this build leadership capital?
- Does this make the user more employable long-term?
- Is this a stepping stone or a destination role?

Gaps Identified:
{gaps}

Hiring Risks:
{risks}

Job Posting:
{job_json}

User Profile:
{profile_json}

Return a concise paragraph (2-4 sentences) addressing the above.
""")

STORY_PROMPT = PromptTemplate.from_template("""
You are a career coach helping a candidate prepare their application story.
Based on all the analysis so far, craft the narrative.

Role Breakdown:
{role_breakdown}

Experience Translation:
{translation}

Gaps Identified:
{gaps}

Hiring Risks:
{risks}

Career Trajectory:
{trajectory}

Job Posting:
{job_json}

User Profile:
{profile_json}

Return an ApplicationStory with:
- why_you: compelling case for why this user fits
- why_this_role: why this role makes sense now
- strongest_arguments: top 2-3 arguments in favor
- weakest_areas: top 2-3 concerns
- interview_risk: most likely hiring manager objection and how to address it
- narrative: one-sentence pitch
""")

MISSING_PROMPT = PromptTemplate.from_template("""
You are an analyst reviewing a fit assessment. What information is still
missing that would significantly change or sharpen the recommendation?

Think about things like:
- Career preferences (management track, stability vs growth, etc.)
- Salary expectations (if not in profile)
- Work mode flexibility (if not stated)
- Relocation willingness
- Any assumptions you had to make

Application Story:
{story}

Job Posting:
{job_json}

User Profile:
{profile_json}

Return a MissingInformation with a list of specific questions.
""")

FINAL_PROMPT = PromptTemplate.from_template("""
You are a job fit assessor. Based on all the analysis below, produce
dimension-level fit scores and an overall recommendation.

The dimension scores use:
exceptional, high, medium_high, medium, medium_low, low, poor

Recommendation is one of: strong_apply, consider, weak, skip

Role Breakdown:
{role_breakdown}

Experience Translation:
{translation}

Gaps Identified:
{gaps}

Hiring Risks:
{risks}

Career Trajectory:
{trajectory}

Application Story:
{story}

Job Posting:
{job_json}

User Profile:
{profile_json}
""")


# ── Step Functions ───────────────────────────────────────────────────

def _job_json(job: JobOpening) -> str:
    return json.dumps(job.model_dump(mode="json"), indent=2, ensure_ascii=False)

def _profile_json(profile: UserProfile) -> str:
    return json.dumps(profile.model_dump(mode="json"), indent=2, ensure_ascii=False)


def classify_role(job: JobOpening) -> RoleBreakdown:
    return role_llm.invoke(ROLE_PROMPT.format(job_json=_job_json(job)))


def translate_experience(job: JobOpening, profile: UserProfile, role: RoleBreakdown) -> list[TranslationMapping]:
    return translation_llm.invoke(
        TRANSLATION_PROMPT.format(
            role_breakdown=role.model_dump_json(indent=2),
            job_json=_job_json(job),
            profile_json=_profile_json(profile),
        )
    ).items


def analyze_gaps(job: JobOpening, profile: UserProfile, translation: list[TranslationMapping]) -> list[GapItem]:
    return gap_llm.invoke(
        GAP_PROMPT.format(
            translation=json.dumps([t.model_dump() for t in translation], indent=2, ensure_ascii=False),
            job_json=_job_json(job),
            profile_json=_profile_json(profile),
        )
    ).items


def assess_hiring_risk(job: JobOpening, profile: UserProfile, gaps: list[GapItem]) -> list[HiringRiskItem]:
    return risk_llm.invoke(
        RISK_PROMPT.format(
            gaps=json.dumps([g.model_dump() for g in gaps], indent=2, ensure_ascii=False),
            job_json=_job_json(job),
            profile_json=_profile_json(profile),
        )
    ).items


def analyze_career_trajectory(job: JobOpening, profile: UserProfile, gaps: list[GapItem], risks: list[HiringRiskItem]) -> str:
    return llm.invoke(
        CAREER_PROMPT.format(
            gaps=json.dumps([g.model_dump() for g in gaps], indent=2, ensure_ascii=False),
            risks=json.dumps([r.model_dump() for r in risks], indent=2, ensure_ascii=False),
            job_json=_job_json(job),
            profile_json=_profile_json(profile),
        )
    ).content


def build_story(
    job: JobOpening, profile: UserProfile,
    role: RoleBreakdown, translation: list[TranslationMapping],
    gaps: list[GapItem], risks: list[HiringRiskItem],
    trajectory: str,
) -> ApplicationStory:
    return story_llm.invoke(
        STORY_PROMPT.format(
            role_breakdown=role.model_dump_json(indent=2),
            translation=json.dumps([t.model_dump() for t in translation], indent=2, ensure_ascii=False),
            gaps=json.dumps([g.model_dump() for g in gaps], indent=2, ensure_ascii=False),
            risks=json.dumps([r.model_dump() for r in risks], indent=2, ensure_ascii=False),
            trajectory=trajectory,
            job_json=_job_json(job),
            profile_json=_profile_json(profile),
        )
    )


def generate_missing_info(job: JobOpening, profile: UserProfile, story: ApplicationStory) -> MissingInformation:
    return missing_llm.invoke(
        MISSING_PROMPT.format(
            story=story.model_dump_json(indent=2),
            job_json=_job_json(job),
            profile_json=_profile_json(profile),
        )
    )


def produce_assessment(
    job: JobOpening, profile: UserProfile,
    role: RoleBreakdown, translation: list[TranslationMapping],
    gaps: list[GapItem], risks: list[HiringRiskItem],
    trajectory: str, story: ApplicationStory,
) -> FitAssessment:
    assessment = structured_llm.invoke(
        FINAL_PROMPT.format(
            role_breakdown=role.model_dump_json(indent=2),
            translation=json.dumps([t.model_dump() for t in translation], indent=2, ensure_ascii=False),
            gaps=json.dumps([g.model_dump() for g in gaps], indent=2, ensure_ascii=False),
            risks=json.dumps([r.model_dump() for r in risks], indent=2, ensure_ascii=False),
            trajectory=trajectory,
            story=story.model_dump_json(indent=2),
            job_json=_job_json(job),
            profile_json=_profile_json(profile),
        )
    )
    assessment.role_breakdown = role
    assessment.experience_translation = translation
    assessment.gaps = gaps
    assessment.hiring_risks = risks
    assessment.career_trajectory = trajectory
    assessment.story = story
    assessment.missing_info = generate_missing_info(job, profile, story)
    return assessment


# ── Verbose logging helper ───────────────────────────────────────────

_verbose: bool = False

def _log(label: str):
    if _verbose:
        print(f"  ╰─ {label}...")


# ── LangGraph Nodes ──────────────────────────────────────────────────

def classify_role_node(state: AssessmentState) -> dict:
    _log("Classifying role")
    return {"role_breakdown": classify_role(state["job"])}

def translate_experience_node(state: AssessmentState) -> dict:
    _log("Translating experience")
    return {"translation": translate_experience(state["job"], state["profile"], state["role_breakdown"])}

def analyze_gaps_node(state: AssessmentState) -> dict:
    _log("Analyzing gaps")
    return {"gaps": analyze_gaps(state["job"], state["profile"], state["translation"])}

def assess_hiring_risk_node(state: AssessmentState) -> dict:
    _log("Assessing hiring risk")
    return {"risks": assess_hiring_risk(state["job"], state["profile"], state["gaps"])}

def analyze_trajectory_node(state: AssessmentState) -> dict:
    _log("Analyzing career trajectory")
    return {"trajectory": analyze_career_trajectory(state["job"], state["profile"], state["gaps"], state["risks"])}

def build_story_node(state: AssessmentState) -> dict:
    _log("Building application story")
    return {"story": build_story(state["job"], state["profile"], state["role_breakdown"], state["translation"], state["gaps"], state["risks"], state["trajectory"])}

def produce_assessment_node(state: AssessmentState) -> dict:
    _log("Producing final assessment")
    return {"assessment": produce_assessment(state["job"], state["profile"], state["role_breakdown"], state["translation"], state["gaps"], state["risks"], state["trajectory"], state["story"])}


# ── Build Graph ──────────────────────────────────────────────────────

builder = StateGraph(AssessmentState)
builder.add_node("classify_role", classify_role_node)
builder.add_node("translate_experience", translate_experience_node)
builder.add_node("analyze_gaps", analyze_gaps_node)
builder.add_node("assess_hiring_risk", assess_hiring_risk_node)
builder.add_node("analyze_trajectory", analyze_trajectory_node)
builder.add_node("build_story", build_story_node)
builder.add_node("produce_assessment", produce_assessment_node)

builder.add_edge(START, "classify_role")
builder.add_edge("classify_role", "translate_experience")
builder.add_edge("translate_experience", "analyze_gaps")
builder.add_edge("analyze_gaps", "assess_hiring_risk")
builder.add_edge("assess_hiring_risk", "analyze_trajectory")
builder.add_edge("analyze_trajectory", "build_story")
builder.add_edge("build_story", "produce_assessment")
builder.add_edge("produce_assessment", END)

graph = builder.compile()


# ── Public API ────────────────────────────────────────────────────────

def assess_fit(
    job: JobOpening,
    profile: UserProfile,
    verbose: bool = False,
) -> FitAssessment:
    global _verbose
    _verbose = verbose

    result = graph.invoke({
        "job": job,
        "profile": profile,
        "url": job.url,
        "role_breakdown": None,
        "translation": None,
        "gaps": None,
        "risks": None,
        "trajectory": None,
        "story": None,
        "assessment": None,
    })

    if verbose:
        print("  ╰─ Done.")

    return result["assessment"]


# ── CLI ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Assess how well a job posting fits your profile (multi-step pipeline)."
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
    parser.add_argument(
        "--verbose", "-v", action="store_true", default=False,
        help="Print progress of each pipeline step.",
    )
    args = parser.parse_args()

    with open(Path(args.job), "r", encoding="utf-8") as f:
        job = JobOpening.model_validate(json.load(f))

    with open(Path(args.profile), "r", encoding="utf-8") as f:
        profile = UserProfile.model_validate(json.load(f))

    assessment = assess_fit(job, profile, verbose=args.verbose)

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
