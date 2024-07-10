# PyPI Auditor

An extremely simple tool that compares, line-by-line, the files of a PyPI wheel with the files
of the GitHub release of the same package. Does this for each PyPI version of a package.


## How do I use this?

Pop your info into the `Auditor` class, and hit run, like so:
```python
    from auditor import Auditor

    auditor = Auditor(
        "bittensor",
        "opentensor/bittensor"
    )
    auditor.run()
```

By default (`verbose=True`), the tool will spit out the differences or OK from each version, and `run`
will return a list of those differences.


https://github.com/thewhaleking/pypi-auditor/assets/37844818/cf571311-afa9-4b96-96f3-3f02fb44be03



## Contributing

Open a PR.
