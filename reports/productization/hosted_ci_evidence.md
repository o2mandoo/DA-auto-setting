# Hosted CI Evidence

Date: 2026-05-10 KST  
Workflow: `packaging-clean-clone.yml`  
Job: `smoke`  
Run: <https://github.com/o2mandoo/DA-auto-setting/actions/runs/25621898578>  
Commit: `3a3a3774b7671c1d29b629746c5b655939791951`  
Observed result: `Success`  
Observed duration: `4m45s`  
Observed via: public GitHub Actions run `summary_partial` HTML.

## No-silent-fallback note

Hosted CI did not pass on the first attempt. The following fixable failures were resolved and rerun instead of being hidden:

1. workflow defaulted to `.venv/bin/python` on a clean GitHub runner;
2. workflow used an unverified Python 3.11 baseline while local release evidence used Python 3.14;
3. full-test diagnostics were too opaque, so suite/file-level test gates were added;
4. product evidence console depended on an untracked local benchmark artifact;
5. eval manifest assertions depended on macOS-only decomposed Korean path normalization.

The passing hosted run above is the current external CI evidence. It does not create production release approval by itself.

## Remaining release gate

Signed or promoted release-candidate approval remains missing and must not be faked by local automation.
