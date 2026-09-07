# E61: share identical source across already-retrieved files

E59 found substantial exact duplicate gold-function bodies in 41/129 C++
tasks and none in Rust. Test an engine-only, default-off `--shared-source`
postprocessor using the existing candidate blocks; no gold or new model is
used. Require an exact body match, at least 64 tokens, different retrieved
files, and one complete copy already present in the original packed regions.

The postprocessor may extend other copies' regions, emitting the identical
body once with explicit file/range locations. Keep every original source line
and file represented. Never claim an un-emitted leader's body, normalize away
source differences, or infer clone equality from a hash alone. Accept changes
only when the complete rendered bundle costs no more than the original
bundle. This bounds cost against the baseline's actual tokens, not a new
claim that the baseline's requested budget includes all formatting overhead.

Try larger eligible bodies first, deterministically. Additional groups must
add represented source or reduce cost. Test source coverage, leader presence,
exact body equality, cost guards, and CLI behavior. Freeze the candidate and
run full Rust/C++ plus flag-off identity controls using the original scorer.
FILE, FUNCTION, LINE, and fraction must not decrease. Expand the ongoing
discovery family to include this sixth candidate for final selection.
Any default adoption still requires other discovery languages/Lite and a
qualifying Verified gate; shared-output interpretation also needs validation.
