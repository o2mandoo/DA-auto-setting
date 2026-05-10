# Hosted CI Evidence

Date: 2026-05-10 KST  
Workflow: `packaging-clean-clone.yml`  
Job: `smoke`  
Run: <https://github.com/o2mandoo/DA-auto-setting/actions/runs/25622121704>  
Commit: `65e3614a331d0677944719af59e37050f7203dcb`  
Observed result: `Success`  
Observed duration: `4m34s`  
Observed via: public GitHub Actions run `summary_partial` HTML.

## No-silent-fallback note

Hosted CI did not pass on the first attempt. The following fixable failures were resolved and rerun instead of being hidden:

1. workflow defaulted to `.venv/bin/python` on a clean GitHub runner;
2. workflow used an unverified Python 3.11 baseline while local release evidence used Python 3.14;
3. full-test diagnostics were too opaque, so suite/file-level test gates were added;
4. product evidence console depended on an untracked local benchmark artifact;
5. eval manifest assertions depended on macOS-only decomposed Korean path normalization.

The passing hosted run above is the current external CI evidence for the latest pushed release-packet evidence commit. It does not create production release approval by itself.

## Hosted artifacts listed by GitHub

The public `artifacts_partial` page for the run lists:

- `ci-diagnostic-logs` — 4.71 KB — `sha256:b919037c332b3194d65c471e0faa340b34974a02fec3b9338e400087c12924c9`
- `ci-smoke-release-packet` — 22.6 KB — `sha256:2bbf73f2cf5e3a5cf7b860d19a99cbce376c51b7d19a1c46de0cad442ce3d4e6`

Direct artifact download may require authenticated GitHub access; the release evidence therefore records the public run URL, summary status, and artifact names/digests rather than silently claiming a downloaded log bundle.

## Remaining release gate

Signed or promoted release-candidate approval remains missing and must not be faked by local automation.
