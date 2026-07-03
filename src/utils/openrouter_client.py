from __future__ import annotations
import json
import logging
import os
from typing import Any
import requests
from dotenv import load_dotenv
load_dotenv()
logger = logging.getLogger(__name__)
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'

def get_openrouter_config() -> dict[str, Any]:
    try:
        from config import OPENROUTER_MODEL, USE_OPENROUTER_FOR_LINKEDIN
    except ImportError:
        OPENROUTER_MODEL = 'openai/gpt-oss-120b:free'
        USE_OPENROUTER_FOR_LINKEDIN = True
    return {'enabled': USE_OPENROUTER_FOR_LINKEDIN, 'api_key': os.getenv('OPENROUTER_API_KEY', '').strip(), 'model': os.getenv('OPENROUTER_MODEL', OPENROUTER_MODEL).strip()}

def answer_application_question(question: str, options: list[str] | None, profile: dict[str, Any]) -> str | None:
    cfg = get_openrouter_config()
    if not cfg['enabled'] or not cfg['api_key']:
        return None
    options_text = ''
    if options:
        options_text = 'Options:\n' + '\n'.join((f'- {o}' for o in options))
    profile_text = f"Years of experience: {profile.get('exp_total', '2')}\nNotice period (days): {profile.get('notice_days', 30)}\nWilling to relocate: {('Yes' if profile.get('willing_to_relocate') else 'No')}\nCurrent location: {profile.get('current_location', 'Pune')}\nDefault for yes/no screening questions: Yes\n"
    system = 'You fill job application forms. Reply with ONLY the exact answer text to enter or the exact option label to choose. No explanation.'
    user = f'Applicant profile:\n{profile_text}\n\nQuestion:\n{question}\n\n{options_text}\n\nAnswer:'
    try:
        res = requests.post(OPENROUTER_URL, headers={'Authorization': f"Bearer {cfg['api_key']}", 'Content-Type': 'application/json', 'HTTP-Referer': 'https://github.com/local/auto-apply'}, json={'model': cfg['model'], 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}], 'max_tokens': 80, 'temperature': 0.1}, timeout=30)
        res.raise_for_status()
        content = res.json()['choices'][0]['message']['content'].strip()
        return content.strip('"').strip("'")
    except Exception as exc:
        logger.debug('OpenRouter call failed: %s', exc)
        return None


def _fallback_application_message(company: str, role: str, person: str, profile: dict[str, Any]) -> str:
    greeting_name = (person or '').strip()
    greeting = f'Hi {greeting_name.split()[0]},' if greeting_name else 'Hi there,'
    applicant = str(profile.get('full_name', '') or '').strip()
    exp = profile.get('exp_total', '2')
    skills = profile.get('skills') or []
    top_skills = ', '.join(str(s) for s in skills[:4]) if skills else 'modern web and cloud tooling'
    role_text = (role or 'this role').strip()
    company_text = (company or 'your team').strip()
    portfolio = str(profile.get('portfolio_url', '') or '').strip()
    lines = [
        greeting,
        '',
        f"I'm excited about the {role_text} opening at {company_text}. "
        f"I have {exp} years of hands-on experience working with {top_skills}, and I'd love to "
        f"help build what you're working on.",
        '',
        "I move fast, care about clean and reliable systems, and enjoy the pace of an early-stage team. "
        "I'd be glad to share more about how I can contribute.",
    ]
    if portfolio:
        lines.append('')
        lines.append(f'You can see some of my work here: {portfolio}')
    lines.append('')
    lines.append('Thanks for your time!')
    if applicant:
        lines.append(applicant)
    return '\n'.join(lines)


def generate_application_message(company: str, role: str, person: str, profile: dict[str, Any], job_description: str = '') -> str:
    """Write a short, personalized outreach message for a Work at a Startup application.

    Uses OpenRouter when configured; otherwise falls back to a solid template so the
    apply flow never blocks on a missing/failed AI call.
    """
    cfg = get_openrouter_config()
    if not cfg['enabled'] or not cfg['api_key']:
        return _fallback_application_message(company, role, person, profile)

    applicant = str(profile.get('full_name', '') or '').strip()
    exp = profile.get('exp_total', '2')
    skills = profile.get('skills') or []
    skills_text = ', '.join(str(s) for s in skills) if skills else ''
    portfolio = str(profile.get('portfolio_url', '') or '').strip()
    desc = (job_description or '').strip()
    if len(desc) > 1200:
        desc = desc[:1200]

    system = (
        'You write short, warm, personalized job application messages sent directly to a '
        'startup founder or hiring manager. Keep it 90-140 words, specific, and genuine. '
        'Address the person by first name if given. Mention the role and company by name, '
        'connect the applicant\'s experience to the role, and close with a friendly call to action. '
        'Do NOT invent facts about the applicant. Return ONLY the message body, no subject line, '
        'no markdown, no placeholders like [Name].'
    )
    profile_text = (
        f'Applicant name: {applicant or "(omit a signature if empty)"}\n'
        f'Years of experience: {exp}\n'
        f'Key skills: {skills_text}\n'
        f'Portfolio/links: {portfolio or "(none)"}\n'
    )
    target_text = (
        f'Company: {company or "the company"}\n'
        f'Role: {role or "the open role"}\n'
        f'Founder/contact name: {person or "(unknown - use a neutral greeting)"}\n'
    )
    if desc:
        target_text += f'\nJob description (for context):\n{desc}\n'
    user = f'{profile_text}\n{target_text}\nWrite the message now:'
    try:
        res = requests.post(
            OPENROUTER_URL,
            headers={'Authorization': f"Bearer {cfg['api_key']}", 'Content-Type': 'application/json', 'HTTP-Referer': 'https://github.com/local/auto-apply'},
            json={'model': cfg['model'], 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}], 'max_tokens': 350, 'temperature': 0.6},
            timeout=45,
        )
        res.raise_for_status()
        content = (res.json()['choices'][0]['message']['content'] or '').strip()
        content = content.strip('"').strip()
        if len(content) < 40:
            return _fallback_application_message(company, role, person, profile)
        return content
    except Exception as exc:
        logger.debug('OpenRouter application-message call failed: %s', exc)
        return _fallback_application_message(company, role, person, profile)
