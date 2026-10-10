---
name: building-genomics-pipelines
description: This skill should be used when the user asks to "build a genomics pipeline", "pick an nf-core pipeline", "which aligner/variant caller should I use", "analyze RNA-seq", "analyze single-cell RNA-seq", "annotate variants", "interpret variants with ACMG criteria", "detect CNVs", "call structural variants", or when choosing tools, file formats, and QC thresholds for NGS data. Provides opinionated tool defaults (aligners, variant callers, annotators), genomics file-format and reproducibility conventions, an nf-core pipeline selection table, and detailed references for RNA-seq (bulk and single-cell), variant annotation with clinical interpretation, and CNV/SV analysis. It does not teach Nextflow DSL2, Snakemake, or WDL authoring — for writing workflow code by hand, use those frameworks' own documentation.
---

# Genomics Pipeline Skill

## Opinionated Defaults

Use **Nextflow** (nf-core ecosystem) for all new pipelines. For HPC-only environments without container support, use Snakemake instead.

### Alignment
- **DNA short reads**: Use BWA-MEM2
- **RNA-seq**: Use STAR (splice-aware)
- **Long reads** (ONT/PacBio): Use Minimap2

### Variant Calling
- **Germline SNV/indel**: Use DeepVariant (most accurate). GATK HaplotypeCaller if GATK ecosystem is required.
- **Somatic variants**: Use Mutect2 (tumor/normal pairs)
- **Structural variants**: Use Manta (Illumina). Add GRIDSS for complex SVs.

### Annotation
- Use **VEP** (Ensembl) as the primary annotator. Use SnpEff as a lightweight alternative for quick checks.

## File Formats

- **FASTQ**: Raw reads (always gzip compressed: `.fastq.gz`)
- **BAM/CRAM**: Aligned reads — prefer **CRAM** over BAM (30-50% smaller)
- **VCF/BCF**: Variant calls — always use **bgzip** + **tabix** for indexing
- **BED**: Genomic intervals
- **GTF/GFF**: Gene annotations

Always use **indexed** files (`.bai`, `.crai`, `.tbi`, `.csi`). Validate files before downstream analysis.

## Pipeline Design Principles

1. **Reproducibility**: Pin exact tool versions, use containers (Docker/Singularity), track reference genome versions
2. **Scalability**: Design for scatter-gather parallelization, use chunking for large files, implement checkpointing/resume
3. **Quality Control**: QC at every stage (raw, aligned, called), generate MultiQC reports, set clear PASS/FAIL thresholds

## Common Workflows

Determine which workflow type is needed and consult the corresponding reference:

1. **RNA-seq Analysis** — see [references/rnaseq.md](references/rnaseq.md)
2. **Variant Annotation** — see [references/annotation.md](references/annotation.md)
3. **CNV & Structural Variants** — see [references/cnv.md](references/cnv.md)

Everything else — ChIP-seq, ATAC-seq, germline and somatic SNV calling, methylation, metagenomics — is covered by the defaults above plus the nf-core table below: reach for the community pipeline rather than assembling the steps by hand, because those pipelines already wire up the tools this skill recommends and carry their own QC. Hand-writing Nextflow DSL2 processes, Snakemake rules, or WDL tasks is outside this skill; consult the framework's own documentation for syntax.

## nf-core Pipelines

Use these production-ready pipelines instead of building from scratch:

| Pipeline | Use Case |
|----------|----------|
| nf-core/sarek | WGS/WES variant calling |
| nf-core/rnaseq | RNA-seq analysis |
| nf-core/chipseq | ChIP-seq analysis |
| nf-core/atacseq | ATAC-seq analysis |
| nf-core/viralrecon | Viral genome analysis |
| nf-core/mag | Metagenome analysis |
| nf-core/methylseq | Bisulfite sequencing |

Example nf-core usage — the `--tools` values mirror the defaults above (DeepVariant for germline calling, VEP for annotation):
```bash
nextflow run nf-core/sarek \
    -profile docker \
    --input samplesheet.csv \
    --genome GRCh38 \
    --tools deepvariant,vep
```

Escape hatch: `--tools haplotypecaller,snpeff` when the GATK ecosystem is mandated or a lightweight annotator is enough. For somatic work, `--tools mutect2,manta,vep` on a tumor/normal samplesheet.
