# Contributing to the documentation

## MkDocs

Install with pip using `requirements_dev.txt` in the above directory :

    pip install -r requirements_dev.txt

For full documentation visit [mkdocs.org](https://mkdocs.org).

## Commands

* `mkdocs serve` - Start the live-reloading docs server.
* `mkdocs build` - Build the documentation site.
* `mkdocs help` - Print this help message.

## Activated Markdown Extensions

- abbr
- admonition
- footnotes
- sane_lists
- smarty
- codehilite
- toc
- mdx_bib

### Abbreviations

    The HTML specification
    is maintained by the W3C.

    *[HTML]: Hyper Text Markup Language
    *[W3C]:  World Wide Web Consortium

### Admonition

Render some text in a coloured box.

    !!! note This is a note
        
        Lorem ipsum ...

Allowed admonition types :

- note, tip
- abstract, summary
- info
- example
- success
- failure
- warning
- danger
- bug

### Footnotes

    Footnotes[^1] have a label and the footnote's content[^2].

    [^1]: This is a footnote content.
    [^2]:
        Footnote content
        can spread over multiple lines
        using an indented block

### Citing with MdxBib

Include references between brackets, using BibTeX citekey prefixed with `@`.

Make sure to add your references into `bibliography.bib`,
which is a BibTeX database.

    The Feature Aggregation algorihtm is based on Hubert's segmentation procedure [@hubert2000].
    For a dynamic progamming implementation [see @kehagias2006].

Multiple citations separated by semi-colon :

    [@hubert2000;@kehagias2006]

Citation at beginning of sentence, in running text :

    [+@hallac2018] says ...

Citations can also be defined within the markdown file (not recommended) :

    Some other claim [@other2018].

    [@other2018]: Other, 2018. Among toher things. Intl Pub.

