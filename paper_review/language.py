"""Shared short-language report policy inspired by public ASD-STE100 guidance.

This module is NOT a formal STE dictionary/compliance checker. Technical names
stay unchanged. Limits below are project checks for reader summaries, not claims
of certified ASD-STE100 conformance.
"""
import re

POLICY = "ste-inspired-v1"
STATUS_TEXT = {
    "supported": ("No conflict found", "The check found no conflict in the supplied evidence.",
                  "This result does not prove that the experiment is correct.",
                  ["Do not change the paper on the basis of this check alone."]),
    "contradicted": ("Check this difference", "The statement does not match the cited evidence.",
                     "The reader can receive a result that the evidence does not support.",
                     ["Compare the statement with the linked evidence.",
                      "Correct the statement only if the difference is confirmed."]),
    "ambiguous": ("Clarify this statement", "The meaning or scope of the statement is not clear.",
                  "The reader can interpret the statement in different ways.",
                  ["Define the terms and scope.", "State the conditions under which the claim applies."]),
    "insufficient_evidence": ("Add missing evidence", "The available evidence is not sufficient for this check.",
                              "The check cannot establish whether the statement is correct.",
                              ["Obtain the missing evidence.", "Repeat the check before you change the statement."]),
    "requires_external_verification": ("Check other sources", "This statement needs evidence outside the supplied paper.",
                                       "The paper alone cannot verify this statement.",
                                       ["Check the cited study, code, or raw data.", "Record the result before you change the statement."]),
    "not_checked": ("Check not complete", "This statement has not been checked.",
                    "No result is available.", ["Complete the check before you use its result."]),
}
ACTION_VERBS = set("Add Avoid Calculate Check Compare Complete Confirm Correct Define Describe Do Ensure Inspect Keep Limit List Obtain Read Record Remove Repeat Replace Report Select Separate Specify State Test Use Verify".split())

READER_INSTRUCTION = """Also return reader_summary with this shape:
{"title":"short problem title", "problem":"what is wrong or unresolved",
"evidence":["short source-grounded facts"], "effect":"why the issue matters",
"actions":["one clear action per item"], "replacement":"optional qualified wording"}.
Use ASD-STE100-inspired plain technical English: short sentences, one topic per
sentence, active voice and consistent terms. Do not claim formal STE compliance.
Use at most 25 words per descriptive sentence and 20 words per instruction.
Start each action with a clear action verb. Preserve numbers, units, qualifiers
and technical names. Give conditional actions for unconfirmed differences.
Do not invent source facts or claim that the code or experiments are wrong.
If no conflict is found, say so and do not invent a problem to correct.
Reader wording is a suggestion until a reviewer checks the source."""


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]


def check_text(text, limit):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Reader text must be a non-empty string")
    if any(len(s.split()) > limit for s in sentences(text)):
        raise ValueError(f"Reader sentence exceeds {limit} words")
    return text.strip()


def validate_summary(summary):
    if not isinstance(summary, dict):
        raise ValueError("Reader summary must be an object")
    allowed = {'title','problem','evidence','effect','actions','replacement'}
    if set(summary)-allowed:
        raise ValueError("Unknown reader-summary fields")
    result = {key:check_text(summary.get(key),25) for key in ('title','problem','effect')}
    if len(result['title'].split()) > 12:
        raise ValueError('Reader title exceeds 12 words')
    if any(len(sentences(result[key])) > 2 for key in ('problem','effect')):
        raise ValueError('Keep each reader description to at most two short sentences')
    for key in ('evidence','actions'):
        entries = summary.get(key)
        if not isinstance(entries,list) or not entries:
            raise ValueError(f"Reader summary needs {key}")
        result[key] = [check_text(entry,20 if key=='actions' else 25) for entry in entries]
    for entry in result['evidence']:
        if len(sentences(entry)) > 1:
            raise ValueError('Use one evidence statement per list item')
    for action in result['actions']:
        if len(sentences(action)) > 1:
            raise ValueError('Use one action sentence per list item')
        if action.split()[0].rstrip(':,') not in ACTION_VERBS:
            raise ValueError("Start each reader action with a clear action verb")
    if summary.get('replacement'):
        result['replacement']=check_text(summary['replacement'],25)
    return result


def fallback_summary(claim):
    status=claim.get('verification',{}).get('status','not_checked')
    title,problem,effect,actions=STATUS_TEXT[status]
    return validate_summary({'title':title,'problem':problem,
                             'evidence':['Read the linked source pages for the supporting values or text.'],
                             'effect':effect,'actions':actions})


def reader_summary(claim, decision):
    # Source-checked editorial text takes precedence over an unreviewed model proposal.
    if decision in {'confirmed','needs_evidence'} and claim.get('review',{}).get('presentation'):
        return validate_summary(claim['review']['presentation']), 'reviewed'
    proposed=claim.get('verification',{}).get('reader_summary')
    if proposed:
        return validate_summary(proposed), 'proposed'
    return fallback_summary(claim), 'template'


def reader_label(claim, decision):
    if decision=='confirmed':
        return 'Difference checked against the source'
    if decision=='needs_evidence':
        return 'More evidence is required'
    return STATUS_TEXT[claim.get('verification',{}).get('status','not_checked')][0]
