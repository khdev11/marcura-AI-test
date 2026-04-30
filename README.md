# Charter Party Clause Parser

A small Python pipeline that extracts numbered legal clauses from Part II of a
maritime charter party PDF and emits them as structured JSON.

The pipeline has two stages:

1. **Local extraction** — `charter_parser/pdf_extractor.py` walks the PDF
   character-by-character with PyMuPDF, collects every horizontal line and
   thin filled rectangle drawn on each page, and drops any character whose
   bounding box is bisected by one. Charter parties are routinely amended
   by striking through printed clauses and writing replacements alongside;
   this step removes the struck-through wording so it never reaches the LLM.

2. **LLM segmentation** — `charter_parser/llm_client.py` sends the cleaned
   text to Anthropic Claude, forcing a tool call against a JSON schema. The
   model returns a list of `{id, title, text}` objects, in source order.
   Tool-use is used as the structured-output mechanism so we never have to
   parse free-form text back into JSON.

The output (`clauses.json`) is a JSON array:

```json
[
  {
    "id": "1",
    "title": "Condition of vessel",
    "text": "Owners shall exercise due diligence ..."
  },
  ...
]
```

## Setup

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate         # on Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# then edit .env and paste your key
```

## Run

Download the example PDF and run the parser:

```bash
curl -L -o charter.pdf \
  https://shippingforum.wordpress.com/wp-content/uploads/2012/09/voyage-charter-example.pdf

python -m charter_parser charter.pdf \
  --first-page 6 --last-page 39 \
  --output clauses.json
```

CLI flags:

| flag | default | meaning |
| --- | --- | --- |
| `pdf` | _(required)_ | path to the input PDF |
| `--first-page` | `6` | first page of Part II, 1-indexed inclusive |
| `--last-page` | `39` | last page of Part II, 1-indexed inclusive |
| `--output, -o` | `clauses.json` | where to write the JSON |
| `--model` | `claude-sonnet-4-6` | Claude model id |
| `--dump-text` | _(off)_ | also write the cleaned PDF text to this path; useful for diagnosing strikethrough/segmentation issues |

## Project layout

```
charter_parser/
  __init__.py        # re-exports the public surface
  __main__.py        # CLI entry point (`python -m charter_parser`)
  models.py          # Pydantic Clause / ClauseList
  pdf_extractor.py   # PDF text + strikethrough-aware cleaning
  llm_client.py      # Anthropic tool-use call
clauses.json         # produced output
requirements.txt
.env.example
```

## Design notes

- **Why a heuristic for strikethroughs instead of trusting font flags?**
  PyMuPDF surfaces underline/strikethrough as `font_flags` only when the
  PDF uses a real strikethrough font feature. The example document doesn't —
  the strikes are drawn as separate path operators on top of the glyphs, so
  we have to look at the page's drawing operators to find them.
- **Why force a tool call?** It guarantees the model returns JSON that
  validates against a schema, eliminating "looks like JSON but isn't" failures
  and removing all post-processing regexes.
- **Why prompt caching?** The system prompt and tool definition stay fixed
  across runs while only the page text changes. Caching them keeps re-runs
  cheap when iterating on page ranges or strikethrough heuristics.
- **Why one call instead of chunking?** Part II of SHELLVOY 5 is ~30 pages
  and ~30k input tokens — comfortably inside Sonnet's 200k context, with a
  16-32k output budget for the JSON. Chunking adds boundary-stitching
  complexity for no quality gain at this size. For genuinely large
  documents, the natural extension is to chunk by page and pass the
  in-flight clause id through the prompt.
