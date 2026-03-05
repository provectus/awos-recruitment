# RNA-seq Analysis Pipeline

## Workflow Overview

### Bulk RNA-seq
```
FASTQ → QC → Alignment/Quantification → Normalization → Differential Expression → Pathway Analysis
```

### Single-cell RNA-seq
```
FASTQ → Cell Ranger/STARsolo → QC → Normalization → Clustering → Annotation → Trajectory
```

## Bulk RNA-seq Pipeline

### 1. Quality Control

```bash
# FastQC
fastqc -t 8 -o qc_raw/ *.fastq.gz

# Trim adapters (if needed)
trim_galore --paired --fastqc \
    -o trimmed/ \
    sample_R1.fastq.gz sample_R2.fastq.gz

# Or use fastp
fastp -i R1.fq.gz -I R2.fq.gz \
    -o R1.trimmed.fq.gz -O R2.trimmed.fq.gz \
    --detect_adapter_for_pe \
    --thread 8 \
    --html fastp.html --json fastp.json
```

### 2. Alignment Options

#### Option A: STAR + featureCounts (Traditional)

```bash
# Build STAR index
STAR --runMode genomeGenerate \
    --runThreadN 16 \
    --genomeDir star_index \
    --genomeFastaFiles genome.fa \
    --sjdbGTFfile genes.gtf \
    --sjdbOverhang 100

# Align
STAR --runThreadN 16 \
    --genomeDir star_index \
    --readFilesIn sample_R1.fq.gz sample_R2.fq.gz \
    --readFilesCommand zcat \
    --outFileNamePrefix sample_ \
    --outSAMtype BAM SortedByCoordinate \
    --outSAMunmapped Within \
    --quantMode GeneCounts \
    --twopassMode Basic

# Count reads (alternative to STAR GeneCounts)
featureCounts -T 8 \
    -p --countReadPairs \
    -t exon \
    -g gene_id \
    -a genes.gtf \
    -o counts.txt \
    *.bam
```

#### Option B: Salmon (Pseudo-alignment, Faster)

```bash
# Build Salmon index
salmon index -t transcripts.fa -i salmon_index -k 31

# Quantify
salmon quant -i salmon_index \
    -l A \
    -1 sample_R1.fq.gz \
    -2 sample_R2.fq.gz \
    -p 8 \
    --validateMappings \
    -o salmon_quant/sample
```

#### Option C: kallisto (Ultra-fast)

```bash
# Build index
kallisto index -i kallisto_idx transcripts.fa

# Quantify
kallisto quant -i kallisto_idx \
    -o kallisto_out/sample \
    -t 8 \
    sample_R1.fq.gz sample_R2.fq.gz
```

### 3. Differential Expression Analysis (R)

#### DESeq2 (Recommended for most cases)

```r
library(DESeq2)
library(tximport)

# Import Salmon counts
files <- file.path("salmon_quant", samples, "quant.sf")
names(files) <- samples
txi <- tximport(files, type = "salmon", tx2gene = tx2gene)

# Create DESeq2 object
dds <- DESeqDataSetFromTximport(txi,
                                 colData = sample_info,
                                 design = ~ condition)

# Filter low counts
keep <- rowSums(counts(dds) >= 10) >= 3
dds <- dds[keep,]

# Run DESeq2
dds <- DESeq(dds)

# Get results
res <- results(dds, contrast = c("condition", "treatment", "control"))
res <- lfcShrink(dds, coef = "condition_treatment_vs_control", type = "apeglm")

# Filter significant genes
sig_genes <- subset(res, padj < 0.05 & abs(log2FoldChange) > 1)

# Export results
write.csv(as.data.frame(res), "deseq2_results.csv")
```

#### edgeR (Good for complex designs)

```r
library(edgeR)

# Create DGEList
y <- DGEList(counts = count_matrix, group = condition)

# Filter
keep <- filterByExpr(y)
y <- y[keep, , keep.lib.sizes = FALSE]

# Normalize
y <- calcNormFactors(y)

# Design matrix
design <- model.matrix(~ condition)

# Estimate dispersion
y <- estimateDisp(y, design)

# Fit model
fit <- glmQLFit(y, design)
qlf <- glmQLFTest(fit, coef = 2)

# Get results
topTags(qlf, n = Inf)
```

#### limma-voom (Fast, good for large datasets)

```r
library(limma)
library(edgeR)

# Create DGEList and normalize
dge <- DGEList(counts = count_matrix)
dge <- calcNormFactors(dge)

# Design matrix
design <- model.matrix(~ condition)

# Voom transformation
v <- voom(dge, design, plot = TRUE)

# Fit linear model
fit <- lmFit(v, design)
fit <- eBayes(fit)

# Get results
topTable(fit, coef = 2, n = Inf)
```

### 4. Visualization

```r
library(ggplot2)
library(pheatmap)
library(EnhancedVolcano)

# PCA plot
vsd <- vst(dds, blind = FALSE)
plotPCA(vsd, intgroup = "condition")

# Volcano plot
EnhancedVolcano(res,
    lab = rownames(res),
    x = 'log2FoldChange',
    y = 'pvalue',
    pCutoff = 0.05,
    FCcutoff = 1)

# Heatmap of top genes
top_genes <- head(order(res$padj), 50)
pheatmap(assay(vsd)[top_genes,],
         cluster_rows = TRUE,
         cluster_cols = TRUE,
         scale = "row",
         annotation_col = sample_info)

# MA plot
plotMA(res, ylim = c(-5, 5))
```

### 5. Pathway Analysis

```r
library(clusterProfiler)
library(org.Hs.eg.db)
library(enrichplot)

# Convert gene symbols to Entrez IDs
gene_list <- bitr(sig_genes$gene_symbol,
                  fromType = "SYMBOL",
                  toType = "ENTREZID",
                  OrgDb = org.Hs.eg.db)

# GO enrichment
go_bp <- enrichGO(gene = gene_list$ENTREZID,
                  OrgDb = org.Hs.eg.db,
                  ont = "BP",
                  pAdjustMethod = "BH",
                  pvalueCutoff = 0.05)

# KEGG pathway
kegg <- enrichKEGG(gene = gene_list$ENTREZID,
                   organism = 'hsa',
                   pvalueCutoff = 0.05)

# GSEA (requires ranked gene list)
gene_ranks <- res$log2FoldChange
names(gene_ranks) <- rownames(res)
gene_ranks <- sort(gene_ranks, decreasing = TRUE)

gsea_result <- gseGO(geneList = gene_ranks,
                     OrgDb = org.Hs.eg.db,
                     ont = "BP",
                     minGSSize = 10,
                     maxGSSize = 500,
                     pvalueCutoff = 0.05)

# Visualize
dotplot(go_bp, showCategory = 20)
cnetplot(go_bp, categorySize = "pvalue")
```

## Single-cell RNA-seq Pipeline

### Cell Ranger (10x Genomics)

```bash
# Run Cell Ranger count
cellranger count --id=sample \
    --transcriptome=/ref/refdata-gex-GRCh38-2024-A \
    --fastqs=/data/fastqs \
    --sample=sample \
    --localcores=16 \
    --localmem=64

# Aggregate multiple samples
cellranger aggr --id=aggregated \
    --csv=aggregation.csv \
    --normalize=mapped
```

### Seurat Analysis (R)

```r
library(Seurat)
library(dplyr)

# Load data
data <- Read10X(data.dir = "filtered_feature_bc_matrix/")
seurat <- CreateSeuratObject(counts = data, project = "project", min.cells = 3, min.features = 200)

# QC metrics
seurat[["percent.mt"]] <- PercentageFeatureSet(seurat, pattern = "^MT-")
VlnPlot(seurat, features = c("nFeature_RNA", "nCount_RNA", "percent.mt"))

# Filter cells
seurat <- subset(seurat,
                 subset = nFeature_RNA > 200 &
                          nFeature_RNA < 5000 &
                          percent.mt < 20)

# Normalize
seurat <- NormalizeData(seurat)
seurat <- FindVariableFeatures(seurat, selection.method = "vst", nfeatures = 2000)

# Scale and PCA
seurat <- ScaleData(seurat)
seurat <- RunPCA(seurat, features = VariableFeatures(seurat))
ElbowPlot(seurat)

# Clustering
seurat <- FindNeighbors(seurat, dims = 1:20)
seurat <- FindClusters(seurat, resolution = 0.5)

# UMAP
seurat <- RunUMAP(seurat, dims = 1:20)
DimPlot(seurat, reduction = "umap", label = TRUE)

# Find markers
markers <- FindAllMarkers(seurat, only.pos = TRUE, min.pct = 0.25, logfc.threshold = 0.25)
top_markers <- markers %>% group_by(cluster) %>% slice_max(n = 5, order_by = avg_log2FC)

# Cell type annotation (manual or automated)
new.cluster.ids <- c("T cells", "B cells", "Monocytes", ...)
names(new.cluster.ids) <- levels(seurat)
seurat <- RenameIdents(seurat, new.cluster.ids)
```

### Scanpy Analysis (Python)

```python
import scanpy as sc
import numpy as np

# Load data
adata = sc.read_10x_mtx('filtered_feature_bc_matrix/')

# QC
sc.pp.filter_cells(adata, min_genes=200)
sc.pp.filter_genes(adata, min_cells=3)
adata.var['mt'] = adata.var_names.str.startswith('MT-')
sc.pp.calculate_qc_metrics(adata, qc_vars=['mt'], inplace=True)

# Filter
adata = adata[adata.obs.n_genes_by_counts < 5000, :]
adata = adata[adata.obs.pct_counts_mt < 20, :]

# Normalize
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)

# Variable genes
sc.pp.highly_variable_genes(adata, n_top_genes=2000)
adata.raw = adata
adata = adata[:, adata.var.highly_variable]

# Scale and PCA
sc.pp.scale(adata, max_value=10)
sc.tl.pca(adata, svd_solver='arpack')

# Neighbors and clustering
sc.pp.neighbors(adata, n_neighbors=10, n_pcs=40)
sc.tl.umap(adata)
sc.tl.leiden(adata, resolution=0.5)

# Visualization
sc.pl.umap(adata, color='leiden')

# Marker genes
sc.tl.rank_genes_groups(adata, 'leiden', method='wilcoxon')
sc.pl.rank_genes_groups(adata, n_genes=10)
```

## nf-core/rnaseq Pipeline

```bash
nextflow run nf-core/rnaseq \
    -profile docker \
    --input samplesheet.csv \
    --genome GRCh38 \
    --aligner star_salmon \
    --pseudo_aligner salmon

# Samplesheet format:
# sample,fastq_1,fastq_2,strandedness
# sample1,s1_R1.fq.gz,s1_R2.fq.gz,auto
```

## Quality Metrics

| Metric | Good Value | Concern |
|--------|------------|---------|
| Total reads | >20M | <10M |
| Mapping rate | >80% | <70% |
| Uniquely mapped | >70% | <60% |
| Exonic rate | >60% | <40% |
| rRNA rate | <10% | >20% |
| Duplication rate | <50% | >70% |
| Gene detection | >15,000 | <10,000 |
| 5'/3' bias | 0.8-1.2 | >2 or <0.5 |

## Common Issues

1. **Batch effects**: Use ComBat or include batch in model
2. **Low mapping rate**: Check rRNA contamination, wrong reference
3. **High duplication**: Low input, over-amplification
4. **Few DE genes**: Low power, high variability, biology
5. **Strand-specificity issues**: Check library prep protocol
