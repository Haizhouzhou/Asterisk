"""Trusted audience instructions, separate from retrieved evidence."""

PROFILES = {
    'maria': ('Maria / Patient organization leader',
              'Assume no biomedical training. Use short sentences and familiar words. Explain every necessary technical term or abbreviation on first use. Explain what each finding means for a patient organization, what is uncertain, and a concrete question to ask an expert. Avoid unexplained jargon and patronizing language.'),
    'researcher': ('Biomedical researcher',
                   'Use precise scientific terminology. Distinguish gene-level from variant-specific mechanisms, association from causation, study designs, model systems, independent evidence and confounding. Discuss falsifiable hypotheses and experimental validation only where supported by the packet.'),
    'clinician': ('Clinical professional',
                  'Use professional clinical terminology. Emphasize phenotype specificity, study population, endpoints, evidence quality and applicability limitations. Keep research leads distinct from clinical recommendations; do not assess individual eligibility or prescribe.'),
    'industry': ('Research development professional',
                 'Use professional translational research language. Discuss evidence maturity, reusable infrastructure, feasibility and validation dependencies. Do not invent commercial, regulatory, funding or efficacy claims.'),
}
LANGUAGES = {'en': 'English', 'zh-CN': 'Simplified Chinese'}


def audience(role='maria', language='en'):
    if not isinstance(role, str) or role not in PROFILES:
        raise ValueError('Unsupported audience role')
    if not isinstance(language, str) or language not in LANGUAGES:
        raise ValueError('Unsupported report language')
    label, style = PROFILES[role]
    return {'role': role, 'label': label, 'language': language,
            'instruction': f'Write all reader-facing review fields in {LANGUAGES[language]} for {label}. {style} Preserve identifiers, citations, evidence status and scientific uncertainty. Adapt explanation and detail, never evidence strength. Do not translate JSON keys or status enum values.'}
