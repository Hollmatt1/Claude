# Guest list additions

The wedding workbook lives in Google Drive and is not reachable from this
environment (outbound requests to `docs.google.com` are blocked by the network
policy, and no Google Drive/Sheets connector is attached), so these files are
built to be pasted in rather than written to the sheet directly.

## Files

- `new_guest_rows.csv` — 45 new rows, columns in the exact order of the
  **Guest List** tab (`#` through `Notes`). Numbered `#110`–`#154`, continuing
  from the sheet's current last row `#109`.
- `new_guest_rows.xlsx` — the same rows, formatted in the olive green scheme.
- `olive_palette.md` — the olive hex values and where to apply them.

## How to paste

1. Open the **Guest List** tab, click cell `A` of the first empty row (just under
   `#109`).
2. `File > Import > Upload` the CSV with **Append to current sheet**, or open the
   CSV, select all, and paste. The columns line up 1:1 — no reordering needed.
3. The Overview tab's counts recalculate on their own.

## Judgment calls made

- **One row per person, `Party Size` 1.** Matches how the Emma side of the sheet is
  already built (`Dick` and `Dick's wife` are separate rows). Collapse a couple into
  a single row of size 2 any time you'd rather match the Holliday-side convention.
- **`Side` = Holliday, `Category` = Friends (Tier 4)** — a new tier alongside
  Family (Tier 1) / Framily (Tier 2) / Influences (Tier 3). Rename freely.
- **Emma and Matt** are included because they were asked for, flagged in Notes.
  Delete both rows if the guest counts should mean *invited guests* only.
- **Not re-added — already on the sheet:** `David tardella and wife` is row 21
  (*Dave Tardella & wife*), and `brad Brett and wife` is row 22 (*Brad Bretz & wife*).
- **`brad Brett`** was read as one person (Brad Bretz), not as `Brad` + `Brett`.

## Still to confirm (each is flagged in the Notes column)

Jay Joyner's wife · Josh Havrilla's +1 · Zander (last name) and his wife ·
Avery (last name) and his wife · `Abby / Maria` (which name, and whether she is
Jon Barnett's guest) · Andrew (last name) · Aaron (last name) ·
Nick Stonaker's +1 · Rocky (last name) and his wife · Shun and Momoka (last names) ·
David Wadijija (spelling) and his +1 · the `ZZZZZZZ` placeholder and its +1 ·
Chitra (last name) · PD (full name) and his wife
