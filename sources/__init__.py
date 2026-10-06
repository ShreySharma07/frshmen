"""Source adapters: one module per ATS, each exposing NAME, fetch() and parse()."""

from sources import ashby, greenhouse, lever

ADAPTERS = {m.NAME: m for m in (greenhouse, lever, ashby)}
