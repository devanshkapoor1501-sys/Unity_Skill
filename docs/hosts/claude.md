# Claude Code pathway

Copy the same canonical `.agents/skills/polyforge` directory into the chosen
project's `.claude/skills/polyforge`. Do not maintain a second instruction fork
or change global configuration to run a smoke test. [Claude's official skills
guide](https://code.claude.com/docs/en/skills) documents its native project path;
version-specific reload, trust and precedence rules remain host-owned.

Check `claude --version` and `claude --help` locally. Launch inside the selected
project, invoke `/polyforge` or ask to use PolyForge for a narrow explanation or
descriptor-validation task. The engine uses the same JSON CLI as Codex. No
provider SDK or secret is part of the skill, but Claude itself requires normal
account authentication and host permissions.

[Headless guidance](https://code.claude.com/docs/en/headless) documents `claude -p`
and structured output. For a bounded smoke, feed an explanation-only prompt on
stdin with `--output-format json --no-session-persistence`, retaining normal
permission settings. Grant only the specific read/CLI tool access required;
never use a permission bypass. The prompt must preserve the exact user output,
read relevant local references and execute the narrow documented knowledge route.
Retain actual command and result evidence, not just the model's summary.

No authentication, blocked permission or unavailable service produces an explicit
host-dependent BLOCKED outcome. Model-free core commands remain usable. Do not
silently install packages, enable network retrieval or substitute an arena for
an explanation. Use serial roles absent verified delegation and human REVIEW
absent actual required visual judgment. The Phase 10 report records this host's
executed version and outcome; it does not qualify all Claude products or hosts.
