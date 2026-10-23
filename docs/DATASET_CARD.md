# Dataset card

Source: https://huggingface.co/datasets/med2425/resume-job-fit-merged-v1 . Card reviewed on 2026-10-24 via its raw README. It describes 80,017 train and 13,716 test records, fields resume/jd/label/source/resume_domain/jd_domain, and three labels: Good Fit, Potential Fit, No Fit.

The card describes merging `cnamuangtoun/resume-job-description-fit` and `kens1ang/resume-job-fit-augmented`, synthetic/cross-domain pair generation and Qwen2.5-32B labels. Labels are proxy annotations, not independently observed hiring outcomes. Its front matter does not declare a license. Public access does not establish redistribution or commercial-use rights. Upstream terms and provenance require operator review before acquisition.

No public dataset has been downloaded, redistributed or trained in this implementation session. The explicit `fetch` command requires a pinned commit and operator acknowledgment of terms review. It records the dataset revision and content checksum locally. Private raw text stays gitignored.

Audits report label/source/domain distributions, duplicates, conflicts and benchmark identity overlap. Strict splitting uses independent resume/JD text hashes and excludes crossing edges. Text fingerprints cannot establish person identity or detect all near duplicates. Full leakage, privacy and source-bias findings remain unavailable until acquisition and audit are authorized and executed.
