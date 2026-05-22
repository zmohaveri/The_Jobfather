from langchain.chat_models import init_chat_model
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field, HttpUrl, field_validator
from datetime import date
from typing import Optional
from dotenv import load_dotenv
from devtools import pprint
import json
import os
import sys
from pathlib import Path
import argparse

base_path = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(base_path))

from src.schemas.structured_job import JobPosting, JobOpening
from src.db.job_store import save_job

load_dotenv()

llm = init_chat_model("gpt-4o-mini", model_provider="openai")


structured_llm = llm.with_structured_output(JobOpening)

prompt_template_str = """
Extract structured data from the following job posting.
Everything has to be extracted in English. 
If the job ad's language is not English, translate the information into English before filling the output.
\n
\n{job_posting_text}"

"""

prompt_template = PromptTemplate.from_template(prompt_template_str)

def get_structured_job(input):
    prompt = prompt_template.format(job_posting_text=input)
    structured_job = structured_llm.invoke(prompt)
    return structured_job


def main():
    parser = argparse.ArgumentParser(description="Scrape a job posting and extract structured data.")
    parser.add_argument(
        "--input_json",
        "-j", 
        type=str, 
        default=None,
        help="Path to the json file containing the JobPosting object."
    )
    parser.add_argument(
        "--input_text",
        "-t", 
        type=str, 
        default=None,
        help="Path to the text file containing the job posting."
    )
    parser.add_argument(
        "--save",
        "-s",
        action="store_true",
        default=False,
        help="Save the extracted structured job to the database."
    )
    args = parser.parse_args()

    if not args.input_json and not args.input_text:
        raise ValueError("Please provide either --input_json or --input_text.")

    if not args.input_json is None:
      with open(Path(args.input_json), 'r', encoding='utf-8') as f:
          job_posting = JobPosting.model_validate(json.load(f)).model_dump_json()

    if not args.input_text is None:
      with open(Path(args.input_text), 'r', encoding='utf-8') as f:
          job_posting = f.read()
    
    structured_job = get_structured_job(job_posting)

    if args.save:
        save_job(structured_job)
    elif pprint:
        pprint(structured_job)

if __name__ == "__main__":
    structured_job = main()
