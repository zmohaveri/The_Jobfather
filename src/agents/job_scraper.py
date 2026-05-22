from langchain.chat_models import init_chat_model
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field, HttpUrl, field_validator
from datetime import date
from typing import Optional
from dotenv import load_dotenv
from devtools import pprint
from html.parser import HTMLParser
import json
import os
import sys
from pathlib import Path
import argparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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

class JobPostingHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self._text_parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth:
            return
        text = data.strip()
        if text:
            self._text_parts.append(text)

    def get_text(self):
        return " ".join(self._text_parts)


def get_job_posting_from_url(url):
    HttpUrl(url)
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; TheJobfather/0.1; +https://example.com/bot)"
        },
    )
    try:
        with urlopen(request, timeout=15) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            html = response.read().decode(charset, errors="replace")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise ValueError(f"Could not read job posting URL: {url}") from exc

    parser = JobPostingHTMLParser()
    parser.feed(html)
    return json.dumps(
        {
            "url": url,
            "job_posting_text": parser.get_text(),
        },
        ensure_ascii=False,
    )


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
        "--url",
        "-u",
        type=str,
        default=None,
        help="URL containing the job posting."
    )
    parser.add_argument(
        "--save",
        "-s",
        action="store_true",
        default=False,
        help="Save the extracted structured job to the database."
    )
    args = parser.parse_args()

    if not args.input_json and not args.input_text and not args.url:
        raise ValueError("Please provide either --input_json, --input_text, or --url.")

    if not args.input_json is None:
      with open(Path(args.input_json), 'r', encoding='utf-8') as f:
          job_posting = JobPosting.model_validate(json.load(f)).model_dump_json()

    if not args.input_text is None:
      with open(Path(args.input_text), 'r', encoding='utf-8') as f:
          job_posting = f.read()

    if not args.url is None:
      job_posting = get_job_posting_from_url(args.url)
    
    structured_job = get_structured_job(job_posting)

    if args.save:
        save_job(structured_job)
    elif pprint:
        pprint(structured_job)

if __name__ == "__main__":
    structured_job = main()
