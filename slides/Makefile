MD_FILES := $(wildcard *.md)
PDF_FILES := $(patsubst %.md,out/%.pdf,$(MD_FILES))
MD_FILES =  tx_prefetch_buffer.md
all: $(PDF_FILES)

out/%.pdf: %.md
	@mkdir -p out
	pandoc -t beamer -s $<  -o $@

clean:
	rm -f out/*.pdf
