"""
Offline demo renderer — rebuilds public/index.html with the genai.works-styled
web theme using the last full digest (29 stories), WITHOUT any network fetch or
email send. Handy for previewing layout changes.

    python render_demo.py

Production still uses `python send_digest.py` (fetch + email + PDF + web).
"""
from collections import OrderedDict
from send_digest import build_web

D = "Developer"
QA = "Tester / QA"
ML = "AI Engineer / ML Engineer"
AR = "Architect / Tech Lead"
PB = "Product / Business"
EV = "AI Awareness (Everyone)"
GA = "General Awareness"

TC = "AI News & Artificial Intelligence | TechCrunch"
ZD = "Latest news"
AX = "cs.AI updates on arXiv.org"
TNW = "The Next Web"

digest = OrderedDict()

digest["🤖 Model Updates"] = [
    {"title": "SpaceXAI releases Grok 4.5, which Elon describes as an ‘Opus-class model’",
     "link": "https://techcrunch.com/2026/07/08/spacexai-releases-grok-4-5-which-elon-describes-as-an-opus-class-model/",
     "source": TC, "roles": [ML],
     "summary": "Elon Musk's tech company released the newest version of Grok on Wednesday, promising a cheaper, more efficient alternative to other powerful AI models."},
    {"title": "This startup thinks robotics is about to have its ChatGPT moment",
     "link": "https://techcrunch.com/2026/07/08/this-startup-thinks-robotics-is-about-to-have-its-chatgpt-moment/",
     "source": TC, "roles": [D, ML, PB],
     "summary": "General Intuition is betting millions of hours of video game data can train the foundation models for physical AI, making it easier to build smarter robots with minimal real-world data."},
    {"title": "OpenAI's new GPT-Live-1 voice model won't interrupt you - why that's a big deal",
     "link": "https://www.zdnet.com/article/ai-model-release-tracker/",
     "source": ZD, "roles": [ML],
     "summary": "Our AI Model Release Tracker keeps new models in context with their peers, so you know which are worth your time."},
    {"title": "When Does In-Context Search Help? A Sampling-Complexity Theory of Reflection-Driven Reasoning",
     "link": "https://arxiv.org/abs/2607.06720",
     "source": AX, "roles": [D, ML, EV],
     "summary": "arXiv:2607.06720v1 — Training large language models with extended reasoning has enabled in-context search, in which models iteratively generate, critique, and revise solution attempts."},
    {"title": "Cost-Effective Agent Harnesses for Abstract Reasoning and Generalization on ARC-AGI-1",
     "link": "https://arxiv.org/abs/2607.06764",
     "source": AX, "roles": [D, QA, ML],
     "summary": "arXiv:2607.06764v1 — Recent progress on ARC-AGI-1 has come from two regimes: heavy test-time compute over frontier models, or benchmark-specific fine-tuning of small models on ARC data."},
    {"title": "Evaluating SageMath-Augmented LLM Agents for Computational and Experimental Mathematics",
     "link": "https://arxiv.org/abs/2607.06820",
     "source": AX, "roles": [D, QA, ML],
     "summary": "arXiv:2607.06820v1 — Recent advances in AI for Mathematics have focused largely on autoformalization and theorem proving, leaving the role of Computer Algebra Systems in agentic LLM workflows underexplored."},
]

digest["🚀 New Launch / Feature"] = [
    {"title": "Nandan Nilekani leaves GP role at Fundamentum as it launches $200M third fund",
     "link": "https://techcrunch.com/2026/07/09/nandan-nilekani-leaves-gp-role-at-his-vc-firm-as-it-launches-third-200m-fund/",
     "source": TC, "roles": [PB],
     "summary": "Nilekani remains Fundamentum's anchor investor as the firm expands its leadership team and targets AI and fintech startups in India."},
    {"title": "IBM and Red Hat launch Lightwell to defend open-source code from AI attacks",
     "link": "https://www.zdnet.com/article/ibm-and-red-hat-have-moved-project-lightwell-from-vision-to-product/",
     "source": ZD, "roles": [D, AR],
     "summary": "Their plan to protect open-source projects from AI-discovered security holes has led to two commercial offerings: Lightwell Network and Lightwell Clearinghouse Premier."},
    {"title": "GitHub's former CEO launches a distributed Git network built for the agentic coding age",
     "link": "https://www.zdnet.com/article/githubs-former-ceo-launches-a-distributed-git-network-built-for-the-agentic-coding-age/",
     "source": ZD, "roles": [D, ML, AR],
     "summary": "The developer tools startup said it's building better infrastructure for a future run by coding agents."},
    {"title": "Our approach to government and national security partnerships",
     "link": "https://openai.com/index/government-national-security-partnerships",
     "source": "OpenAI News", "roles": [AR, PB, EV],
     "summary": "Learn how OpenAI approaches government and national security partnerships, with principles for responsible AI use, democratic accountability, and public safety."},
    {"title": "Introducing Claude apps gateway for AWS",
     "link": "https://aws.amazon.com/blogs/machine-learning/introducing-claude-apps-gateway-for-aws/",
     "source": "Artificial Intelligence", "roles": [D, AR, EV],
     "image": "https://d2908q01vomqb2.cloudfront.net/f1f836cb4ea6efb2a0b1b99f41ad8b103eff4b59/2026/07/08/Screenshot-2026-07-08-at-2.00.31 PM.png",
     "summary": "A self-hosted control plane that gives organizations a single point of control over access, cost, and policy for Claude Code and Claude Desktop, running on Amazon Bedrock and Claude Platform on AWS."},
]

digest["🔬 R&D / Research"] = [
    {"title": "Prime Intellect raises $130M Series A to help enterprises build their own AI agents",
     "link": "https://techcrunch.com/2026/07/08/prime-intellect-raises-130m-series-a-to-help-enterprises-build-their-own-ai-agents/",
     "source": TC, "roles": [ML, AR],
     "summary": "Founded in 2024, Prime Intellect's goal is to give organizations capabilities to train their own agentic systems without relying on frontier AI labs."},
    {"title": "Europe's sovereign AI ambition risks stalling on data centre limits, new research warns",
     "link": "https://thenextweb.com/news/europe-sovereign-ai-data-centre-constraints-onnec",
     "source": TNW, "roles": [ML, AR, EV],
     "image": "https://media.thenextweb.com/2026/05/European-flag.avif",
     "summary": "As Washington tightens access to its most capable models and Brussels leans into European AI sovereignty, a new survey from Onnec warns the continent's ambitions could be strangled by data-centre infrastructure limits."},
    {"title": "Half of parents worry their children rely on AI too much, survey finds",
     "link": "https://thenextweb.com/news/half-of-parents-worried-kids-hooked-on-ai",
     "source": TNW, "roles": [GA],
     "image": "https://media.thenextweb.com/2026/07/AI-and-kids.avif",
     "summary": "AI has moved into the primary-school classroom, and half of parents polled said they were worried their child 'relies on AI too much,' according to Deloitte's annual back-to-school study."},
    {"title": "I tried Claude Cowork on my Gmail inbox after Gemini choked - and it saved me hours of work",
     "link": "https://www.zdnet.com/article/claude-cowork-sift-emails-vs-gemini/",
     "source": ZD, "roles": [GA],
     "summary": "Gmail's AI failed at a nuanced research task, but Claude Cowork found the right pitches, quotes, and permissions — proving connected AI assistants may finally help tackle email overload."},
    {"title": "AgentLens: Production-Assessed Trajectory Reviews for Coding Agent Evaluation",
     "link": "https://arxiv.org/abs/2607.06624",
     "source": AX, "roles": [D, QA, ML],
     "summary": "arXiv:2607.06624v1 — AgentLens is a production-assessed benchmark for interactive code agents, going beyond the single pass/fail bit that most code-agent benchmarks reduce a run to."},
    {"title": "LLM-powered reasoning in agent-based modeling",
     "link": "https://arxiv.org/abs/2607.06757",
     "source": AX, "roles": [D, ML, AR],
     "summary": "arXiv:2607.06757v1 — Agent-based modeling can simulate millions of individuals, but has traditionally relied on static priors; LLM-powered reasoning lets the models adapt to real-time changes."},
]

digest["✅ Good News / Wins"] = [
    {"title": "Meta wants its AI glasses to seem less creepy. Its AI strategy says otherwise.",
     "link": "https://techcrunch.com/2026/07/08/meta-wants-its-ai-glasses-to-seem-less-creepy-its-ai-strategy-says-otherwise/",
     "source": TC, "roles": [PB],
     "summary": "Meta is adding a safeguard to stop people from secretly recording others with its AI glasses — even as the company keeps expanding how much personal data its AI products collect and use."},
    {"title": "'I'm not a programmer' anymore: Linus Torvalds on the only two tools he uses now",
     "link": "https://www.zdnet.com/article/open-source-summit-linus-torvalds/",
     "source": ZD, "roles": [D],
     "summary": "At the Open Source Summit in Mumbai, Torvalds discusses the pain and power of AI in the kernel, and why Linux no longer supports 'museum' technology."},
]

digest["⚠️ Bad News / Risk"] = [
    {"title": "France's antitrust probe into Nvidia is nearing its end, regulator says",
     "link": "https://thenextweb.com/news/france-nvidia-antitrust-probe-nearing-end",
     "source": TNW, "roles": [PB],
     "image": "https://media.thenextweb.com/2026/04/france-linux-windows-migration-digital-sovereignty.avif",
     "summary": "France's competition regulator signalled its long-running inquiry into Nvidia is drawing to a close, edging the chipmaker nearer to a formal reckoning over its grip on the AI-hardware market."},
    {"title": "Taiwan's central bank chief urges caution on leverage as AI stock rally runs hot",
     "link": "https://thenextweb.com/news/taiwan-central-bank-yang-chin-long-ai-leverage-warning",
     "source": TNW, "roles": [D, ML, AR],
     "image": "https://media.thenextweb.com/2026/07/Governor-Yang-Chin-long.avif",
     "summary": "Taiwan's top central banker urged investors to steer clear of heavy borrowing to chase the island's surging stock market, a rally powered by global demand for AI hardware."},
]

digest["💡 AI Awareness / Must Know"] = [
    {"title": "Why this CEO thinks video games make better training data than the internet",
     "link": "https://techcrunch.com/video/why-this-ceo-thinks-video-games-make-better-training-data-than-the-internet/",
     "source": TC, "roles": [D, ML, PB],
     "summary": "LLMs are great at text but weaker at understanding how things move through space and time — an essential skill for intelligence that generalizes toward AGI."},
    {"title": "Your gaming data could be the secret to AGI, according to this Bezos-backed startup",
     "link": "https://techcrunch.com/podcast/your-gaming-data-could-be-the-secret-to-agi-according-to-this-bezos-backed-startup/",
     "source": TC, "roles": [ML, PB],
     "summary": "The startup argues that gaming data captures the spatial, temporal reasoning that text-trained models like ChatGPT and Claude still lack."},
]

digest["📰 General AI Update"] = [
    {"title": "Google Photos adds a new AI ‘Video Remix’ tool",
     "link": "https://techcrunch.com/2026/07/08/google-photos-adds-a-new-ai-video-remix-tool/",
     "source": TC, "roles": [D],
     "summary": "The feature can apply cinematic relighting to brighten a dark clip, swap out a plain background, or add artistic styles to videos."},
    {"title": "OpenAI releases new voice models for more natural live conversations",
     "link": "https://techcrunch.com/2026/07/08/openai-releases-new-voice-models-for-more-natural-live-conversations/",
     "source": TC, "roles": [ML, AR],
     "summary": "OpenAI says its new voice mode can speak and listen at the same time, a key ability for live translation."},
    {"title": "These AI startups are growing revenue at faster and faster rates",
     "link": "https://techcrunch.com/2026/07/08/these-ai-startups-are-growing-revenue-at-faster-and-faster-rates/",
     "source": TC, "roles": [PB],
     "summary": "There are a lot of fast-growing AI startups, but some are growing even faster, they say."},
    {"title": "Former OpenAI exec Kevin Weil is now on the board of Stoke Space",
     "link": "https://techcrunch.com/2026/07/08/former-openai-exec-kevin-weil-is-now-on-the-board-of-stoke-space/",
     "source": TC, "roles": [GA],
     "summary": "Kevin Weil's new role at Stoke Space suggests reusable rockets are the next hot thing in Silicon Valley."},
    {"title": "NHS AI blood test could reduce invasive womb cancer checks",
     "link": "https://www.artificialintelligence-news.com/news/nhs-ai-blood-test-womb-cancer-checks/",
     "source": "AI News", "roles": [QA],
     "image": "https://www.artificialintelligence-news.com/wp-content/uploads/2026/06/image.png",
     "summary": "Several NHS hospitals are preparing to use an AI-powered blood test to help assess women referred for possible womb cancer before invasive checks are carried out."},
    {"title": "Meta's new AI feature lets people create images from your Instagram posts - how to opt out",
     "link": "https://www.zdnet.com/article/meta-muse-ai-feature-instagram-posts-opting-out/",
     "source": ZD, "roles": [GA],
     "summary": "Any public Instagram account is fair game to be used for AI generation with Meta's new Muse Image — here's how to turn it off."},
]

if __name__ == "__main__":
    import os
    html = build_web(digest)
    os.makedirs("public", exist_ok=True)
    with open(os.path.join("public", "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    total = sum(len(v) for v in digest.values())
    print(f"Wrote public/index.html — {total} stories across {len(digest)} categories.")
