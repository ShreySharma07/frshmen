"""Source adapters: one module per ATS, each exposing NAME, fetch() and parse()."""

from sources import (amazon, ashby, careersite, darwinbox, eightfold, greenhouse, hn, keka, lever, oracle,
                     smartrecruiters, workable, workday, zoho_recruit)

ADAPTERS = {m.NAME: m for m in (greenhouse, lever, ashby, workday, darwinbox, keka, zoho_recruit, amazon, eightfold, hn,
                                    careersite, oracle, workable, smartrecruiters)}
