"""Source adapters: one module per ATS, each exposing NAME, fetch() and parse()."""

from sources import (amazon, ashby, avature, careersite, darwinbox, eightfold, gem, greenhouse, hn, jazzhr, keka, lever, oracle,
                     rippling, smartrecruiters, teamtailor, workable, workday, yc_jobs, zoho_recruit)

ADAPTERS = {m.NAME: m for m in (greenhouse, lever, ashby, workday, darwinbox, keka, zoho_recruit, amazon, eightfold, hn,
                                    careersite, oracle, workable, smartrecruiters, gem, rippling, teamtailor, jazzhr,
                                    yc_jobs, avature)}
