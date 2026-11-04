# RQ7.1 license semantics and URL audit

The pilot filled a previously empty license field in **277** records. Across all recovered records, **277/277** have at least one URL and every stored URL is syntactically HTTP(S). This is syntax, not reachability or legal validity. The arrays contain **897** URLs; **0** recovered records have a recognised Creative Commons `/licenses/...` identifier under the conservative parser. **270** contain explicit content-version values beyond `unspecified`. Observed values include `tdm`, `vor`, `am` and `stm-asf`; these are not interchangeable with an unrestricted OA licence.

The 30 selected license-recovery cases contain 104 syntactically valid URL entries. A separately logged, allowlisted HEAD probe made **10** requests; **2** returned direct HTTP 2xx. Other statuses or failures are not proof the policy is absent. HEAD does not verify text, applicability, rights, or whether the paper's version was covered.

Independent license semantics verified: **0**; human/legal interpretation pending: **277** recovered records. `license_metadata_present` and `reuse_rights_status` must remain separate; the latter is **UNKNOWN**. Do **not** use the 277 additions as OA status, Creative Commons count, or redistribution permission. [DOI agency evidence](RQ7_CROSSREF_404_AUDIT.md) is not a substitute for publisher license terms.
