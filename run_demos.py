import json
import os

from repogate_engine import RepoGateEngine


def main():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        # Fallback to local user hermes env for running demo benchmarks if present
        try:
            with open(os.path.expanduser("~/.hermes/.env")) as f:
                for line in f:
                    if line.startswith("GH_TOKEN="):
                        token = line.strip().split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    engine = RepoGateEngine(github_token=token)

    cases = [
        ("yunaremaia", "driftcheck", 66, "high_quality_clean"),
        ("abduznik", "bitbox", 482, "duplicate_dirty_pr"),
        ("yunaremaia", "driftcheck", 68, "superseded_race_pr"),
    ]

    os.makedirs("demo_reports", exist_ok=True)

    for owner, repo, pr_num, label in cases:
        print(f"[*] Running RepoGate evaluation on {owner}/{repo} PR #{pr_num} ({label})...")
        report = engine.analyze_pr(owner, repo, pr_num)

        json_path = f"demo_reports/{label}_pr{pr_num}.json"
        md_path = f"demo_reports/{label}_pr{pr_num}.md"

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        md_content = engine.format_markdown_report(report)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(f"    -> Risk: {report['risk_score']}/100 | Rec: {report['recommended_action']}")

    print("\n[+] All 3 Demo Cases evaluated and reports generated in demo_reports/")


if __name__ == "__main__":
    main()
