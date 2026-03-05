# CNV and Structural Variant Analysis

## Contents
- Workflow Overview
- CNV Detection Methods
- GATK CNV Pipeline (Germline, Somatic)
- CNVkit (WES-optimized)
- Structural Variant Callers (Manta, DELLY, GRIDSS, LUMPY)
- SV/CNV Merging and Consensus
- CNV/SV Annotation
- Visualization
- Quality Metrics
- nf-core Pipelines
- Interpretation Guidelines

## Workflow Overview

```
BAM → Coverage/Read-pairs → CNV/SV Calling → Filtering → Annotation → Visualization
```

## CNV Detection Methods

| Method | Best For | Tools |
|--------|----------|-------|
| Read depth | Large CNVs (>1kb) | GATK, CNVkit, cn.MOPS |
| Read pairs | SVs, translocations | Manta, DELLY, GRIDSS |
| Split reads | Precise breakpoints | LUMPY, DELLY |
| Assembly | Complex SVs | GRIDSS, SvABA |
| Combined | Best sensitivity | Manta + read depth |

## GATK CNV Pipeline

### Germline CNV (gCNV) - Cohort Mode

Best for WES with 30+ samples in cohort.

```bash
# 1. Collect read counts
gatk CollectReadCounts \
    -I sample.bam \
    -L targets.interval_list \
    --interval-merging-rule OVERLAPPING_ONLY \
    -O sample.counts.hdf5

# 2. Annotate intervals with GC content
gatk AnnotateIntervals \
    -R reference.fa \
    -L targets.interval_list \
    --interval-merging-rule OVERLAPPING_ONLY \
    -O annotated_intervals.tsv

# 3. Filter intervals (remove low-mappability)
gatk FilterIntervals \
    -L targets.interval_list \
    --annotated-intervals annotated_intervals.tsv \
    -I sample1.counts.hdf5 \
    -I sample2.counts.hdf5 \
    -I sample3.counts.hdf5 \
    --minimum-gc-content 0.1 \
    --maximum-gc-content 0.9 \
    --minimum-mappability 0.9 \
    --maximum-segmental-duplication-content 0.5 \
    -O filtered_intervals.interval_list

# 4. Determine contig ploidy
gatk DetermineGermlineContigPloidy \
    -L filtered_intervals.interval_list \
    --interval-merging-rule OVERLAPPING_ONLY \
    -I sample1.counts.hdf5 \
    -I sample2.counts.hdf5 \
    -I sample3.counts.hdf5 \
    --contig-ploidy-priors ploidy_priors.tsv \
    --output ploidy_output \
    --output-prefix ploidy

# 5. Run gCNV in cohort mode
gatk GermlineCNVCaller \
    --run-mode COHORT \
    -L filtered_intervals.interval_list \
    -I sample1.counts.hdf5 \
    -I sample2.counts.hdf5 \
    -I sample3.counts.hdf5 \
    --contig-ploidy-calls ploidy_output/ploidy-calls \
    --annotated-intervals annotated_intervals.tsv \
    --interval-merging-rule OVERLAPPING_ONLY \
    --output cohort_output \
    --output-prefix cohort

# 6. Postprocess calls for each sample
gatk PostprocessGermlineCNVCalls \
    --model-shard-path cohort_output/cohort-model \
    --calls-shard-path cohort_output/cohort-calls \
    --allosomal-contig chrX \
    --allosomal-contig chrY \
    --contig-ploidy-calls ploidy_output/ploidy-calls \
    --sample-index 0 \
    --output-genotyped-intervals sample1_intervals.vcf.gz \
    --output-genotyped-segments sample1_segments.vcf.gz \
    --output-denoised-copy-ratios sample1_denoised_cr.tsv
```

### Somatic CNV (GATK Best Practices)

For tumor/normal pairs or tumor-only analysis.

```bash
# 1. Create Panel of Normals (PoN) - run on each normal sample
gatk CollectReadCounts \
    -I normal.bam \
    -L targets.interval_list \
    --interval-merging-rule OVERLAPPING_ONLY \
    -O normal.counts.hdf5

# 2. Create PoN
gatk CreateReadCountPanelOfNormals \
    -I normal1.counts.hdf5 \
    -I normal2.counts.hdf5 \
    -I normal3.counts.hdf5 \
    --minimum-interval-median-percentile 5.0 \
    -O cnv_pon.hdf5

# 3. Collect tumor read counts
gatk CollectReadCounts \
    -I tumor.bam \
    -L targets.interval_list \
    --interval-merging-rule OVERLAPPING_ONLY \
    -O tumor.counts.hdf5

# 4. Denoise read counts
gatk DenoiseReadCounts \
    -I tumor.counts.hdf5 \
    --count-panel-of-normals cnv_pon.hdf5 \
    --standardized-copy-ratios tumor.standardizedCR.tsv \
    --denoised-copy-ratios tumor.denoisedCR.tsv

# 5. Collect allelic counts (for BAF)
gatk CollectAllelicCounts \
    -I tumor.bam \
    -R reference.fa \
    -L common_snps.interval_list \
    -O tumor.allelicCounts.tsv

# Optional: matched normal allelic counts
gatk CollectAllelicCounts \
    -I normal.bam \
    -R reference.fa \
    -L common_snps.interval_list \
    -O normal.allelicCounts.tsv

# 6. Model segments
gatk ModelSegments \
    --denoised-copy-ratios tumor.denoisedCR.tsv \
    --allelic-counts tumor.allelicCounts.tsv \
    --normal-allelic-counts normal.allelicCounts.tsv \
    --output-prefix tumor \
    -O segments_output/

# 7. Call copy ratio segments
gatk CallCopyRatioSegments \
    -I segments_output/tumor.cr.seg \
    -O segments_output/tumor.called.seg

# 8. Plot results
gatk PlotDenoisedCopyRatios \
    --standardized-copy-ratios tumor.standardizedCR.tsv \
    --denoised-copy-ratios tumor.denoisedCR.tsv \
    --sequence-dictionary reference.dict \
    --output-prefix tumor \
    -O plots/

gatk PlotModeledSegments \
    --denoised-copy-ratios tumor.denoisedCR.tsv \
    --allelic-counts segments_output/tumor.hets.tsv \
    --segments segments_output/tumor.modelFinal.seg \
    --sequence-dictionary reference.dict \
    --output-prefix tumor \
    -O plots/
```

## CNVkit (WES-optimized)

### Basic Pipeline

```bash
# Full pipeline (tumor with matched normal)
cnvkit.py batch tumor.bam \
    --normal normal.bam \
    --targets targets.bed \
    --annotate refFlat.txt \
    --fasta reference.fa \
    --access access-5k-mappable.bed \
    --output-reference my_reference.cnn \
    --output-dir results/ \
    --diagram --scatter

# With panel of normals
cnvkit.py batch tumor.bam \
    --reference pon_reference.cnn \
    --output-dir results/ \
    --diagram --scatter

# Tumor-only (use flat reference)
cnvkit.py batch tumor.bam \
    --normal \
    --targets targets.bed \
    --fasta reference.fa \
    --access access-5k-mappable.bed \
    --output-dir results/
```

### Step-by-Step CNVkit

```bash
# 1. Generate target and antitarget BED files
cnvkit.py target targets.bed --annotate refFlat.txt -o targets.target.bed
cnvkit.py antitarget targets.bed -g access.bed -o targets.antitarget.bed

# 2. Calculate coverage for each sample
cnvkit.py coverage tumor.bam targets.target.bed -o tumor.targetcoverage.cnn
cnvkit.py coverage tumor.bam targets.antitarget.bed -o tumor.antitargetcoverage.cnn
cnvkit.py coverage normal.bam targets.target.bed -o normal.targetcoverage.cnn
cnvkit.py coverage normal.bam targets.antitarget.bed -o normal.antitargetcoverage.cnn

# 3. Build reference from normals
cnvkit.py reference normal*.targetcoverage.cnn normal*.antitargetcoverage.cnn \
    --fasta reference.fa \
    -o reference.cnn

# 4. Normalize and segment
cnvkit.py fix tumor.targetcoverage.cnn tumor.antitargetcoverage.cnn reference.cnn \
    -o tumor.cnr

cnvkit.py segment tumor.cnr -o tumor.cns

# 5. Call CNVs
cnvkit.py call tumor.cns -o tumor.call.cns

# 6. Visualization
cnvkit.py scatter tumor.cnr -s tumor.cns -o tumor_scatter.png
cnvkit.py diagram tumor.cnr -s tumor.cns -o tumor_diagram.pdf
cnvkit.py heatmap *.cns -o heatmap.pdf
```

### CNVkit with B-allele Frequency

```bash
# Call variants for BAF
bcftools mpileup -f reference.fa tumor.bam | \
    bcftools call -mv -Oz -o tumor_variants.vcf.gz

# Segment with BAF
cnvkit.py segment tumor.cnr \
    --vcf tumor_variants.vcf.gz \
    --sample-id TUMOR \
    -o tumor.cns

# Call with purity/ploidy estimation
cnvkit.py call tumor.cns \
    --vcf tumor_variants.vcf.gz \
    --sample-id TUMOR \
    --purity 0.7 \
    --ploidy 2 \
    -o tumor.call.cns
```

## Structural Variant Callers

### Manta (Illumina recommended)

```bash
# Configure
configManta.py \
    --normalBam normal.bam \
    --tumorBam tumor.bam \
    --referenceFasta reference.fa \
    --runDir manta_output

# Run
manta_output/runWorkflow.py -j 8

# Output files:
# - candidateSV.vcf.gz (all candidates)
# - candidateSmallIndels.vcf.gz (indels for Strelka)
# - diploidSV.vcf.gz (germline SVs)
# - somaticSV.vcf.gz (somatic SVs)

# Germline-only mode
configManta.py \
    --bam sample.bam \
    --referenceFasta reference.fa \
    --runDir manta_germline
```

### DELLY

```bash
# Call SVs (all types)
delly call -g reference.fa -o sv.bcf sample.bam

# With exclusion regions
delly call -g reference.fa -x excludeTemplates.tsv -o sv.bcf sample.bam

# Somatic SVs (tumor/normal)
delly call -g reference.fa -o sv.bcf tumor.bam normal.bam

delly filter -f somatic -o somatic.sv.bcf -s samples.tsv sv.bcf

# Genotype SVs in cohort
delly call -g reference.fa -v sv.bcf -o geno.bcf sample1.bam sample2.bam

# CNV calling with DELLY
delly cnv -g reference.fa -m mappability.map -o cnv.bcf sample.bam
```

### GRIDSS (Assembly-based)

```bash
# Run GRIDSS
gridss \
    --reference reference.fa \
    --output sv.vcf.gz \
    --assembly assembly.bam \
    --threads 8 \
    --jvmheap 31g \
    --workingdir gridss_work/ \
    tumor.bam normal.bam

# Somatic filtering
gridss_somatic_filter \
    --input sv.vcf.gz \
    --output somatic.sv.vcf.gz \
    --fulloutput full.sv.vcf.gz \
    --scriptdir /path/to/gridss/ \
    -n 1 -t 2  # normal index, tumor index
```

## SV/CNV Merging and Consensus

### SURVIVOR (Merge SV calls)

```bash
# Create list of VCF files
ls manta.vcf delly.vcf gridss.vcf > vcf_list.txt

# Merge calls (max distance 1000bp, min 2 callers, same type, same strand)
SURVIVOR merge vcf_list.txt 1000 2 1 1 0 50 merged.vcf

# Filter by size
SURVIVOR filter merged.vcf NA 50 -1 0 -1 filtered.vcf
```

### Jasmine (SV merging with population support)

```bash
jasmine \
    file_list=vcf_list.txt \
    out_file=merged.vcf \
    max_dist=500 \
    min_support=2 \
    spec_reads=3 \
    threads=8
```

## CNV/SV Annotation

### AnnotSV

```bash
# Annotate SVs/CNVs
AnnotSV -SVinputFile sv.vcf \
    -genomeBuild GRCh38 \
    -outputFile annotated_sv \
    -svtBEDcol 5

# Output includes:
# - Gene overlaps
# - DGV (Database of Genomic Variants)
# - gnomAD-SV frequencies
# - Clinical databases (ClinVar, ClinGen)
# - ACMG classification
```

### ClassifyCNV

```bash
# ACMG-based CNV classification
ClassifyCNV --infile cnv.bed \
    --GenomeBuild hg38 \
    --outdir classification/
```

### VEP for SVs

```bash
vep -i sv.vcf \
    --cache \
    --offline \
    --assembly GRCh38 \
    --plugin StructuralVariantOverlap,file=gnomad_sv.vcf.gz \
    --custom clinvar.vcf.gz,ClinVar,vcf,exact,0,CLNSIG \
    -o sv.annotated.vcf
```

## Visualization

### IGV Batch Visualization

```bash
# Create IGV batch script
cat << 'EOF' > igv_batch.txt
new
genome hg38
load tumor.bam
load normal.bam
load cnv.seg
snapshotDirectory ./snapshots
goto chr1:1000000-2000000
snapshot region1.png
goto chr17:7500000-7700000
snapshot TP53_region.png
EOF

# Run IGV
igv.sh -b igv_batch.txt
```

## Quality Metrics

### CNV Quality Indicators

| Metric | Good | Concern |
|--------|------|---------|
| Median absolute deviation | <0.3 | >0.5 |
| Segment count | <500 | >1000 (noisy) |
| Median segment size | >100kb | <50kb |
| Log2 ratio noise | <0.2 | >0.4 |

### SV Quality Filters

```bash
# Filter high-confidence SVs
bcftools filter -i '
    FILTER="PASS" &&
    INFO/PE >= 3 &&
    INFO/SR >= 1 &&
    INFO/SVLEN >= 50
' sv.vcf > sv.filtered.vcf
```

## nf-core Pipelines

```bash
# nf-core/sarek includes SV calling
nextflow run nf-core/sarek \
    -profile docker \
    --input samplesheet.csv \
    --genome GRCh38 \
    --tools manta,tiddit,cnvkit

# Standalone CNV pipeline
nextflow run nf-core/copynumber \
    -profile docker \
    --input samplesheet.csv \
    --genome GRCh38
```

## Interpretation Guidelines

### CNV Classification (ACMG/ClinGen)

| Category | Criteria |
|----------|----------|
| Pathogenic | Contains known pathogenic gene, >3Mb with protein-coding genes |
| Likely Pathogenic | 2-3 supporting evidence points |
| VUS | Insufficient evidence |
| Likely Benign | Common in population (>1%), no gene impact |
| Benign | Very common (>5%), well-documented benign |

### Key Databases

| Database | Content |
|----------|---------|
| gnomAD-SV | Population SV frequencies |
| DGV | Database of Genomic Variants |
| ClinGen | Gene/region dosage sensitivity |
| DECIPHER | Clinical CNV database |
| dbVar | NCBI SV database |

## Common Issues

1. **High noise in WES CNV**: Use larger bin sizes, better PoN
2. **False positive deletions**: Check mappability, segmental duplications
3. **Missed small CNVs**: Increase coverage, use multiple callers
4. **Breakpoint imprecision**: Add assembly-based caller (GRIDSS)
5. **Batch effects**: Build PoN from same capture kit/batch
