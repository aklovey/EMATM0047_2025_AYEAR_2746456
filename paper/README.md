# Dissertation LaTeX sources

This directory contains the active editable sources for the eight-chapter manuscript snapshot of **14 September 2026**. It includes the current system-exploration chapter, the final local-review changes, the shortened list-of-tables entries and the contents spacing adjustment. The compiled thesis PDF is not included in the repository.

Compile `main.tex` with pdfLaTeX and BibTeX, or import this directory into Overleaf. The original school `dissertation.cls`, Computer Modern typography, two-sided chapter starts, logo and existing figure assets are retained. `main.tex` explicitly selects the supplied `causeplain.bst` bibliography style. More than three authors or editors are displayed as the first three names followed by *et al.*; their full metadata remains in `references.bib`.

The main text contains eight numbered chapters. The checked local compilation contains 27 body pages from Introduction through Conclusion and 17 numbered bibliography entries. Its 49 physical PDF pages also include front matter, the school template's verso spacers, bibliography and appendix. Compilation products were generated outside the repository and are not distributed here.

`main.tex` uses twelve chapter/front-matter input files. `system_exploration.tex` supplies Chapter 6, `chapter_6.tex` supplies Chapter 7, and `chapter_7.tex` supplies Chapter 8. The filenames retained from earlier drafts do not determine the displayed chapter numbers. An unused `front_support.tex`, if present, is not included by this manuscript.

The [evidence guide](../docs/EVIDENCE.md) maps the current studies to repository materials. The [system-exploration source register](../supplement/system_exploration/source_register.json) identifies the historical run reports, accounting records and code excerpts. The [figure directory](../figures/) provides editable diagrams and plotting sources, while `paper/figures/` contains the existing graphics included by LaTeX. Current experiment data and outputs are under [experiment/](../experiment/).
