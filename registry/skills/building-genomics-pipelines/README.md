# Building Genomics Pipelines

Opinionated tool defaults, file-format conventions, and nf-core pipeline selection for NGS data, with deep references for RNA-seq, variant annotation, and CNV/SV analysis.

## Install

```bash
npx @provectusinc/awos-recruitment skill building-genomics-pipelines
```

## Scope

The skill covers:

- Opinionated defaults: aligner, variant caller, and annotator selection
- Genomics file formats (FASTQ/BAM/CRAM/VCF/BED/GTF) and indexing conventions
- Pipeline design principles: reproducibility, scalability, QC gates
- nf-core pipeline selection and invocation
- Bulk and single-cell RNA-seq, from QC through pathway analysis
- Variant annotation (VEP, SnpEff, ANNOVAR) and ACMG clinical interpretation
- CNV and structural variant detection, merging, annotation, and classification

It does **not** cover writing Nextflow DSL2, Snakemake, or WDL workflow code by
hand — the frameworks' own documentation is the authority for syntax, and the
nf-core pipelines already wrap the steps this skill recommends.

## Usage

Once installed, the skill activates automatically when Claude Code detects a
genomics or NGS task — picking tools, choosing an nf-core pipeline, analyzing
expression or variant data, or setting QC thresholds.

Reference files are organized by workflow in `references/`:

```
references/rnaseq.md
references/annotation.md
references/cnv.md
```

## Reference Topics

| Topic | File | Covers |
|-------|------|--------|
| RNA-seq | `references/rnaseq.md` | Bulk QC/alignment/quantification, DESeq2, edgeR, limma-voom, pathway analysis, Cell Ranger, Seurat, Scanpy |
| Annotation | `references/annotation.md` | Normalization, VEP, SnpEff, ANNOVAR, population and clinical databases, filtering, ACMG interpretation |
| CNV & SV | `references/cnv.md` | GATK gCNV, CNVkit, Manta, DELLY, GRIDSS, SV merging, AnnotSV, ACMG/ClinGen CNV classification |

## Trigger Evaluations

Prompts for checking that the `description` in `SKILL.md` triggers this skill
when it should and stays quiet when a sibling skill is the better fit. Run each
prompt in a fresh session that has the registry skills installed, and check
whether this skill was consulted; edit the description when the outcome
disagrees with the table.

### Should trigger

| # | Prompt |
|---|--------|
| 1 | we just got 48 WES samples back from the core and i need to set up annotation — vep or snpeff? and what gnomAD cutoff makes sense for a recessive rare-disease panel |
| 2 | I've got salmon quant output for 3 treated and 3 control samples and a tx2gene table already built. Write the DESeq2 block that gets me shrunken log2 fold changes and a significant-gene table. |
| 3 | tumor/normal BAMs from a custom 2Mb capture panel, need copy number segments out of them. CNVkit or the GATK somatic CNV workflow? |
| 4 | which nf-core pipeline should I run for mouse ATAC-seq, and do I have to build the genome index myself first |
| 5 | my 10x run finished, help me get from filtered_feature_bc_matrix to annotated clusters in scanpy — resolution 0.5 is giving me way too many clusters |
| 6 | we're at ~40TB of aligned reads and the S3 bill is out of hand. should we be storing BAM or CRAM, and what do we lose by switching? |

### Should not trigger

| # | Prompt | Better fit |
|---|--------|-----------|
| 1 | write a python parser for the tab-delimited file our sequencer's LIMS exports, with type hints and a small CLI | `modern-python-development` |
| 2 | add pytest fixtures for the FastAPI routes that serve our variant browser | `pytest-best-practices` |
| 3 | how do I write a Nextflow DSL2 process with a dynamic output glob and an optional channel? | Nextflow docs — workflow-language authoring is explicitly out of scope (see the open question below) |
| 4 | design the Postgres schema for tracking samples, sequencing runs, and their QC status | `postgres-best-practices` |
| 5 | our GitHub Actions job on the genomics repo keeps timing out while downloading the reference genome | `gha-diagnosis` |
| 6 | review this PR — it refactors the variant filtering panel in our React dashboard | `pr-review` |

Open question for maintainers: eval 3 above is a deliberate near-miss under the
current scope. If `references/workflow-frameworks.md` (Nextflow DSL2 / Snakemake
skeletons) and `references/variant-calling.md` (DeepVariant, GATK, Mutect2
commands and QC thresholds) are ever added, move it to the should-trigger table
and widen the description accordingly.
