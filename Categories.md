# Rare Disease Atlas Categories

## 1. Mechanism

### Molecular Function
- Protein dysfunction
- Loss of function
- Gain of function
- Enzyme activity changes
- Ion-channel dysfunction

### Pathway / Process
- Biological pathways
- Metabolic pathways
- Lysosomal degradation
- Autophagy
- Synaptic signaling
- DNA repair
- Other disease-relevant biological processes

### Cellular Effect
- Lysosomal dysfunction
- Mitochondrial dysfunction
- Protein accumulation
- ER stress
- Inflammation
- Neuroinflammation
- Other downstream cellular effects


## 2. Phenotype

### Neurological
- Seizures
- Movement abnormalities
- Developmental delay
- Cognitive abnormalities
- Muscle tone abnormalities
- Neurodegenerative manifestations

### Blood
- Anemia
- Thrombocytopenia
- Bleeding abnormalities
- Other blood-related phenotypes

### Organs
- Splenomegaly
- Hepatomegaly
- Cardiac abnormalities
- Renal abnormalities
- Other organ-related phenotypes

### Musculoskeletal
- Bone abnormalities
- Bone pain
- Muscle weakness
- Joint abnormalities
- Other musculoskeletal phenotypes

### Other
- Phenotypes that do not clearly fit the major groups

> The actual graph nodes should be standardized HPO terms.  
> These subcategories are primarily for UI grouping and filtering.


## 3. Gene

### Disease Gene
- Genes with established or well-supported disease associations
- Causal genes
- Strongly associated disease genes

### Variant
- Pathogenic variants
- Likely pathogenic variants
- Variants of uncertain significance
- Variants with conflicting classifications

> Variant classification should normally be stored as metadata on the variant node rather than as separate graph node types.


## 4. Research & Community

### Studies & Trials
- Clinical trials
- Natural-history studies
- Observational studies
- Biomarker studies
- Registry studies
- Therapeutic studies

### Researchers & Institutions
- Researchers working on the disease
- Principal investigators
- Relevant research groups
- Universities
- Hospitals and medical centers
- Research institutes
- Companies involved in relevant studies

### Patient Groups & Registries
- Patient organizations
- Disease foundations
- Patient registries
- Research registries
- Natural-history communities
- Disease-specific support or research communities


# Hidden / Supporting Graph Entities

These entities can exist in the backend knowledge graph but do not need to appear as top-level Atlas categories.

## Disease
- Central entity used for search and graph navigation

## Paper
- Used as evidence for graph relationships
- Usually shown in the Evidence Panel rather than directly on the main graph

## Evidence
- Source
- Source ID
- URL
- Supporting text
- Publication date
- Retrieval date
- Evidence type
- Contradictory evidence
- Confidence / review status