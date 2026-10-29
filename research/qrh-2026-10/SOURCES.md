# Izvori

Ovo su svi izvori na kojima počiva analiza kvazi-Rimanove hipoteze u ovom folderu. Polazna tačka je OpenAI rad od 30. septembra 2026, koji tvrdi da ζ i sve Dirichletove L-funkcije nemaju nula za Re s > 7/8, i kraći dokaz za 11/12 od 5. oktobra. Na njega se nadovezuju dva preprinta koja granicu pomjeraju malo ispod 7/8: Liu (0.874957) i Xu–Sang (0.8748867). Nijedan od ovih radova još nije prošao recenziju, iako su glavni iskazi formalizovani u Lean-u. Novinski i blog izvori služe samo za kontekst i reakcije matematičara; brojevi i formule su uzeti isključivo iz samih radova.

- OpenAI, *The Quasi-Riemann Hypothesis* (Sept 30, 2026; 7/8) i (Oct 5, 2026; 11/12): https://github.com/openai/math/tree/main/preprints
  - Lean: https://github.com/openai/math/tree/main/lean (QuasiRiemannHypothesis.lean, DirichletSevenEighths.lean, HeckeSevenEighths.lean, SiegelZeros.lean)
- OpenAI, *Uniform exclusion of Landau–Siegel zeros* (Oct 1, 2026): isti repo
- B. Liu, *Improved zero-free half-planes for the quasi-Riemann hypothesis*, arXiv:2610.12234 (v2, 12 Oct 2026): https://arxiv.org/abs/2610.12234
- Y. Xu, H. Sang, *Amplified moments and a refinement of the quasi-Riemann hypothesis*, arXiv:2610.15291 (v2, 15 Oct 2026): https://arxiv.org/abs/2610.15291
- Quanta, *AI Proved the Quasi-Riemann Hypothesis. What Happens Now?* (19 Oct 2026): https://www.quantamagazine.org/ai-proved-the-quasi-riemann-hypothesis-what-happens-now-20261019/
- Emergent Mind, OpenAI rezultat 003: https://www.emergentmind.com/openai-math-explorer/results/003
- J. Gomila, ekspozicija: https://www.judegomila.com/posts/quasi-riemann-hypothesis
- aecon.ai: https://aecon.ai/blog/openai-quasi-riemann-hypothesis
- Science: https://www.science.org/content/article/ai-edges-closer-solving-riemann-hypothesis-one-math-s-hardest-problems
- NEPOUZDANO (odbačeno): https://tech-insider.org/anthropic-claude-riemann-hypothesis-breakthrough-2026/

Fajlovi korišteni za izvlačenje (u `papers-local/`, samo lokalno):
oai5/paper2.tex · oai30/paper.tex · liu/ex/combine_v2-2.tex · xs/ex/seven_eighths_and_beyond_v7.tex
