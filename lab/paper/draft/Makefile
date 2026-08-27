# Requires a LaTeX toolchain (pdflatex + bibtex, or tectonic).
# Not available in the dev container this draft was written in -- see README.md.
PAPER = main

all: $(PAPER).pdf

$(PAPER).pdf: $(PAPER).tex refs.bib
	pdflatex -interaction=nonstopmode $(PAPER).tex
	bibtex $(PAPER) || true
	pdflatex -interaction=nonstopmode $(PAPER).tex
	pdflatex -interaction=nonstopmode $(PAPER).tex

tectonic:
	tectonic $(PAPER).tex

clean:
	rm -f $(PAPER).aux $(PAPER).bbl $(PAPER).blg $(PAPER).log $(PAPER).out $(PAPER).pdf
