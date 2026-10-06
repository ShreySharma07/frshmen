"""Can Shrey take this role from where he is? Location rules from config/profile.yaml.

- India: any city, except onsite-only roles whose cities are all in the hidden list
  (Bengaluru, Hyderabad); hybrid, remote or unknown work mode there is fine.
- Remote with no country: fine.
- Anywhere else (including "remote, US"): only with visa sponsorship or relocation.
- No location at all: kept, since there is nothing to rule it out.
"""

from __future__ import annotations

from dataclasses import dataclass

from extract.location import REMOTE_UNSPECIFIED
from extract.visa import Visa


@dataclass(frozen=True)
class Eligibility:
    eligible: bool
    reason: str


def check_eligibility(countries: list[str], cities: list[str], location_type: str | None, visa: Visa,
                      hide_onsite_only_in: frozenset[str] = frozenset({"bengaluru", "hyderabad"})) -> Eligibility:
    if not countries:
        return Eligibility(True, "no location given")
    if "India" in countries:
        hidden = cities and all(c.lower() in hide_onsite_only_in for c in cities)
        if location_type == "onsite" and hidden:
            return Eligibility(False, f"onsite-only in {', '.join(cities)}")
        return Eligibility(True, "in India")
    if countries == [REMOTE_UNSPECIFIED]:
        return Eligibility(True, "remote, no country restriction")
    where = ", ".join(countries)
    if visa.sponsorship == "yes":
        return Eligibility(True, f"{where}, visa sponsorship offered")
    if visa.relocation and visa.sponsorship != "no":
        return Eligibility(True, f"{where}, relocation offered")
    return Eligibility(False, f"{where} without visa sponsorship")
