# ics-tally

Count iCalendar components and property names without printing event details, people, dates, locations, or other property values. The scanner unfolds continuation lines, verifies that component boundaries match, and reads at most 128 MiB from a regular file.

## Use

Requires Python 3.8+; no packages to install.

```sh
python ics_tally.py calendar.ics
```

The output includes component and property-name counts; names are normalized to uppercase. Property values stay opaque and are never interpreted or displayed. The scanner accepts CRLF and LF line endings, treats property and component names as case-insensitive, enforces one `VCALENDAR` root, and checks matching `BEGIN`/`END` component names. It is not a complete RFC 5545 validator and does not expand recurrence rules. Physical and unfolded lines are limited to 1 MiB. Exit status is 0 for a structurally valid calendar, 1 for malformed or unsupported structure, and 2 for unreadable input.

## License

MIT

