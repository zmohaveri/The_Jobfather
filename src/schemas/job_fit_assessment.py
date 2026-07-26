from pydantic import BaseModel, Field
from typing import Optional


class FitScore(BaseModel):
    score: str = Field(
        description=(
            "Qualitative fit score. One of: "
            "exceptional, high, medium_high, medium, medium_low, low, poor"
        )
    )
    explanation: str = Field(
        description="Concise reason this score was assigned for this dimension"
    )


class RoleBreakdown(BaseModel):
    coding_pct: int = Field(description="What percentage of the role is hands-on coding")
    stakeholder_pct: int = Field(description="What percentage is stakeholder management / communication")
    data_engineering_pct: int = Field(description="Percentage focused on data engineering, pipelines, infrastructure")
    consulting_pct: int = Field(description="Percentage that is internal or external consulting / advisory")
    research_pct: int = Field(description="Percentage that is research, experimentation, or exploration")
    reasoning: str = Field(description="Why this breakdown was chosen based on the job ad")


class TranslationMapping(BaseModel):
    cv_element: str = Field(description="Specific element from the CV or profile")
    maps_to: str = Field(description="What this element demonstrates that is relevant to the role")
    confidence: str = Field(description="How directly this maps: high / medium / low")


class GapItem(BaseModel):
    area: str = Field(description="The skill, knowledge area, or qualification that is missing")
    gap_type: str = Field(description="hard / soft / negotiable")
    detail: str = Field(description="Why this gap matters and how critical it is")


class HiringRiskItem(BaseModel):
    area: str = Field(description="Risk area — e.g. technical_interview, domain_knowledge, german_communication, seniority_expectations")
    level: str = Field(description="low / medium / high")
    note: str = Field(description="Why this risk level was assigned")


class ApplicationStory(BaseModel):
    why_you: str = Field(description="Compelling case for why the user specifically fits this role")
    why_this_role: str = Field(description="Why this role makes sense for the user at this stage in their career")
    strongest_arguments: list[str] = Field(description="Top 2-3 arguments in favor of applying")
    weakest_areas: list[str] = Field(description="Top 2-3 areas of concern")
    interview_risk: str = Field(description="The most likely objection from the hiring manager and how to address it")
    narrative: str = Field(description="One-sentence pitch: 'Bridge between X and Y'")


class MissingInformation(BaseModel):
    questions: list[str] = Field(description="Questions whose answers would significantly change the assessment")


# ── Wrappers for list-typed structured outputs ───────────────────────

class TranslationMappingList(BaseModel):
    items: list[TranslationMapping] = Field(description="Experience translation mappings")

class GapItemList(BaseModel):
    items: list[GapItem] = Field(description="Gap analysis items")

class HiringRiskItemList(BaseModel):
    items: list[HiringRiskItem] = Field(description="Hiring risk items")


class FitAssessment(BaseModel):
    url: str = Field(description="Job posting URL this assessment is for")
    overall: FitScore = Field(
        description="Overall fit assessment across all dimensions combined"
    )
    role_fit: FitScore = Field(
        description=(
            "How well the job title and field match the user's desired roles "
            "and what their CV experience suggests"
        )
    )
    skill_fit: FitScore = Field(
        description=(
            "How well the user's skills match the required and nice-to-have "
            "skills listed in the job ad"
        )
    )
    location_fit: FitScore = Field(
        description=(
            "How well the job location aligns with the user's preferred locations "
            "and nearby big city commute options"
        )
    )
    work_mode_fit: FitScore = Field(
        description=(
            "Alignment between the job's work mode and the user's preference: "
            "remote, hybrid, or on-site"
        )
    )
    seniority_fit: FitScore = Field(
        description=(
            "Whether the job's seniority level matches the user's experience level "
            "as indicated in their profile and CV"
        )
    )
    salary_fit: FitScore | None = Field(
        default=None,
        description=(
            "Whether the salary meets or exceeds the user's minimum expectation. "
            "Null if salary is not mentioned in the job ad."
        ),
    )
    main_mismatch_reason: str | None = Field(
        default=None,
        description=(
            "Single most important reason the user should not apply to this job. "
            "Null if recommendation is strong_apply or consider."
        ),
    )
    matched_skills: list[str] = Field(
        description=(
            "Skills from the job ad (required or nice-to-have) that the user "
            "possesses based on their profile and CV"
        )
    )
    missing_key_skills: list[str] = Field(
        description=(
            "Required skills from the job ad that the user appears to lack "
            "based on their profile and CV"
        )
    )
    recommendation: str = Field(
        description=(
            "Whether the user should apply. One of: "
            "strong_apply, consider, weak, skip"
        )
    )
    reasoning: str = Field(
        description=(
            "Concise narrative explaining the overall assessment and key factors "
            "that influenced each dimension"
        )
    )

    role_breakdown: Optional[RoleBreakdown] = Field(default=None, description="What the role actually is behind the title")
    experience_translation: Optional[list[TranslationMapping]] = Field(default=None, description="How CV experience maps to role needs")
    gaps: Optional[list[GapItem]] = Field(default=None, description="Hard, soft, and negotiable gaps")
    hiring_risks: Optional[list[HiringRiskItem]] = Field(default=None, description="Per-area hiring risk assessment")
    career_trajectory: Optional[str] = Field(default=None, description="Where this role leads in 2-3 years")
    story: Optional[ApplicationStory] = Field(default=None, description="Application narrative and strongest arguments")
    missing_info: Optional[MissingInformation] = Field(default=None, description="Questions that would sharpen the assessment")
