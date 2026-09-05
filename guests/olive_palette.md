# Olive green color scheme (replaces sage)

Apply these in the Google Sheet via **Format > Theme** for the accent color, and by
selecting the header rows and using the paint-bucket **Custom** hex field.

| Role | Where it's used | Olive hex |
|---|---|---|
| Deep olive | Tab title bars, table header rows (white bold text on top) | `#4B5320` |
| Mid olive | Section labels, totals rows, chart accents, italic note text | `#6B7A3A` |
| Light olive tint | Banded row fill (odd bands) | `#E7EAD4` |
| Lighter olive tint | Banded row fill (even bands) | `#F4F6EA` |
| Olive line | Cell borders and gridline overrides | `#BFC79E` |
| Olive text | Body text on light fills | `#2F3517` |

## Where to apply it, tab by tab

- **Overview** — the `EVENT DETAILS` / `GUEST SUMMARY` / `GUESTS BY GROUP` /
  `BUDGET SNAPSHOT` / `CHECKLIST PROGRESS` section bars take deep olive; the
  `TOTAL` row takes mid olive.
- **Guest List** — header row deep olive; alternating-color banding set to the two
  tints (Format > Alternating colors > Custom).
- **Budget** — header row deep olive; the `TOTAL` row mid olive.
- **Vendors & Contacts**, **Planning Checklist**, **Seating Chart** — header rows
  deep olive, banding on the two tints.

Conditional-formatting rules that were sage (RSVP Yes/No/Pending, Status
Done/In Progress/Not Started) keep their traffic-light greens/ambers — only swap the
sage green fill for `#E7EAD4` with `#2F3517` text so it reads as the same family.
