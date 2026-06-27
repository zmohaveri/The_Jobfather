from pydantic import BaseModel, Field


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
