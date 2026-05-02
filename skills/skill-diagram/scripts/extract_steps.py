#!/usr/bin/env python3
"""Extract workflow steps and skill invocations from a SKILL.md file."""

import json
import re
import sys


def extract(path):
    text = open(path).read()
    lines = text.splitlines()

    # Skill name from frontmatter
    name = ""
    fm = re.search(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if fm:
        m = re.search(r'name:\s*(.+)', fm.group(1))
        if m:
            name = m.group(1).strip()

    # Steps: ## Step N or ### Step N (with optional suffix like "3b")
    steps = []
    for i, line in enumerate(lines, 1):
        m = re.match(r'^#{2,3}\s+Step\s+(\w+)[:\s]*(.*)', line)
        if m:
            steps.append({
                "number": m.group(1),
                "title": m.group(2).strip().strip("—- "),
                "line": i,
            })

    # Skill invocations
    invocations = []
    seen = set()
    for i, line in enumerate(lines, 1):
        for m in re.finditer(r'invoke\s+(/[\w-]+)|Skill\(\{[^}]*skill:\s*["\']?([\w:/-]+)', line):
            skill = m.group(1) or m.group(2)
            if skill and skill not in seen:
                seen.add(skill)
                invocations.append({
                    "skill": skill,
                    "line": i,
                    "context": line.strip()[:120],
                })

    # Arguments from ## Arguments section
    arguments = []
    in_args = False
    for line in lines:
        if re.match(r'^#{1,3}\s+Arguments', line):
            in_args = True
            continue
        if in_args and re.match(r'^#{1,3}\s+', line) and 'argument' not in line.lower():
            break
        if in_args:
            m = re.match(r'[-*]\s+`(--[\w-]+)', line)
            if m:
                arguments.append(m.group(1))

    return {"name": name, "steps": steps, "skill_invocations": invocations, "arguments": arguments}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: extract_steps.py <SKILL.md>", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(extract(sys.argv[1]), indent=2))
