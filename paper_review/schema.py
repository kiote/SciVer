"""Validation, deterministic calculations and conservative coverage accounting."""
import hashlib
import json
import re
import unicodedata
from decimal import Decimal

STATUSES = {"supported", "contradicted", "ambiguous", "insufficient_evidence", "requires_external_verification"}
DISPOSITIONS = {"claims", "no_checkable_claim", "references", "unreadable"}
ORIGINS = {"paper_statement", "visual_observation"}


def normalize(text):
    text = unicodedata.normalize("NFKC", text).replace('\u00ad', '')
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    return " ".join(text.split())


def digest(value):
    data = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(data).hexdigest()


def parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object")
    return result


def validate_extraction(result, units):
    if not isinstance(result.get("claims"), list) or not isinstance(result.get("units"), list):
        raise ValueError("Extraction needs claims and unit dispositions")
    known = {u["id"]: u for u in units}
    dispositions = result["units"]
    if len(dispositions) != len(known) or {u.get("unit_id") for u in dispositions} != set(known):
        raise ValueError("Every supplied unit must be accounted for exactly once")
    for entry in dispositions:
        if entry.get("disposition") not in DISPOSITIONS or not isinstance(entry.get("reason"), str):
            raise ValueError("Invalid unit disposition")
    seen_claim_units = set()
    for claim in result["claims"]:
        refs = claim.get("source_unit_ids")
        if not isinstance(refs, list) or not refs or not set(refs).issubset(known):
            raise ValueError("Claim references unknown/empty source units")
        if claim.get("origin") not in ORIGINS or not isinstance(claim.get("text"), str) or not claim["text"].strip():
            raise ValueError("Invalid claim origin/text")
        quoted = claim.get("source_quote", "")
        if not isinstance(quoted, str) or not isinstance(claim.get("kind", "other"), str):
            raise ValueError("Invalid quote/kind")
        if claim["origin"] == "paper_statement":
            # Only actual authored text, not invented negative controls or stronger paraphrases.
            if normalize(claim["text"]) != normalize(quoted) or not quoted.strip():
                raise ValueError("Paper statements must use the actual verbatim source quote")
            if not any(known[ref].get("role", "text") == "text" and normalize(quoted) in normalize(known[ref]["text"]) for ref in refs):
                raise ValueError("Quote is not present in the referenced source unit")
        if "id" in claim or "label" in claim or "expected" in claim:
            raise ValueError("Model must not assign internal IDs or gold labels")
        seen_claim_units.update(refs)
    mapped = {u["unit_id"]: u["disposition"] for u in dispositions}
    if any(mapped[ref] != "claims" for ref in seen_claim_units):
        raise ValueError("Claims conflict with unit dispositions")
    if any(value == "claims" and key not in seen_claim_units for key, value in mapped.items()):
        raise ValueError("A claims disposition needs at least one attached claim")
    return result


def calculate(entry):
    """Arithmetic only: this does not validate that operands were read correctly."""
    a, b = Decimal(str(entry["a"])), Decimal(str(entry["b"]))
    if not a.is_finite() or not b.is_finite():
        raise ValueError("Non-finite arithmetic operand")
    if entry["operation"] == "difference":
        value = a-b
    elif entry["operation"] == "relative_change_percent":
        value = (b-a)/a*100
    elif entry["operation"] == "ratio":
        value = a/b
    else:
        raise ValueError("Unsupported arithmetic operation")
    return {**entry, "computed": str(value), "note": "Arithmetic checked; source operands still require review"}


def validate_verification(result, units, require_reader=False):
    if result.get("status") not in STATUSES or not isinstance(result.get("explanation"), str):
        raise ValueError("Invalid verification status/explanation")
    refs = result.get("evidence_unit_ids")
    known = {u["id"] for u in units}
    if not isinstance(refs, list) or not set(refs).issubset(known):
        raise ValueError("Verification cites unknown evidence units")
    if result["status"] in {"supported", "contradicted"} and not refs:
        raise ValueError("Supported/contradicted verdict needs evidence")
    calculations = result.get("calculations", [])
    if not isinstance(calculations, list):
        raise ValueError("Invalid calculation list")
    result["calculations"] = [calculate(c) for c in calculations]
    if 'reader_summary' in result:
        from paper_review.language import validate_summary
        result['reader_summary']=validate_summary(result['reader_summary'])
    elif require_reader:
        raise ValueError('Verification needs a short-language reader summary')
    return result


def review_decision(claim):
    review = claim.get("review", {})
    if not review:
        return "pending human review"
    if review.get("verification_sha256") != digest(claim.get("verification", {})):
        return "stale decision — re-review needed"
    if review.get("decision") == "confirmed" and (claim.get("origin") != "paper_statement" or claim.get("verification", {}).get("status") not in {"contradicted", "ambiguous"}):
        return "invalid confirmation — re-review needed"
    return review.get("decision", "pending human review")


def coverage(document, state):
    per_page = []
    for page in document["pages"]:
        primary = state.get("passes", {}).get(f"primary-{page['number']}")
        audit = state.get("passes", {}).get(f"audit-{page['number']}")
        exclusion = state.get("page_exclusions", {}).get(str(page["number"]), {})
        exclusion = exclusion if exclusion.get("page_sha256") == digest(page) else {}
        per_page.append({"page": page["number"], "units": len(page["units"]),
                         "excluded": bool(exclusion), "exclusion_reason": exclusion.get("reason", ""),
                         "primary": bool(primary), "audit": bool(audit),
                         "text_available": not page["needs_ocr"],
                         "unreadable_units": sum(u["disposition"] == "unreadable" for u in (audit or {}).get("units", []))})
    in_scope = [p for p in per_page if not p["excluded"]]
    inventory = bool(in_scope) and all(p["primary"] and p["audit"] and p["text_available"] and not p["unreadable_units"] for p in in_scope)
    claims = state.get("claims", [])
    verified = sum(bool(c.get("verification")) for c in claims)
    unresolved = sum(c.get("verification", {}).get("status") in
                     {"ambiguous", "insufficient_evidence", "requires_external_verification"} for c in claims)
    confirmed = sum(review_decision(c) == "confirmed" and c.get('review',{}).get('reviewer_type','human') == 'human' for c in claims)
    assistant_checked = sum(review_decision(c) == 'confirmed' and c.get('review',{}).get('reviewer_type') == 'assistant' for c in claims)
    checked_issues = len({c.get('review',{}).get('issue_id') or c['id'] for c in claims if review_decision(c) == 'confirmed'})
    assistant_issues = len({c.get('review',{}).get('issue_id') or c['id'] for c in claims
                           if review_decision(c) == 'confirmed' and c.get('review',{}).get('reviewer_type') == 'assistant'})
    candidates = sum(c.get("verification", {}).get("status") in {"contradicted", "ambiguous"}
                     and review_decision(c) != 'dismissed'
                     and not (review_decision(c) == 'confirmed' and c.get('review',{}).get('reviewer_type','human') == 'human') for c in claims)
    complete = inventory and verified == len(claims) and not state.get("task_errors")
    return {"pages": per_page, "total_pages": len(per_page), "in_scope_pages": len(in_scope),
            "excluded_pages": len(per_page)-len(in_scope), "automated_checks_complete": complete,
            "primary_pages": sum(p["primary"] for p in per_page),
            "audited_pages": sum(p["audit"] for p in per_page),
            "inventory_complete": inventory, "claims": len(claims), "verified": verified,
            "not_checked": len(claims)-verified, "unresolved": unresolved,
            "candidate_findings": candidates, "confirmed_findings": confirmed, "assistant_checked_findings": assistant_checked,
            "assistant_checked_issue_groups": assistant_issues, "source_checked_issue_groups": checked_issues,
            "coverage_human_approved": state.get("coverage_approval") == digest({"passes": state.get("passes", {}), "claims": [c["id"] for c in claims], "exclusions": state.get("page_exclusions", {})}),
            "label": "All configured checks completed for in-scope content; human/external review may remain" if complete
                     else "Partial review — not a whole-paper conclusion"}
