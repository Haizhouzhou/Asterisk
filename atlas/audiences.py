"""Trusted audience instructions, separate from retrieved evidence."""

PROFILES = {
    'patient': ('Patient & family',
                'Assume no biomedical training. Use short sentences and familiar words. Explain every necessary technical term or abbreviation on first use. Explain what each finding means for patients, families and their patient organization, what is uncertain, and a concrete question to ask an expert. Avoid unexplained jargon and patronizing language.'),
    'expert': ('Expert',
               'Use precise scientific and clinical terminology. Distinguish gene-level from variant-specific mechanisms, association from causation, study designs, model systems, independent evidence and confounding. Emphasize phenotype specificity, study population, endpoints, evidence quality, evidence maturity, reusable infrastructure, feasibility and validation dependencies. Discuss falsifiable hypotheses and experimental validation only where supported by the packet. Keep research leads distinct from clinical recommendations; do not assess individual eligibility, prescribe, or invent commercial, regulatory, funding or efficacy claims.'),
}
LANGUAGES = {'en': 'English', 'zh-CN': 'Simplified Chinese'}


def audience(role='patient', language='en'):
    if not isinstance(role, str) or role not in PROFILES:
        raise ValueError('Unsupported audience role')
    if not isinstance(language, str) or language not in LANGUAGES:
        raise ValueError('Unsupported report language')
    label, style = PROFILES[role]
    return {'role': role, 'label': label, 'language': language,
            'instruction': f'Write all reader-facing review fields in {LANGUAGES[language]} for {label}. {style} Preserve identifiers, citations, evidence status and scientific uncertainty. Adapt explanation and detail, never evidence strength. Do not translate JSON keys or status enum values.'}
