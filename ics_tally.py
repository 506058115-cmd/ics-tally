#!/usr/bin/env python3
"""Count iCalendar components and property names without exposing values."""

import argparse
from collections import Counter
from pathlib import Path
import stat
import sys


MAX_BYTES = 128 * 1024 * 1024
MAX_LINE_BYTES = 1024 * 1024


class IcsError(ValueError):
    pass


def content_line(line, number, components, properties, stack, state):
    quote = False
    delimiter = None
    for index, byte in enumerate(line):
        if byte == 34:
            quote = not quote
        elif byte == 58 and not quote:
            delimiter = index
            break
    if delimiter is None:
        raise IcsError(f"line {number}: missing property separator")

    prefix = line[:delimiter]
    name = prefix.split(b";", 1)[0].upper()
    if not name or any(byte not in b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-" for byte in name):
        raise IcsError(f"line {number}: invalid property name")

    if name in (b"BEGIN", b"END"):
        if prefix != name:
            raise IcsError(f"line {number}: component marker cannot have parameters")
        raw_component = line[delimiter + 1 :]
        component = raw_component.upper()
        if not component or any(byte not in b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-" for byte in component):
            raise IcsError(f"line {number}: invalid component name")
        if name == b"BEGIN":
            if not stack:
                if state["root_seen"] or component != b"VCALENDAR":
                    raise IcsError(f"line {number}: expected a single VCALENDAR root")
                state["root_seen"] = True
            stack.append(component)
            components[component.decode("ascii")] += 1
        else:
            if not stack or stack[-1] != component:
                raise IcsError(f"line {number}: component end does not match its start")
            stack.pop()
            if not stack:
                state["root_closed"] = True
    else:
        if not stack or state["root_closed"]:
            raise IcsError(f"line {number}: property outside VCALENDAR")
        properties[name.decode("ascii")] += 1


def inspect(path):
    source = Path(path)
    file_stat = source.stat()
    if not stat.S_ISREG(file_stat.st_mode):
        raise IcsError("input must be a regular file")
    if file_stat.st_size > MAX_BYTES:
        raise IcsError("input exceeds the 128 MiB limit")

    components, properties = Counter(), Counter()
    stack = []
    state = {"root_seen": False, "root_closed": False}
    logical_line = None
    logical_number = 0
    physical_number = 0
    total_bytes = 0
    line_count = 0

    with source.open("rb") as stream:
        while True:
            raw = stream.readline(MAX_LINE_BYTES + 3)
            if not raw:
                break
            physical_number += 1
            total_bytes += len(raw)
            if total_bytes > MAX_BYTES:
                raise IcsError("input grew beyond the 128 MiB limit while reading")
            if len(raw) > MAX_LINE_BYTES + 2:
                raise IcsError(f"line {physical_number}: physical line exceeds the 1 MiB limit")
            if raw.endswith(b"\r\n"):
                part = raw[:-2]
            elif raw.endswith(b"\n"):
                part = raw[:-1]
            else:
                part = raw
            if b"\r" in part:
                raise IcsError(f"line {physical_number}: bare carriage return")
            if len(part) > MAX_LINE_BYTES:
                raise IcsError(f"line {physical_number}: physical line exceeds the 1 MiB limit")

            if part.startswith((b" ", b"\t")):
                if logical_line is None:
                    raise IcsError(f"line {physical_number}: folded line has no preceding content")
                if len(logical_line) + len(part) - 1 > MAX_LINE_BYTES:
                    raise IcsError(f"line {logical_number}: unfolded line exceeds the 1 MiB limit")
                logical_line.extend(part[1:])
                continue

            if logical_line is not None:
                line_count += 1
                content_line(bytes(logical_line), logical_number, components, properties, stack, state)
            logical_line = bytearray(part)
            logical_number = physical_number

    if logical_line is not None:
        line_count += 1
        content_line(bytes(logical_line), logical_number, components, properties, stack, state)
    if not state["root_seen"] or not state["root_closed"] or stack:
        raise IcsError("calendar is missing a complete VCALENDAR component")
    return line_count, components, properties


def main():
    parser = argparse.ArgumentParser(
        description="Count iCalendar components and property names without printing values."
    )
    parser.add_argument("input", help="iCalendar .ics file")
    args = parser.parse_args()

    try:
        lines, components, properties = inspect(args.input)
    except IcsError as error:
        print(f"ics-tally: invalid or unsupported calendar: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"ics-tally: {error.strerror or 'unable to read input'}", file=sys.stderr)
        return 2

    print(f"Content lines: {lines}")
    print(f"Properties: {sum(properties.values())}")
    print("Components:")
    for name, count in sorted(components.items()):
        print(f"  {name}: {count}")
    print("Properties by name:")
    for name, count in sorted(properties.items()):
        print(f"  {name}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
