# Variant Annotation Pipeline

## Contents
- Workflow Overview
- Versions and Databases (how to pick current releases)
- Variant Normalization
- VEP (cache setup, basic annotation, plugins, Docker)
- SnpEff and SnpSift
- ANNOVAR (database download, table annotation)
- Key Annotation Databases (population, functional prediction, clinical)
- Filtering Strategies (rare disease, cancer)
- Clinical Interpretation (ACMG evidence codes, InterVar)
- Variant Prioritization Tools (GEMINI, bcftools)
- Output Formats
- Best Practices

## Workflow Overview

```
VCF → Normalization → Functional Annotation → Population Frequencies → Clinical Databases → Filtering → Interpretation
```

## Versions and Databases

Annotation resources move faster than this file does, so treat every version string below as a placeholder and resolve the current one before running anything. Pin the resolved version in the pipeline (a re-run must reproduce the same calls) and record it in the run manifest.

| Resource | Where to find the current release |
|----------|-----------------------------------|
| VEP + cache | `hub.docker.com/r/ensemblorg/ensembl-vep/tags`; cache release must match the VEP version |
| SnpEff database | `snpEff databases \| grep GRCh38` |
| ANNOVAR databases | `annotate_variation.pl -buildver hg38 -downdb -webfrom annovar avdblist humandb/` |
| ClinVar | Re-download monthly — it is the fastest-moving database here |
| gnomAD | `gnomad.broadinstitute.org` — check for a newer major release |
| dbNSFP, CADD, SpliceAI, AlphaMissense | The plugin's own release page; the file name encodes the version |

Placeholders used below: `<RELEASE>` (VEP/Ensembl release, e.g. `116.2`), `<YYYYMMDD>` (ClinVar snapshot date), `<NN>` (a database's major/minor version digits).

## Variant Normalization

Always normalize variants before annotation:

```bash
# Decompose multi-allelic variants and normalize
bcftools norm -m -both -f reference.fa input.vcf.gz | \
    bcftools norm -d exact - | \
    bgzip > normalized.vcf.gz
tabix -p vcf normalized.vcf.gz

# Or use vt
vt decompose -s input.vcf.gz | \
    vt normalize -r reference.fa - | \
    bgzip > normalized.vcf.gz
```

## VEP (Ensembl Variant Effect Predictor)

### Installation and Cache Setup

```bash
# Install VEP
git clone https://github.com/Ensembl/ensembl-vep.git
cd ensembl-vep
perl INSTALL.pl

# Download cache (GRCh38)
perl INSTALL.pl -a cf -s homo_sapiens -y GRCh38

# Download plugins
perl INSTALL.pl -a p --PLUGINS all
```

### Basic Annotation

```bash
vep -i input.vcf.gz \
    --cache \
    --offline \
    --assembly GRCh38 \
    --fork 4 \
    --vcf \
    --everything \
    --output_file annotated.vcf
```

### Comprehensive Annotation with Plugins

```bash
vep -i input.vcf.gz \
    --cache \
    --offline \
    --assembly GRCh38 \
    --fork 8 \
    --vcf \
    --force_overwrite \
    --output_file annotated.vcf \
    \
    # Basic annotations
    --sift b \
    --polyphen b \
    --ccds \
    --hgvs \
    --symbol \
    --numbers \
    --domains \
    --regulatory \
    --canonical \
    --protein \
    --biotype \
    --tsl \
    --appris \
    --gene_phenotype \
    --af \
    --af_1kg \
    --af_gnomade \
    --af_gnomadg \
    --max_af \
    --pubmed \
    --variant_class \
    --mane \
    \
    # Plugins
    --plugin CADD,whole_genome_SNVs.tsv.gz,gnomad.genomes.r3.0.indel.tsv.gz \
    --plugin SpliceAI,snv=spliceai_scores.masked.snv.hg38.vcf.gz,indel=spliceai_scores.masked.indel.hg38.vcf.gz \
    --plugin AlphaMissense,file=AlphaMissense_hg38.tsv.gz \
    --plugin REVEL,file=revel_scores.tsv.gz \
    --plugin dbNSFP,dbNSFP<NN>a_grch38.gz,ALL \
    --plugin ClinVar,clinvar.vcf.gz \
    --plugin gnomADc,gnomad.v<NN>.constraint.txt \
    --plugin LoFtool \
    --plugin MaxEntScan,/path/to/maxentscan \
    --plugin Mastermind,mastermind.vcf.gz
```

### VEP Docker

Always pin an explicit `release_*` tag — `:latest` silently changes the transcript set under a running pipeline. Resolve `<RELEASE>` from the tag list in [Versions and Databases](#versions-and-databases).

```bash
docker run -v $PWD:/data ensemblorg/ensembl-vep:release_<RELEASE> \
    vep -i /data/input.vcf.gz \
    --cache \
    --dir_cache /data/vep_cache \
    --assembly GRCh38 \
    --vcf \
    --everything \
    -o /data/annotated.vcf
```

## SnpEff

### Basic Usage

```bash
# Download database
snpEff download -v GRCh38.105

# Annotate
snpEff -Xmx8g \
    -v GRCh38.105 \
    -csvStats stats.csv \
    -htmlStats stats.html \
    input.vcf > annotated.vcf

# With additional annotations
snpEff -Xmx8g \
    -v GRCh38.105 \
    -canon \
    -hgvs \
    -lof \
    -nodownload \
    input.vcf > annotated.vcf
```

### SnpSift for Database Annotation

```bash
# ClinVar annotation
SnpSift annotate clinvar.vcf.gz annotated.vcf > annotated.clinvar.vcf

# dbSNP annotation
SnpSift annotate dbsnp.vcf.gz annotated.vcf > annotated.dbsnp.vcf

# gnomAD annotation
SnpSift annotate gnomad.exomes.vcf.gz annotated.vcf > annotated.gnomad.vcf

# Filter by impact
SnpSift filter "(ANN[*].IMPACT = 'HIGH')" annotated.vcf > high_impact.vcf
```

## ANNOVAR

### Database Download

ANNOVAR database keywords carry their version in the name, so list what is
currently published before downloading — a stale keyword fails silently with an
empty annotation column rather than an error.

```bash
# List every database ANNOVAR currently ships for this build
annotate_variation.pl -buildver hg38 -downdb -webfrom annovar avdblist humandb/

# Download databases (substitute the current keywords from avdblist;
# clinvar is clinvar_<YYYYMMDD>, dbnsfp is dbnsfp<NN>a academic / dbnsfp<NN>c commercial)
annotate_variation.pl -buildver hg38 -downdb -webfrom annovar refGene humandb/
annotate_variation.pl -buildver hg38 -downdb -webfrom annovar clinvar_<YYYYMMDD> humandb/
annotate_variation.pl -buildver hg38 -downdb -webfrom annovar gnomad<NN>_exome humandb/
annotate_variation.pl -buildver hg38 -downdb -webfrom annovar dbnsfp<NN>a humandb/
annotate_variation.pl -buildver hg38 -downdb -webfrom annovar cadd humandb/
```

### Annotation

```bash
# Convert VCF to ANNOVAR format
convert2annovar.pl -format vcf4 input.vcf > input.avinput

# Table annotation
table_annovar.pl input.avinput humandb/ \
    -buildver hg38 \
    -out annotated \
    -remove \
    -protocol refGene,clinvar_<YYYYMMDD>,gnomad<NN>_exome,dbnsfp<NN>a \
    -operation g,f,f,f \
    -nastring . \
    -vcfinput \
    -polish

# Gene-based annotation only
annotate_variation.pl -geneanno -dbtype refGene \
    -buildver hg38 input.avinput humandb/
```

## Key Annotation Databases

### Population Frequencies
Sizes below describe the release named in each row; check for a newer major
release before choosing a frequency cutoff, since larger callsets shift what
counts as rare.

| Database | Description | Use |
|----------|-------------|-----|
| gnomAD | Largest population callset — v4 covers 730,947 exomes and 76,215 genomes (807,162 individuals) | Filter common variants |
| 1000 Genomes | 2,504 individuals | Population structure |
| ExAC | Legacy, use gnomAD | - |
| TOPMed | 150K+ genomes | Additional filtering |

### Functional Prediction
| Tool | Type | Threshold |
|------|------|-----------|
| SIFT | Protein function | <0.05 deleterious |
| PolyPhen-2 | Protein function | >0.85 probably damaging |
| CADD | Combined | >20 top 1%, >30 top 0.1% |
| REVEL | Ensemble | >0.5 likely pathogenic |
| AlphaMissense | AI-based | >0.564 likely pathogenic |
| SpliceAI | Splice prediction | >0.5 significant |
| LOFTEE | LoF assessment | HC = high confidence |

### Clinical Databases
| Database | Content |
|----------|---------|
| ClinVar | Clinical significance |
| HGMD | Disease mutations (licensed) |
| OMIM | Gene-disease associations |
| UniProt | Protein annotations |
| Mastermind | Literature mining |

## Filtering Strategies

### Rare Disease Filtering (R)

```r
library(vcfR)
library(dplyr)

# Load annotated VCF
vcf <- read.vcfR("annotated.vcf.gz")
variants <- vcfR2tidy(vcf)$fix

# Filter strategy
filtered <- variants %>%
  filter(
    # Rare in population
    gnomAD_AF < 0.001 | is.na(gnomAD_AF),

    # Functional impact
    IMPACT %in% c("HIGH", "MODERATE") |
      CADD_phred > 20 |
      SpliceAI_max > 0.5,

    # Not benign in ClinVar
    !grepl("benign", ClinVar_CLNSIG, ignore.case = TRUE),

    # Quality filters
    FILTER == "PASS",
    DP >= 10
  )
```

### Cancer Filtering

```bash
# Filter somatic variants
bcftools filter -i '
    FILTER="PASS" &&
    INFO/AF >= 0.05 &&
    INFO/DP >= 20 &&
    (INFO/gnomAD_AF < 0.001 || INFO/gnomAD_AF = ".") &&
    (INFO/IMPACT="HIGH" || INFO/IMPACT="MODERATE")
' somatic.annotated.vcf.gz > somatic.filtered.vcf.gz
```

## Clinical Interpretation (ACMG Guidelines)

### Evidence Categories

**Pathogenic (PVS/PS/PM/PP)**
- PVS1: Null variant in gene where LoF is mechanism
- PS1: Same amino acid change as known pathogenic
- PS3: Functional studies support damaging effect
- PM1: Located in critical domain
- PM2: Absent from population databases
- PP3: Multiple computational evidence support
- PP5: Reputable source reports pathogenic

**Benign (BA/BS/BP)**
- BA1: MAF >5% in population database
- BS1: MAF greater than expected for disease
- BS2: Observed in healthy adults
- BP4: Multiple computational evidence suggest benign
- BP6: Reputable source reports benign

### InterVar (Automated ACMG)

```bash
# Run InterVar
python Intervar.py \
    -i input.vcf \
    -o output \
    --input_type VCF \
    -b hg38 \
    -d humandb/ \
    --table_annovar=/path/to/table_annovar.pl
```

## Variant Prioritization Tools

### GEMINI (SQLite database)

```bash
# Load VCF into GEMINI
gemini load -v annotated.vcf.gz -t snpEff gemini.db

# Query for de novo variants
gemini de_novo --columns "chrom,start,ref,alt,gene,impact" gemini.db

# Compound heterozygotes
gemini comp_hets --columns "chrom,start,ref,alt,gene,impact" gemini.db

# Autosomal recessive
gemini autosomal_recessive --columns "chrom,start,ref,alt,gene,impact" gemini.db
```

### VCF Filtering with bcftools

```bash
# High impact variants
bcftools view -i 'INFO/ANN ~ "HIGH"' annotated.vcf.gz

# Rare, damaging variants
bcftools view -i '
    INFO/gnomAD_AF < 0.001 &&
    INFO/CADD_phred > 20 &&
    INFO/FILTER = "PASS"
' annotated.vcf.gz

# Specific gene list
bcftools view -i 'INFO/SYMBOL = "BRCA1" || INFO/SYMBOL = "BRCA2"' annotated.vcf.gz
```

## Output Formats

### Generate Reports

```r
library(knitr)
library(DT)

# Create HTML report
variants_df <- read.csv("annotated_variants.csv")

datatable(variants_df %>%
  select(Gene, Variant, Consequence, gnomAD_AF, CADD, ClinVar, ACMG) %>%
  filter(ACMG %in% c("Pathogenic", "Likely_pathogenic")),
  options = list(pageLength = 25),
  filter = 'top')
```

### Standard Output Files

```
output/
├── annotated.vcf.gz           # Full annotated VCF
├── filtered.vcf.gz            # Filtered candidates
├── variants.tsv               # Tab-separated summary
├── stats.html                 # Annotation statistics
├── clinical_candidates.xlsx   # For clinical review
└── igv_session.xml            # IGV session file
```

## Best Practices

1. **Always normalize variants** before annotation
2. **Use multiple annotation sources** and cross-validate
3. **Document annotation versions** for reproducibility
4. **Apply population-appropriate filters** (ancestry matters)
5. **Review in IGV** before clinical reporting
6. **Follow ACMG guidelines** for clinical interpretation
7. **Update databases regularly** (especially ClinVar)
