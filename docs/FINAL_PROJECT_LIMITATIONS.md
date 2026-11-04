# Final project limitations

1. **Population scope:** primary AI/CV subfields 1702/1707, selected work types and 2020–2025; not all global AI.
2. **Sampling:** 12,000-work stratified API sample has nominal weights but no proven probability inclusion mechanism. Sampled descriptive tables are not complete-population counts.
3. **OpenAlex changes:** records, primary topics, citations, OA and institutional affiliations can be revised; the project is a timestamped snapshot.
4. **Missingness:** 2,558 abstracts, 2,678 FWCI, 2,902 institutions and 2,949 countries are unavailable in the original sample. All sampled preprints lack FWCI.
5. **Citations and OA:** raw counts are age-dependent and not scientific-quality scores. Adjusted OA coefficients are observational associations and do not establish causality.
6. **Networks:** country/institution edges are sampled co-affiliation, not universal collaboration or author nationality. Missing affiliation is unknown, not negative collaboration.
7. **ML labels:** the 14 targets are OpenAlex machine-assigned silver labels. Topic overlap and catalogue omissions remain; no independent human semantic validity estimate is available.
8. **Open set:** 2024 development outside-catalogue false acceptance was 21.66%; the model may recommend a wrong in-catalogue topic even when the draft is outside scope.
9. **Final evaluation:** no legitimate final-test estimate can be reported. The 2025 labels were subsequently published in the public workspace and are no longer independently sealed; the local one-time registry is not a cross-clone lock.
10. **Paper discovery:** the new TF-IDF/cosine feature indexes 11,558/12,000 original-sample works, with only 9,075 having usable title+abstract. It is lexical, biased toward available text and English vocabulary, and has no independent human relevance judgments. Its scores are not novelty/plagiarism evidence or a comprehensive search result. Title-only scores are not directly comparable to full-text scores and are opt-in.
11. **Delivery:** browser app is a local research prototype. A fresh clone must fetch selected Git LFS binaries and build the ignored discovery index once. Public hosting, artifact redistribution rights, real user study and accessibility audit remain open.
