# Local demo accounts (development only)

Created for demonstrating the product on http://localhost:8700. Not valid anywhere else. All data in the demo businesses
is synthetic (see `scripts/demo_data.py`).

Every demo login below shares one password. It is not written in any file; only its salted scrypt hash is kept
(in `scripts/seed_demo.py` and the database), which cannot be turned back into the password. Ask the project owner for it.

## Super user

- Username: `admin` (sign in with the username, no email needed)
- Owner of every business, so one login reaches everything

## Demo owner, several businesses

- Email: demo.owner@example.com
- After signing in you choose a business:
  - Northwind Rentals (demo): mid-setup, the go-live checklist is incomplete
  - Peak Outdoor Gear (demo): online retail, fully set up with history
  - Lumen Dental Clinics (demo): dental clinics, fully set up with history
  - Brightline Freight (demo): road freight, fully set up with history

## Onboarding demo

- Email: demo.onboarding@example.com
- One business, Northwind Rentals (onboarding demo): a copy of Northwind as it is, mid-setup

## People inside the demo businesses

Each fully set-up business has a team you can sign in as, to show what each role sees:

| Business | Org admin | Builder | Reviewer | Operators |
|---|---|---|---|---|
| Peak Outdoor Gear | daniel.reyes@peakoutdoor.example | priya.shah@peakoutdoor.example | sofia.lindqvist@peakoutdoor.example | tom.okafor@, hannah.kelly@peakoutdoor.example |
| Lumen Dental Clinics | helen.brooks@lumendental.example | arjun.mehta@lumendental.example | claire.dawson@lumendental.example | kofi.mensah@, laura.price@lumendental.example |
| Brightline Freight | lena.vogel@brightlinefreight.example | mateo.silva@brightlinefreight.example | ingrid.larsen@brightlinefreight.example | piotr.nowak@, chloe.martin@brightlinefreight.example |
| Harbor Health Network (healthcare) | rachel.kim@harborhealth.example | omar.haddad@harborhealth.example | elena.ruiz@harborhealth.example | sam.patel@, grace.liu@harborhealth.example |
| Northstar Wealth Partners (financial services) | jonathan.pierce@northstarwealth.example | mei.tanaka@northstarwealth.example | carla.mendes@northstarwealth.example | ben.adler@, sofia.rossi@northstarwealth.example |
| Ironvale Manufacturing (industrial AI) | klaus.werner@ironvale.example | ana.silva@ironvale.example | jakub.novak@ironvale.example | lea.fischer@, marco.bianchi@ironvale.example |
| Kinetiq Robotics (robotics and physical AI) | nadia.haas@kinetiq.example | leo.martins@kinetiq.example | victor.hale@kinetiq.example | ivy.brooks@, kenji.sato@kinetiq.example |
| Cedarline Residential (property tech) | monica.reyes@cedarline.example | tyler.grant@cedarline.example | denise.okoro@cedarline.example | alex.rivera@, nina.brooks@cedarline.example |
| Atlas Commodities Trading (commodities and markets) | henrik.dahl@atlascommodities.example | zara.ahmed@atlascommodities.example | olivia.grant@atlascommodities.example | lucas.moreau@, ravi.shah@atlascommodities.example |

The six vertical businesses are defined in `scripts/demo_verticals.py`.

## Rebuilding the demo data

```
python scripts/seed_demo.py           # add anything missing
python scripts/seed_demo.py --reset   # delete the synthetic businesses and create them again
```

The nine fully set-up demo businesses share one AI model. Add a model once, in Control Centre, AI models of any of them, and
all nine use it for live chat (the key stays in the business where it was added; usage is counted per business).
Northwind Rentals (demo) and the onboarding copy are not in the group, so their checklists stay incomplete.
