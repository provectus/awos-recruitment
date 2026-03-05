---
name: building-genomics-pipelines
description: This skill should be used when the user asks to "build a genomics pipeline", "call variants", "analyze RNA-seq", "run ChIP-seq analysis", "annotate variants", "QC sequencing data", "detect CNVs", or when writing any bioinformatics pipeline code involving NGS data. Provides expert guidance on pipeline frameworks (Nextflow, Snakemake, WDL), alignment, variant calling, and production-ready nf-core workflows.
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

Example nf-core usage:
```bash
nextflow run nf-core/sarek \
    -profile docker \
    --input samplesheet.csv \
    --genome GRCh38 \
    --tools haplotypecaller,snpeff
```
