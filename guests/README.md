# Wedding planning workbook

`Wedding_Planning_Workbook.xlsx` is a full rebuild of the workbook from
`Logistics.pdf` — all six tabs, the 45 new guests merged in, and the sage color
scheme replaced with olive green.

The live Google Sheet is not reachable from this environment (outbound requests to
`docs.google.com` are blocked by the network policy, and no Google Drive/Sheets
connector is attached), so this is a file to upload rather than an edit in place.
`File > Import > Replace spreadsheet` on the existing sheet keeps the same URL.

## Tabs

| Tab | Contents |
|---|---|
| Overview | Event details, guest summary, guests by group, budget snapshot, checklist progress — all formula-driven off the other tabs |
| Guest List | 154 rows (109 original + 45 new), 18 columns, RSVP/`+1?` dropdowns |
| Budget | 28 line items in 12 categories; Balance and TOTAL calculate themselves |
| Vendors & Contacts | 16 vendor types; Balance = Quoted − Deposit |
| Planning Checklist | 41 tasks, 12+ months out through After; Status dropdown |
| Seating Chart | 60 blank assignment rows with a live Seats Assigned total |

Guest counts by group, reconciled against the PDF's Overview:

| Side | Category | Parties | Guests |
|---|---|---:|---:|
| Holliday | Family (Tier 1) | 10 | 19 |
| Holliday | Framily (Tier 2) | 7 | 13 |
| Holliday | Influences (Tier 3) | 7 | 12 |
| Holliday | Friends (Tier 4) — new | 43 | 43 |
| Emma | Family | 61 | 61 |
| Emma | Parents' Friends | 24 | 24 |
| Couple | Bride & Groom — new | 2 | 2 |
| **TOTAL** | | **154** | **174** |

The first five rows match the original workbook exactly, so the reconstruction is
verified against its own totals.

## Other files

- `new_guest_rows.csv` / `.xlsx` — just the 45 additions, if you'd rather paste rows
  into the existing sheet than replace it.
- `olive_palette.md` — the olive hex values and where each is applied.
- `build_workbook.py` — the generator, so any of this can be regenerated.

## Judgment calls

- **One row per person, `Party Size` 1** for the new names, matching how the Emma
  side is already built (`Dick` and `Dick's wife` are separate rows).
- **New tier `Friends (Tier 4)`** on the Holliday side, alongside Family/Framily/
  Influences.
- **Emma and Matt** are rows 152–153 under a `Couple` side so they don't inflate
  either family's group counts. Delete both if the totals should mean invited guests.
- **Not re-added — already present:** `David tardella and wife` is row 21
  (*Dave Tardella & wife*); `brad Brett and wife` is row 22 (*Brad Bretz & wife*).
  So `brad Brett` was read as one person, Brad Bretz.
- **Wedding date** is set to **May 22, 2026**, which reproduces the PDF's
  `Days Until Wedding = -106`. If the wedding is May 22, 2027, change Overview!B5.

## Carried over from the PDF, worth a check

- The two `Just thoughts` notes are placed on *Jim & Shelley Sexton* and
  *Steve & Jana Harmon*. The PDF prints notes in a separate column block, so the
  row they attach to is inferred — they belong somewhere in rows 10–19.
- Four `Name to confirm` notes are placed on *Baby*, *Ansen*, *Brayden* and
  *Baby 2* — the four placeholder-ish names in that block.
- Row 63 read as `Ansen` with `New baby` moved into Notes.
- Row 76 printed as `(Brayden` with a stray parenthesis; entered as `Brayden`.

## Still to confirm in the new names (flagged inline in Notes)

Jay Joyner's wife · Josh Havrilla's +1 · Zander and his wife · Avery and his wife ·
`Abby / Maria` (which name, and whether she is Jon Barnett's guest) · Andrew ·
Aaron · Nick Stonaker's +1 · Rocky and his wife · Shun and Momoka · David Wadijija
(spelling) and his +1 · the `ZZZZZZZ` placeholder and its +1 · Chitra · PD and his wife
