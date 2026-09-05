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
| Guest List | 180 rows, 18 columns, RSVP/`+1?` dropdowns |
| Budget | 28 line items in 12 categories; Balance and TOTAL calculate themselves |
| Vendors & Contacts | 16 vendor types; Balance = Quoted − Deposit |
| Planning Checklist | 41 tasks, 12+ months out through After; Status dropdown |
| Seating Chart | 60 blank assignment rows with a live Seats Assigned total |

Guest counts by group, reconciled against the PDF's Overview:

| Side | Category | Parties | Guests |
|---|---|---:|---:|
| Holliday | Family (Tier 1) | 10 | 19 |
| Holliday | Framily (Tier 2) | 11 | 17 |
| Holliday | Influences (Tier 3) | 4 | 8 |
| Holliday | Friends (Tier 4) — new, Matt's friends | 43 | 43 |
| Emma | Family | 61 | 61 |
| Emma | Parents' Friends | 24 | 24 |
| Emma | Friends — new, Emma's friends | 25 | 25 |
| Couple | Bride & Groom — new | 2 | 2 |
| **TOTAL** | | **180** | **199** |

The first three Holliday tiers and both Emma groups reconciled against the PDF's own
Overview before anything was added (10/19, 7/13, 7/12, 61/61, 24/24), so the
reconstruction is verified against the source's totals.

**No names were struck out in the source.** Every glyph in the export was tested
against every horizontal rule on all 24 pages; not one rule crosses a character's
midline, and there are no strikethrough font variants. Nothing scratched out was
silently counted.

## Other files

- `new_guest_rows.csv` — just the 71 added rows (110-180), if you'd rather paste rows
  into the existing sheet than replace it.
- `olive_palette.md` — the olive hex values and where each is applied.
- `build_workbook.py` — the generator, so any of this can be regenerated.

## Judgment calls

- **One row per person, `Party Size` 1** for the new names, matching how the Emma
  side is already built (`Dick` and `Dick's wife` are separate rows).
- **Two new friend groups, split by side.** Matt's friends are
  `Holliday / Friends (Tier 4)` (rows 112-154); Emma's friends are
  `Emma / Friends` (rows 155-179). The `Side` column is what separates them, so
  either group filters on its own.
- **The Wexler kids** (rows 180-183) go under `Framily (Tier 2)` with their parents,
  each with a spouse +1 marked TBD. Row 12's `Household / Group` was set to `Wexler`
  so all five rows group together; that column feeds no totals, so no count moved.
- **Emma and Matt** are rows 110-111 under a `Couple` side so they don't inflate
  either family's group counts. Delete both if the totals should mean invited guests.
- **Rows renumbered sequentially** after the three deletions, so `#` has no gaps.
  Everything above the old row 21 keeps its number; below it, numbers drop by three.
  The four Notes that cite a row number were re-pointed to match.
- **Wedding date** is **May 29, 2027** and the venue is **Berry**, both taken from
  your edited copy.

## Carried over from the PDF, worth a check

- The two `Just thoughts` notes are placed on *Jim & Shelley Sexton* and
  *Steve & Jana Harmon*. The PDF prints notes in a separate column block, so the
  row they attach to is inferred — they belong somewhere in rows 10–19.
- Four `Name to confirm` notes are placed on *Baby*, *Ansen*, *Brayden* and
  *Baby 2* — the four placeholder-ish names in that block.
- Row 63 read as `Ansen` with `New baby` moved into Notes.
- Row 76 printed as `(Brayden` with a stray parenthesis; entered as `Brayden`.

## Merged back from your edited copy (Wedding_Planning_Workbook_2)

- **Deleted:** *Dave Tardella & wife*, *Brad Bretz & wife* and *Network pastors (TBD)*
  — Influences (Tier 3) drops from 7 parties/12 guests to 4/8.
- **Renamed:** Andre → **Andie** · Anabelle → **Anabel** · Jackie → **Jackie Smith** ·
  Brady Laubach → **Brad Laubach** · Garrett/Abby Thurmond → **Thurman** ·
  the placeholder pair → **ZZZZ** and **Zs wife**.
- **Wedding date** May 22, 2026 → **May 29, 2027**; **Venue** → **Berry**.
- Budget, Vendors, Checklist and Seating carried no entries in your copy, so they are
  unchanged.

## Possible duplicates worth a look

- **Jackie Santander** vs **Jackie Smith** on row 88, an Emma parents' friend.
- **Chris Santander** vs **Chris** / **Chris' wife** on rows 98-99, also
  parents' friends with the wife's name still TBD — this could be the same couple.
- **Garrett** (with Moriah) is treated as a different person from **Garrett Thurman**
  (with Abby).
- **Michael** (with Alisa), **Michael Rumende** and **Michael** on row 33 are all
  entered as separate people.
- **Rachel** (with Nathaniel), **Rachel Lane**, **Rachel Guy** and **Rachel** on
  row 91 are likewise all separate.

## Still to confirm in the new names (flagged inline in Notes)

**Matt's friends:** Jay Joyner's wife · Josh Havrilla's +1 · Zander and his wife · Avery and his wife ·
`Abby / Maria` (which name, and whether she is Jon Barnett's guest) · Andrew ·
Aaron · Nick Stonaker's +1 · Rocky and his wife · Shun and Momoka · David Wadijija
(spelling) and his +1 · the `ZZZZZZZ` placeholder and its +1 · Chitra · PD and his wife

**Emma's friends:** last names for Nathaniel & Rachel, Viet & Debbie, Noah & Emily,
Michael & Alisa, Grant & Samantha, Garrett & Moriah, and Sheona · Rhiannon Beard's
plus-one · `Issac` (or Isaac?)
