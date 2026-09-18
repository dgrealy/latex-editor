# One build configuration for the editor, the command line and CI.
$pdf_mode = 1;              # pdflatex; 4 = lualatex, 5 = xelatex
$out_dir = 'build';
$bibtex_use = 2;
$biber = 'biber %O %S';
$pdflatex = 'pdflatex -interaction=nonstopmode -file-line-error -synctex=1 %O %S';
$clean_ext = 'synctex.gz bbl run.xml glo gls glg nls nlo ist acn acr alg';
