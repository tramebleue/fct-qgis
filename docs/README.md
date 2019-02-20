# Contributing to the documentation

The documentation is built with MkDocs.

## Documenting algorithms

Documentation for algorithms is generated from the YAML metadata.
You should also provide a useful docstring in the Python class
where the algorithm is defined.

What to document in YAML metadata:

1. description of the algorithms

    - `displayName`: label to display in the processing toolbox
    - `group`: algorithm's group id
    - `summary`: a short description of what the algorithm does
    - `description`: a longer description
    - `tags`: a list of (untranslated) tags
    - `parameters`: list of parameter descriptions; see after
    - `example`: (optional) python example
    - `seealso`:
        (optional)
        a list of relevant pointers ;
        designate other algorithm by their class name, eg. AggregateStreamSegments
    - `references`:
        (optional)
        a list of bibliographic reference to include in the doc

2. description of parameters

    - `type`: informative type of parameter
    - `description`: a longer description

    example:

    ```yaml
    INPUT:
      type: LineString(ZM)
      description: |
        Linestrings with identified nodes.
        MutliLineStrings are not supported.
    ```

3. fields for output parameters

    example:

    ```yaml
    OUTPUT:
      type: LineString(ZM)
      description: |
        Aggregated lines
      fields:
        - GID: new unique identifier
        - LENGTH: length of the aggregated line feature
        - $CATEGORY_FIELD: from <code>INPUT</code>
    ```


## MkDocs

### Installing

Install with pip using `requirements_dev.txt` in parent directory :

    pip install -r requirements_dev.txt

For full documentation visit [mkdocs.org](https://mkdocs.org).

### Commands

* `make doc-toc` - Print YAML Table of content to be included in `mkdocs.yml` (when you add a new algorithm)
* `make doc-serve` - Start the live-reloading docs server.
* `make doc-build` - Build the documentation site.
* `make doc-deploy` - Deploy documentation on GitHub Pages.
* `make doc-clean` - Clean generated documentation and website.

### Activated Markdown Extensions

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

