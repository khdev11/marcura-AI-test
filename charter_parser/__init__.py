"""Charter party clause extractor.

A small pipeline that:
  1. Extracts text from a maritime charter party PDF, dropping any
     characters that appear under a strikethrough line.
  2. Asks an LLM (Anthropic Claude) to segment the cleaned text into
     numbered legal clauses with id / title / body.
  3. Emits the result as JSON.
"""

from charter_parser.models import Clause
from charter_parser.pdf_extractor import extract_pages
from charter_parser.llm_client import extract_clauses

__all__ = ["Clause", "extract_pages", "extract_clauses"]
