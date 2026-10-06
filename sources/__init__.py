"""Source adapters: one module per ATS, each exposing NAME, fetch() and parse()."""

from sources import amazon, ashby, darwinbox, eightfold, greenhouse, keka, lever, workday, zoho_recruit

ADAPTERS = {m.NAME: m for m in (greenhouse, lever, ashby, workday, darwinbox, keka, zoho_recruit, amazon, eightfold)}
