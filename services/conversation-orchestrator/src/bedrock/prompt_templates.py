"""
Prompt templates for different conversation scenarios.
All templates enforce RAG-grounded, anti-hallucination responses.
"""

SCHEME_INFO_TEMPLATE = """
You are answering a question about the government scheme: {scheme_name}.
Based ONLY on the verified information below, answer the citizen's question.

Verified Scheme Information:
{scheme_content}

Citizen's Question: {user_question}

Rules:
- Answer only what's in the verified information above
- Use simple, clear language (reading level: Class 5)
- If asked about eligibility, list the criteria clearly
- Always mention how to apply and required documents if relevant
"""

ELIGIBILITY_EXPLAIN_TEMPLATE = """
Explain this eligibility result to the citizen in {language}:
Result: {eligibility_status}
Score: {score}
Matched: {matched_criteria}
Failed: {failed_criteria}
Missing: {missing_info}

Be encouraging and specific about next steps.
"""

SCHEME_COMPARISON_TEMPLATE = """
Compare these government schemes for the citizen based ONLY on the verified information provided:
{schemes_context}

Citizen profile: {user_profile_summary}
Question: {user_question}

Present a clear comparison focusing on which schemes they may be eligible for.
"""
