# Rare Disease Atlas Categories and Identifiers

## Disease

> Disease is the central entity and does not belong to the four UI categories.

### Standard IDs
- MONDO ID
  - Example: `MONDO:0000001`
- Orphanet ID
  - Example: `ORPHA:355`
- OMIM ID
  - Example: `OMIM:230800`

### Recommended canonical ID
Use `MONDO ID` as the primary disease identifier whenever available.

---

## 1. Mechanism

### Molecular Function

Examples:
- Enzyme dysfunction
- Loss of function
- Gain of function
- Ion-channel dysfunction
- Protein dysfunction

### Recommended IDs
Depending on the entity:

- Gene Ontology Molecular Function
  - `GO:xxxxxxx`
- Reactome reaction
  - `R-HSA-xxxxxxx`
- Protein
  - UniProt ID, e.g. `P04062`

> "Molecular Function" itself is only a UI category and does not need an ID.

---

### Pathway / Process

Examples:
- Lysosomal degradation
- Autophagy
- Glycosphingolipid metabolism
- Synaptic signaling
- DNA repair

### Recommended IDs

- Reactome pathway ID
  - `R-HSA-xxxxxxx`
- Gene Ontology Biological Process
  - `GO:xxxxxxx`

### Recommended canonical source
Prefer Reactome for pathway nodes.

---

### Cellular Effect

Examples:
- Lysosomal dysfunction
- Mitochondrial dysfunction
- Protein accumulation
- ER stress
- Neuroinflammation

### Recommended IDs

Use a standard ontology ID when one exists:

- Gene Ontology
  - `GO:xxxxxxx`
- HPO if the concept is actually an observable phenotype
  - `HP:xxxxxxx`

If no suitable canonical identifier exists:

- Internal Atlas ID
  - Example: `ATLAS:MECH:000123`

The internal node must still carry supporting evidence.

---

## 2. Phenotype

### Neurological

Examples:
- Seizure
- Ataxia
- Developmental delay
- Hypotonia

### Blood

Examples:
- Anemia
- Thrombocytopenia

### Organs

Examples:
- Splenomegaly
- Hepatomegaly

### Musculoskeletal

Examples:
- Muscle weakness
- Bone pain
- Skeletal abnormalities

### Other

For phenotypes that do not fit the main UI groups.

### Standard ID

Use Human Phenotype Ontology:

- HPO ID
  - `HP:xxxxxxx`

Examples:

- Seizure → HPO ID
- Splenomegaly → HPO ID
- Anemia → HPO ID

### Recommended canonical ID
Always prefer `HPO ID`.

> Neurological / Blood / Organs / Musculoskeletal are UI groups only.
> They should not become graph nodes unless there is a specific product reason.

---

## 3. Gene

### Disease Gene

Examples:
- GBA1
- MECP2
- CFTR

### Standard IDs

Prefer one canonical gene identifier:

- HGNC ID
  - `HGNC:xxxx`
- NCBI Gene ID
  - numeric Gene ID
- Ensembl Gene ID
  - `ENSGxxxxxxxxxxx`

### Recommended canonical ID
Use `HGNC ID` for human genes.

Store other IDs as cross-references.

Example:

```json
{
  "label": "GBA1",
  "canonical_id": "HGNC:4177",
  "xrefs": {
    "ncbi_gene": "...",
    "ensembl": "..."
  }
}