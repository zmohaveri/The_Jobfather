from langchain.chat_models import init_chat_model
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field, HttpUrl, field_validator
from datetime import date
from typing import Optional
from dotenv import load_dotenv
from devtools import pprint
import json
import os
from pathlib import Path

base_path = Path(__file__).resolve().parent.parent

#desired_roles = [] #TODO to make it more general and easier to manipulate
#language options #TODO

class JobPosting (BaseModel):
  url: str = Field(description="Job posting URL")
  job_posting_text: str = Field(description="Job posting")
  source: str= Field(description="Platform where job ad was found (e.g. LinkedIn, Xing, Indeed, company website).")
  date_posted: date = Field(default=None,description="Date when job ad was posted")
  
  @field_validator("url")
  @classmethod
  def validate_url(cls,u):
    HttpUrl(u) #to raise error if invalid
    return u
  

    
#models for nesting
class LanguageSkill (BaseModel):
  language: str = Field(description="Language")
  level_literal: str = Field(description=(
    "Fluency level with the exact phrasing they have asked in the ad. "
    "e.g. 'Good knowledge' or 'comfortable with' or 'very good command'"
  ))
  level_infered: str = Field(description="Interpretation of exact phrasing for the fluency level in format of A1/A2/B1/B2/C1/C2")

class RangedInt (BaseModel):
  minimum: Optional[int] = Field(default=None, description="minimum value in range")
  maximum: Optional[int] = Field(default=None, description="maximum value in range")

class Location (BaseModel):
  location: str = Field(description="location exactly as mentioned in the job ad. e.g. Wiesbaden, Germany")
  city: str = Field(description="The city the position is located in. e.g. Wiesbaden")
  big_city_nearby: str = Field(
    default=None, 
    description=(
      "If the city itself is small, mention the big city close by, from and to which I can easily commute. "
      "e.g. if the city is Wiesbaden, use 'Frankfurt'"
    )
  )
  country: str = Field(description="The country the city is located in")

class Skill (BaseModel):
  #skill_type: str = Field(description="type of skill. e.g. 'technical' or 'softskill'")
  skill: str = Field(description="the skill or tool in lower case without special characters. e.g. 'hypothesis testing' or 'langchain'")
  skill_level: str = Field(default=None, description="Proficiency level required. e.g. 'familiarity', 'comfortable' or 'proficient'")
  skill_urgency: str = Field(default=None, description=(
    "'nice to have' or 'required'."
    "Whether the skill was mentioned as a requirement or just as an addition."
  ))
#output model
class JobOpening (BaseModel):
  url: str = Field(description="Job posting URL")
  job_title: str = Field(description="Job title with exact phrasing mentioned in the ad")
  job_field: str = Field(description=(
    "Which field describes the job best?"
    "'Data Scientist', 'Machine Learning engineer', 'Machine Learning Scientist', "
    "'Data engineer', 'Bioinformatics', 'AI Engineer' or 'other'"
  ))
  company: str = Field(description="company name")
  company_sector: str = Field(description="company's sector. e.g. phrama, life sciences, tech, logistic, finance etc.")
  location: Location = Field(default=None, description="location mentioned in the job ad for the position.")
  job_ad_language: str = Field(description="The Language the job ad is written in. 'English', 'German' or 'other'")
  language_skills_required: list[LanguageSkill] = Field(default=None,description="Language skill requirements mentioned in the ad.")
  work_mode: str = Field(default='On-site',description=(
    "'Remote', 'Hybrid' or 'On-site'. "
    "If nothing is mentioned in the ad and there is a location, assume 'On-site'."
  ))
  skills_and_tools: list[Skill] = Field(description="list of the skills mentioned in the job")
  seniority: str = Field(description=(
    "seniority of the job position. "
    "'junior', 'medior or Associate', 'internship or working student', or 'team lead or higher'."
    "If it's not explicitly mentioned, try to infer based on requirements."
  ))
  company_culture: str = Field(default=None,description=(
    "concise explanation of how the company culture feels based on the ad. "
    "e.g. whether they seem to be supportive, caring of employees' well-being, or hostile and competitive."
  ))
  salary: Optional[RangedInt] = Field(default=None,description=(
    "Yearly salary estimate given in the ad in euros. e.g. 70000 to 90000. "
    "If salary is not mentioned in the posting, omit this field entirely."
  ))
  summary: str = Field(description="Short summary of the job.")
  company_size: RangedInt = Field(default=None, description="size of the company. e.g. 10-50")
  point_of_contact: str = Field(default=None, description="Point of contact")
  source: str= Field(description="Platform where job ad was found (e.g. LinkedIn, Xing, Indeed, company website).")
  date_posted: date = Field(default=None,description="Date when job ad was posted")
  special_consideration: str = Field(description=(
    "Any notable extra information about the role or company not captured elsewhere. "
    "e.g. unusual requirements, strong preferences, or standout benefits."
  ))
  @field_validator("url")
  @classmethod
  def validate_url(cls,u):
    HttpUrl(u) #to raise error if invalid
    return u