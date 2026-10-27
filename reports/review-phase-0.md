# Phase 0 independent review

One fresh-context reviewer inspected the foundation read-only. Later Blender,
Unity, OS-isolation, benchmark execution, and external qualification were excluded
because they are explicitly assigned to later phases. No review edits or extra
review agents were used.

## Findings resolved

1. **Decoder failures escaped structured output.** Reproduced uncaught
   RecursionError with 20,000 nested arrays and ValueError with a 5,000-digit
   integer, both below the input-byte limit. Normalize decoder failures to
   InputError/FAIL/2. CLI regression tests now pass.
2. **Accepted option spellings selected inconsistent output.** Reproduced accepted
   option abbreviations and repeated format arguments choosing the wrong output
   mode. Disable abbreviation on all parsers and honor parsed output options.
   Exact --format=json works; unregistered abbreviations fail; last format wins.
3. **Regex dollar anchors admitted trailing newlines.** Reproduced descriptors
   with newline suffixes in IDs, versions, runner names, and schema paths.
   Require absolute end of input with a portable negative lookahead. Apply the
   same rule to task IDs and digest patterns. Negative regression fixtures pass.

All three findings were reproduced failing before fixes, then passed focused
checks and the final 33-test suite. No actionable review findings remain deferred.
