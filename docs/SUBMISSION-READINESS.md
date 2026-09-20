# Hackathon submission readiness

Reviewed 19 September 2026 against the Nebius x NVIDIA Global AI Hackathon official rules supplied
by Om and the public Devpost rules page. This is an engineering checklist, not legal advice. Recheck
the official rules before submitting because the organizers may amend them.

## Deadline and selected track

- **Submission deadline:** 30 October 2026 at 10:00 AM Pacific / 1:00 PM Eastern.
- **Primary track:** Coding and Agentic Engineering.
- **Submission representative:** Om Thakur, if entered as an individual or team representative.
- **Project:** ReplayForge, a paired model-migration and reliability lab for coding agents.

ReplayForge is a strong fit because both lanes plan, edit and test work in real repository fixtures,
while deterministic graders and a stored policy decide whether the candidate model is safe to release.
The final description should avoid implying that the local sandbox is a Nebius product. The qualifying
Nebius usage is the live NVIDIA-model inference call through Token Factory.

## Eligibility gate

| Requirement | Current state | Required evidence or action |
|---|---|---|
| Working application | **Built offline** | Keep the fixture demonstration available, but do not submit using fixture-only evidence |
| Runs on Nebius Token Factory or AI Cloud | **Not yet proven live** | Redeem credits, create a key and run `make live-smoke` |
| Uses an NVIDIA open-source model | **Code path built; live proof missing** | Select an NVIDIA entry from the live Token Factory catalog and preserve the exact model ID and request IDs |
| Coding and Agentic Engineering fit | **Strong** | Show the model reading, modifying and testing a repository—not only answering a prompt |
| Created or significantly updated after 26 Aug 2026 | **Documented** | Keep `HACKATHON-DISCLOSURE.md`; repository work began 17 Sep 2026 |
| Authorized third-party tools and code | **Mostly documented** | Retain Apache-2.0 license and benchtrace attribution; review every external asset before video/submission |
| Public open-source repository | **Blocked** | Make the GitHub repository public and confirm the Apache-2.0 license appears in GitHub's About panel |
| Public working demo or test build | **Not deployed** | Host the web app and API, keep it available through the judging period, and supply any test instructions |
| Public YouTube demo under three minutes | **Not recorded** | Record the real live flow, upload publicly, and stop before 3:00 |
| English description and testing instructions | **Draft material exists** | Create final Devpost copy and a short judge test path |
| Product feedback | **Not written** | Submit specific Token Factory/NVIDIA feedback based on the real run |

The repository currently has an Apache-2.0 `LICENSE`, setup instructions and an honest pre-existing-work
disclosure. The public GitHub URL must still be checked from a signed-out browser after visibility is
changed.

## Credit and community actions

1. Claim the first **$25 Token Factory credit** through the official promo form using activation code
   `NEBIUS-DEVPOST-GLOBAL26`.
2. Join the free **Nebius Builders Program** and claim the additional $25 credit plus Tavily access,
   training and office hours.
3. Join the Nebius Discord for technical questions and model-access problems.
4. If practical, attend **Builders & Brews NYC on 25 September**. Attendance can make the project
   eligible for the separate $500 New York City award; keep registration/attendance evidence.

Never commit the Token Factory key. Store it only in `.env` as `NEBIUS_TOKEN_FACTORY_API_KEY`.

## Live qualifying run

After the key is available:

```bash
cp .env.example .env
# add NEBIUS_TOKEN_FACTORY_API_KEY locally
set -a; source .env; set +a

.venv/bin/replayforge models
.venv/bin/replayforge validate-model <exact-nvidia-model-id>
make live-smoke
```

The live-smoke script discovers the account's current catalog, requires an NVIDIA candidate, performs a
validation completion and runs five paired cases. Preserve its evidence directory for the demo. Then run
the full selected suite from the product UI so the video shows the same live model ID, provider evidence,
traces, graders and release decision.

Do not call fixture results NVIDIA results. The app already labels fixture mode across the CLI, API,
report, UI and GitHub check.

## Submission package

Before submitting, all of these must be complete:

- [ ] Devpost registration and project draft
- [ ] Coding and Agentic Engineering track selected
- [ ] Public GitHub repository URL works while signed out
- [ ] GitHub About section detects Apache-2.0
- [ ] Hosted demo/test URL works in a private browser with no developer setup
- [ ] Live NVIDIA/Token Factory experiment saved
- [ ] Exact model ID and Nebius usage explained in README and submission
- [ ] Real GitHub pull request receives the ReplayForge check
- [ ] Demo video is public on YouTube and shorter than three minutes
- [ ] Video includes working software, not only slides or mockups
- [ ] Text description explains the user, problem, workflow and concrete evidence
- [ ] Setup and judge testing instructions are complete
- [ ] Token Factory/NVIDIA feedback section is complete
- [ ] Pre-existing benchtrace dependency is disclosed
- [ ] All visible music, images, fonts, trademarks and code are owned, licensed or permitted
- [ ] No secrets, personal data, private repository content or copyrighted music appear in the video

## Recommended video structure

Use the existing `DEMO.md` script and keep the total around 2:40 so export or narration variance does not
cross the three-minute limit.

1. **Problem:** model migration breaks agent behavior that static benchmarks do not measure.
2. **Live setup:** versioned suite, baseline and live NVIDIA model from the Token Factory catalog.
3. **Work:** both lanes edit and test the same repository work in fresh sandboxes.
4. **Failure evidence:** open a disagreement, failing grader and referenced trace.
5. **Decision:** show measurement labels, stored policy and pass/warn/block outcome.
6. **External handoff:** publish the same decision to a real GitHub pull request.

The in-product Presentation and System Design routes are for follow-up questions. The timed video should
spend most of its time on the working application.

## Judging strategy

The four scored criteria are equally weighted, so the submission should establish each one explicitly:

- **Technological implementation:** live Token Factory request, NVIDIA model identity, bounded tool loop,
  isolated repository execution, deterministic grading, resume and GitHub delivery.
- **Design:** one coherent journey from experiment setup through visible 3D execution to inspectable
  evidence and an external release check.
- **Potential impact:** teams operating coding agents need to migrate models without silently changing
  tool behavior or repository outcomes.
- **Quality of idea:** ReplayForge evaluates the complete agent trajectory and release contract rather
  than another chat or code-completion wrapper.

## Optional Tavily bonus

The Tavily prize requires a functional runtime API call. Do not add a decorative search box solely for
eligibility. A meaningful extension would be a **Migration Research Brief** that retrieves current model
documentation, licensing, deprecation notices and provider incident information, cites its sources, and
keeps that research separate from measured experiment results. Only implement it if it can be completed,
tested and demonstrated without distracting from the live NVIDIA run and deployment.

## Prize constraints worth remembering

- One project can receive one overall award **or** one track award, plus one bonus award.
- The feedback award is separately judged on useful, complete product feedback.
- A New York City award depends on attending the participating in-person event, not merely living in NYC.
- The application and test access must remain free and available through the judging period.
