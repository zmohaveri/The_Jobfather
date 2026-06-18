from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    cv_text: str = Field(description="CV or resume text of the user")
    desired_roles: list[str] = Field(
        default=[], description="Job titles or roles the user is interested in"
    )
    avoided_roles: list[str] = Field(
        default=[], description="Job titles or roles the user wants to avoid"
    )
    skills: list[str] = Field(
        default=[], description="Skills the user possesses"
    )
    languages: list[str] = Field(
        default=[], description="Languages the user speaks"
    )
    preferred_locations: list[str] = Field(
        default=[], description="Cities or regions the user prefers to work in"
    )
    avoided_locations: list[str] = Field(
        default=[], description="Cities or regions the user wants to avoid"
    )
    preferred_work_mode: str | None = Field(
        default=None, description="Preferred work mode: 'Remote', 'Hybrid', or 'On-site'"
    )
    preferred_salary_min: int | None = Field(
        default=None, description="Minimum annual salary the user is willing to accept"
    )
    seniority: str | None = Field(
        default=None, description="User's seniority level: 'junior', 'medior', 'senior', etc."
    )
    dealbreakers: list[str] = Field(
        default=[], description="Conditions or factors that would make the user reject a job"
    )
    notes: str | None = Field(
        default=None, description="Additional notes or preferences about the job search"
    )
    model_config = {"extra": "allow"} #let the model accept additional fields, so we're not limited by structure.